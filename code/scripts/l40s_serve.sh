#!/usr/bin/env bash
# L40S (Forgehand) serving: llama-server (CUDA, llama.cpp b11185) + harness (FastAPI RAG over the BM25 KB).
#
#   scripts/l40s_serve.sh start      # llama-server :18080 + harness :18000 (Bielik 11B Q4_K_M by default)
#   scripts/l40s_serve.sh stop
#   scripts/l40s_serve.sh restart
#   scripts/l40s_serve.sh status
#
#   MODEL_FILE=qwen3-8b/Qwen3-8B-Q4_K_M.gguf CHAT_TEMPLATE_KWARGS='{"enable_thinking":false}' scripts/l40s_serve.sh restart
#   LORA_FILE=loras/bielik11b-r16.gguf scripts/l40s_serve.sh restart           # base GGUF + LoRA adapter
#   LLM_PORT=18081 HARNESS_PORT=18001 scripts/l40s_serve.sh start               # a second, independent pair
#   ONLY=llm scripts/l40s_serve.sh start                                        # only llama-server (e.g. untouched base)
#
# Env (defaults in brackets):
#   MODEL_FILE    GGUF, absolute or relative to MODELS_DIR [bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf]
#   LORA_FILE     optional GGUF LoRA adapter (convert_lora_to_gguf.py output), absolute or relative to MODELS_DIR
#   LORA_SCALE    [1.0]
#   MODELS_DIR    [/workspace/models]            LLAMA_DIR [/workspace/opt/llama/current]
#   LLM_HOST      [127.0.0.1]   LLM_PORT [18080]  CTX [16384]  NP [8]  NGL [999]
#   ALIAS         model name served by llama-server and sent by the harness [directory name of MODEL_FILE]
#   CHAT_TEMPLATE_KWARGS  JSON for --chat-template-kwargs, e.g. '{"enable_thinking":false}' (Qwen3)
#   LLAMA_EXTRA   extra llama-server args (word-split)
#   HARNESS_HOST  [127.0.0.1]   HARNESS_PORT [18000]   KB_INDEX_DIR [/workspace/kb_data/index]
#   LLM_CONCURRENCY [NP]        BASE_LLM_BASE_URL  target of /base/... (repo rule: an untouched base server
#                               without LoRA; defaults to this llama-server, so set it when LORA_FILE is used)
#   ONLY          llm | harness (act on one side only)
# Logs and pid files: /workspace/logs/{llama,harness}-<port>.{log,pid}
set -euo pipefail

ROOT=${ROOT:-/workspace/wmt-matura}
VENV=${VENV:-/workspace/venvs/wmt}
LOGS=${LOGS:-/workspace/logs}
MODELS_DIR=${MODELS_DIR:-/workspace/models}
LLAMA_DIR=${LLAMA_DIR:-/workspace/opt/llama/current}
MODEL_FILE=${MODEL_FILE:-bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf}
LORA_FILE=${LORA_FILE:-}
LORA_SCALE=${LORA_SCALE:-1.0}
LLM_HOST=${LLM_HOST:-127.0.0.1}
LLM_PORT=${LLM_PORT:-18080}
CTX=${CTX:-16384}
NP=${NP:-8}
NGL=${NGL:-999}
CHAT_TEMPLATE_KWARGS=${CHAT_TEMPLATE_KWARGS:-}
LLAMA_EXTRA=${LLAMA_EXTRA:-}
HARNESS_HOST=${HARNESS_HOST:-127.0.0.1}
HARNESS_PORT=${HARNESS_PORT:-18000}
KB_INDEX_DIR=${KB_INDEX_DIR:-/workspace/kb_data/index}
ONLY=${ONLY:-}

