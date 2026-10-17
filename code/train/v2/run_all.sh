#!/usr/bin/env bash
# v2 orchestrator (26.09), all on /scratch/ovl. Bielik-4.5B-v3 only (Qwen3.5-0.8B dropped, team decision). Two chains:
#   A (GPU training): Bielik v2 r16e2 -> export + merge Q8_0 -> Bielik v2 r16e3 -> export
#   B (harness evals QTYPE_V2=1 RERANK=1, sequential): v1 adapter re-run, then each adapter as soon as it is exported,
#     merged r16e2; after all training: best adapter (pooled strict) with DENSE=1 + clean latency pairs; B(merged) last.
#   setsid nohup bash /scratch/v2/run_all.sh > /scratch/v2/run_all.out 2>&1 < /dev/null &
set -uo pipefail
source /scratch/v2/env.sh; source /scratch/v2/lib.sh
KEY=run
HFB=speakleash/Bielik-4.5B-v3.0-Instruct
GB=$S/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf
DATA=$S/data/sft_v2_train.jsonl
NB1=bielik45-v2-r16-e2 NB2=bielik45-v2-r16-e3
V1=$S/loras/final-bielik-4.5b-v3-r16-e2.gguf
seqlen() {  # HF_TOKENIZER DATA -> "seq p95 max" (seq = max+16 rounded up to 256, clipped to [2048, 4096])
  "$TPY" - "$1" "$2" 2>/dev/null <<'PY'
import json, sys
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(sys.argv[1])
L = sorted(len(tok(tok.apply_chat_template(json.loads(ln)["messages"], tokenize=False), add_special_tokens=False)["input_ids"])
           for ln in open(sys.argv[2], encoding="utf-8"))
print(min(4096, max(2048, (L[-1] + 16 + 255) // 256 * 256)), L[int(0.95 * len(L))], L[-1])
PY
}
until grep -q "BUILD DONE" "$V2/build.status" 2>/dev/null; do sleep 60; done
read -r SEQB PB MB <<< "$(seqlen $HFB $DATA)"; SEQB=${SEQB:-3328}
say "=== start: data $(grep -c . $DATA) rows; bielik tokens p95=$PB max=$MB -> seq $SEQB"
rerank_up
mark() { touch "$V2/$1.$2"; }
waitm() { until [ -f "$V2/$1.exported" ] || [ -f "$V2/$1.failed" ]; do sleep 60; done; [ -f "$V2/$1.exported" ]; }

chainA() {
  KEY=trainA
  if train_run $NB1 $HFB $DATA $SEQB 16 32 2 "" --gen-eval-n 128 --gen-eval-base && export_run $NB1 $GB
  then mark $NB1 exported; sync_bg
       if export_run $NB1 $GB --merge-only; then mark $NB1 merged; else mark $NB1 mergefail; fi; sync_bg
  else mark $NB1 failed; mark $NB1 mergefail; fi
  if train_run $NB2 $HFB $DATA $SEQB 16 32 3 "" --gen-eval-n 128 && export_run $NB2 $GB
  then mark $NB2 exported; sync_bg; else mark $NB2 failed; fi
  touch "$V2/train.done"
  say "chainA DONE"
}
chainB() {
  KEY=evalB
  evals 18083 18003 bielik45-v2-harness-v2-lora-v1 answer $GB $V1 ""
  if waitm $NB1; then
    evals 18082 18002 bielik45-v2-harness-v2-lora-r16e2 answer $GB $LORA_DIR/$NB1.gguf ""
    sync_bg
    until [ -f "$V2/$NB1.merged" ] || [ -f "$V2/$NB1.mergefail" ]; do sleep 60; done
    m=$(ls $LORA_DIR/merged/$NB1.*.gguf 2>/dev/null | head -1)
    [ -n "$m" ] && evals 18085 18005 bielik45-v2-harness-v2-merged-r16e2 answer $m "" "" && sync_bg
  fi
  waitm $NB2 && evals 18082 18002 bielik45-v2-harness-v2-lora-r16e3 answer $GB $LORA_DIR/$NB2.gguf "" && sync_bg
  until [ -f "$V2/train.done" ]; do sleep 60; done
  # best adapter by pooled strict over all DEVS (tie -> tourney160); v1 wins ties (already shipped)
  read -r BEST BESTLAB <<< "$("$PY" "$V2/pick_best.py" v1=bielik45-v2-harness-v2-lora-v1 \
      r16e2=bielik45-v2-harness-v2-lora-r16e2 r16e3=bielik45-v2-harness-v2-lora-r16e3)"
  case "$BEST" in v1) BL=$V1 ;; r16e2) BL=$LORA_DIR/$NB1.gguf ;; r16e3) BL=$LORA_DIR/$NB2.gguf ;; *) BL= ;; esac
  say "best adapter: ${BEST:-none} ($BESTLAB) -> $BL"
  if [ -n "$BL" ] && dense_ready; then
    ( export DENSE=1 DENSE_WEIGHT=1.0 DENSE_FAISS_THREADS=1 DENSE_INDEX_DIR=$DENSE_DIR DENSE_URL=http://127.0.0.1:18096
      evals 18086 18006 bielik45-v2-harness-v2-lora-$BEST-dense1 answer $GB "$BL" ""
      DEVS=tourney160 evals 18086 18006 bielik45-v2-lat1-dense1-$BEST answer $GB "$BL" "" --workers 1 --limit 60 )
    sync_bg
    ( unset DENSE; DEVS=tourney160 evals 18087 18007 bielik45-v2-lat8-dense0-$BEST answer $GB "$BL" ""
      DEVS=tourney160 evals 18087 18007 bielik45-v2-lat1-dense0-$BEST answer $GB "$BL" "" --workers 1 --limit 60 )
    embed_down; sync_bg
  else say "DENSE stage skipped (best=$BEST dense_ready=$(dense_ready && echo y || echo n))"; fi
  m=$(ls $LORA_DIR/merged/$NB1.*.gguf 2>/dev/null | head -1)
  [ -n "$m" ] && evals 18085 18005 bielik45-v2-merged-r16e2-base-raw base $m "" "" --max-tokens 512
  say "chainB DONE"
}
chainA & A=$!
chainB & B=$!
wait $A $B
bash scripts/l40s_rerank.sh stop >> "$V2/serve.log" 2>&1 || true
wait; bash "$V2/sync_back.sh" >> "$V2/sync_back.log" 2>&1
say "=== ALL DONE"
