#!/bin/bash
# Final exam, whole procedure on ONE box, fully offline (no network except 127.0.0.1):
#   1. start the vision llama-server (Qwen3.5-9B Q5_K_M + mmproj F16, -np 1, --cache-ram 0)
#   2. describe every image of the exam pack in Polish (scripts/describe_images.py --prompt literal; image +
#      caption only, never the question) -> OUT/image_vlm.json
#   3. stop the vision server (frees its ~7.7 GB VRAM)
#   4. start the reranker (bge-reranker-v2-m3) + Bielik-4.5B-v3 Q8_0 (-np 1 for determinism) + harness v3
#      (CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0), the same flags as the mock run
#      submissions/mock/bielik45-harness-v3-vlm-qwen35-9b-q5km
#   5. harness/exam_runner.py --image-desc OUT/image_vlm.json --desc-caveat -> OUT/answers.json + OUT/debug.jsonl
#      (descriptions stay out of the retrieval queries: IMG_DESC_NO_QUERY=1, the harness default)
#   6. validate against the pack's answers-template.json, stop everything we started, print the answers path
#
# Image defaults = mock config C of 26.09 evening (submissions/mock/vlmx-C-r*): literal description prompt,
# max 800 tokens, repeat penalty 1.05, --desc-caveat, IMG_DESC_NO_QUERY=1. PROVISIONAL: the CKE-rubric grading
# of vlmx-A/B/C decides; to go back to the 16:30 setting use
#   VLM_PROMPT=default VLM_MAX_TOKENS=600 VLM_REPEAT_PENALTY=1.0 DESC_CAVEAT=0 IMG_DESC_NO_QUERY=0
#
# Usage:
#   scripts/run_final.sh PKG_DIR [OUT_DIR]
#     PKG_DIR = organizers' pack: exam.json + answers-template.json + images/
#     OUT_DIR = default submissions/final/<basename of PKG_DIR>
#   Re-running with the same OUT_DIR resumes: describe_images.py reuses its per-image cache and
#   exam_runner.py skips ids that already have an answer in OUT/debug.jsonl. Use a fresh OUT_DIR for a clean run.
#
# Overridable env (defaults = the L40S layout):
#   LS, PY, VLM_MODEL, VLM_MMPROJ, BIELIK, BIELIK_LORA (empty = no LoRA, as in the mock), RERANKER, KB_INDEX_DIR,
#   VLM_PORT, LLM_PORT, RER_PORT, H_PORT, RUN_CONC (items in flight),
#   VLM_PROMPT (literal|default), VLM_MAX_TOKENS (800), VLM_REPEAT_PENALTY (1.05), DESC_CAVEAT (1|0),
#   IMG_DESC_NO_QUERY (1 = descriptions not used as retrieval queries | 0)
# Never stops processes it did not start. Needs ~9.5 GB free VRAM for step 4, ~8 GB for step 1.
set -u
R=$(cd "$(dirname "$0")/.." && pwd)
cd "$R"

PKG=${1:?usage: scripts/run_final.sh PKG_DIR [OUT_DIR]}
PKG=$(cd "$PKG" && pwd) || exit 2
OUT=${2:-$R/submissions/final/$(basename "$PKG")}
mkdir -p "$OUT" "$R/logs"
OUT=$(cd "$OUT" && pwd)

