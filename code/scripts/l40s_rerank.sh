#!/usr/bin/env bash
# L40S: bge-reranker-v2-m3 (GGUF Q8_0, 636 MB) on a separate llama-server --reranking, for harness RERANK=1.
# Same llama.cpp b11185 CUDA build + glibc shim as scripts/l40s_serve.sh; small (about 1.5 GB VRAM).
#
#   bash scripts/l40s_rerank.sh start | stop | status
#
# Env: RERANK_PORT [18092]  RERANK_HOST [127.0.0.1]  CTX [16384]  NP [8]  UB [4096]
#      MODEL [/workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf]
# Model download (once): hf download gpustack/bge-reranker-v2-m3-GGUF bge-reranker-v2-m3-Q8_0.gguf \
#                          --local-dir /workspace/models/bge-reranker-v2-m3
# Log / pid: /workspace/logs/llama-<port>.{log,pid}
set -euo pipefail

LOGS=${LOGS:-/workspace/logs}
LLAMA_DIR=${LLAMA_DIR:-/workspace/opt/llama/current}
MODEL=${MODEL:-/workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf}
RERANK_HOST=${RERANK_HOST:-127.0.0.1}
RERANK_PORT=${RERANK_PORT:-18092}
CTX=${CTX:-16384}
NP=${NP:-8}
UB=${UB:-4096}
PID=$LOGS/llama-$RERANK_PORT.pid
LOG=$LOGS/llama-$RERANK_PORT.log
mkdir -p "$LOGS"

alive() {
  [ -f "$PID" ] || return 1
  local pid; pid=$(cat "$PID")
  kill -0 "$pid" 2>/dev/null && tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q 'llama-server'
}

case "${1:-status}" in
  start)
    if alive; then echo "reranker already running (pid $(cat "$PID"), :$RERANK_PORT)"; exit 0; fi
    [ -f "$MODEL" ] || { echo "model not found: $MODEL" >&2; exit 1; }
    echo "starting reranker :$RERANK_PORT  model=$MODEL ctx=$CTX np=$NP"
    setsid nohup "$LLAMA_DIR/llama-server" -m "$MODEL" --reranking --host "$RERANK_HOST" --port "$RERANK_PORT" \
      -ngl 999 -c "$CTX" -b "$UB" -ub "$UB" -np "$NP" --alias bge-reranker-v2-m3 --no-webui \
      > "$LOG" 2>&1 < /dev/null &
    echo $! > "$PID"
    for i in $(seq 1 120); do
      curl -sf -m 5 "http://$RERANK_HOST:$RERANK_PORT/health" >/dev/null 2>&1 && { echo "  ready after ${i}s"; exit 0; }
      sleep 1
    done
    echo "reranker not ready; tail of $LOG:" >&2; tail -30 "$LOG" >&2; exit 1
    ;;
  stop)
    if alive; then kill "$(cat "$PID")"; echo "stopped reranker (pid $(cat "$PID"))"; else echo "reranker not running"; fi
    ;;
  status)
    if alive; then
      echo "reranker :$RERANK_PORT pid $(cat "$PID")"
      curl -s -m 10 "http://$RERANK_HOST:$RERANK_PORT/v1/rerank" -H 'Content-Type: application/json' \
        -d '{"model":"bge-reranker-v2-m3","query":"bitwa pod Grunwaldem","documents":["Bitwa pod Grunwaldem 1410","Zjazd gnieźnieński"]}'
      echo
    else
      echo "reranker not running"
    fi
    ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
