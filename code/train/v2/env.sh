# Common env for the v2 runs (26.09): everything from local /scratch/ovl (NFS /workspace is flaky, see overnight report).
S=/scratch/ovl
V2=/scratch/v2
ROOT=$S/wmt-matura
PY=$S/venvs/wmt/bin/python
TPY=$S/venvs/train/bin/python
export HOME=$S/home HF_HOME=$S/hf HF_HUB_OFFLINE=1 RUNS_DIR=$S/runs LORA_DIR=$S/loras MODELS_DIR=$S/models \
       LLAMA_DIR=$S/opt/llama/current LLAMA_SRC=$S/opt/llama.cpp-src CONVERT_PY=$S/venvs/convert/bin/python \
       TRAIN_PY=$TPY GLIBC_SHIM=$S/opt/glibc-2.39/lib VENV=$S/venvs/wmt LOGS=$S/logs ROOT \
       MODEL=$S/models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf KB_INDEX_DIR=/scratch/kb_index \
       CSV=$ROOT/devset/experiments.csv SCRATCH=/scratch/export
DENSE_DIR=/scratch/dense_idx                      # index.faiss + ids.npy + meta.json + vectors.f16.npy (mmap) from /workspace/kb_data/dense/bge-m3
EMBED_GGUF=$S/models/bge-m3/bge-m3-Q8_0.gguf
DEVS="tourney160 dev-a dev-b dev-c dev-f dev-g dev-h cke-2023 cke-more"
say() { echo "$(date -u +%H:%M:%S) $*" >> "$V2/${KEY:-v2}.status"; }
rerank_up() { curl -sf -m 5 http://127.0.0.1:18092/health >/dev/null || (cd "$ROOT" && bash scripts/l40s_rerank.sh start >> "$V2/serve.log" 2>&1); }
