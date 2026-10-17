#!/usr/bin/env bash
# Export a PEFT LoRA adapter (train/train_lora.py output) for llama.cpp and check the 8 GB limit.
#
#   train/export.sh --run bielik11b-r16 --base-gguf bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf
#   train/export.sh --adapter /workspace/runs/x/adapter --base-gguf qwen3-4b-2507/Qwen3-4B-Instruct-2507-Q8_0.gguf \
#                   --name x --outtype q8_0 --merge
#
# 1. LoRA -> GGUF adapter: convert_lora_to_gguf.py (venv /workspace/venvs/convert, llama.cpp b11185 source)
#    -> /workspace/loras/<name>.gguf  (+ <name>.gguf.json manifest: sizes, sha256, base GGUF, run)
# 2. Size check: base GGUF + adapter <= 8.0 GB (decimal, 8,000,000,000 bytes). The base GGUF is only read.
# 3. --merge (optional): merge adapter into the bf16 HF base -> convert_hf_to_gguf (bf16) -> llama-quantize to the
#    base GGUF's quant type (read from general.file_type) -> /workspace/loras/merged/<name>.<QUANT>.gguf, size check.
#    Needs ~2x model size in RAM or a free GPU (MERGE_DEVICE=cuda|cpu, default cuda if >= model size free).
#    Official GGUFs may use an imatrix; pass --imatrix FILE to use one for the merged quant.
#
# Options:
#   --run NAME        adapter = $RUNS_DIR/NAME/adapter (RUNS_DIR default /workspace/runs); default --name = NAME
#   --adapter DIR     explicit adapter dir (adapter_config.json + adapter_model.safetensors)
#   --base-gguf PATH  registered base GGUF (absolute or relative to /workspace/models)   [required]
#   --base-hf REPO|DIR  HF base for config/merge [adapter_config.json base_model_name_or_path]
#   --name NAME       output name
#   --outtype T       adapter tensor type: f16 (default) | bf16 | f32 | q8_0
#   --merge           also build a merged + quantized GGUF
#   --merge-only      like --merge, but reuse an existing adapter GGUF + manifest (no re-conversion)
#   --quant TYPE      override quant type for --merge (default: same as base GGUF)
#   --imatrix FILE    imatrix for llama-quantize (--merge)
#   --limit-bytes N   [8000000000]
set -euo pipefail

RUNS_DIR=${RUNS_DIR:-/workspace/runs}
MODELS_DIR=${MODELS_DIR:-/workspace/models}
LORA_DIR=${LORA_DIR:-/workspace/loras}
LLAMA_DIR=${LLAMA_DIR:-/workspace/opt/llama/current}
LLAMA_SRC=${LLAMA_SRC:-/workspace/opt/llama.cpp-src}
CONVERT_PY=${CONVERT_PY:-/workspace/venvs/convert/bin/python}
TRAIN_PY=${TRAIN_PY:-/workspace/venvs/train/bin/python}
SCRATCH=${SCRATCH:-/scratch/export}
GLIBC_SHIM=${GLIBC_SHIM:-/workspace/opt/glibc-2.39/lib}
RUN="" ADAPTER="" BASE_GGUF="" BASE_HF="" NAME="" OUTTYPE=f16 MERGE=0 MERGE_ONLY=0 QUANT="" IMATRIX="" LIMIT=8000000000

while [ $# -gt 0 ]; do
  case "$1" in
    --run) RUN=$2; shift 2 ;;
    --adapter) ADAPTER=$2; shift 2 ;;
    --base-gguf) BASE_GGUF=$2; shift 2 ;;
    --base-hf) BASE_HF=$2; shift 2 ;;
    --name) NAME=$2; shift 2 ;;
    --outtype) OUTTYPE=$2; shift 2 ;;
    --merge) MERGE=1; shift ;;
    --merge-only) MERGE=1; MERGE_ONLY=1; shift ;;
    --quant) QUANT=$2; shift 2 ;;
    --imatrix) IMATRIX=$2; shift 2 ;;
    --limit-bytes) LIMIT=$2; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f /workspace/env.sh ] && source /workspace/env.sh   # HF_TOKEN for gated configs (never printed)
