#!/usr/bin/env bash
# Overnight supervisor v2: runner-up (Bielik-4.5B-v3) pipeline entirely on local /scratch/ovl (see mirror.sh).
# Qwen3-8B finished under sup.sh (04:11 UTC, LORA_HELPS=1). Results are synced back to /workspace by sync_back.sh.
#   setsid nohup bash /scratch/overnight/sup2.sh > /scratch/overnight/sup2.out 2>&1 < /dev/null &
set -uo pipefail
OD=/scratch/overnight
S=/scratch/ovl
ROOT=$S/wmt-matura
PY=$S/venvs/wmt/bin/python
TPY=$S/venvs/train/bin/python
export HOME=$S/home HF_HOME=$S/hf HF_HUB_OFFLINE=1 RUNS_DIR=$S/runs LORA_DIR=$S/loras MODELS_DIR=$S/models \
       LLAMA_DIR=$S/opt/llama/current LLAMA_SRC=$S/opt/llama.cpp-src CONVERT_PY=$S/venvs/convert/bin/python \
       TRAIN_PY=$TPY GLIBC_SHIM=$S/opt/glibc-2.39/lib VENV=$S/venvs/wmt LOGS=$S/logs ROOT \
       MODEL=$S/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf KB_INDEX_DIR=/scratch/kb_index \
       CSV=$ROOT/devset/experiments.csv
DEVS="tourney160 dev-a dev-b dev-c dev-f dev-g dev-h cke-2023 cke-more"
source /workspace/env.sh >/dev/null 2>&1 || true   # HF_TOKEN (never printed), only used by online retries
cd "$ROOT" || exit 1
KEY=sup
say() { echo "$(date -u +%H:%M:%S) $*" >> "$OD/$KEY.status"; }
isdone() { "$PY" "$OD/done.py" "$1" "$2"; }

