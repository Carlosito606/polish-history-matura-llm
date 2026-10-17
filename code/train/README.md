# LoRA training and export (L40S)

Pipeline: chat JSONL -> `train_lora.py` (bf16 LoRA, completions-only loss) -> `export.sh` (GGUF LoRA, 8 GB check,
optional merged quant) -> `eval_lora.sh` (official GGUF + `--lora` on :18082, harness on :18002, `devset/eval.py`).
Everything runs on the L40S (`ssh l40s`, repo copy in `/workspace/wmt-matura`; see `docs/l40s_setup.md`).

| file | what it does |
|---|---|
| `train_lora.py` | SFT with LoRA. Uses Unsloth when it can be imported, otherwise transformers+PEFT. bf16 (no 4-bit). The loss covers only the assistant answer. Logs go to `/workspace/runs/<name>/`. |
| `export.sh` | PEFT adapter -> `/workspace/loras/<name>.gguf` via `convert_lora_to_gguf.py`, plus a manifest (sizes, sha256). It checks base + adapter <= 8.0 GB. `--merge` also builds a merged GGUF quantized like the base. |
| `eval_lora.sh` | Starts a separate llama-server (:18082) and harness (:18002), runs `devset/eval.py`, appends a labelled row to `devset/experiments.csv`, then stops both. It never touches the main :18080/:18000 pair. |
| `make_toy_data.py` | Toy data for testing the pipeline only: fresh questions from a hand-written fact bank, rendered with the harness prompt code. |
| `requirements-*.txt` | Pinned venvs (`train` on /scratch, `convert`, `wmt`), installed by `/workspace/setup.sh`. |

## Data format

```json
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."},
              {"role": "assistant", "content": "C, A, D, B"}], "meta": {"type": "chrono"}}
```

- The last message must be the assistant answer.
- `meta.type` is optional. It is used for the per-type breakdown and for `--pf-numbered`.
- The system and user messages should be exactly what the harness sends at inference time: `harness.prompts.SYSTEM`, and `build_user(question, contexts, instruction(pq))` for the user turn. `make_toy_data.py` shows how.
- `train_lora.py` refuses data files under `devset/` (repo rule).

**P/F format mismatch.** For `pf` questions the harness instruction and GBNF grammar ask for
`1: P\n2: F\n3: P`, and the harness then renders the canonical `P, F, P`.
A LoRA trained on bare `P, F, P` answers therefore works against the grammar.
You can either train with `--pf-numbered`, which rewrites `pf` answers into the numbered format, or change the harness pf prompt and grammar first.
Every other type already matches the harness grammar: `B`, `C, A, D, B`, `1-B, 2-A`, and the short open answer.

### Masking (completions-only loss)

1. Render the prompt with `apply_chat_template(messages[:-1], add_generation_prompt=True)` and the full conversation with `apply_chat_template(messages)`.
2. Tokenize the full text once and split it at the prompt's token count. The prompt gets label -100. The answer is trained up to and including the first end-of-turn token (`<|im_end|>` / `<end_of_turn>` / eos).
3. Do not tokenize the answer on its own. With SentencePiece vocabularies (Bielik), that adds a dummy-prefix `▁` (`▁C` instead of `C`), which the model never produces after `assistant\n` and which the GBNF grammar rejects. Tokenizing the full text avoids this.
4. `data_stats.json` records `boundary_token_mismatch` and `template_fallback_used`. Both were 0 for Bielik 11B v3 and Qwen3.
5. Checked for Bielik 11B: the HF prompt ids are identical to llama-server's (`/apply-template` + `/tokenize`, 401/401 tokens, a single BOS).
6. Qwen3 hybrids (Qwen3-8B, and Qwen3.5 if used in non-thinking mode) need `--chat-template-kwargs '{"enable_thinking": false}'` at training time. Pass the same JSON to `eval_lora.sh` and llama-server. Qwen3-4B-Instruct-2507 does not need it.

## Commands