LS=${LS:-/scratch/ovl/opt/llama/current/llama-server}
PY=${PY:-$R/.venv/bin/python}
[ -x "$PY" ] || PY=python3
VLM_MODEL=${VLM_MODEL:-/scratch/vlm/models/qwen35-9b-q5km/Qwen3.5-9B-Q5_K_M.gguf}
VLM_MMPROJ=${VLM_MMPROJ:-/scratch/vlm/models/qwen35-9b-q5km/mmproj-F16.gguf}
BIELIK=${BIELIK:-/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf}
BIELIK_LORA=${BIELIK_LORA:-}
RERANKER=${RERANKER:-/scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf}
KB_INDEX_DIR=${KB_INDEX_DIR:-/scratch/kb_index}
[ -d "$KB_INDEX_DIR" ] || KB_INDEX_DIR=$R/kb_data/index
VLM_PORT=${VLM_PORT:-18210}
LLM_PORT=${LLM_PORT:-18200}
RER_PORT=${RER_PORT:-18202}
H_PORT=${H_PORT:-18203}
# config C (provisional, see header; the grading decides)
VLM_PROMPT=${VLM_PROMPT:-literal}
VLM_MAX_TOKENS=${VLM_MAX_TOKENS:-800}
VLM_REPEAT_PENALTY=${VLM_REPEAT_PENALTY:-1.05}
DESC_CAVEAT=${DESC_CAVEAT:-1}
IMG_DESC_NO_QUERY=${IMG_DESC_NO_QUERY:-1}
CAVEAT_ARGS=(); [ "$DESC_CAVEAT" = 1 ] && CAVEAT_ARGS=(--desc-caveat)
RUN_CONC=${RUN_CONC:-2}
EXAM=$PKG/exam.json
DESC=$OUT/image_vlm.json
LOG=$R/logs/final-$(date +%Y%m%d-%H%M%S)
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost

PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done; sleep 2
            for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done; }
trap cleanup EXIT
trap 'exit 130' INT TERM
die() { echo "FINAL: $*" >&2; exit 1; }
say() { echo "$(date +%T) $*"; }
wait_up() {  # $1 url, $2 pid
  for i in $(seq 1 600); do
    curl -sf "$1/health" >/dev/null 2>&1 && { say "up $1 after ${i}s"; return 0; }
    kill -0 "$2" 2>/dev/null || return 1
    sleep 1
  done; return 1
}
stop_pid() {  # wait until the process is gone, so its VRAM is really free
  kill "$1" 2>/dev/null
  for i in $(seq 1 30); do kill -0 "$1" 2>/dev/null || return 0; sleep 1; done
  kill -9 "$1" 2>/dev/null; sleep 2
}
need_vram() {  # $1 MiB; no-op without nvidia-smi
  command -v nvidia-smi >/dev/null || return 0
  local free; free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  [ "$free" -ge "$1" ] || die "free VRAM ${free} MiB < needed $1 MiB"
}
port_free() { curl -s -m 2 "http://127.0.0.1:$1/health" >/dev/null 2>&1 && die "port $1 already in use"; return 0; }

# ---- preflight
for f in "$LS" "$VLM_MODEL" "$VLM_MMPROJ" "$BIELIK" "$RERANKER" "$EXAM" "$PKG/answers-template.json"; do
  [ -e "$f" ] || die "missing $f"
done
[ -z "$BIELIK_LORA" ] || [ -f "$BIELIK_LORA" ] || die "missing $BIELIK_LORA"
[ -d "$PKG/images" ] || say "WARNING: $PKG/images missing"
[ -d "$KB_INDEX_DIR" ] || die "missing KB index $KB_INDEX_DIR"
for p in $VLM_PORT $LLM_PORT $RER_PORT $H_PORT; do port_free $p; done
say "pack $PKG -> $OUT (logs $LOG-*)"

# ---- 1-3. vision model: describe images, then free the GPU
if [ -s "$DESC" ] && "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d and all(d.values()) else 1)" "$DESC"; then
  say "descriptions already complete: $DESC"
else
  need_vram 9000
  "$LS" -m "$VLM_MODEL" --mmproj "$VLM_MMPROJ" --host 127.0.0.1 --port $VLM_PORT -ngl 999 -c 8192 -np 1 \
    --cache-ram 0 -fa on --jinja --no-warmup --no-webui --alias qwen35-9b-q5km > "$LOG-vlm.log" 2>&1 < /dev/null &
  VPID=$!; PIDS+=($VPID)
  wait_up http://127.0.0.1:$VLM_PORT $VPID || { tail -20 "$LOG-vlm.log"; die "vision server did not start"; }
  "$PY" scripts/describe_images.py --exam-json "$EXAM" --url http://127.0.0.1:$VLM_PORT --out "$DESC" \
    --prompt "$VLM_PROMPT" --max-tokens $VLM_MAX_TOKENS --repeat-penalty $VLM_REPEAT_PENALTY 2>&1 | tee "$LOG-describe.log"
  stop_pid $VPID
  [ -s "$DESC" ] || die "no descriptions written ($DESC)"
  say "vision server stopped; $("$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print(sum(1 for v in d.values() if v), 'of', len(d), 'images described')" "$DESC")"
