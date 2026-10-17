# L40S session (Forgehand): setup, serving, training

This file describes the GPU box used for evaluation and training. It is not the exam machine.

- Access: `ssh -o BatchMode=yes l40s` (root). After a restart the IP may change: `fh session ls --json`, then update `Host l40s` in `~/.ssh/config`.
- Hardware: 1x NVIDIA L40S 46 GB, 4 vCPU, 30 GB RAM, driver 595.91.07, Ubuntu 22.04 (glibc 2.35), no docker.
- Idle timeout is 240 min. Run long jobs in `tmux` or `nohup` and write logs to `/workspace/logs`.

## Storage

| path | persistent | contents |
|---|---|---|
| `/workspace` | yes (network FS, **slow for small files**, fine for big ones) | repo, models, KB, venvs `wmt`/`convert`, llama.cpp, logs |
| `/team` | yes | (unused so far) |
| `/scratch` | **no**, wiped on stop (217 GB local NVMe) | training venv, uv cache, KB build scratch, downloads |
| `/` | no | 139 GB free |

`HOME=/workspace/.home`, so the HF cache (`~/.cache/huggingface`) is persistent.

| what | where |
|---|---|
| repo | `/workspace/wmt-matura` (tar-over-ssh copy of the laptop repo; not a git remote) |
| llama.cpp b11185 CUDA 13.4 release | `/workspace/opt/llama/current` -> `b11185-cuda-13.4` |
| glibc 2.39 shim for it | `/workspace/opt/glibc-2.39/lib` (debs cached in `/workspace/opt/debs`) |
| llama.cpp source at tag b11185 | `/workspace/opt/llama.cpp-src` (`convert_lora_to_gguf.py`, `convert_hf_to_gguf.py`, `gguf-py`) |
| harness + KB venv | `/workspace/venvs/wmt` (`train/requirements-wmt.txt`) |
| GGUF conversion venv | `/workspace/venvs/convert` (`train/requirements-convert.txt`) |
| training venv | `/scratch/venvs/train` (symlink `/workspace/venvs/train`; `train/requirements-train.txt`) |
| GGUF models | `/workspace/models/<dir>/`, checksums in `/workspace/models/SHA256SUMS` |
| KB | `/workspace/kb_data/{index,index_mini,chunks,raw}` |
| HF token | `/workspace/.secrets/hf_token` (mode 600; never print it) |
| logs, pid files | `/workspace/logs` |

## After a session restart: `/workspace/setup.sh`

Forgehand runs `/workspace/setup.sh` at session start. The repo copy is `scripts/forgehand_setup.sh`; after editing it, copy it to `/workspace/setup.sh`.
The script is idempotent. Each step checks its target and installs only what is missing. It never fails the session start: every step prints `OK`, `FAIL` or `BG`.

1. Base tools: tmux and zstd (apt), plus uv, hf and patchelf (pip).
2. llama.cpp b11185 CUDA 13.4 release binaries. If missing, it downloads them from GitHub, installs the glibc shim and patchelfs them (see below).
3. llama.cpp source at b11185. If missing, it runs a shallow clone.
4. The `wmt`, `convert` and `train` venvs, from `train/requirements-*.txt`. The checks read package metadata, so they are fast even on the network FS.
   The training venv lives on `/scratch`, so it is reinstalled after every restart. This takes about 50 s with an empty uv cache.
5. GGUF models. If any is missing, `setup.sh fetch-models` starts in tmux `fetch_models`.
6. KB. The index gets a smoke query. If the index is missing, `setup.sh build-kb` starts in tmux `build_kb` (about 25 min).
7. Writes `/workspace/env.sh`: uv and HF env vars, `HF_TOKEN` read from the secrets file, `KB_INDEX_DIR`, and llama.cpp on `PATH`. Use it with `source /workspace/env.sh`.
8. Optional autostart. If `/workspace/.serve_on_start` exists, the script sources it (`VAR=value` lines such as `MODEL_FILE=`, `LORA_FILE=`) and runs `scripts/l40s_serve.sh start`.
   The file is off by default, so a fresh session keeps the GPU free for training.

Other entry points: `bash /workspace/setup.sh verify-sha` (sha256 of all GGUFs, about 2.5 min), `fetch-models` and `build-kb`. The log is `/workspace/logs/setup.log`.
A no-op run takes about 5 s. A restore test ran on 2026-09-25 with `/scratch/venvs/train` and the uv cache deleted:
the train venv was reinstalled from PyPI in 48 s, the whole run took 52 s, the freeze was identical and the training smoke test passed.

### Why a glibc shim

