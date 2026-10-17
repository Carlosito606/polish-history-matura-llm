#!/bin/bash
# L40S mock + Qwen papers driver (mirror /scratch/mock/wmt-matura). Ports: Bielik llama 18050, reranker 18052,
# Bielik harness v3 18053; Qwen llama 18070, Qwen harness v2-bm25 18071, Qwen harness v3-bm25 18074.
#   run_mock.sh up        -> start all servers
#   run_mock.sh chainB    -> mock: bielik raw, bielik v3
#   run_mock.sh chainQ    -> mock: q08 raw, bm25, v3; then papers cke2024-2026 raw, bm25, v3
#   run_mock.sh down
set -u
R=/scratch/mock/wmt-matura
cd $R
PY=$R/.venv/bin/python
LS=/scratch/ovl/opt/llama/current/llama-server
BIELIK=/scratch/ovl/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf
RER=/scratch/ovl/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf
QWEN=/scratch/mock/models/Qwen3.5-0.8B-Q8_0.gguf
EX=data_cke/mock2023/exam.json
IMG=data_cke/mock2023/image_desc.json
wait_up() { for i in $(seq 1 240); do curl -sf "$1/health" >/dev/null && { echo "up $1 ${i}s"; return 0; }; sleep 1; done; echo "NOT UP $1"; return 1; }
qwen_harness() {  # $1 port, $2 tag, $3 flags
  env $3 HARNESS_PORT=$1 TAG=$2 SNAPSHOT_KB=0 KB_INDEX_DIR=/scratch/kb_index LLM_BASE_URL=http://127.0.0.1:18070/v1 \
    BASE_LLM_BASE_URL=http://127.0.0.1:18070/v1 LLM_MODEL=qwen35-0.8b REQUEST_LOG=logs/harness-$2-requests.jsonl \
    LLM_CONCURRENCY=4 TOP_K=4 CTX_TOKENS=1200 ESSAY_CTX_TOKENS=2500 ESSAY_TOP_K=6 ESSAY_MAX_TOKENS=1400 \
    ESSAY_TEMPERATURE=0.6 ESSAY_DRY_MULTIPLIER=1.0 ESSAY_DRY_ALLOWED=3 CKE_SOURCE_TOP_K=3 \
    CKE_ESSAY_PART_CTX_TOKENS=1200 CKE_ESSAY_PART_TOP_K=4 harness/scripts/start_harness.sh
}
case "${1:-}" in
up)
  mkdir -p /scratch/mock/models logs
  [ -f $QWEN ] || cp /workspace/models/qwen35-0.8b/Qwen3.5-0.8B-Q8_0.gguf $QWEN
  nohup $LS -m $BIELIK --host 127.0.0.1 --port 18050 -ngl 999 -c 32768 -np 4 -kvu -fa on --jinja \
    --alias bielik-4.5b-v3 --metrics --no-webui --cache-ram 0 > logs/llama-18050.log 2>&1 & echo $! > logs/llama-18050.pid
  nohup $LS -m $RER --reranking --host 127.0.0.1 --port 18052 -ngl 999 -c 8192 -b 4096 -ub 4096 -np 2 \
    --alias bge-reranker-v2-m3 --no-webui --cache-ram 0 > logs/rerank-18052.log 2>&1 & echo $! > logs/rerank-18052.pid
  nohup $LS -m $QWEN --host 127.0.0.1 --port 18070 -ngl 999 -c 32768 -np 4 -kvu -fa on --jinja \
    --alias qwen35-0.8b --chat-template-kwargs '{"enable_thinking":false}' --metrics --no-webui --cache-ram 0 > logs/llama-18070.log 2>&1 &
  echo $! > logs/llama-18070.pid
  wait_up http://127.0.0.1:18050; wait_up http://127.0.0.1:18052; wait_up http://127.0.0.1:18070
  HARNESS_PORT=18053 TAG=b45v3 SNAPSHOT_KB=0 KB_INDEX_DIR=/scratch/kb_index LLM_BASE_URL=http://127.0.0.1:18050/v1 \
    BASE_LLM_BASE_URL=http://127.0.0.1:18050/v1 LLM_MODEL=bielik-4.5b-v3 CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0 \
    RERANK_URL=http://127.0.0.1:18052 REQUEST_LOG=logs/harness-b45v3-requests.jsonl LLM_CONCURRENCY=4 \
    harness/scripts/start_harness.sh
  qwen_harness 18071 q08bm25 "QTYPE_V2=1 RERANK=0 DENSE=0 CKE_MODE=0"
  qwen_harness 18074 q08v3bm25 "QTYPE_V2=1 RERANK=0 DENSE=0 CKE_MODE=1"
  ;;