[ -n "$ADAPTER" ] || { [ -n "$RUN" ] || { echo "need --run or --adapter" >&2; exit 2; }; ADAPTER=$RUNS_DIR/$RUN/adapter; }
[ -f "$ADAPTER/adapter_config.json" ] || { echo "no adapter_config.json in $ADAPTER" >&2; exit 1; }
[ -n "$BASE_GGUF" ] || { echo "need --base-gguf" >&2; exit 2; }
case "$BASE_GGUF" in /*) ;; *) BASE_GGUF=$MODELS_DIR/$BASE_GGUF ;; esac
[ -f "$BASE_GGUF" ] || { echo "base GGUF not found: $BASE_GGUF" >&2; exit 1; }
NAME=${NAME:-${RUN:-$(basename "$(dirname "$ADAPTER")")}}
if [ -z "$BASE_HF" ]; then
  BASE_HF=$("$CONVERT_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_model_name_or_path"])' "$ADAPTER/adapter_config.json")
fi
mkdir -p "$LORA_DIR" "$SCRATCH"
LORA_OUT=$LORA_DIR/$NAME.gguf

# local dir with the base config (convert_lora_to_gguf only needs config.json; works offline from the HF cache)
resolve_hf() {  # repo|dir  allow_patterns(json list)
  if [ -d "$1" ]; then echo "$1"; return; fi
  "$CONVERT_PY" -c 'import sys, json
from huggingface_hub import snapshot_download
print(snapshot_download(sys.argv[1], allow_patterns=json.loads(sys.argv[2])))' "$1" "$2"
}
BASE_CFG_DIR=$(resolve_hf "$BASE_HF" '["*.json"]')

gguf_filetype() {  # path -> e.g. Q4_K_M
  PYTHONPATH=$LLAMA_SRC/gguf-py "$CONVERT_PY" - "$1" <<'EOF'
import sys
from gguf import GGUFReader, LlamaFileType
r = GGUFReader(sys.argv[1])
f = r.fields.get("general.file_type")
v = int(f.parts[f.data[0]][0]) if f else -1
try:
    print(LlamaFileType(v).name.replace("MOSTLY_", ""))
except ValueError:
    print(f"unknown({v})")
EOF
}
human() { awk -v b="$1" 'BEGIN{printf "%.3f GB (%.2f GiB)", b/1e9, b/1073741824}'; }

BASE_BYTES=$(stat -c %s "$BASE_GGUF")
BASE_TYPE=$(gguf_filetype "$BASE_GGUF")
echo "adapter   : $ADAPTER"
echo "base HF   : $BASE_HF  (config from $BASE_CFG_DIR)"
echo "base GGUF : $BASE_GGUF  [$BASE_TYPE, $(human "$BASE_BYTES")]"

# ---------------------------------------------------------------- 1. LoRA -> GGUF
if [ "$MERGE_ONLY" = 1 ] && [ -f "$LORA_OUT" ] && [ -f "$LORA_OUT.json" ]; then
  echo "LoRA GGUF : reusing $LORA_OUT (--merge-only)"
else
t0=$(date +%s)
"$CONVERT_PY" "$LLAMA_SRC/convert_lora_to_gguf.py" --base "$BASE_CFG_DIR" --outtype "$OUTTYPE" \
  --outfile "$LORA_OUT" "$ADAPTER" 2>&1 | grep -vE '^INFO:(lora-to-gguf|gguf\.gguf_writer):(blk|output|token_embd)' | tail -15
[ -f "$LORA_OUT" ] || { echo "convert_lora_to_gguf failed" >&2; exit 1; }
LORA_BYTES=$(stat -c %s "$LORA_OUT")
LORA_SHA=$(sha256sum "$LORA_OUT" | cut -d' ' -f1)
BASE_SHA=$(awk -v f="$(basename "$BASE_GGUF")" '$2 ~ f"$" {print $1}' "$MODELS_DIR/SHA256SUMS" 2>/dev/null | head -1)
TOTAL=$((BASE_BYTES + LORA_BYTES))
echo "LoRA GGUF : $LORA_OUT  [$OUTTYPE, $(human "$LORA_BYTES"), $(( $(date +%s) - t0 ))s]  sha256 $LORA_SHA"
if [ "$TOTAL" -le "$LIMIT" ]; then VERDICT=PASS; else VERDICT=FAIL; fi
echo "base+LoRA : $(human "$TOTAL")  limit $(human "$LIMIT")  -> $VERDICT"

"$CONVERT_PY" - "$LORA_OUT.json" <<EOF
import json, sys
json.dump({"lora_gguf": "$LORA_OUT", "lora_bytes": $LORA_BYTES, "lora_sha256": "$LORA_SHA", "outtype": "$OUTTYPE",
           "adapter_dir": "$ADAPTER", "base_hf": "$BASE_HF", "base_gguf": "$BASE_GGUF", "base_gguf_type": "$BASE_TYPE",
           "base_bytes": $BASE_BYTES, "base_sha256_registered": "$BASE_SHA", "total_bytes": $TOTAL,
           "limit_bytes": $LIMIT, "size_check": "$VERDICT"}, open(sys.argv[1], "w"), indent=1)
EOF
echo "manifest  : $LORA_OUT.json"
fi

# ---------------------------------------------------------------- 2. optional merged model
if [ "$MERGE" = 1 ]; then
  QUANT=${QUANT:-$BASE_TYPE}
  case "$QUANT" in unknown*|BF16|F16|ALL_F32) echo "cannot derive a quant type from base ($BASE_TYPE); pass --quant" >&2; exit 1 ;; esac
  BASE_FULL_DIR=$(resolve_hf "$BASE_HF" '["*.json", "*.safetensors", "*.model", "*.jinja", "*.txt", "*.tiktoken"]')
  MERGED=$SCRATCH/$NAME-merged-hf
  BF16_GGUF=$SCRATCH/$NAME-merged.bf16.gguf
  OUT_Q=$LORA_DIR/merged/$NAME.$QUANT.gguf
  mkdir -p "$LORA_DIR/merged"
  t0=$(date +%s)
  if [ -f "$BF16_GGUF" ] && [ "$BF16_GGUF" -nt "$ADAPTER/adapter_model.safetensors" ]; then
    echo "merge     : reusing $BF16_GGUF (newer than the adapter)"
  else
  rm -rf "$MERGED"
  echo "merge     : $ADAPTER + $BASE_FULL_DIR -> $MERGED"
  "$TRAIN_PY" - "$BASE_FULL_DIR" "$ADAPTER" "$MERGED" <<'EOF'
import os, shutil, sys, torch
from peft import PeftModel
from transformers import AutoModelForCausalLM
base, adapter, out = sys.argv[1:4]
dev = os.environ.get("MERGE_DEVICE")
if not dev:
    need = sum(os.path.getsize(os.path.join(base, f)) for f in os.listdir(base) if f.endswith(".safetensors"))
    dev = "cuda" if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > need * 1.1 else "cpu"
print("merge device:", dev)
m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map={"": dev})
m = PeftModel.from_pretrained(m, adapter).merge_and_unload()
m.save_pretrained(out, safe_serialization=True, max_shard_size="5GB")
for f in os.listdir(base):  # keep the base tokenizer / chat template files byte-identical
    if f.endswith((".model", ".jinja", ".tiktoken", ".txt")) or f.startswith(("tokenizer", "special_tokens", "generation_config", "chat_template", "added_tokens")):
        shutil.copy2(os.path.join(base, f), os.path.join(out, f))
print("merged ok")
EOF
  "$CONVERT_PY" "$LLAMA_SRC/convert_hf_to_gguf.py" "$MERGED" --outtype bf16 --outfile "$BF16_GGUF.tmp" 2>&1     | tr '
' '
' | grep -v 'it/s]' | tail -2
  mv "$BF16_GGUF.tmp" "$BF16_GGUF"
  rm -rf "$MERGED"
  fi
  QARGS=()
  [ -n "$IMATRIX" ] && QARGS+=(--imatrix "$IMATRIX")
  # the glibc-2.39 shim binaries need LD_LIBRARY_PATH here: libllama-common pulls system libcrypto, whose libm
  # lookup would otherwise resolve to the system glibc 2.35 libm (GLIBC_2.38 not found). Never set it globally.
  LD_LIBRARY_PATH=$GLIBC_SHIM:$LLAMA_DIR "$LLAMA_DIR/llama-quantize" "${QARGS[@]}" "$BF16_GGUF" "$OUT_Q.tmp" "$QUANT"     > "$SCRATCH/$NAME-quantize.log" 2>&1 || { tail -5 "$SCRATCH/$NAME-quantize.log" >&2; exit 1; }
  grep -E "model size|quant size" "$SCRATCH/$NAME-quantize.log" | sed 's/^/            /'
  mv "$OUT_Q.tmp" "$OUT_Q"
  rm -f "$BF16_GGUF"
  Q_BYTES=$(stat -c %s "$OUT_Q")
  if [ "$Q_BYTES" -le "$LIMIT" ]; then QV=PASS; else QV=FAIL; fi
  echo "merged    : $OUT_Q  [$QUANT, $(human "$Q_BYTES"), $(( $(date +%s) - t0 ))s] -> $QV (limit $(human "$LIMIT"))"
  echo "            sha256 $(sha256sum "$OUT_Q" | cut -d' ' -f1)"
  echo "            (a merged model is a NEW model file, not the registered base; the LoRA path keeps the base untouched)"
fi
