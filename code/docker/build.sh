#!/usr/bin/env bash
# Build the harness image for linux/amd64 (prod VM) + linux/arm64 (Mac smoke test) with buildx,
# then export linux/amd64 image tarballs for an offline transfer to the VM.
#
#   bash docker/build.sh                 # on the Mac (sources docker/mac_env.sh automatically)
#
# Env:
#   TAG         image tag (default: UTC timestamp); wmt-harness:latest is always tagged too
#   PLATFORMS   default linux/amd64,linux/arm64
#   CONTEXT     build context containing kb/ harness/ docker/ (default: repo root)
#   DIST        output dir for tarballs (default: <repo>/dist)
#   SAVE        1 = write dist/*.tar.gz (default 1)
#   SAVE_LLM    1 = also pull + save the pinned llama.cpp CUDA image for linux/amd64 (default 1)
# Needs the containerd image store (Docker Desktop default; Docker Engine >= 29 default) for
# multi-platform --load and `docker save --platform`.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
# shellcheck source=mac_env.sh
. "$HERE/mac_env.sh"

IMAGE=${IMAGE:-wmt-harness}
TAG=${TAG:-$(date -u +%Y%m%d-%H%M%S)}
PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
CONTEXT=${CONTEXT:-$ROOT}
DIST=${DIST:-$ROOT/dist}
SAVE=${SAVE:-1}
SAVE_LLM=${SAVE_LLM:-1}
LLM_IMAGE=${LLM_IMAGE:-ghcr.io/ggml-org/llama.cpp:server-cuda-b11176}
LLM_IMAGE_CPU=${LLM_IMAGE_CPU:-ghcr.io/ggml-org/llama.cpp:server-b11176}

log() { printf '[build %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
zip1() { if command -v pigz >/dev/null; then pigz -1; else gzip -1; fi; }

for f in harness/__main__.py harness/server.py docker/requirements.txt; do
  [ -f "$CONTEXT/$f" ] || { echo "missing $CONTEXT/$f" >&2; exit 1; }
done
[ -f "$CONTEXT/kb/search.py" ] || log "WARN: kb/search.py missing in context -> harness runs in no-context mode"

VCS_REF=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)
log "docker: $(docker version --format '{{.Server.Version}} ({{.Server.Os}}/{{.Server.Arch}})')"
log "building $IMAGE:$TAG for $PLATFORMS from $CONTEXT"
t0=$(date +%s)
docker buildx build \
  --platform "$PLATFORMS" \
  -f "$HERE/Dockerfile.harness" \
  --build-arg "VCS_REF=$VCS_REF" \
  --build-arg "BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --provenance=false --sbom=false \
  -t "$IMAGE:$TAG" -t "$IMAGE:latest" \
  --load "$CONTEXT"
log "build done in $(( $(date +%s) - t0 ))s"

for p in ${PLATFORMS//,/ }; do
  sz=$(docker image inspect --platform "$p" --format '{{.Size}}' "$IMAGE:$TAG" 2>/dev/null || echo "?")
  log "image $IMAGE:$TAG [$p] size=${sz} bytes"
done

# pinned llama.cpp images: CPU for the native platform (smoke test), CUDA amd64 for prod
docker pull -q "$LLM_IMAGE_CPU" >/dev/null && log "pulled $LLM_IMAGE_CPU"

[ "$SAVE" = 1 ] || exit 0
mkdir -p "$DIST"
H_TAR="$DIST/${IMAGE}_${TAG}_linux-amd64.tar.gz"
log "saving $IMAGE:$TAG (linux/amd64) -> $H_TAR"
docker save --platform linux/amd64 "$IMAGE:$TAG" "$IMAGE:latest" | zip1 > "$H_TAR.part"
mv "$H_TAR.part" "$H_TAR"
ln -sf "$(basename "$H_TAR")" "$DIST/${IMAGE}_latest_linux-amd64.tar.gz"

L_TAR=""
if [ "$SAVE_LLM" = 1 ]; then
  L_NAME=$(echo "${LLM_IMAGE##*/}" | tr ':@' '__')
  L_TAR="$DIST/${L_NAME}_linux-amd64.tar.gz"
  docker pull -q --platform linux/amd64 "$LLM_IMAGE" >/dev/null
  if [ -s "$L_TAR" ]; then
    log "exists, skipping: $L_TAR"
  else
    log "saving $LLM_IMAGE (linux/amd64) -> $L_TAR"
    docker save --platform linux/amd64 "$LLM_IMAGE" | zip1 > "$L_TAR.part"
    mv "$L_TAR.part" "$L_TAR"
  fi
fi

cat > "$DIST/images.env" <<EOF
# written by docker/build.sh $(date -u +%Y-%m-%dT%H:%M:%SZ)
HARNESS_IMAGE=$IMAGE:$TAG
HARNESS_TARBALL=$(basename "$H_TAR")
LLM_IMAGE=$LLM_IMAGE
LLM_TARBALL=$( [ -n "$L_TAR" ] && basename "$L_TAR" )
VCS_REF=$VCS_REF
EOF
( cd "$DIST" && sha256 ./*.tar.gz > SHA256SUMS 2>/dev/null || true )
ls -la "$DIST"
log "done: $DIST/images.env"
