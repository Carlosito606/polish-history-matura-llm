#!/bin/bash
# Mock (CKE May 2023) under final-exam conditions on the L40S (mirror /scratch/mock/wmt-matura):
#   *-noimg : no image descriptions at all ('[Obraz: images/X.png]' placeholders stay in the input)
#   *-ocr   : offline Tesseract OCR text (scripts/ocr_images.py -> data_cke/mock2023/image_ocr.json)
# Same runner flags as scripts/l40s_run_mock.sh chainB (bielik45-base-raw / bielik45-harness-v3).
# LLM: the untouched Bielik-4.5B Q8_0 server (no LoRA), default :18093 (shared with RFT sampling, so the
# runner keeps at most 4 requests in flight); reranker :18092. Our own harness v3 on :18043.
#   l40s_run_mock_ocr.sh ocr | up | chain | down
set -u
R=/scratch/mock/wmt-matura
cd $R
PY=$R/.venv/bin/python
LLM=${LLM:-http://127.0.0.1:18093}
RER=${RER:-http://127.0.0.1:18092}
HP=${HP:-18043}
EX=data_cke/mock2023/exam.json
OCR=data_cke/mock2023/image_ocr.json
OUT=submissions/mock
run() {  # $1 system name, rest = runner args
  local s=$1; shift
  $PY -m harness.exam_runner $EX "$@" --timeout 1800 --concurrency 4 --system-name $s --out $OUT/$s/answers.json
  $PY -m harness.exam_runner --validate $OUT/$s/answers.json --exam $EX
}
case "${1:-}" in
ocr)
  /scratch/ocr/venv/bin/python scripts/ocr_images.py data_cke/mock2023 --jobs 3
  ;;
up)
  HARNESS_PORT=$HP TAG=b45v3img SNAPSHOT_KB=0 KB_INDEX_DIR=/scratch/kb_index LLM_BASE_URL=$LLM/v1 \
    BASE_LLM_BASE_URL=$LLM/v1 LLM_MODEL=bielik-4.5b-v3 CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 \
    RERANK_URL=$RER REQUEST_LOG=logs/harness-b45v3img-requests.jsonl LLM_CONCURRENCY=4 \
    harness/scripts/start_harness.sh
  ;;
chain)
  [ -s $OCR ] || { echo "missing $OCR"; exit 1; }
  run bielik45-base-raw-noimg --mode raw --llm-url $LLM --model bielik-4.5b-v3
  run bielik45-base-raw-ocr --mode raw --llm-url $LLM --model bielik-4.5b-v3 --image-desc $OCR
  run bielik45-harness-v3-noimg --mode harness --url http://127.0.0.1:$HP
  run bielik45-harness-v3-ocr --mode harness --url http://127.0.0.1:$HP --image-desc $OCR
  echo CHAIN_OCR_DONE
  ;;
down)
  kill "$(cat logs/harness-b45v3img.pid)" 2>/dev/null
  ;;
esac