abspath() { case "$1" in /*) echo "$1" ;; *) echo "$MODELS_DIR/$1" ;; esac; }
MODEL_PATH=$(abspath "$MODEL_FILE")
ALIAS=${ALIAS:-$(basename "$(dirname "$MODEL_PATH")")}
LLM_PID=$LOGS/llama-$LLM_PORT.pid
LLM_LOG=$LOGS/llama-$LLM_PORT.log
H_PID=$LOGS/harness-$HARNESS_PORT.pid
H_LOG=$LOGS/harness-$HARNESS_PORT.log
mkdir -p "$LOGS"

# pid files live on persistent /workspace: after a session restart a stale pid may belong to another process,
# so also require the process command line to match (llama-server or python -m harness).
alive() {
  [ -f "$1" ] || return 1
  local pid; pid=$(cat "$1")
  kill -0 "$pid" 2>/dev/null && tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -qE 'llama-server|-m harness'
}

wait_http() {  # url seconds
  local i
  for i in $(seq 1 "$2"); do
    curl -sf -m 5 "$1" >/dev/null 2>&1 && { echo "  ready after ${i}s"; return 0; }
    sleep 1
  done
  return 1
}

start_llm() {
  if alive "$LLM_PID"; then echo "llama-server already running (pid $(cat "$LLM_PID"), :$LLM_PORT)"; return 0; fi
  [ -f "$MODEL_PATH" ] || { echo "model not found: $MODEL_PATH" >&2; exit 1; }
  local args=(-m "$MODEL_PATH" --host "$LLM_HOST" --port "$LLM_PORT" -ngl "$NGL" -c "$CTX" -np "$NP"
              --alias "$ALIAS" --jinja -fa on -kvu --metrics --no-webui)
  if [ -n "$LORA_FILE" ]; then
    local lora; lora=$(abspath "$LORA_FILE")
    [ -f "$lora" ] || { echo "LoRA not found: $lora" >&2; exit 1; }
    args+=(--lora-scaled "$lora:$LORA_SCALE")
  fi
  [ -n "$CHAT_TEMPLATE_KWARGS" ] && args+=(--chat-template-kwargs "$CHAT_TEMPLATE_KWARGS")
  # host prompt cache defaults to 8 GiB per server; the container has a 30 GB RAM limit (OOM on 26.09)
  [[ " $LLAMA_EXTRA " == *" --cache-ram "* ]] || args+=(--cache-ram "${CACHE_RAM:-0}")
  echo "starting llama-server :$LLM_PORT  model=$MODEL_PATH ${LORA_FILE:+lora=$LORA_FILE@$LORA_SCALE} ctx=$CTX np=$NP"
  # shellcheck disable=SC2086  # LLAMA_EXTRA is intentionally word-split
  setsid nohup "$LLAMA_DIR/llama-server" "${args[@]}" $LLAMA_EXTRA > "$LLM_LOG" 2>&1 < /dev/null &
  echo $! > "$LLM_PID"
  if ! wait_http "http://$LLM_HOST:$LLM_PORT/health" 300; then
    echo "llama-server not ready; tail of $LLM_LOG:" >&2; tail -30 "$LLM_LOG" >&2; exit 1
  fi
}

start_harness() {
  if alive "$H_PID"; then echo "harness already running (pid $(cat "$H_PID"), :$HARNESS_PORT)"; return 0; fi
  [ -d "$KB_INDEX_DIR" ] || echo "WARNING: KB index $KB_INDEX_DIR missing -> harness runs without KB" >&2
  echo "starting harness :$HARNESS_PORT -> http://$LLM_HOST:$LLM_PORT/v1 (model $ALIAS, KB $KB_INDEX_DIR)"
  (
    cd "$ROOT"
    export LLM_BASE_URL="http://$LLM_HOST:$LLM_PORT/v1" LLM_MODEL="$ALIAS" KB_INDEX_DIR
    export HARNESS_HOST HARNESS_PORT LLM_CONCURRENCY=${LLM_CONCURRENCY:-$NP}
    [ -n "${BASE_LLM_BASE_URL:-}" ] && export BASE_LLM_BASE_URL
    setsid nohup "$VENV/bin/python" -m harness > "$H_LOG" 2>&1 < /dev/null &
    echo $! > "$H_PID"
  )
  if ! wait_http "http://127.0.0.1:$HARNESS_PORT/health" 180; then
    echo "harness not ready; tail of $H_LOG:" >&2; tail -30 "$H_LOG" >&2; exit 1
  fi
}

stop_pid() {  # pidfile name
  if alive "$1"; then
    local pid; pid=$(cat "$1")
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null || true
    echo "stopped $2 (pid $pid)"
  else
    echo "$2 not running"
  fi
  rm -f "$1"
}

status() {
  if alive "$LLM_PID"; then
    echo "llama-server :$LLM_PORT pid $(cat "$LLM_PID"): $(curl -s -m 5 "http://$LLM_HOST:$LLM_PORT/health" || echo unreachable)"
    curl -s -m 5 "http://$LLM_HOST:$LLM_PORT/v1/models" | "$VENV/bin/python" -c 'import json,sys; print("  models:", [m["id"] for m in json.load(sys.stdin)["data"]])' 2>/dev/null || true
  else echo "llama-server :$LLM_PORT not running"; fi
  if alive "$H_PID"; then
    echo "harness :$HARNESS_PORT pid $(cat "$H_PID"):"
    curl -s -m 10 "http://127.0.0.1:$HARNESS_PORT/health" | "$VENV/bin/python" -c '
import json, sys
d = json.load(sys.stdin)
keep = {k: d[k] for k in d if k != "config"}
cfg = d.get("config", {})
print("  ", json.dumps(keep, ensure_ascii=False)[:600])
print("   config:", {k: cfg.get(k) for k in ("llm_base_url", "llm_model", "kb_index_dir", "llm_concurrency") if k in cfg})' 2>/dev/null || echo "  unreachable"
  else echo "harness :$HARNESS_PORT not running"; fi
  command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader | sed 's/^/gpu: /'
}

case "${1:-status}" in
  start)
    [ "$ONLY" = harness ] || start_llm
    [ "$ONLY" = llm ] || start_harness ;;
  stop)
    [ "$ONLY" = llm ] || stop_pid "$H_PID" "harness :$HARNESS_PORT"
    [ "$ONLY" = harness ] || stop_pid "$LLM_PID" "llama-server :$LLM_PORT" ;;
  restart)
    bash "$0" stop; bash "$0" start ;;
  status) status ;;
  *) echo "usage: $0 start|stop|restart|status" >&2; exit 2 ;;
esac
