#!/usr/bin/env bash
# Fresh-session entrypoint for the v2 runs (after the 26.09 09:59 UTC session loss): restore /scratch/ovl from
# /workspace like train/overnight/mirror.sh (v2 data, KB index, bge-m3 dense index), then start train/v2/run_all.sh.
# Bielik-4.5B-v3 only (Qwen3.5-0.8B dropped, team decision).
# SFT v2 is persisted: /workspace/data/sft_v2{,_train}.jsonl (+ .stats.json); REBUILD=1 rebuilds it from data/src.
#   (laptop) scp -r train/v2 l40s:/workspace/wmt-matura/train/ && scp train/export.sh train/train_lora.py \
#              train/build_sft.py l40s:/workspace/wmt-matura/train/
#   optional fresher data: upload claude_verified/zpe_verified/cke_items to /workspace/data/src and pass REBUILD=1
#   ssh l40s 'mkdir -p /scratch/v2; [REBUILD=1] setsid nohup bash /workspace/wmt-matura/train/v2/launch_v2.sh \
#              > /scratch/v2/launch.out 2>&1 < /dev/null &'
# Progress: /scratch/v2/{launch.out,run.status,trainA.status,evalB.status}; results synced back to /workspace
# (loras, runs, devset/experiments.csv, data/v2_logs) after every milestone.
set -u
S=/scratch/ovl
V2=/scratch/v2
log() { echo "$(date -u +%H:%M:%S) $*"; }
retry() { local i; for i in 1 2 3 4 5 6 7 8; do "$@" && return 0; log "retry $i: $*"; sleep 30; done; return 1; }
mkdir -p $V2 $S/opt $S/venvs $S/models $S/logs $S/runs $S/loras $S/hf $S/home $S/data
tv_ok() { /scratch/venvs/train/bin/python -c 'import torch, peft, transformers, unsloth' >/dev/null 2>&1; }
for i in $(seq 1 40); do tv_ok && break; sleep 30; done      # Forgehand runs /workspace/setup.sh at session start
tv_ok || { log "train venv missing -> setup.sh"; bash /workspace/setup.sh > $V2/setup.log 2>&1; }
tv_ok || { log "FAILED: /scratch/venvs/train not usable"; exit 1; }
retry cp -a /workspace/opt/uv-python /workspace/opt/llama /workspace/opt/glibc-2.39 /workspace/opt/llama.cpp-src $S/opt/
retry cp -a /workspace/venvs/wmt /workspace/venvs/convert $S/venvs/
PYB=$S/opt/uv-python/cpython-3.12.12-linux-x86_64-gnu/bin
mkdir -p $S/venvs/train/bin $S/venvs/train/lib/python3.12
ln -sfn /scratch/venvs/train/lib/python3.12/site-packages $S/venvs/train/lib/python3.12/site-packages
printf 'home = %s\nimplementation = CPython\nversion_info = 3.12.12\ninclude-system-site-packages = false\n' "$PYB" \
  > $S/venvs/train/pyvenv.cfg
for v in wmt convert train; do
  for b in python python3 python3.12; do ln -sfn $PYB/python3.12 $S/venvs/$v/bin/$b; done
  sed -i "s#^home = .*#home = $PYB#" $S/venvs/$v/pyvenv.cfg
done
retry cp -a /workspace/wmt-matura $S/
retry cp /workspace/data/sft_v2_train.jsonl /workspace/data/sft_v2.jsonl.stats.json $S/data/
retry cp /workspace/loras/final-bielik-4.5b-v3-r16-e2.gguf /workspace/loras/final-bielik-4.5b-v3-r16-e2.gguf.json $S/loras/
for m in bielik-4.5b-v3 bge-reranker-v2-m3 bge-m3; do mkdir -p $S/models/$m; done
retry cp /workspace/models/SHA256SUMS $S/models/
retry cp /workspace/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf $S/models/bielik-4.5b-v3/
retry cp /workspace/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf $S/models/bge-reranker-v2-m3/
retry cp /workspace/models/bge-m3/gguf/bge-m3-Q8_0.gguf $S/models/bge-m3/
( cd $S/models && grep -E 'bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0' SHA256SUMS \
  | sha256sum -c ) > $S/models/verify.txt 2>&1
log "sha256 check: $(tr '\n' ' ' < $S/models/verify.txt)"
[ -d /scratch/kb_index ] || retry cp -a /workspace/kb_data/index /scratch/kb_index
( mkdir -p /scratch/dense_idx; D=/workspace/kb_data/dense/bge-m3      # DENSE=1 stage (hours later), in background
  for f in meta.json ids.npy index.faiss vectors.f16.npy; do retry cp $D/$f /scratch/dense_idx/ || exit 1; done
  cmp -s $D/ids.npy /scratch/dense_idx/ids.npy && [ "$(stat -c %s $D/index.faiss)" = "$(stat -c %s /scratch/dense_idx/index.faiss)" ]     && touch $V2/dense.copied && log "dense index copied" ) >> $V2/dense_copy.log 2>&1 &
for repo in speakleash/Bielik-4.5B-v3.0-Instruct; do   # token only for the download, never printed
  retry bash -c "source /workspace/env.sh >/dev/null 2>&1; HF_HOME=$S/hf HOME=$S/home $S/venvs/train/bin/python -c \
    \"from huggingface_hub import snapshot_download as s; print(s('$repo'))\""
done
$S/venvs/wmt/bin/python -c 'import faiss' 2>/dev/null || retry uv pip install -q -p $S/venvs/wmt/bin/python faiss-cpu
(cd $S/wmt-matura && $S/venvs/wmt/bin/python -c 'import harness, httpx, faiss; print("wmt venv ok, faiss", faiss.__version__)')
$S/venvs/convert/bin/python -c 'import gguf, torch; print("convert venv ok")'
cp $S/wmt-matura/train/v2/*.sh $S/wmt-matura/train/v2/*.py $V2/
if [ "${REBUILD:-0}" = 1 ]; then   # rebuild sft_v2 from the current /workspace/data/src (upload fresh data first)
  log "REBUILD=1 -> build.sh"; bash $V2/build.sh > $V2/build.out 2>&1
  grep -q "BUILD DONE" $V2/build.status || { log "FAILED: build"; exit 1; }
else
  echo "$(date -u +%H:%M:%S) BUILD DONE (sft_v2 restored from /workspace/data)" >> $V2/build.status
fi
log "MIRROR DONE -> run_all.sh"
exec bash $V2/run_all.sh > $V2/run_all.out 2>&1 < /dev/null
