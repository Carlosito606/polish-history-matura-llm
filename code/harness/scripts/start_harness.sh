#!/usr/bin/env bash
# Start the harness (FastAPI) in the background. All config via env (see harness/README.md).
#   harness/scripts/start_harness.sh                 -> :18000 -> Bielik on :18080
#   HARNESS_PORT=18001 LLM_BASE_URL=http://127.0.0.1:18081/v1 LLM_MODEL=qwen3-8b harness/scripts/start_harness.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .venv/bin/activate ] && source .venv/bin/activate
export HARNESS_PORT=${HARNESS_PORT:-18000}
mkdir -p logs
# SNAPSHOT_KB=1: clone the index first (APFS `cp -c` = instant copy-on-write). The KB is numpy-memmapped;
# if someone rebuilds kb_data/index in place while the harness runs, the process dies with SIGBUS.
if [ "${SNAPSHOT_KB:-0}" = "1" ]; then
  SRC=${KB_INDEX_DIR:-kb_data/index}
  DST=harness/_kb_snapshot/$(basename "$SRC")
  rm -rf "$DST"; mkdir -p "$(dirname "$DST")"
  cp -cR "$SRC" "$DST" 2>/dev/null || cp -R "$SRC" "$DST"
  export KB_INDEX_DIR=$DST
  echo "KB snapshot: $SRC -> $DST"
fi
TAG=${TAG:-$HARNESS_PORT}
nohup python -m harness > "logs/harness-$TAG.log" 2>&1 &
echo $! > "logs/harness-$TAG.pid"
for i in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:$HARNESS_PORT/health" >/dev/null 2>&1; then
    echo "harness ready on :$HARNESS_PORT after ${i}s (pid $(cat "logs/harness-$TAG.pid"))"; exit 0
  fi
  sleep 1
done
echo "harness not ready; see logs/harness-$TAG.log"; tail -30 "logs/harness-$TAG.log"; exit 1
