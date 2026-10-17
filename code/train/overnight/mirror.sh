#!/usr/bin/env bash
# Mirror what the overnight run needs from NFS /workspace to local /scratch/ovl.
# /workspace (nfs4 via 127.0.0.1) intermittently returns EACCES (seen 01:36, 03:33, 04:35 UTC): it killed
# train_lora.py (PermissionError on train_log.jsonl), exec of venv pythons (exit 126) and the eval drivers.
set -u
S=/scratch/ovl
log() { echo "$(date -u +%H:%M:%S) $*"; }
retry() { local i; for i in 1 2 3 4 5 6 7 8; do "$@" && return 0; log "retry $i: $*"; sleep 30; done; return 1; }
mkdir -p $S/opt $S/venvs $S/models $S/logs $S/runs $S/loras $S/hf $S/home $S/data
retry cp -a /workspace/opt/uv-python /workspace/opt/llama /workspace/opt/glibc-2.39 /workspace/opt/llama.cpp-src $S/opt/
retry cp -a /workspace/venvs/wmt /workspace/venvs/convert $S/venvs/
PYB=$S/opt/uv-python/cpython-3.12.12-linux-x86_64-gnu/bin
# train venv: a shim reusing the shared site-packages already on /scratch (the shared venv is not modified)
mkdir -p $S/venvs/train/bin $S/venvs/train/lib/python3.12
ln -sfn /scratch/venvs/train/lib/python3.12/site-packages $S/venvs/train/lib/python3.12/site-packages
printf 'home = %s\nimplementation = CPython\nversion_info = 3.12.12\ninclude-system-site-packages = false\n' "$PYB" \
  > $S/venvs/train/pyvenv.cfg
for v in wmt convert train; do
  for b in python python3 python3.12; do ln -sfn $PYB/python3.12 $S/venvs/$v/bin/$b; done
  sed -i "s#^home = .*#home = $PYB#" $S/venvs/$v/pyvenv.cfg
done
retry cp -a /workspace/wmt-matura $S/
retry cp /workspace/data/sft_v1_train.jsonl $S/data/
retry cp /workspace/loras/final-qwen3-8b-r16-e2.gguf /workspace/loras/final-qwen3-8b-r16-e2.gguf.json $S/loras/
for m in qwen3-8b bielik-4.5b-v3 bge-reranker-v2-m3; do mkdir -p $S/models/$m; done
retry cp /workspace/models/SHA256SUMS $S/models/
retry cp /workspace/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf $S/models/qwen3-8b/
retry cp /workspace/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf $S/models/bielik-4.5b-v3/
retry cp /workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf $S/models/bge-reranker-v2-m3/
( cd $S/models && grep -E 'qwen3-8b/Qwen3-8B-Q4_K_M|bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0' SHA256SUMS | sha256sum -c ) \
  > $S/models/verify.txt 2>&1
log "sha256 check: $(tr '\n' ' ' < $S/models/verify.txt)"
# HF weights for the runner-up to local disk (token only for this download, never printed)
retry bash -c "source /workspace/env.sh >/dev/null 2>&1; HF_HOME=$S/hf HOME=$S/home $S/venvs/train/bin/python -c \
  \"from huggingface_hub import snapshot_download as s; print(s('speakleash/Bielik-4.5B-v3.0-Instruct'))\""
(cd $S/wmt-matura && $S/venvs/wmt/bin/python -c 'import harness, httpx; print("wmt venv ok")')
$S/venvs/train/bin/python -c 'import torch, peft, transformers; print("train venv ok", torch.__version__)'
$S/venvs/convert/bin/python -c 'import gguf, torch; print("convert venv ok")'
du -sh $S
log "MIRROR DONE"
