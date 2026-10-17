#!/usr/bin/env bash
# Start a llama-server (OpenAI API) for one of our models.
#   harness/scripts/start_llama.sh bielik     -> 127.0.0.1:18080  (Bielik-11B-v3 Q4_K_M)
#   harness/scripts/start_llama.sh qwen3      -> 127.0.0.1:18081  (Qwen3-8B Q4_K_M, thinking disabled)
# Env overrides: PORT, MODEL_PATH, LLAMA_BIN, CTX (16384), NP (4), NGL (999), HOST (127.0.0.1), EXTRA
# On Linux/CUDA (L40S) point LLAMA_BIN at the CUDA build; flags are identical.
set -euo pipefail
cd "$(dirname "$0")/../.."
WHICH=${1:-bielik}
LLAMA_BIN=${LLAMA_BIN:-bin/llama/llama-b11185/llama-server}
HOST=${HOST:-127.0.0.1}
CTX=${CTX:-16384}
NP=${NP:-4}
NGL=${NGL:-999}
EXTRA=${EXTRA:-}
mkdir -p logs
case "$WHICH" in
  bielik)
    MODEL_PATH=${MODEL_PATH:-models/bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf}
    PORT=${PORT:-18080}; ALIAS=bielik-11b-v3; KW="" ;;
  qwen3)
    MODEL_PATH=${MODEL_PATH:-models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf}
    PORT=${PORT:-18081}; ALIAS=qwen3-8b; KW='{"enable_thinking":false}' ;;
  *)
    : "${MODEL_PATH:?set MODEL_PATH}"; PORT=${PORT:-18082}; ALIAS=$WHICH; KW="" ;;
esac
if (command -v lsof >/dev/null && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1); then
  echo "port $PORT already in use"; exit 1
fi
ARGS=(-m "$MODEL_PATH" --host "$HOST" --port "$PORT" -ngl "$NGL" -c "$CTX" -np "$NP" --alias "$ALIAS"
      --jinja -fa on -kvu --metrics)
if [ -n "$KW" ]; then ARGS+=(--chat-template-kwargs "$KW"); fi
# shellcheck disable=SC2086
nohup "$LLAMA_BIN" "${ARGS[@]}" $EXTRA > "logs/llama-$WHICH.log" 2>&1 &
echo $! > "logs/llama-$WHICH.pid"
echo "started $WHICH pid $(cat "logs/llama-$WHICH.pid") on $HOST:$PORT (log logs/llama-$WHICH.log)"
for i in $(seq 1 120); do
  if curl -sf "http://$HOST:$PORT/health" >/dev/null 2>&1; then echo "ready after ${i}s"; exit 0; fi
  sleep 1
done
echo "not ready after 120s, see logs/llama-$WHICH.log"; exit 1
