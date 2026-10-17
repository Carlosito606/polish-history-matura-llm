# docker/ - production packaging (exam VM: 1x L40S 48 GB, 4 vCPU, 32 GB RAM, Ubuntu x86_64)

Two images, one compose file, fully offline at exam time.

| service    | image                                                        | networks         | role |
|------------|--------------------------------------------------------------|------------------|------|
| `llm`      | `ghcr.io/ggml-org/llama.cpp:server-cuda-b11176` (official, pinned) | internal         | trained model: `MODEL_FILE` (+ optional `LORA_FILE`) |
| `llm-base` | same (profile `base`)                                        | internal         | untouched base model for the gain benchmark |
| `harness`  | `wmt-harness` (built here: `Dockerfile.harness`)             | internal         | FastAPI RAG server (`python -m harness`) + `kb/` BM25 over the mounted index |
| `gateway`  | `wmt-harness` (`python /opt/wmt/gateway.py`)                 | internal + edge  | stdlib TCP forwarder; the only container that has a route out or published ports |

```
host 127.0.0.1:18000 -> gateway -> harness:18000 -> llm:8080            RAG endpoint (OpenAI API: /v1/chat/completions, model "wmt-matura-rag"; "base" = harness passthrough)
host 127.0.0.1:18080 -> gateway -> llm-base:8080 | llm:8080             raw llama-server OpenAI API, no RAG (untouched base when --profile base is up)
```

`internal` is a Docker `internal: true` network: `llm`, `llm-base` and `harness` have no egress and no
published ports (Docker does not publish ports of containers that sit only on an internal network,
which is why the gateway exists).  The gateway only pipes bytes to the upstreams in `GATEWAY_ROUTES`,
so SSE streaming and keep-alive pass through unchanged.

llama.cpp pin: our native builds are b11185, but ggml-org publishes Docker images only for some
releases; **b11176** is the newest image at or below b11185 (checked in the ghcr tag list on
25.09.2026). `server-cuda-b11176` = `server-cuda12-b11176` (CUDA 12.8.1, Ubuntu 24.04), index digest
`sha256:1f4b9cf58982dd4d7cc497aea31b1a456ca9a3a1f94f527d317d3fdee0d60ab6`; CPU image
`server-b11176` = `sha256:6257697a7f5d034b8fb499ddb07af3e250506352f94102054252a23f3b85e0af`.
The same GGUF files run in both images.

## Files

| file | what |
|------|------|
| `Dockerfile.harness` (+ `.dockerignore`) | python:3.12-slim (digest-pinned), wheels-only hashed install into /opt/venv, copies `kb/` `harness/`, uid 10001, `HF_HUB_OFFLINE=1`, no proxies, healthcheck |
| `requirements.in` -> `requirements.txt` | runtime deps (what `harness/` + `kb/search.py` import) -> hashed universal lock via `lock.sh` (uv) |
| `llm-entrypoint.sh` | builds the llama-server command line from env (`MODEL_FILE`, `LORA_FILE`, `LORA_SCALE`, `N_GPU_LAYERS`, `CTX_SIZE`, `N_PARALLEL`, `KV_UNIFIED`, `CHAT_TEMPLATE_FILE`, `SEED`, `LLAMA_EXTRA_ARGS`) |
| `compose.yaml` | prod (GPU) stack described above |
| `compose.mac.yaml` + `mac.env` | CPU override for the Mac smoke test (CPU image, Bielik-1.5B Q8_0, mini index, ports 18050/18051, CPU/RAM caps) |
| `.env.example` | prod settings; copy to `docker/.env` on the VM |
| `gateway.py`, `healthcheck.py`, `smoke_test.py` | stdlib-only helpers baked into the harness image under /opt/wmt |
| `build.sh` | buildx multi-arch build (amd64+arm64), `docker save` linux/amd64 tarballs to `dist/` + `images.env` + `SHA256SUMS` |
| `prod_bootstrap.sh` | fresh VM: Docker Engine + compose + NVIDIA Container Toolkit, `nvidia-smi` and `--list-devices` inside the pinned CUDA image |
| `deploy.sh` | build host -> VM: rsync docker/, image tarballs, models, index (or HF private repo download on the VM), then `vm_up.sh` |
| `vm_up.sh` | on the VM: docker load, verify files, `compose up --wait`, smoke test |
| `offline_check.sh` | proves no egress for llm/llm-base/harness, positive control from the gateway, harness TCP peers all internal |
| `hf_push.sh` | optional: push GGUFs + index to a private HF repo for `deploy.sh --hf-repo` |
| `lock.sh` | `uv pip compile --universal --generate-hashes` of `requirements.in` |
| `mac_env.sh` | Mac SSH sessions: docker CLI without the locked-keychain credential helper |

## Model options