fi

# ---- 4. reranker + Bielik (-np 1: one sequence at a time -> no cross-request batching effects at T=0) + harness v3
need_vram 9500
"$LS" -m "$RERANKER" --reranking --host 127.0.0.1 --port $RER_PORT -ngl 999 -c 8192 -b 4096 -ub 4096 -np 1 \
  --cache-ram 0 --no-webui --alias bge-reranker-v2-m3 > "$LOG-rerank.log" 2>&1 < /dev/null &
RPID=$!; PIDS+=($RPID)
LORA_ARGS=(); [ -n "$BIELIK_LORA" ] && LORA_ARGS=(--lora "$BIELIK_LORA")
"$LS" -m "$BIELIK" "${LORA_ARGS[@]}" --host 127.0.0.1 --port $LLM_PORT -ngl 999 -c 16384 -np 1 -fa on --jinja \
  --cache-ram 0 --no-webui --metrics --alias bielik-4.5b-v3 > "$LOG-bielik.log" 2>&1 < /dev/null &
BPID=$!; PIDS+=($BPID)
wait_up http://127.0.0.1:$RER_PORT $RPID || { tail -20 "$LOG-rerank.log"; die "reranker did not start"; }
wait_up http://127.0.0.1:$LLM_PORT $BPID || { tail -20 "$LOG-bielik.log"; die "Bielik did not start"; }

[ -f .venv/bin/activate ] && source .venv/bin/activate
IMG_DESC_NO_QUERY=$IMG_DESC_NO_QUERY HARNESS_PORT=$H_PORT SNAPSHOT_KB=0 KB_INDEX_DIR=$KB_INDEX_DIR \
  LLM_BASE_URL=http://127.0.0.1:$LLM_PORT/v1 BASE_LLM_BASE_URL=http://127.0.0.1:$LLM_PORT/v1 LLM_MODEL=bielik-4.5b-v3 \
  CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 RERANK_URL=http://127.0.0.1:$RER_PORT \
  LLM_CONCURRENCY=$RUN_CONC LLM_TIMEOUT=1200 REQUEST_LOG=$LOG-harness-requests.jsonl \
  "$PY" -m harness > "$LOG-harness.log" 2>&1 < /dev/null &
HPID=$!; PIDS+=($HPID)
wait_up http://127.0.0.1:$H_PORT $HPID || { tail -30 "$LOG-harness.log"; die "harness did not start"; }

# ---- 5. answer the exam (Bielik only; images arrive as '[Opis obrazu: ...]' text)
# RUN_MODE=hybrid (team decision 26.09 ~20:40): short items go straight to Bielik (raw), only the essay goes
# through harness v3 -- its essay pipeline is the one gain that held on the held-out CKE 2024/2026 papers.
RUN_MODE=${RUN_MODE:-hybrid}
"$PY" -m harness.exam_runner "$EXAM" --mode $RUN_MODE --url http://127.0.0.1:$H_PORT --llm-url http://127.0.0.1:$LLM_PORT \
  --model bielik-4.5b-v3 --image-desc "$DESC" "${CAVEAT_ARGS[@]}" \
  --timeout 1800 --concurrency $RUN_CONC --system-name bielik45-$RUN_MODE-vlm-qwen35-9b-q5km-$VLM_PROMPT \
  --out "$OUT/answers.json" 2>&1 | tee "$LOG-runner.log"

# ---- 6. validate
"$PY" -m harness.exam_runner --validate "$OUT/answers.json" --exam "$EXAM" 2>&1 | tee "$LOG-validate.log"
grep -q '^VALID' "$LOG-validate.log" || die "answers.json NOT valid, see $LOG-validate.log"
say "done"
echo "ANSWERS: $OUT/answers.json"
