#!/usr/bin/env bash
# Optional transfer path: push the exam artifacts (GGUFs + BM25 index) to a PRIVATE Hugging Face
# model repo, so the VM can fetch them with `docker/deploy.sh <vm> --hf-repo <repo>`.
# Layout in the repo mirrors the VM layout: models/<rel path>, kb_data/index/<files>.
#
#   HF_TOKEN=... bash docker/hf_push.sh <org>/<private-repo> [--index DIR] model1.gguf [lora.gguf ...]
#   (model paths relative to models/; run on the Mac with ~/wmt-matura/.venv)
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
[ $# -ge 1 ] || { sed -n '2,8p' "$0"; exit 2; }
REPO=$1; shift
INDEX="$ROOT/kb_data/index"
if [ "${1:-}" = "--index" ]; then INDEX=$2; shift 2; fi
[ -f "$ROOT/.venv/bin/activate" ] && . "$ROOT/.venv/bin/activate"
command -v hf >/dev/null || { echo "hf CLI not found (pip install huggingface_hub)" >&2; exit 1; }

hf repos create "$REPO" --repo-type model --private >/dev/null 2>&1 || true   # no-op if it exists
for m in "$@"; do
  [ -f "$ROOT/models/$m" ] || { echo "missing $ROOT/models/$m" >&2; exit 1; }
  echo "[hf_push] models/$m"
  hf upload "$REPO" "$ROOT/models/$m" "models/$m" --repo-type model --private --commit-message "model $m"
done
if [ -d "$INDEX" ]; then
  echo "[hf_push] index $INDEX -> kb_data/index"
  hf upload "$REPO" "$INDEX" kb_data/index --repo-type model --private --commit-message "bm25 index"
fi
echo "[hf_push] done: https://huggingface.co/$REPO (private)"
