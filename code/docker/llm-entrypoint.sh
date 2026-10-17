#!/bin/sh
# Entrypoint for the llama.cpp server containers (official image; CUDA in prod, CPU on the Mac).
# Bind-mounted read-only at /opt/wmt/llm-entrypoint.sh by compose.yaml.
#
# Env (all paths relative to /models):
#   MODEL_FILE      required  GGUF to serve (base, or merged fine-tune)
#   LORA_FILE       optional  GGUF LoRA adapter (convert_lora_to_gguf.py output), applied on MODEL_FILE
#   LORA_SCALE      1.0
#   MODEL_ALIAS     wmt       name reported by /v1/models
#   N_GPU_LAYERS    999       0 on CPU
#   CTX_SIZE        16384     total KV cache (tokens)
#   N_PARALLEL      4         server slots (concurrent requests)
#   KV_UNIFIED      1         1 = one KV pool shared by all slots (a single request may use all CTX_SIZE);
#                             0 = each slot gets CTX_SIZE/N_PARALLEL
#   CHAT_TEMPLATE_FILE        optional Jinja template overriding the one embedded in the GGUF
#   SEED                      optional
#   LLAMA_EXTRA_ARGS          appended verbatim (word-split), e.g. "-t 4 --cache-type-k q8_0"
set -eu

MODELS_ROOT=${MODELS_ROOT:-/models}
: "${MODEL_FILE:?MODEL_FILE is not set (path relative to $MODELS_ROOT)}"

model="$MODELS_ROOT/$MODEL_FILE"
if [ ! -f "$model" ]; then
  echo "[llm] model not found: $model" >&2
  ls -la "$MODELS_ROOT" >&2 || true
  exit 1
fi

set -- --model "$model" \
  --host 0.0.0.0 --port "${LLM_PORT:-8080}" \
  --n-gpu-layers "${N_GPU_LAYERS:-999}" \
  --ctx-size "${CTX_SIZE:-16384}" \
  --parallel "${N_PARALLEL:-4}" \
  --alias "${MODEL_ALIAS:-wmt}" \
  --jinja --no-webui --metrics

if [ "${KV_UNIFIED:-1}" = "1" ]; then
  set -- "$@" --kv-unified
fi

if [ -n "${LORA_FILE:-}" ]; then
  lora="$MODELS_ROOT/$LORA_FILE"
  if [ ! -f "$lora" ]; then
    echo "[llm] LoRA adapter not found: $lora" >&2
    exit 1
  fi
  set -- "$@" --lora-scaled "$lora:${LORA_SCALE:-1.0}"
fi

if [ -n "${CHAT_TEMPLATE_FILE:-}" ]; then
  set -- "$@" --chat-template-file "$MODELS_ROOT/$CHAT_TEMPLATE_FILE"
fi

if [ -n "${SEED:-}" ]; then
  set -- "$@" --seed "$SEED"
fi

echo "[llm] exec /app/llama-server $* ${LLAMA_EXTRA_ARGS:-}" >&2
# shellcheck disable=SC2086  # LLAMA_EXTRA_ARGS is intentionally word-split
exec /app/llama-server "$@" ${LLAMA_EXTRA_ARGS:-}
