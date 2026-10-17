#!/bin/bash
# Full dense index build on a GPU box (L40S): llama-server --embedding (CUDA) + kb.dense_build.
# Run inside tmux; resumable (re-run with the same args continues from progress.json).
#
#   PRESET=qwen3-emb-0.6b GGUF=/workspace/models/emb/Qwen3-Embedding-0.6B-Q8_0.gguf POOLING=last \
#   SCOPE="--min-hist 2 --min-inlinks 50" bash scripts/dense_build_l40s.sh
#   (SCOPE="--all" for all 3.45 M chunks; FAISS_KIND=hnsw|ivfpq|sq8|none)
set -euo pipefail
cd "$(dirname "$0")/.."
PRESET=${PRESET:-qwen3-emb-0.6b}
GGUF=${GGUF:-/workspace/models/emb/Qwen3-Embedding-0.6B-Q8_0.gguf}
POOLING=${POOLING:-last}            # qwen3-emb: last, bge-m3: cls
SCOPE=${SCOPE:---min-hist 2 --min-inlinks 50}
PORT=${PORT:-18093}
KB_INDEX=${KB_INDEX:-/workspace/kb_data/index}
CHUNKS=${CHUNKS:-/workspace/kb_data/chunks}
OUT=${OUT:-/workspace/kb_data/dense/$PRESET}
PY=${PY:-/workspace/venvs/wmt/bin/python}
CONC=${CONC:-8}
BATCH=${BATCH:-64}
FAISS_KIND=${FAISS_KIND:-none}
LOG=/workspace/logs
mkdir -p "$OUT" "$LOG"

if ! curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
  nohup llama-server -m "$GGUF" --embedding --pooling "$POOLING" -c 65536 -np 16 -b 8192 -ub 8192 -ngl 999 \
    --cache-ram 0 --host 127.0.0.1 --port "$PORT" --alias "$PRESET" > "$LOG/emb-$PORT.log" 2>&1 &
  echo $! > "$LOG/emb-$PORT.pid"
  until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do sleep 2; done
fi

[ -f "$OUT/scope_ids.npy" ] || $PY -m kb.dense_build select --chunks "$CHUNKS" --index "$KB_INDEX" \
  --out "$OUT/scope_ids.npy" $SCOPE
RESUME=""; [ -f "$OUT/progress.json" ] && RESUME="--resume"
$PY -m kb.dense_build embed --preset "$PRESET" --url "http://127.0.0.1:$PORT" --ids "$OUT/scope_ids.npy" \
  --index "$KB_INDEX" --out "$OUT" --batch "$BATCH" --conc "$CONC" $RESUME
[ "$FAISS_KIND" = none ] || $PY -m kb.dense_build faiss --out "$OUT" --kind "$FAISS_KIND"
du -sh "$OUT"
echo DENSE_BUILD_DONE
