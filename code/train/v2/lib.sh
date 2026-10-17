# Functions for the v2 runs (generalized from train/overnight/sup2.sh). Source env.sh first.
isdone() { "$PY" "$V2/done.py" "$1" "$2"; }
srv_stop() { (cd "$ROOT" && LLM_PORT=$1 HARNESS_PORT=$2 bash scripts/l40s_serve.sh stop >> "$V2/serve.log" 2>&1); }
srv_ok() { curl -sf -m 5 "http://127.0.0.1:$1/health" >/dev/null && curl -sf -m 10 "http://127.0.0.1:$2/health" >/dev/null; }
srv_start() {  # LLM_PORT HARNESS_PORT GGUF LORA_GGUF|"" CTK|""  (DENSE=1 in env -> embedder + dense harness)
  srv_stop "$1" "$2"; rerank_up
  if [ "${DENSE:-0}" = 1 ]; then embed_up || { say "embedder :18096 FAILED"; return 1; }; fi
  (
    cd "$ROOT" || exit 1
    export LLM_PORT=$1 HARNESS_PORT=$2 MODEL_FILE=$3 CTX=32768 NP=8 CHAT_TEMPLATE_KWARGS="$5"
    export LORA_FILE="$4" LORA_SCALE=1.0 QTYPE_V2=1 RERANK=1 RERANK_URL=http://127.0.0.1:18092 LLM_CONCURRENCY=8
    export REQUEST_LOG=$V2/harness-requests-$2.jsonl
    if [ -n "$5" ]; then export LLM_EXTRA_BODY="{\"chat_template_kwargs\": $5}"; else unset LLM_EXTRA_BODY; fi
    bash scripts/l40s_serve.sh start >> "$V2/serve.log" 2>&1
  ) || { say "serve :$1/:$2 FAILED ($3 lora=${4:-none})"; return 1; }
  say "serve :$1/:$2 up $(basename "$3") lora=$(basename "${4:-none}") adapters=$(curl -s -m 5 "http://127.0.0.1:$1/lora-adapters" | cut -c1-60)"
  if [ "${DENSE:-0}" = 1 ]; then
    say "  dense health: $(curl -s -m 10 "http://127.0.0.1:$2/health" | "$PY" -c 'import json,sys; print(json.dumps(json.load(sys.stdin).get("kb",{}).get("dense"))[:300])' 2>&1)"
  fi
}
evals() {  # LLM_PORT HARNESS_PORT LABEL ENDPOINT GGUF LORA CTK [eval.py args...]
  local lp=$1 hp=$2 lab=$3 ep=$4 gg=$5 lora=$6 ctk=$7 d try log; shift 7
  srv_stop "$lp" "$hp"
  for d in $DEVS; do
    isdone "$lab" "$d" && continue
    for try in 1 2 3; do
      srv_ok "$lp" "$hp" || srv_start "$lp" "$hp" "$gg" "$lora" "$ctk" || { sleep 60; continue; }
      log=$V2/eval_${lab}_$d.t$try.log
      (cd "$ROOT" && "$PY" devset/eval.py --endpoint "$ep" --url "http://127.0.0.1:$hp" --files "devset/$d.jsonl" \
          --workers 8 --label "$lab" "$@" > "$log" 2>&1)
      say "$lab $d t$try $(grep -a '^=== ' "$log" | tail -1 | grep -o 'errors=[0-9]*') $(grep -a '^overall' "$log" | tail -1 | tr -s ' ' | cut -c1-60)"
      isdone "$lab" "$d" && break
      srv_stop "$lp" "$hp"; sleep 30
    done
  done
  srv_stop "$lp" "$hp"
}
train_run() {  # NAME HF DATA SEQ R ALPHA EPOCHS CTK [extra train_lora args...]
  local name=$1 hf=$2 data=$3 seq=$4 r=$5 al=$6 ep=$7 ctk=$8 try; shift 8
  local ad=$RUNS_DIR/$name/adapter/adapter_config.json
  for try in 1 2 3; do
    [ -f "$ad" ] && return 0
    say "train: start $name t$try"
    local args=(--data "$data" --eval-frac 0.03 --base "$hf" --name "$name" --r "$r" --alpha "$al" --lr 1e-4
                --epochs "$ep" --max-seq-len "$seq" --batch 4 --grad-accum 4 --seed 42 "$@")
    [ -n "$ctk" ] && args+=(--chat-template-kwargs "$ctk")
    (cd "$ROOT" && "$TPY" train/train_lora.py "${args[@]}" > "$V2/train_$name.t$try.log" 2>&1)
    say "train: $name exit $? metrics: $(tr -d '\n ' < "$RUNS_DIR/$name/metrics.json" 2>/dev/null | cut -c1-400)"
    [ -f "$ad" ] || sleep 60
  done
  [ -f "$ad" ]
}
export_run() {  # NAME GGUF [--merge|--merge-only]
  local name=$1 gg=$2 m=${3:-} lf=$LORA_DIR/$1.gguf try
  for try in 1 2 3; do
    if [ -f "$lf.json" ] && { [ -z "$m" ] || ls "$LORA_DIR"/merged/"$name".*.gguf >/dev/null 2>&1; }; then return 0; fi
    (cd "$ROOT" && bash train/export.sh --run "$name" --base-gguf "$gg" $m > "$V2/export-$name$m.t$try.log" 2>&1)
    say "export $name $m: exit $? $(grep -E 'PASS|FAIL' "$V2/export-$name$m.t$try.log" | tr '
' ' ' | cut -c1-300)"
    sleep 5
  done
  [ -f "$lf.json" ] && { [ -z "$m" ] || ls "$LORA_DIR"/merged/"$name".*.gguf >/dev/null 2>&1; }
}
sync_bg() {  # persist finished artifacts to NFS without blocking the pipeline (NFS can hang)
  ( timeout 1800 bash "$V2/sync_back.sh" >> "$V2/sync_back.log" 2>&1 ) &
}
dense_ready() { [ -f "$DENSE_DIR/index.faiss" ] && [ -f "$DENSE_DIR/vectors.f16.npy" ] && [ -f "$DENSE_DIR/ids.npy" ] && [ -f "$DENSE_DIR/meta.json" ]                 && [ -f "$EMBED_GGUF" ] && [ -f "$V2/dense.copied" ]; }
embed_up() {  # bge-m3 Q8_0 query embedder for DENSE=1 (docs/dense_retrieval.md), :18096
  curl -sf -m 5 http://127.0.0.1:18096/health >/dev/null && return 0
  setsid nohup "$LLAMA_DIR/llama-server" -m "$EMBED_GGUF" --embedding --pooling cls --host 127.0.0.1 --port 18096     -ngl 999 -c 8192 -np 4 -b 4096 -ub 4096 --alias bge-m3 --no-webui > "$LOGS/llama-18096.log" 2>&1 < /dev/null &
  echo $! > "$V2/embed.pid"
  local i; for i in $(seq 1 180); do curl -sf -m 5 http://127.0.0.1:18096/health >/dev/null && return 0; sleep 1; done
  return 1
}
embed_down() { [ -f "$V2/embed.pid" ] && kill "$(cat "$V2/embed.pid")" 2>/dev/null; rm -f "$V2/embed.pid"; }
