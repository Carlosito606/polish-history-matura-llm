#!/usr/bin/env bash
# Forgehand session-start hook for the wmt-matura L40S session. Installed as /workspace/setup.sh
# (repo copy: scripts/forgehand_setup.sh). Idempotent and fast: every step checks first and installs only
# what is missing. Persistent state lives on /workspace. /scratch (local NVMe) is wiped when the session
# stops, so after a restart the training venv /scratch/venvs/train is reinstalled from
# train/requirements-train.txt (about 50 s with an empty uv cache).
#
#   bash /workspace/setup.sh                # full check/restore (Forgehand runs this at session start)
#   bash /workspace/setup.sh verify-sha     # sha256 of every GGUF vs /workspace/models/SHA256SUMS (~2.5 min)
#   bash /workspace/setup.sh fetch-models   # download missing GGUFs (setup.sh starts this in tmux if needed)
#   bash /workspace/setup.sh build-kb       # rebuild the KB into /workspace/kb_data (tmux if needed, ~25 min)
#   touch /workspace/.serve_on_start        # opt-in: also start llama-server + harness after setup
#                                           # (the file may hold VAR=value lines: MODEL_FILE=..., LORA_FILE=...)
# Log: /workspace/logs/setup.log.  Shell env for interactive work: source /workspace/env.sh
set -uo pipefail

W=/workspace
REPO=$W/wmt-matura
LOGS=$W/logs
OPT=$W/opt
LLAMA_TAG=b11185
LLAMA_CUDA=13.4
LLAMA_DIR=$OPT/llama/$LLAMA_TAG-cuda-$LLAMA_CUDA
GLIBC=$OPT/glibc-2.39/lib
SRC=$OPT/llama.cpp-src
MODELS=$W/models
KB=$W/kb_data
TV=/scratch/venvs/train
DUMP=plwiki-20251229-cirrussearch-content.json.gz
SELF=$(readlink -f "$0")

export UV_CACHE_DIR=/scratch/uv-cache UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=$OPT/uv-python
export HF_XET_HIGH_PERFORMANCE=1 HF_HUB_DISABLE_TELEMETRY=1
export PATH=/opt/conda/bin:$PATH
mkdir -p "$LOGS" /scratch/dl

log() { echo "[$(date +%T)] $*"; }

# dir repo file (same directory names as on the Mac)
MODEL_LIST='bielik-11b-v3 speakleash/Bielik-11B-v3.0-Instruct-GGUF Bielik-11B-v3.0-Instruct.Q4_K_M.gguf
gemma-4-12b ggml-org/gemma-4-12B-it-GGUF gemma-4-12B-it-Q4_0.gguf
qwen3.5-9b unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf
qwen3-8b Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf
qwen3-4b-2507 unsloth/Qwen3-4B-Instruct-2507-GGUF Qwen3-4B-Instruct-2507-Q8_0.gguf
bielik-4.5b-v3 speakleash/Bielik-4.5B-v3.0-Instruct-GGUF Bielik-4.5B-v3.0-Instruct.Q8_0.gguf
bielik-minitron-7b-v3 speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf'

hf_token() { [ -r $W/.secrets/hf_token ] && HF_TOKEN=$(cat $W/.secrets/hf_token) && export HF_TOKEN; return 0; }

# ---------------------------------------------------------------------------------------------- subcommands
fetch_models() {
  hf_token
  local dir repo file
  while read -r dir repo file; do
    [ -z "$dir" ] && continue
    if [ -s "$MODELS/$dir/$file" ] && [ ! -e "$MODELS/$dir/.cache/huggingface/download/$file.incomplete" ]; then
      echo "have $dir/$file"; continue
    fi
    log "get $repo $file -> $MODELS/$dir"
    hf download "$repo" "$file" --local-dir "$MODELS/$dir" || echo "FAILED $repo $file"
  done <<< "$MODEL_LIST"
  log MODELS_DONE
}

verify_sha() {
  [ -f "$MODELS/SHA256SUMS" ] || { echo "no $MODELS/SHA256SUMS"; return 1; }
  (cd "$MODELS" && sha256sum -c SHA256SUMS)
}

