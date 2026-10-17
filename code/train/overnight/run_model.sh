#!/usr/bin/env bash
# Overnight LoRA pipeline for one model: [baseline evals || train] -> export -> LoRA evals.
#   run_model.sh KEY HF_REPO GGUF_REL CTK SEQ
# Stages are idempotent (skip when their output exists). Status lines -> /workspace/data/overnight/KEY.status
set -uo pipefail
KEY=$1 HF=$2 GGUF=$3 CTK=$4 SEQ=$5
ROOT=/workspace/wmt-matura
cd "$ROOT" || exit 1
source /workspace/env.sh >/dev/null 2>&1
PY=/workspace/venvs/wmt/bin/python
TPY=/workspace/venvs/train/bin/python
NAME=final-$KEY-r16-e2
OD=/workspace/data/overnight
mkdir -p "$OD" /workspace/logs
ST=$OD/$KEY.status
DEVS="tourney160 dev-a dev-b dev-c dev-f dev-g dev-h cke-2023 cke-more"
say() { echo "$(date -u +%H:%M:%S) $*" >> "$ST"; }

do_train() {
  if [ -f "/workspace/runs/$NAME/adapter/adapter_config.json" ]; then say "train: already done"; return 0; fi
  say "train: start $NAME"
  local args=(--data /workspace/data/sft_v1_train.jsonl --eval-frac 0.03 --base "$HF" --name "$NAME"
              --r 16 --alpha 32 --lr 1e-4 --epochs 2 --max-seq-len "$SEQ" --batch 4 --grad-accum 4 --seed 42
              --gen-eval-n 67 --gen-eval-base)
  [ -n "$CTK" ] && args+=(--chat-template-kwargs "$CTK")
  "$TPY" train/train_lora.py "${args[@]}" > "/workspace/logs/train_$NAME.log" 2>&1
  local rc=$?
  say "train: exit $rc; metrics: $(tr -d '\n' < "/workspace/runs/$NAME/metrics.json" 2>/dev/null | cut -c1-400)"
  return $rc
}

serve() {  # $1 = LoRA gguf path or ""
  export LLM_PORT=18082 HARNESS_PORT=18002 MODEL_FILE=$GGUF CTX=32768 NP=8 CHAT_TEMPLATE_KWARGS="$CTK"
  export LORA_FILE="$1" LORA_SCALE=1.0 QTYPE_V2=1 RERANK=1 RERANK_URL=http://127.0.0.1:18092 LLM_CONCURRENCY=8
  export REQUEST_LOG=$OD/harness-requests-$KEY.jsonl
  if [ -n "$CTK" ]; then export LLM_EXTRA_BODY="{\"chat_template_kwargs\": $CTK}"; else unset LLM_EXTRA_BODY; fi
  bash scripts/l40s_serve.sh start >> "$OD/serve-$KEY.log" 2>&1 || { say "serve: FAILED (see serve-$KEY.log)"; return 1; }
  say "serve: up lora=${1:-none} adapters=$(curl -s -m 5 http://127.0.0.1:18082/lora-adapters | cut -c1-200)"
}
stopsrv() { LLM_PORT=18082 HARNESS_PORT=18002 bash scripts/l40s_serve.sh stop >> "$OD/serve-$KEY.log" 2>&1; }

evalset() {  # label endpoint [extra eval.py args]
  local lab=$1 ep=$2; shift 2
  for d in $DEVS; do
    local log=$OD/eval_${lab}_$d.log
    if grep -q '^appended -> ' "$log" 2>/dev/null; then continue; fi
    "$PY" devset/eval.py --endpoint "$ep" --url http://127.0.0.1:18002 --files "devset/$d.jsonl" --workers 8 \
        --label "$lab" "$@" > "$log" 2>&1
    say "$lab $d: $(grep -E '^overall' "$log" | tail -1)"
  done
}

phase_base() {
  local lab=final-$KEY
  if grep -q '^appended -> ' "$OD/eval_$lab-base-raw_cke-more.log" 2>/dev/null; then say "phase A: already done"; return 0; fi
  stopsrv; serve "" || return 1
  evalset "$lab-harness-v2" answer
  evalset "$lab-base-raw" base --max-tokens 512
  stopsrv
  say "phase A: done"
}

phase_lora() {
  local lab=final-$KEY
  local lf=/workspace/loras/$NAME.gguf
  if [ ! -f "$lf" ]; then
    bash train/export.sh --run "$NAME" --base-gguf "$GGUF" > "$OD/export-$KEY.log" 2>&1
    say "export: exit $? $(grep -iE 'PASS|FAIL' "$OD/export-$KEY.log" | tail -2 | tr '\n' ' ')"
  fi
  [ -f "$lf" ] || { say "export: no adapter gguf"; return 1; }
  stopsrv; serve "$lf" || return 1
  evalset "$lab-harness-v2-lora" answer
  stopsrv
  say "phase B: done"
}

say "=== start $KEY ($HF, $GGUF, ctk='$CTK', seq=$SEQ)"
curl -sf -m 3 http://127.0.0.1:18092/health >/dev/null || bash scripts/l40s_rerank.sh start >> "$OD/serve-$KEY.log" 2>&1
# baselines (no LoRA) run next to training on the same GPU; greedy decoding, so only latency is affected
( phase_base ) &
BP=$!
do_train; TRC=$?
wait $BP
if [ $TRC -ne 0 ]; then say "=== FAILED: training exit $TRC"; exit 1; fi
phase_lora || { say "=== FAILED: phase B"; exit 1; }
"$PY" "$OD/summarize.py" "$KEY" >> "$ST" 2>&1
say "=== DONE $KEY"