The official `llama-b11185-bin-ubuntu-cuda-13.4-x64` release is built on Ubuntu 24.04 (glibc 2.39, libstdc++ 14), but the session runs Ubuntu 22.04.
The fix leaves the system alone:
- `libc6`, `libstdc++6`, `libgcc-s1` and `libgomp1` from Ubuntu noble are extracted into `/workspace/opt/glibc-2.39/lib`.
- Every ELF in the release is patched with patchelf: the interpreter becomes `/workspace/opt/glibc-2.39/lib/ld-linux-x86-64.so.2` and RUNPATH becomes `$ORIGIN:/workspace/opt/glibc-2.39/lib`.

The CUDA 13.4 build runs on driver 595.91, so the 12.8 fallback was not needed. `llama-server --version` reports build 11185 (commit 27b20ba8b).

## Serving: `scripts/l40s_serve.sh`

```bash
cd /workspace/wmt-matura
bash scripts/l40s_serve.sh start     # llama-server 127.0.0.1:18080 (CUDA, -ngl 999 -c 16384 -np 8 -fa on) + harness 127.0.0.1:18000
bash scripts/l40s_serve.sh status    # health of both, GPU memory
bash scripts/l40s_serve.sh stop

MODEL_FILE=qwen3-8b/Qwen3-8B-Q4_K_M.gguf CHAT_TEMPLATE_KWARGS='{"enable_thinking":false}' bash scripts/l40s_serve.sh restart
LORA_FILE=/workspace/loras/x.gguf LORA_SCALE=1.0 BASE_LLM_BASE_URL=http://127.0.0.1:18081/v1 bash scripts/l40s_serve.sh restart
ONLY=llm LLM_PORT=18081 bash scripts/l40s_serve.sh start   # a separate untouched base server (repo rule: base benchmark without LoRA)
```

`MODEL_FILE` and `LORA_FILE` can be absolute paths or paths relative to `/workspace/models`. Defaults: Bielik 11B v3 Q4_K_M, KB `/workspace/kb_data/index`.
Logs and pid files are in `/workspace/logs/{llama,harness}-<port>.{log,pid}`. A pid only counts if its command line matches, so stale pid files left from a previous session are ignored.
Evaluate with the `wmt` venv:

```bash
/workspace/venvs/wmt/bin/python devset/eval.py --endpoint answer --files devset/smoke.jsonl --workers 8 --label l40s-harness-kb-<model>
/workspace/venvs/wmt/bin/python devset/eval.py --endpoint openai --url http://127.0.0.1:18080/v1 --model bielik-11b-v3 \
    --files devset/smoke.jsonl --workers 8 --label l40s-base-raw-<model>
```

Eval rows are appended to the L40S copy of `devset/experiments.csv`. That file is not synced back automatically.

### Measured (2026-09-25, Bielik-11B-v3.0-Instruct Q4_K_M, llama.cpp b11185 CUDA)

| run | smoke.jsonl (51 q, 53 pts) | throughput | latency avg / p50 / p90 |
|---|---|---|---|
| raw base (`openai` endpoint, 8 workers) | extract 0.471-0.510, 25-27/53 pts (2 runs) | 112-136 q/min | 3.3-4.0 / 2.6-3.1 / 6.6-8.7 s |
| harness + full KB (`answer`, 8 workers) | strict 0.961, **51/53 pts** | **68.5 q/min** | 6.97 / 6.27 / 11.23 s |

`llama-bench` on a single stream gives pp512 6.1k tok/s, pp4096 6.4k tok/s and tg128 90.7 tok/s.
With 8 parallel slots, decode runs at about 42-57 tok/s per slot. The server uses 10.2 GB of VRAM (model 6.3 GiB + 16k unified KV).

## Models (`/workspace/models`, all ≤ 8 GB; sha256 = HF LFS oid, verified)

| dir | file | bytes | sha256 |
|---|---|---|---|
| bielik-11b-v3 | Bielik-11B-v3.0-Instruct.Q4_K_M.gguf | 6724051584 | c16841621efe93c7c8ebf1b374709a96276f3741e649f83ed90131a7b5ad23a8 |
| gemma-4-12b | gemma-4-12B-it-Q4_0.gguf | 7219673216 | 3712b9bd32cae83a22f67ee7a4466d8d7a4f21646ac8a07d19bf9418e8767a70 |
| qwen3.5-9b | Qwen3.5-9B-Q4_K_M.gguf | 5680522464 | 03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8 |
| qwen3-8b | Qwen3-8B-Q4_K_M.gguf | 5027783488 | d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785 |
| qwen3-4b-2507 | Qwen3-4B-Instruct-2507-Q8_0.gguf | 4280405600 | 391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068 |
| bielik-4.5b-v3 | Bielik-4.5B-v3.0-Instruct.Q8_0.gguf | 5061215424 | 562f2291de257890adf2b4a914da8b194affe6a7a838a6b7ef3d342f306c1b7f |
| bielik-minitron-7b-v3 | minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf | 4501556256 | 0c1475426645924970b9ed1383df1ce89c47b991e7b78ce9a12d3fde94455b16 |