build_kb() {
  # Same steps as kb/run_all.sh (Mac), on fast /scratch with --workers 4, then persisted to /workspace/kb_data.
  set -e
  local S=/scratch/kb_build
  source $W/venvs/wmt/bin/activate
  cd "$REPO"
  if [ ! -f "$S/raw/$DUMP" ]; then
    if [ -f "$KB/raw/$DUMP" ]; then mkdir -p "$S/raw" && cp "$KB/raw/$DUMP" "$S/raw/"
    else bash kb/download_dump.sh "$S/raw" 16; fi
  fi
  log chunks; rm -rf "$S/chunks"
  python -m kb.build_chunks --dump "$S/raw/$DUMP" --out "$S/chunks" --workers 4 --batch 2000
  log index_mini
  python -m kb.build_index --chunks "$S/chunks" --out "$S/index_mini" --target-chunks 40000 --max-chunks-per-article 5 --workers 4
  log index
  python -m kb.build_index --chunks "$S/chunks" --out "$S/index" --workers 4
  log "persist to $KB"; mkdir -p "$KB/raw"
  local d
  for d in index index_mini chunks; do
    rm -rf "$KB/$d.tmp"; cp -r "$S/$d" "$KB/$d.tmp"; rm -rf "$KB/$d"; mv "$KB/$d.tmp" "$KB/$d"
  done
  [ -f "$KB/raw/$DUMP" ] || { cp "$S/raw/$DUMP" "$KB/raw/$DUMP.tmp" && mv "$KB/raw/$DUMP.tmp" "$KB/raw/$DUMP"; }
  log KB_BUILD_DONE
}

in_tmux() {  # session-name subcommand
  if tmux has-session -t "$1" 2>/dev/null; then echo "tmux session $1 already running"; return 0; fi
  tmux new-session -d -s "$1" "bash '$SELF' $2 >> '$LOGS/$1.log' 2>&1"
}

case "${1:-all}" in
  fetch-models) fetch_models; exit $? ;;
  verify-sha)   verify_sha; exit $? ;;
  build-kb)     build_kb; exit $? ;;
  all) ;;
  *) echo "usage: $0 [all|fetch-models|verify-sha|build-kb]" >&2; exit 2 ;;
esac

# ---------------------------------------------------------------------------------------------- main
exec > >(tee -a "$LOGS/setup.log") 2>&1
exec 9>/tmp/wmt-setup.lock
flock -n 9 || { echo "setup.sh already running"; exit 0; }
T0=$(date +%s)
STATUS=()
ok()   { STATUS+=("OK    $*"); }
bad()  { STATUS+=("FAIL  $*"); }
bgd()  { STATUS+=("BG    $*"); }
log "setup.sh start on $(hostname)"