chainB)
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode raw --llm-url http://127.0.0.1:18050 --model bielik-4.5b-v3 \
    --system-name bielik45-base-raw --out submissions/mock/bielik45-base-raw/answers.json
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode harness --url http://127.0.0.1:18053 \
    --system-name bielik45-harness-v3 --out submissions/mock/bielik45-harness-v3/answers.json
  echo CHAINB_DONE
  ;;
chainQ)
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode raw --llm-url http://127.0.0.1:18070 --model qwen35-0.8b \
    --system-name qwen08-base-raw --out submissions/mock/qwen08-base-raw/answers.json
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode harness --url http://127.0.0.1:18071 \
    --system-name qwen08-harness-v2-bm25 --out submissions/mock/qwen08-harness-v2-bm25/answers.json
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode harness --url http://127.0.0.1:18074 \
    --system-name qwen08-harness-v3-bm25 --out submissions/mock/qwen08-harness-v3-bm25/answers.json
  echo CHAINQ_MOCK_DONE
  cd devset/cke_full
  for C in raw bm25 v3; do
    for p in cke2024 cke2025 cke2026; do
      if [ $C = raw ]; then
        $PY run_paper.py $p.jsonl answers_q08_raw_$p.jsonl --mode raw --url http://127.0.0.1:18070 --system q08_raw --conc 4
      else
        P=18071; [ $C = v3 ] && P=18074
        $PY run_paper.py $p.jsonl answers_q08_${C}_$p.jsonl --mode harness --url http://127.0.0.1:$P --system q08_$C --conc 4
      fi
    done
  done
  echo CHAINQ_DONE
  ;;
qup)
  mkdir -p /scratch/mock/models logs
  [ -f $QWEN ] || cp /workspace/models/qwen35-0.8b/Qwen3.5-0.8B-Q8_0.gguf $QWEN
  nohup $LS -m $QWEN --host 127.0.0.1 --port 18070 -ngl 999 -c 32768 -np 4 -kvu -fa on --jinja     --alias qwen35-0.8b --chat-template-kwargs '{"enable_thinking":false}' --metrics --no-webui --cache-ram 0     > logs/llama-18070.log 2>&1 &
  echo $! > logs/llama-18070.pid
  wait_up http://127.0.0.1:18070
  qwen_harness 18071 q08bm25 "QTYPE_V2=1 RERANK=0 DENSE=0 CKE_MODE=0"
  qwen_harness 18074 q08v3bm25 "QTYPE_V2=1 RERANK=0 DENSE=0 CKE_MODE=1"
  ;;
chainQ2)
  $PY -m harness.exam_runner $EX --image-desc $IMG --mode harness --url http://127.0.0.1:18074     --system-name qwen08-harness-v3-bm25 --out submissions/mock/qwen08-harness-v3-bm25/answers.json
  echo CHAINQ_MOCK_DONE
  cd devset/cke_full
  for C in raw bm25 v3; do
    for p in cke2024 cke2025 cke2026; do
      if [ $C = raw ]; then
        $PY run_paper.py $p.jsonl answers_q08_raw_$p.jsonl --mode raw --url http://127.0.0.1:18070 --system q08_raw --conc 4
      else
        P=18071; [ $C = v3 ] && P=18074
        $PY run_paper.py $p.jsonl answers_q08_${C}_$p.jsonl --mode harness --url http://127.0.0.1:$P --system q08_$C --conc 4
      fi
    done
  done
  echo CHAINQ_DONE
  ;;
down)
  for f in logs/harness-b45v3.pid logs/harness-q08bm25.pid logs/harness-q08v3bm25.pid logs/llama-18050.pid \
    logs/rerank-18052.pid logs/llama-18070.pid; do kill "$(cat $f)" 2>/dev/null; done
  ;;
esac
