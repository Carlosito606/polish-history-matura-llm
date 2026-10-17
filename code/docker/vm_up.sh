#!/usr/bin/env bash
# Bring the exam stack up on the VM (idempotent). Run from anywhere:
#   bash ~/wmt-matura/docker/vm_up.sh [--base] [--no-smoke] [--build]
# 1. loads image tarballs listed in ../dist/images.env (if the images are missing)
# 2. makes sure the pinned llama.cpp image is present (pull only if missing) and checks its digest
# 3. checks that the model files and the index exist
# 4. docker compose up -d --wait   (+ --profile base for the untouched-base server)
# 5. one-question smoke test through 127.0.0.1:$HARNESS_HOST_PORT (and the raw port)
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
cd "$HERE"
log() { printf '[vm_up %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

BASE=0; SMOKE=1; BUILD=0
for a in "$@"; do
  case "$a" in
    --base) BASE=1 ;;
    --no-smoke) SMOKE=0 ;;
    --build) BUILD=1 ;;
    *) echo "unknown arg $a" >&2; exit 2 ;;
  esac
done

[ -f .env ] || { cp .env.example .env; log "created docker/.env from .env.example -- review it"; }
envget() { local v; v=$(grep -E "^$1=" .env | tail -1 | cut -d= -f2-); printf '%s' "${v:-${2:-}}"; }
envset() {
  if grep -qE "^$1=" .env; then sed -i.bak "s#^$1=.*#$1=$2#" .env && rm -f .env.bak; else echo "$1=$2" >> .env; fi
}

# ---- 1. image tarballs
if [ -f "$ROOT/dist/images.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/dist/images.env"
  if [ -n "${HARNESS_TARBALL:-}" ] && [ -f "$ROOT/dist/$HARNESS_TARBALL" ] && ! docker image inspect "$HARNESS_IMAGE" >/dev/null 2>&1; then
    log "docker load $HARNESS_TARBALL"; docker load -i "$ROOT/dist/$HARNESS_TARBALL"
  fi
  [ -n "${HARNESS_IMAGE:-}" ] && envset HARNESS_IMAGE "$HARNESS_IMAGE"
  if [ -n "${LLM_TARBALL:-}" ] && [ -f "$ROOT/dist/$LLM_TARBALL" ] && ! docker image inspect "$LLM_IMAGE" >/dev/null 2>&1; then
    log "docker load $LLM_TARBALL"; docker load -i "$ROOT/dist/$LLM_TARBALL"
  fi
fi

HARNESS_IMAGE=$(envget HARNESS_IMAGE wmt-harness:latest)
LLM_IMAGE=$(envget LLM_IMAGE ghcr.io/ggml-org/llama.cpp:server-cuda-b11176)
LLM_IMAGE_DIGEST=$(envget LLM_IMAGE_DIGEST)

# ---- 2. images present?
if [ "$BUILD" = 1 ]; then
  log "building $HARNESS_IMAGE locally"; docker compose build harness
fi
docker image inspect "$HARNESS_IMAGE" >/dev/null 2>&1 || { log "harness image $HARNESS_IMAGE missing (deploy the tarball or use --build)"; exit 1; }
if ! docker image inspect "$LLM_IMAGE" >/dev/null 2>&1; then
  log "pulling $LLM_IMAGE"; docker pull "$LLM_IMAGE"
fi
if [ -n "$LLM_IMAGE_DIGEST" ]; then
  if docker image inspect --format '{{join .RepoDigests " "}}' "$LLM_IMAGE" | grep -q "$LLM_IMAGE_DIGEST"; then
    log "LLM image digest OK ($LLM_IMAGE_DIGEST)"
  else
    log "NOTE: $LLM_IMAGE has no RepoDigest $LLM_IMAGE_DIGEST (normal after docker load; verify tarball SHA256SUMS instead)"
  fi
fi

# ---- 3. data present?
MODELS_DIR=$(envget MODELS_DIR ../models); INDEX_DIR=$(envget INDEX_DIR ../kb_data/index)
miss=0
for k in MODEL_FILE LORA_FILE BASE_MODEL_FILE; do
  f=$(envget "$k"); [ -n "$f" ] || continue
  if [ -f "$MODELS_DIR/$f" ]; then log "$k=$f ($(du -h "$MODELS_DIR/$f" | cut -f1))"; else log "MISSING $k: $MODELS_DIR/$f"; miss=1; fi
done
if [ -d "$INDEX_DIR" ] && [ -n "$(ls -A "$INDEX_DIR" 2>/dev/null)" ]; then
  log "index: $INDEX_DIR ($(du -sh "$INDEX_DIR" | cut -f1))"
else
  log "MISSING/empty index dir: $INDEX_DIR"; miss=1
fi
[ "$miss" = 0 ] || { log "fix the missing files (docker/deploy.sh transfers them)"; exit 1; }

# ---- 4. up
PROFILE=""; [ "$BASE" = 1 ] && PROFILE="--profile base"
log "docker compose $PROFILE up -d --wait"
# shellcheck disable=SC2086
docker compose $PROFILE up -d --wait --wait-timeout 1800
# shellcheck disable=SC2086
docker compose $PROFILE ps
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader || true

# ---- 5. smoke
if [ "$SMOKE" = 1 ]; then
  HP=$(envget HARNESS_HOST_PORT 18000); RP=$(envget RAW_HOST_PORT 18080)
  python3 "$HERE/smoke_test.py" --url "http://127.0.0.1:$HP" --raw-url "http://127.0.0.1:$RP" --require-kb --require-llm --wait 60
fi