# --- base tools
apt_need=()
for t in tmux zstd; do command -v $t >/dev/null || apt_need+=($t); done
if [ ${#apt_need[@]} -gt 0 ]; then
  log "apt install ${apt_need[*]}"
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${apt_need[@]}" >/dev/null
fi
command -v uv >/dev/null || python3 -m pip install -q uv
command -v hf >/dev/null || python3 -m pip install -q -U huggingface_hub
command -v patchelf >/dev/null || python3 -m pip install -q patchelf
if nvidia-smi >/dev/null 2>&1; then
  ok "gpu: $(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)"
else bad "gpu: nvidia-smi failed"; fi

# --- glibc 2.39 shim + llama.cpp release binaries
# The official Linux release is built on Ubuntu 24.04 (glibc 2.39, libstdc++ 14); this session runs Ubuntu 22.04
# (glibc 2.35). Fix: libc6/libstdc++6/libgcc-s1/libgomp1 from Ubuntu noble extracted to $GLIBC, and every ELF
# in the release patched with patchelf (interpreter -> $GLIBC/ld-linux-x86-64.so.2, RUNPATH -> $ORIGIN:$GLIBC).
install_glibc() {
  local debs=$OPT/debs p fn idx=/scratch/dl/noble-updates-Packages
  mkdir -p "$debs"
  if ! ls "$debs"/libc6_2.39*.deb >/dev/null 2>&1; then
    curl -fsSL http://archive.ubuntu.com/ubuntu/dists/noble-updates/main/binary-amd64/Packages.gz | gunzip > "$idx" || return 1
    for p in libc6 libgcc-s1 libgomp1 libstdc++6; do
      fn=$(awk -v p="$p" '$1=="Package:"{cur=$2} cur==p && $1=="Filename:"{print $2; exit}' "$idx")
      [ -n "$fn" ] || { echo "package $p not in noble-updates index"; return 1; }
      curl -fsSL -o "$debs/$(basename "$fn")" "http://archive.ubuntu.com/ubuntu/$fn" || return 1
    done
  fi
  rm -rf /scratch/dl/gx; mkdir -p /scratch/dl/gx "$GLIBC"
  for p in "$debs"/*.deb; do dpkg-deb -x "$p" /scratch/dl/gx || return 1; done
  cp -a /scratch/dl/gx/usr/lib/x86_64-linux-gnu/. "$GLIBC/"
}

install_llama() {
  [ -x "$GLIBC/ld-linux-x86-64.so.2" ] && [ -f "$GLIBC/libstdc++.so.6" ] || install_glibc || return 1
  local base=https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG f
  local a=llama-$LLAMA_TAG-bin-ubuntu-cuda-$LLAMA_CUDA-x64.tar.gz
  local b=cudart-llama-$LLAMA_TAG-bin-ubuntu-cuda-$LLAMA_CUDA-x64.tar.gz
  for f in $a $b; do
    if [ ! -s /scratch/dl/$f ]; then
      curl -fL --retry 3 -o /scratch/dl/$f.part $base/$f || return 1
      mv /scratch/dl/$f.part /scratch/dl/$f
    fi
  done
  local tmp=/scratch/dl/llama-x new=$LLAMA_DIR.new
  rm -rf $tmp $new; mkdir -p $tmp $new
  tar -C $tmp -xzf /scratch/dl/$a && tar -C $tmp -xzf /scratch/dl/$b || return 1
  cp -a $tmp/llama-$LLAMA_TAG/. $new/ && cp -a $tmp/cudart-llama-$LLAMA_TAG-bin-ubuntu-cuda-$LLAMA_CUDA-x64/. $new/ || return 1
  for f in $new/*; do
    [ -L "$f" ] || [ ! -f "$f" ] && continue
    [ "$(head -c4 "$f" | tail -c3)" = ELF ] || continue
    if patchelf --print-interpreter "$f" >/dev/null 2>&1; then
      patchelf --set-interpreter "$GLIBC/ld-linux-x86-64.so.2" "$f" || return 1
    fi
    patchelf --set-rpath "\$ORIGIN:$GLIBC" "$f" || return 1
  done
  rm -rf $LLAMA_DIR && mv $new $LLAMA_DIR && ln -sfn "$(basename $LLAMA_DIR)" $OPT/llama/current
}

llama_ok() { "$OPT/llama/current/llama-server" --version 2>&1 | grep -q "build ${LLAMA_TAG#b}"; }
if llama_ok; then ok "llama.cpp $LLAMA_TAG CUDA $LLAMA_CUDA ($OPT/llama/current)"
else
  log "installing llama.cpp $LLAMA_TAG CUDA $LLAMA_CUDA"
  if install_llama && llama_ok; then ok "llama.cpp $LLAMA_TAG installed"; else bad "llama.cpp $LLAMA_TAG install"; fi
fi

# --- llama.cpp source at the same tag (convert_lora_to_gguf.py, convert_hf_to_gguf.py, gguf-py)
if [ -f $SRC/convert_lora_to_gguf.py ] && [ "$(git -C $SRC describe --tags 2>/dev/null)" = "$LLAMA_TAG" ]; then
  ok "llama.cpp source $LLAMA_TAG ($SRC)"
else
  log "cloning llama.cpp $LLAMA_TAG"
  rm -rf /scratch/llama.cpp-src
  if git clone -q --depth 1 --branch $LLAMA_TAG https://github.com/ggml-org/llama.cpp /scratch/llama.cpp-src \
     && rm -rf $SRC && cp -a /scratch/llama.cpp-src $SRC; then ok "llama.cpp source cloned"; else bad "llama.cpp source clone"; fi
fi

# --- Python venvs (uv managed CPython 3.12 in $OPT/uv-python)
mkvenv() {  # dir requirements-file [extra uv pip args...]
  local d=$1 r=$2; shift 2
  [ -f "$r" ] || { echo "missing $r"; return 1; }
  [ -x "$d/bin/python" ] || uv venv -q --managed-python -p 3.12 "$d" || return 1
  uv pip install -q -p "$d/bin/python" "$@" -r "$r"
}
venv_step() {  # name dir import-check requirements-file [extra uv pip args...]
  local name=$1 d=$2 chk=$3; shift 3
  if "$d/bin/python" -c "$chk" >/dev/null 2>&1; then ok "venv $name ($d)"; return 0; fi
  log "installing venv $name -> $d"
  if mkvenv "$d" "$@" && "$d/bin/python" -c "$chk" >/dev/null 2>&1; then ok "venv $name installed"; else bad "venv $name"; fi
}
# checks read package metadata (plus one cheap import) instead of importing torch/transformers from NFS
venv_step wmt $W/venvs/wmt \
  "import importlib.metadata as m; [m.version(p) for p in ('fastapi','uvicorn','httpx','rapidfuzz','orjson','regex','pyarrow','pandas')]; import numpy" \
  $REPO/train/requirements-wmt.txt
venv_step convert $W/venvs/convert \
  "import importlib.metadata as m; [m.version(p) for p in ('torch','transformers','sentencepiece','safetensors')]; import gguf" \
  $REPO/train/requirements-convert.txt --index-strategy unsafe-best-match
# training venv on local NVMe (NFS is too slow for tens of thousands of small files); /workspace/venvs/train -> it
if [ ! -L $W/venvs/train ]; then
  [ -e $W/venvs/train ] && mv $W/venvs/train $W/venvs/.trash-train-$(date +%s)
  ln -sfn $TV $W/venvs/train
fi
mkdir -p /scratch/venvs
venv_step train $TV \
  "import importlib.metadata as m; [m.version(p) for p in ('torch','transformers','peft','trl','accelerate','datasets','bitsandbytes','unsloth')]; import torch; assert torch.cuda.is_available()" \
  $REPO/train/requirements-train.txt

# --- GGUF models (persistent on /workspace; background download if any is missing)
missing=0
while read -r dir repo file; do [ -s "$MODELS/$dir/$file" ] || missing=$((missing + 1)); done <<< "$MODEL_LIST"
if [ $missing -eq 0 ]; then ok "models: 7/7 GGUF in $MODELS (verify: bash $SELF verify-sha)"
else in_tmux fetch_models fetch-models; bgd "models: $missing missing -> tmux fetch_models, log $LOGS/fetch_models.log"; fi

# --- KB (BM25 index over plwiki; persistent on /workspace)
if [ -f $KB/index/tokenizer.json ] && [ -f $KB/index/store.bin ]; then
  if (cd $REPO && $W/venvs/wmt/bin/python -c "from kb.search import KB; assert KB('$KB/index').search('pokój w Oliwie 1660', k=1)") >/dev/null 2>&1
  then ok "kb: $KB/index"; else bad "kb: $KB/index present but search failed"; fi
else in_tmux build_kb build-kb; bgd "kb: index missing -> tmux build_kb, log $LOGS/build_kb.log"; fi

# --- shell env for interactive work
cat > $W/env.sh <<'EOF'
# source /workspace/env.sh   (written by /workspace/setup.sh)
export UV_CACHE_DIR=/scratch/uv-cache UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/workspace/opt/uv-python
export HF_XET_HIGH_PERFORMANCE=1 HF_HUB_DISABLE_TELEMETRY=1
[ -r /workspace/.secrets/hf_token ] && export HF_TOKEN="$(cat /workspace/.secrets/hf_token)"
export KB_INDEX_DIR=/workspace/kb_data/index LLAMA_CPP_SRC=/workspace/opt/llama.cpp-src
export PATH=/workspace/opt/llama/current:/opt/conda/bin:$PATH
EOF

# --- optional: start serving
if [ -f $W/.serve_on_start ]; then
  log "starting llama-server + harness (.serve_on_start)"
  if (set -a; . $W/.serve_on_start; set +a; bash $REPO/scripts/l40s_serve.sh start); then ok "serving started"; else bad "serving start"; fi
fi

log "summary ($(( $(date +%s) - T0 ))s):"
printf '  %s\n' "${STATUS[@]}"
exit 0
