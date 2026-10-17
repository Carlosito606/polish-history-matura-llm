#!/usr/bin/env bash
# RFT sampling servers on the L40S (untouched base, no LoRA): Bielik-4.5B-v3 Q8_0 on :18093, bge-reranker on :18094.
# Everything from the /scratch mirrors (NFS is flaky). VRAM budget <= 14 GB (LoRA training may share the GPU).
#   bash train/rft/serve.sh start | stop | status
set -uo pipefail
R=${RFT_DIR:-/scratch/rft}
LLAMA=${LLAMA:-/scratch/ovl/opt/llama/current/llama-server}
MODEL=${MODEL:-/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf}
RMODEL=${RMODEL:-/scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf}
NP=${NP:-8}; SLOT_CTX=${SLOT_CTX:-7168}
mkdir -p "$R/logs"
alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null && tr '\0' ' ' < "/proc/$(cat "$1")/cmdline" | grep -q llama-server; }
wait_up() { for i in $(seq 1 180); do curl -sf -m 3 "http://127.0.0.1:$1/health" >/dev/null && { echo "  :$1 ready ${i}s"; return 0; }; sleep 1; done; echo "  :$1 NOT ready"; tail -20 "$2"; return 1; }
case "${1:-status}" in
  start)
    if ! alive "$R/logs/llm.pid"; then
      setsid nohup "$LLAMA" -m "$MODEL" --host 127.0.0.1 --port 18093 -ngl 999 -c $((NP * SLOT_CTX)) -np "$NP" \
        --alias bielik-4.5b-v3 --jinja -fa on --no-webui --metrics --cache-ram 256 > "$R/logs/llm.log" 2>&1 < /dev/null &
      echo $! > "$R/logs/llm.pid"; wait_up 18093 "$R/logs/llm.log"
    fi
    if ! alive "$R/logs/rr.pid"; then
      setsid nohup "$LLAMA" -m "$RMODEL" --reranking --host 127.0.0.1 --port 18094 -ngl 999 -c 8192 -b 4096 -ub 4096 \
        -np 4 --alias bge-reranker-v2-m3 --no-webui > "$R/logs/rr.log" 2>&1 < /dev/null &
      echo $! > "$R/logs/rr.pid"; wait_up 18094 "$R/logs/rr.log"
    fi
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader ;;
  stop)
    for p in llm rr; do alive "$R/logs/$p.pid" && kill "$(cat "$R/logs/$p.pid")" && echo "stopped $p"; done ;;
  status)
    for p in llm rr; do alive "$R/logs/$p.pid" && echo "$p up pid $(cat "$R/logs/$p.pid")" || echo "$p down"; done
    nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader ;;
esac
