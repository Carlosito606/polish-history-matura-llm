#!/usr/bin/env bash
# Ship everything to the exam VM and start the stack there (run on the build host, e.g. the Mac).
#
#   bash docker/deploy.sh <ssh-target> [options]
#
# Options:
#   --env FILE        docker .env to install on the VM (default: docker/.env if it exists,
#                     else the VM keeps/creates its own from .env.example)
#   --models "A B"    model files, relative to models/, to transfer (default: MODEL_FILE,
#                     LORA_FILE, BASE_MODEL_FILE read from the env file)
#   --index DIR       local index dir to transfer to kb_data/index (default: kb_data/index)
#   --hf-repo REPO    instead of rsync-ing models+index, download them ON THE VM from a (private)
#                     HF model repo laid out as models/... and kb_data/index/...; needs HF_TOKEN
#                     in the local env (sent over ssh stdin, never on a command line)
#   --no-llm-tarball  do not send the llama.cpp CUDA image tarball (the VM pulls it from ghcr.io)
#   --base            also start the untouched-base llama-server (compose profile "base")
#   --no-up           transfer only
# Env: REMOTE_DIR (default: wmt-matura, relative to the remote home), SSH_OPTS
#
# Transfer is rsync over ssh (resumable: --partial). Build the images first: bash docker/build.sh
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
log() { printf '[deploy %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

[ $# -ge 1 ] || { sed -n '2,22p' "$0"; exit 2; }
TARGET=$1; shift
ENV_FILE=""; MODELS=""; INDEX="$ROOT/kb_data/index"; HF_REPO=""; SEND_LLM=1; BASE=0; UP=1
while [ $# -gt 0 ]; do
  case "$1" in
    --env) ENV_FILE=$2; shift ;;
    --models) MODELS=$2; shift ;;
    --index) INDEX=$2; shift ;;
    --hf-repo) HF_REPO=$2; shift ;;
    --no-llm-tarball) SEND_LLM=0 ;;
    --base) BASE=1 ;;
    --no-up) UP=0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
[ -z "$ENV_FILE" ] && [ -f "$HERE/.env" ] && ENV_FILE="$HERE/.env"
REMOTE_DIR=${REMOTE_DIR:-wmt-matura}
SSH_OPTS=${SSH_OPTS:-}
# shellcheck disable=SC2086
SSH() { ssh $SSH_OPTS "$TARGET" "$@"; }
RSYNC() { rsync -a --partial --info=progress2 -e "ssh $SSH_OPTS" "$@" 2>/dev/null || rsync -a --partial --progress -e "ssh $SSH_OPTS" "$@"; }

envget() { [ -n "$ENV_FILE" ] || return 0; grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }

log "target $TARGET:$REMOTE_DIR"
SSH "mkdir -p $REMOTE_DIR/docker $REMOTE_DIR/dist $REMOTE_DIR/models $REMOTE_DIR/kb_data/index"

# ---- code + compose
log "docker/ -> VM"
RSYNC --exclude .env --exclude _ctx --exclude '*.bak' "$HERE/" "$TARGET:$REMOTE_DIR/docker/"
if [ -n "$ENV_FILE" ]; then
  log "env $ENV_FILE -> VM docker/.env"
  RSYNC "$ENV_FILE" "$TARGET:$REMOTE_DIR/docker/.env"
fi

# ---- images
[ -f "$ROOT/dist/images.env" ] || { echo "no dist/images.env - run docker/build.sh first" >&2; exit 1; }
# shellcheck disable=SC1091
. "$ROOT/dist/images.env"
FILES=("$ROOT/dist/images.env" "$ROOT/dist/$HARNESS_TARBALL")
[ -f "$ROOT/dist/SHA256SUMS" ] && FILES+=("$ROOT/dist/SHA256SUMS")
if [ "$SEND_LLM" = 1 ] && [ -n "${LLM_TARBALL:-}" ] && [ -f "$ROOT/dist/$LLM_TARBALL" ]; then
  FILES+=("$ROOT/dist/$LLM_TARBALL")
fi
log "images -> VM: ${FILES[*]##*/}"
RSYNC "${FILES[@]}" "$TARGET:$REMOTE_DIR/dist/"
SSH "cd $REMOTE_DIR/dist && (command -v sha256sum >/dev/null && sha256sum --ignore-missing -c SHA256SUMS || true)"

# ---- models + index
if [ -n "$HF_REPO" ]; then
  [ -n "${HF_TOKEN:-}" ] || { echo "--hf-repo needs HF_TOKEN in the environment" >&2; exit 1; }
  log "VM downloads models/ + kb_data/index/ from HF repo $HF_REPO"
  printf '%s\n' "$HF_TOKEN" | SSH "read -r HF_TOKEN; export HF_TOKEN; cd $REMOTE_DIR && \
    docker run --rm -u \$(id -u):\$(id -g) -e HOME=/tmp -e HF_TOKEN -v \$PWD:/w python:3.12-slim sh -c \
    'python -m venv /tmp/v && /tmp/v/bin/pip -q install huggingface_hub && \
     /tmp/v/bin/hf download $HF_REPO --repo-type model --local-dir /w --include \"models/*\" \"kb_data/index/*\"'"
else
  if [ -z "$MODELS" ]; then
    MODELS="$(envget MODEL_FILE) $(envget LORA_FILE) $(envget BASE_MODEL_FILE)"
  fi
  for m in $MODELS; do
    [ -f "$ROOT/models/$m" ] || { echo "model not found locally: $ROOT/models/$m" >&2; exit 1; }
    log "model $m -> VM"
    ( cd "$ROOT/models" && RSYNC -R "$m" "$TARGET:$REMOTE_DIR/models/" )
  done
  if [ -d "$INDEX" ]; then
    log "index $INDEX -> VM kb_data/index"
    RSYNC --delete "$INDEX/" "$TARGET:$REMOTE_DIR/kb_data/index/"
  else
    log "WARN: no local index at $INDEX (skipped)"
  fi
fi

# ---- up + smoke
if [ "$UP" = 1 ]; then
  ARGS=""; [ "$BASE" = 1 ] && ARGS="--base"
  log "vm_up.sh $ARGS on VM"
  SSH "bash $REMOTE_DIR/docker/vm_up.sh $ARGS"
fi
log "DEPLOY DONE"