* base + LoRA: `MODEL_FILE=<base>.gguf`, `LORA_FILE=<adapter>.gguf` (convert with llama.cpp
  `convert_lora_to_gguf.py`), `LORA_SCALE=1.0`. Untouched base = `--profile base` (defaults to
  `MODEL_FILE` without the adapter).
* merged: `MODEL_FILE=<merged>.gguf`, `LORA_FILE=` empty, `BASE_MODEL_FILE=<original>.gguf`.

`CTX_SIZE=16384 N_PARALLEL=4 KV_UNIFIED=1`: one 16k KV pool shared by the 4 slots, so a single long
RAG prompt can use more than 4k tokens. Bielik-11B Q4_K_M = 6.7 GB weights + ~3.2 GB f16 KV at 16k;
both `llm` and `llm-base` fit on the 48 GB L40S together with room for `CTX_SIZE=32768`.

## Build (Mac Studio, Docker Desktop, containerd image store)

```bash
cd ~/wmt-matura && bash docker/lock.sh     # only when requirements.in changes
bash docker/build.sh                       # TAG=... SAVE_LLM=0 to skip the 3 GB CUDA tarball
# CONTEXT=<dir with kb/ harness/ docker/> bash docker/build.sh   to build from a staging copy
```

## Mac smoke test (CPU)

```bash
cd ~/wmt-matura && . docker/mac_env.sh
C="docker compose -p wmt-smoke --env-file docker/mac.env -f docker/compose.yaml -f docker/compose.mac.yaml"
$C up -d --wait            # add --profile base to also start llm-base
python3 docker/smoke_test.py --url http://127.0.0.1:18050 --raw-url http://127.0.0.1:18051
COMPOSE_ARGS="${C#docker compose }" bash docker/offline_check.sh
$C down
```

## Production VM

```bash
# once, on the VM (needs internet during setup)
sudo bash ~/wmt-matura/docker/prod_bootstrap.sh
# from the Mac: images + models + index + compose, then up + smoke test on the VM
bash docker/deploy.sh <vm-ssh-alias> --env docker/.env.prod [--base]
#   or: HF_TOKEN=... bash docker/deploy.sh <vm> --hf-repo <org>/<private-repo>   (VM downloads models/ + kb_data/index/)
# on the VM
bash ~/wmt-matura/docker/vm_up.sh --base
bash ~/wmt-matura/docker/offline_check.sh
```

Layout on the VM: `~/wmt-matura/{docker,dist,models,kb_data/index}`; compose runs from `docker/`,
`MODELS_DIR=../models`, `INDEX_DIR=../kb_data/index`, request log in the `harness-logs` volume
(`docker compose cp harness:/logs/harness-requests.jsonl .`).

## Measured (Mac Studio M4 Max, 25.09.2026)

* build: 341 s cold (both arches; pip wheels over a congested link), 7-15 s when only code changed.
* `wmt-harness`: linux/amd64 84.9 MB compressed (367 MB unpacked); linux/arm64 82.5 MB (381 MB).
  `dist/wmt-harness_<tag>_linux-amd64.tar.gz` = 84 MB; `dist/llama.cpp_server-cuda-b11176_linux-amd64.tar.gz` = 2.58 GB.
* Mac smoke stack (CPU, Bielik-1.5B Q8_0, index_mini): `up --wait` 22 s; smoke test OK
  (RAG answer "A" correct, kb available, n_ctx 7-8, ~40 s on CPU; base passthrough and raw port OK);
  the linux/amd64 harness image also passes under emulation; `--profile base` routes the raw port to `llm-base`.
* `offline_check.sh`: ALL PASS (internal network, no DNS/TCP egress from llm and harness, positive
  control from the gateway reaches the internet, all 19 harness TCP peers internal).
* `vm_up.sh` exercised on the Mac with `COMPOSE_FILE=compose.yaml:compose.mac.yaml`: OK.
* shellcheck (warning level): clean.

## Gotchas

* The harness' own `base` model / `/base/v1/...` passthrough uses `BASE_LLM_BASE_URL`, which compose
  sets to `http://gateway:18080/v1` (the gateway's raw route: `llm-base` when `--profile base` is up,
  otherwise falls back to `llm` = the trained model). For a real base benchmark always start
  `--profile base` and wait until `llm-base` is healthy (during its startup the fallback hits `llm`).
* Mac only: the official arm64 CPU image's armv8.2+ backend variants emit garbage inside Docker
  Desktop on the M4; `compose.mac.yaml` masks them so ggml uses the armv8.0 variant.
* Mac only: `docker load` of the amd64 tarball replaces the multi-arch `wmt-harness:<tag>` locally;
  re-run `build.sh` with `SAVE=0` to restore it.
* `docker compose` inside `ssh host '...'` eats stdin: never pipe a tar stream into the same remote
  command.
