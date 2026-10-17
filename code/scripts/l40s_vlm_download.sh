#!/bin/bash
# download vision candidates to /scratch/vlm/models/<name>/ ; HF_TOKEN from env.sh (never printed)
source /workspace/env.sh >/dev/null 2>&1
HF=/opt/conda/bin/hf
export HF_XET_CACHE=/scratch/vlm/.xet HF_HUB_DISABLE_XET=${HF_HUB_DISABLE_XET:-0}
cd /scratch/vlm/models
dl() { # name repo file...
  local name=$1 repo=$2; shift 2
  mkdir -p "$name"
  for f in "$@"; do
    [ -s "$name/$f" ] && [ ! -d "$name/.cache/huggingface/download/$f.incomplete" ] && { echo "skip $name $f"; continue; }
    echo "$(date +%T) $name $f"
    $HF download "$repo" "$f" --local-dir "$name" >/dev/null 2>>/scratch/vlm/logs/dl.err || echo "FAIL $name $f"
  done
}
dl qwen3vl-4b-q8   Qwen/Qwen3-VL-4B-Instruct-GGUF Qwen3VL-4B-Instruct-Q8_0.gguf mmproj-Qwen3VL-4B-Instruct-F16.gguf
dl gemma4-e4b-q5km unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-Q5_K_M.gguf mmproj-F16.gguf
dl gemma4-12b-qat  google/gemma-4-12B-it-qat-q4_0-gguf gemma-4-12b-it-qat-q4_0.gguf mmproj-gemma-4-12b-it-qat-q4_0.gguf
dl qwen35-9b-q5km  unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q5_K_M.gguf mmproj-F16.gguf
dl qwen3vl-8b-q6k  unsloth/Qwen3-VL-8B-Instruct-GGUF Qwen3-VL-8B-Instruct-Q6_K.gguf mmproj-F16.gguf
echo "$(date +%T) verifying sha256"
/opt/conda/bin/python - <<'PY'
import json, hashlib, os
man = json.load(open("/scratch/vlm/manifest.json"))
for name, e in man.items():
    for f, meta in e["files"].items():
        p = f"/scratch/vlm/models/{name}/{f}"
        if not os.path.exists(p): print("MISSING", name, f); continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 24), b""): h.update(b)
        ok = h.hexdigest() == meta["sha256"]
        print("OK" if ok else "BADSHA", name, f, os.path.getsize(p))
PY
echo "$(date +%T) DONE"
