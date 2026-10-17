#!/usr/bin/env bash
# Winner (Qwen3-8B) first; runner-up (Bielik-4.5B-v3) only if the winner's LoRA beats harness-v2 (pooled strict).
OD=/workspace/data/overnight
bash "$OD/run_model.sh" qwen3-8b Qwen/Qwen3-8B qwen3-8b/Qwen3-8B-Q4_K_M.gguf '{"enable_thinking": false}' 2816
if grep -q '^LORA_HELPS=1' "$OD/qwen3-8b.status"; then
  bash "$OD/run_model.sh" bielik-4.5b-v3 speakleash/Bielik-4.5B-v3.0-Instruct \
       bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf '' 3072
else
  echo "$(date -u +%H:%M:%S) runner-up skipped (LoRA did not help or qwen run failed)" >> "$OD/qwen3-8b.status"
fi
bash /workspace/wmt-matura/scripts/l40s_rerank.sh stop >> "$OD/driver.log" 2>&1
echo "$(date -u +%H:%M:%S) ALL DONE" > "$OD/ALL_DONE"
