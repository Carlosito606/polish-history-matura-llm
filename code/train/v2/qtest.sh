#!/usr/bin/env bash
# Smoke test: Qwen3.5-0.8B LoRA (unsloth) 3 steps on sft_v1 -> export -> llama-server loads the adapter.
set -uo pipefail
source /scratch/v2/env.sh; source /scratch/v2/lib.sh
export RUNS_DIR=/scratch/v2/test_runs LORA_DIR=/scratch/v2/test_loras
mkdir -p $RUNS_DIR $LORA_DIR
cd $ROOT
$TPY train/train_lora.py --data $S/data/sft_v1_train.jsonl --limit 64 --eval-frac 0.1 --base Qwen/Qwen3.5-0.8B \
  --name qtest --r 16 --alpha 32 --max-steps 3 --max-seq-len 3072 --batch 4 --grad-accum 1 \
  --chat-template-kwargs '{"enable_thinking": false}' --gen-eval-n 6 --gen-eval-base > /scratch/v2/qtest_train.log 2>&1
echo "train exit $?"
bash train/export.sh --run qtest --base-gguf $S/models/qwen35-0.8b/Qwen3.5-0.8B-Q8_0.gguf > /scratch/v2/qtest_export.log 2>&1
echo "export exit $?"; grep -E "PASS|FAIL|rror" /scratch/v2/qtest_export.log | head -5
echo QTEST DONE
