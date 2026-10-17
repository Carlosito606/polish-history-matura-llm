#!/usr/bin/env bash
# Re-run eval files whose earlier run had errors (llama-server :18082 died at ~00:51 UTC).
#   rerun.sh KEY GGUF_REL CTK LORA_GGUF|"" "label:file file ..." ["label:file ..."]
# Own port pair (LLM_PORT/HARNESS_PORT env, default 18083/18003) so it can run next to run_model.sh.
# Each file: up to 3 attempts; the servers are restarted when a run has errors.
set -uo pipefail
KEY=$1 GGUF=$2 CTK=$3 LORA=$4; shift 4
ROOT=/workspace/wmt-matura
cd "$ROOT" || exit 1
PY=/workspace/venvs/wmt/bin/python
OD=/workspace/data/overnight
ST=$OD/$KEY.rerun.status
LP=${LLM_PORT:-18083} HP=${HARNESS_PORT:-18003}
say() { echo "$(date -u +%H:%M:%S) $*" >> "$ST"; }
export LLM_PORT=$LP HARNESS_PORT=$HP MODEL_FILE=$GGUF CTX=32768 NP=8 CHAT_TEMPLATE_KWARGS="$CTK"
export LORA_FILE="$LORA" LORA_SCALE=1.0 QTYPE_V2=1 RERANK=1 RERANK_URL=http://127.0.0.1:18092 LLM_CONCURRENCY=8
export REQUEST_LOG=$OD/harness-requests-$KEY-rerun.jsonl
if [ -n "$CTK" ]; then export LLM_EXTRA_BODY="{\"chat_template_kwargs\": $CTK}"; else unset LLM_EXTRA_BODY; fi
restart() {
  bash scripts/l40s_serve.sh stop >> "$OD/serve-$KEY-rerun.log" 2>&1
  curl -sf -m 3 http://127.0.0.1:18092/health >/dev/null || bash scripts/l40s_rerank.sh start >> "$OD/serve-$KEY-rerun.log" 2>&1
  bash scripts/l40s_serve.sh start >> "$OD/serve-$KEY-rerun.log" 2>&1 || say "serve start FAILED"
  say "serve up :$LP/:$HP lora=${LORA:-none} adapters=$(curl -s -m 5 http://127.0.0.1:$LP/lora-adapters | cut -c1-120)"
}
restart
for spec in "$@"; do
  lab=${spec%%:*}; files=${spec#*:}
  case "$lab" in *base-raw) ep=base; extra=(--max-tokens 512) ;; *) ep=answer; extra=() ;; esac
  for d in $files; do
    for try in 1 2 3; do
      log=$OD/eval_${lab}_$d.try$try.log
      "$PY" devset/eval.py --endpoint "$ep" --url "http://127.0.0.1:$HP" --files "devset/$d.jsonl" --workers 8 \
          --label "$lab" "${extra[@]}" > "$log" 2>&1
      head=$(grep -a '^=== ' "$log" | tail -1); err=$(sed -n 's/.*errors=\([0-9]*\).*/\1/p' <<< "$head")
      say "$lab $d try$try errors=${err:-?} $(grep -a '^overall' "$log" | tail -1)"
      [ "${err:-1}" = 0 ] && break
      restart
    done
  done
done
bash scripts/l40s_serve.sh stop >> "$OD/serve-$KEY-rerun.log" 2>&1
say "RERUN DONE"