Source repos: speakleash/Bielik-11B-v3.0-Instruct-GGUF, ggml-org/gemma-4-12B-it-GGUF, unsloth/Qwen3.5-9B-GGUF, Qwen/Qwen3-8B-GGUF,
unsloth/Qwen3-4B-Instruct-2507-GGUF, speakleash/Bielik-4.5B-v3.0-Instruct-GGUF, speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF.

### HF safetensors repos (for training)

| repo | gated | our token (`/workspace/.secrets/hf_token`) |
|---|---|---|
| speakleash/Bielik-11B-v3.0-Instruct | yes (auto-approve) | access OK |
| speakleash/Bielik-4.5B-v3.0-Instruct | yes (auto-approve) | access OK |
| speakleash/Bielik-Minitron-7B-v3.0-Instruct | yes (auto-approve) | access OK |
| google/gemma-4-12B-it | no | OK |
| Qwen/Qwen3.5-9B, Qwen/Qwen3-8B, Qwen/Qwen3-4B-Instruct-2507 | no | OK |

## KB

The KB was built with the repo scripts, the same steps as `kb/run_all.sh`. `setup.sh build-kb` runs them on `/scratch` with `--workers 4` and then copies the results to `/workspace/kb_data`.
The dump is fetched through `kb/download_dump.sh` (16 range segments from ftp.acc.umu.se). The build produced 3,446,110 chunks and 1,554,413 articles; the full index takes 458 s. Sizes: index 5.4 GB, chunks 1.6 GB, raw dump 5.3 GB, index_mini 79 MB.

Recall is identical to the Mac build (`python -m kb.eval_recall --index /workspace/kb_data/index ...`):

| set | n | R@1 | R@5 | R@10 | p50 / p95 |
|---|---|---|---|---|---|
| dev-a | 70 | 0.586 | 0.914 | 0.971 | 47 / 134 ms (cold network FS) |
| smoke | 51 | 0.353 | 0.647 | 0.706 | 45 / 68 ms |
| sanity | 42 | 0.548 | 0.738 | 0.857 | 33 / 44 ms |

## Training

```bash
source /workspace/env.sh                       # HF_TOKEN, uv/HF env
/workspace/venvs/train/bin/python your_train.py
```

- Stack: Python 3.12, torch 2.12.1 (PyPI wheel, CUDA 13.0), transformers 5.5.0, peft 0.21.0, trl 0.24.0, accelerate 1.15.0, datasets 4.3.0, bitsandbytes 0.50.2, **unsloth 2026.9.11** (unsloth-zoo 2026.9.7), xformers 0.0.35 and triton 3.7.1.
  Unsloth installed cleanly.
- Smoke test: `/workspace/opt/train_smoke.py` runs unsloth 4-bit LoRA on Qwen3-0.6B for 20 SFT steps and saves the adapter. Result: `TRAIN_SMOKE_OK loss=2.11 wall=43s peak_mem=0.8GB`.
- LoRA to GGUF uses the convert venv (torch 2.11 CPU, transformers 4.57.6, gguf-py from the b11185 tag):
  `/workspace/venvs/convert/bin/python /workspace/opt/llama.cpp-src/convert_lora_to_gguf.py --base-model-id speakleash/Bielik-11B-v3.0-Instruct --outtype f16 --outfile /workspace/loras/<name>.gguf <adapter_dir>`.
  `--base-model-id` fetches only the config. The repo is gated, so export `HF_TOKEN` first (`source /workspace/env.sh`).
- The llama-server started with the defaults takes about 10 GB of VRAM. Stop it (`scripts/l40s_serve.sh stop`) before bf16 LoRA runs on 11-12B models.

## Gotchas

- The network FS handles small files at a few dozen per second. Deleting the 1.8 GB half-built venv took more than a minute. Keep venvs with many files on `/scratch`, and build or unpack there before copying big files to `/workspace`.
- Write remote shell scripts from Git Bash (LF), never from PowerShell.
- Sync code from the laptop with `tar -C $HOME/wmt-matura --exclude=./bin --exclude=./models --exclude=./data_cke --exclude=./.venv --exclude=./.env --exclude=./devset/experiments.csv --exclude=./devset/runs -cf - . | ssh l40s 'tar -C /workspace/wmt-matura -xf -'`.
  Exclude `.env` because the laptop's `.env` holds an HF token, and exclude the eval logs so the L40S rows are kept.