```bash
ssh l40s
cd /workspace/wmt-matura && source /workspace/env.sh          # HF_TOKEN from /workspace/.secrets (never printed)

# 1. train  (the main llama-server may keep running: 11B bf16 LoRA peaks at 25.7 GB next to its 10 GB)
tmux new -s train
/workspace/venvs/train/bin/python train/train_lora.py \
    --data /workspace/data/sft/train.jsonl --eval-frac 0.03 \
    --base speakleash/Bielik-11B-v3.0-Instruct --name bielik11b-r16-e1 \
    --r 16 --alpha 32 --lr 1e-4 --epochs 1 --max-seq-len 3072 --batch 4 --grad-accum 4 --seed 42 \
    --pf-numbered --gen-eval-n 200 --gen-eval-base  2>&1 | tee /workspace/logs/train_bielik11b-r16-e1.log
#    Qwen3-8B:  --base Qwen/Qwen3-8B --chat-template-kwargs '{"enable_thinking": false}'
#    dry run (tokenize, length stats, show the trained span, no GPU): add --dry-run

# 2. export (+ size check). --merge optional (adds a merged GGUF quantized like the base: 11B about 5 min)
bash train/export.sh --run bielik11b-r16-e1 --base-gguf bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf

# 3. evaluate through the harness on a dev file (A/B against the adapter switched off on the same server)
bash train/eval_lora.sh --lora bielik11b-r16-e1 --base-gguf bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf \
    --dev devset/dev-a.jsonl,devset/dev-c.jsonl --label r16-e1 --ab
#    Qwen3-8B: --chat-template-kwargs '{"enable_thinking":false}'; extra harness env: --harness-env "CHRONO_MODE=hybrid"

# toy end-to-end test (about 5 min in total)
/workspace/venvs/wmt/bin/python train/make_toy_data.py --n 200 --out /workspace/data/toy/train.jsonl \
    --eval-n 24 --eval-out /workspace/data/toy/eval.jsonl
/workspace/venvs/train/bin/python train/train_lora.py --data /workspace/data/toy/train.jsonl \
    --eval-data /workspace/data/toy/eval.jsonl --base Qwen/Qwen3-4B-Instruct-2507 --name toy-qwen4b-r16-v2 \
    --r 16 --alpha 32 --lr 2e-4 --max-steps 40 --batch 4 --grad-accum 2 --gen-eval-base
bash train/export.sh --run toy-qwen4b-r16-v2 --base-gguf qwen3-4b-2507/Qwen3-4B-Instruct-2507-Q8_0.gguf
bash train/eval_lora.sh --lora toy-qwen4b-r16-v2 --base-gguf qwen3-4b-2507/Qwen3-4B-Instruct-2507-Q8_0.gguf \
    --dev devset/smoke.jsonl --label toy-e2e --ab --raw
```

### Outputs

- `/workspace/runs/<name>/` contains:
  - `config.json`: arguments, backend and versions.
  - `data_stats.json`: lengths, dropped rows, and the decoded trained span of example 0.
  - `train_log.jsonl`: loss, lr, grad_norm and eval_loss.
  - `metrics.json`: train and eval loss, tokens/s, peak memory, and greedy exact match on the eval split with and without the adapter.
  - `gen_eval.jsonl` and `adapter/`.
- `/workspace/loras/<name>.gguf` and `<name>.gguf.json`: adapter sha256, base sha256 from `models/SHA256SUMS`, sizes, and the PASS/FAIL result of the 8 GB check.
- `devset/experiments.csv` gets rows labelled `lora=<name>@<scale>|base=<gguf>|<label>`, plus `lora=<name>@0(off)|...` with `--ab`, and `...|raw` with `--raw`.
  This is the L40S copy of the file and is not synced to the laptop.
- `eval_lora.sh` prints `GET /lora-adapters` and a raw probe comparing the first dev question with the adapter at scale 1 and at 0.
  llama.cpp b11185 does not log the LoRA load at the default verbosity, so `/lora-adapters` is the proof that the adapter loaded.
  It then prints how many answers changed between LoRA on and off, and which ones it fixed or broke.

## Measured on the L40S (2026-09-25)

All runs: bf16 LoRA r=16 on q/k/v/o/gate/up/down, Unsloth 2026.9.11, gradient checkpointing, batch 4 x grad-accum 4.
The sequences were about 2.8–3.0k tokens (`make_toy_data.py --ctx-chars 5500`).
The main llama-server (Bielik 11B, 10.2 GB) kept running on the same GPU during these runs.

| base (HF) | train tokens/s | peak VRAM (alloc) | model load (HF cache on /workspace) |
|---|---|---|---|
| Qwen/Qwen3-4B-Instruct-2507 | 4,821 | 10.4 GB | 19 s |
| Qwen/Qwen3-8B | 2,956 | 19.3 GB | 30 s |
| speakleash/Bielik-11B-v3.0-Instruct | 2,007 | 25.7 GB | 117 s |
| Qwen/Qwen3.5-9B, google/gemma-4-12B-it | not measured; about 2,600 and 1,800 by parameter count | about 21 / 28 GB | – |