rerank_up() { curl -sf -m 5 http://127.0.0.1:18092/health >/dev/null || bash scripts/l40s_rerank.sh start >> "$OD/serve.log" 2>&1; }
srv_stop() { LLM_PORT=$1 HARNESS_PORT=$2 bash scripts/l40s_serve.sh stop >> "$OD/serve.log" 2>&1; }
srv_ok() { curl -sf -m 5 "http://127.0.0.1:$1/health" >/dev/null && curl -sf -m 10 "http://127.0.0.1:$2/health" >/dev/null; }
srv_start() {  # LLM_PORT HARNESS_PORT LORA_GGUF|""
  srv_stop "$1" "$2"; rerank_up
  (
    export LLM_PORT=$1 HARNESS_PORT=$2 MODEL_FILE=$GGUF CTX=32768 NP=8 CHAT_TEMPLATE_KWARGS="$CTK"
    export LORA_FILE="$3" LORA_SCALE=1.0 QTYPE_V2=1 RERANK=1 RERANK_URL=http://127.0.0.1:18092 LLM_CONCURRENCY=8
    export REQUEST_LOG=$OD/harness-requests-$KEY-$2.jsonl
    if [ -n "$CTK" ]; then export LLM_EXTRA_BODY="{\"chat_template_kwargs\": $CTK}"; else unset LLM_EXTRA_BODY; fi
    bash scripts/l40s_serve.sh start >> "$OD/serve.log" 2>&1
  ) || { say "serve :$1/:$2 FAILED"; return 1; }
  say "serve :$1/:$2 up lora=${3:-none} adapters=$(curl -s -m 5 "http://127.0.0.1:$1/lora-adapters" | cut -c1-70)"
}

evals() {  # LLM_PORT HARNESS_PORT LABEL ENDPOINT LORA [eval.py args...]
  local lp=$1 hp=$2 lab=$3 ep=$4 lora=$5; shift 5
  for d in $DEVS; do
    isdone "$lab" "$d" && continue
    for try in 1 2 3; do
      srv_ok "$lp" "$hp" || srv_start "$lp" "$hp" "$lora" || { sleep 60; continue; }
      local log=$OD/eval_${lab}_$d.v2t$try.log
      "$PY" devset/eval.py --endpoint "$ep" --url "http://127.0.0.1:$hp" --files "devset/$d.jsonl" --workers 8 \
          --label "$lab" "$@" > "$log" 2>&1
      say "$lab $d v2t$try $(grep -a '^=== ' "$log" | tail -1 | grep -o 'errors=[0-9]*') $(grep -a '^overall' "$log" | tail -1 | tr -s ' ')"
      isdone "$lab" "$d" && break
      srv_stop "$lp" "$hp"; sleep 30
    done
  done
}

train() {
  local ad=$RUNS_DIR/$NAME/adapter/adapter_config.json try
  for try in 1 2 3; do
    [ -f "$ad" ] && return 0
    say "train: start $NAME v2t$try"
    local args=(--data $S/data/sft_v1_train.jsonl --eval-frac 0.03 --base "$HF" --name "$NAME"
                --r 16 --alpha 32 --lr 1e-4 --epochs 2 --max-seq-len "$SEQ" --batch 4 --grad-accum 4 --seed 42
                --gen-eval-n 67 --gen-eval-base)
    [ -n "$CTK" ] && args+=(--chat-template-kwargs "$CTK")
    local off=1; [ "$try" -gt 1 ] && off=0   # try 1 offline (local cache), later tries online with the token
    HF_HUB_OFFLINE=$off "$TPY" train/train_lora.py "${args[@]}" >"$OD/train_$NAME.v2t$try.log" 2>&1
    say "train: exit $? metrics: $(tr -d '\n' < "$RUNS_DIR/$NAME/metrics.json" 2>/dev/null | cut -c1-300)"
    [ -f "$ad" ] || sleep 60
  done
  [ -f "$ad" ]
}

export_lora() {
  local lf=$LORA_DIR/$NAME.gguf try
  for try in 1 2 3; do
    [ -f "$lf" ] && [ -f "$lf.json" ] && return 0
    bash train/export.sh --run "$NAME" --base-gguf "$GGUF" > "$OD/export-$KEY.v2t$try.log" 2>&1
    say "export: exit $? $(grep -iE 'PASS|FAIL' "$OD/export-$KEY.v2t$try.log" | tail -1)"
    [ -f "$lf.json" ] || sleep 60
  done
  [ -f "$lf" ]
}

run_model() {  # KEY HF_REPO GGUF_REL CTK SEQ
  KEY=$1 HF=$2 GGUF=$3 CTK=$4 SEQ=$5 NAME=final-$1-r16-e2
  say "=== sup2 start $KEY ($HF, $GGUF, seq=$SEQ) on /scratch/ovl"
  rerank_up
  ( evals 18083 18003 "final-$KEY-harness-v2" answer ""
    evals 18083 18003 "final-$KEY-base-raw" base "" --max-tokens 512
    srv_stop 18083 18003; say "baselines done" ) &
  local bp=$!
  if ! train; then say "=== FAILED train"; wait $bp; return 1; fi
  if ! export_lora; then say "=== FAILED export"; wait $bp; return 1; fi
  evals 18082 18002 "final-$KEY-harness-v2-lora" answer "$LORA_DIR/$NAME.gguf"
  srv_stop 18082 18002
  wait $bp
  "$PY" "$OD/summarize.py" qwen3-8b "$KEY" >> "$OD/$KEY.status" 2>&1
  say "=== DONE $KEY"
}

run_model bielik-4.5b-v3 speakleash/Bielik-4.5B-v3.0-Instruct bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf '' 3072
bash scripts/l40s_rerank.sh stop >> "$OD/serve.log" 2>&1
bash "$OD/sync_back.sh" >> "$OD/sync_back.log" 2>&1
echo "$(date -u +%H:%M:%S) ALL DONE" > "$OD/ALL_DONE2"