For short sequences (about 360 tokens, the toy set) Qwen3-4B runs at 4,012 tokens/s, and 40 steps take 29 s.

**Expected time for about 8k examples, 1 epoch.** Time = examples x mean tokens / tokens/s, plus load time.
Check the mean length first with `--dry-run` (`len_mean` in `data_stats.json`).
Harness prompts with the default `CTX_TOKENS=1200` context come to roughly 1.5–2k tokens. Prompts without context are about 350–450 tokens.

| base | 8k x 400 tok (no context) | 8k x 1.5k tok | 8k x 3k tok |
|---|---|---|---|
| 4B (Qwen3-4B-2507) | about 11 min | about 42 min | about 1 h 25 min |
| 8B (Qwen3-8B) | about 18 min | about 1 h 8 min | about 2 h 15 min |
| 9B (Qwen3.5-9B, estimated) | about 21 min | about 1 h 17 min | about 2 h 35 min |
| 11B (Bielik 11B v3) | about 27 min | about 1 h 40 min | about 3 h 20 min |

- A second epoch doubles these times. Gen-eval on 200 examples adds under a minute.
- Export takes about 30–45 s for a LoRA, because writes to `/workspace` run at about 10 MB/s for this pattern.
- `--merge` adds merge + bf16 GGUF + quantize: 4B took about 2.5 min, so expect about 6 min for 11B.
- `eval_lora.sh` on `smoke.jsonl` with `--ab --raw` took about 3 min for the 4B model.

**Memory.**
- 11B bf16 LoRA at 3k tokens and batch 4 peaks at 25.7 GB, so it runs next to the 10 GB main llama-server (46 GB card).
- For batch 8 or seq 4096 on 11–12B, stop the main server first with `scripts/l40s_serve.sh stop`.
- The eval pair on :18082 adds one more GGUF plus KV cache (4B Q8_0: about 7 GB; 11B Q4_K_M: about 10 GB). Do not run it while an 11B training run is using most of the card.
- RAM is 30 GB, and `export.sh --merge` merges on the GPU when there is enough free VRAM (`MERGE_DEVICE=cpu|cuda` overrides).

## Gated repos / tokens

| repo | gated | notes |
|---|---|---|
| speakleash/Bielik-11B-v3.0-Instruct, Bielik-4.5B-v3.0-Instruct, Bielik-Minitron-7B-v3.0-Instruct | yes (license click-through, auto-approve) | our token has access; `source /workspace/env.sh` exports `HF_TOKEN` |
| google/gemma-4-12B-it | no (Gemma license applies) | token not required |
| Qwen/Qwen3-4B-Instruct-2507, Qwen/Qwen3-8B, Qwen/Qwen3.5-9B | no | Apache-2.0 |

HF downloads to `/workspace/.home/.cache/huggingface` run at about 400 MB/s: 7.6 GB in 18 s, and Bielik 11B (22 GB) in about 1 min.
`export.sh` reads the base config from that cache, so it works offline after training.

## Rules this pipeline keeps

- The registered base GGUF is only read and never re-saved. The LoRA is applied at runtime with `--lora-scaled adapter.gguf:SCALE`.
- The 8 GB check adds base + adapter together. The merged model is a new model file, so use `--merge` only if the organizers accept a model other than the registered GGUF.
- Base benchmarks without a LoRA run on a separate server. `eval_lora.sh --ab` runs scale 0 on the same server only as a same-harness A/B, not as the official base number.
- Dev sets are never used for training (`train_lora.py` refuses `devset/` paths).

## Known gaps

- Only Qwen3-4B-2507 (full train, export, merge and eval), plus Qwen3-8B and Bielik 11B (training throughput), were run.
  - Gemma 4 12B and Qwen3.5-9B are multimodal/hybrid checkpoints. Unsloth `FastLanguageModel` and `convert_lora_to_gguf` support for them was not tested.
  - The PEFT fallback (`--backend peft`) restricts LoRA to language-model linears with a regex, but it was not run either.
  - For those models, run a 5-step `--max-steps 5` plus `export.sh` check before any long run.
- `llama-quantize` (used by `--merge`) needs `LD_LIBRARY_PATH=/workspace/opt/glibc-2.39/lib`. Without it, system libcrypto pulls in the system libm and the run fails with `GLIBC_2.38 not found`. `export.sh` sets this for that one call. Do not export it globally, because it breaks the system Python.
- Official GGUFs may have been quantized with an imatrix. The merged quant has none unless you pass `--imatrix`.
