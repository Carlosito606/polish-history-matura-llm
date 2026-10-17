# Model sweep on the L40S (devset/tourney160.jsonl)

Updated 2026-09-25 22:02 UTC. 160 history items (curriculum 56, long tail 34, historical geography 25, real CKE 45), same subset as devset/sweep_results.md (Mac). All numbers are % of items.

- **B** = raw untouched base GGUF through the harness `/base` passthrough: question as the only user message, no system prompt, temperature 0, max_tokens 512, chat-template defaults; the hybrid Qwen models (Qwen3.5-*, Qwen3-1.7B/0.6B/8B) run with thinking OFF (`--chat-template-kwargs enable_thinking=false`).
- **T_kb** = harness defaults + full Wikipedia BM25 KB; **T_nokb** = same with `use_kb=0`. Harness = frozen copy of the L40S/Mac harness (identical md5 to the Mac sweep's copy), thinking off, retrieval cache on.
- **GAIN_strict** = T_kb strict - B strict, **GAIN_len** = T_kb lenient - B lenient (percentage points). Sorted by GAIN_strict.
- llama.cpp b11185 CUDA, one model at a time on :18081 (`-c 32768 -np 8 -kvu -fa on`), 8 eval workers, phases run one after another (kb, nokb, base); p50 = per-item latency in s. The main :18080 Bielik-11B server shared the GPU.

| # | model | params | GB | B_strict | B_len | T_kb strict | T_kb len | T_nokb strict | T_nokb len | GAIN_strict | GAIN_len | T_kb len per type (abcd/chrono/match/open/pf) | pass>=35% (T_kb s/l) | p50 T_kb | p50 B | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | qwen35-4b | 4B | 4.48 | 1.9 | 33.1 | 58.1 | 66.2 | 36.2 | 41.9 | **56.3** | 33.1 | 87/28/47/76/48 | yes/yes | 3.55 | 4.69 | B hit 512-tok cap=24; thinking off |

## Headlines

- highest GAIN_strict: **qwen35-4b** +56.3 pp (T_kb 58.1 vs B 1.9)
- highest GAIN_len: **qwen35-4b** +33.1 pp (T_kb 66.2 vs B 33.1)
- highest T_kb strict: **qwen35-4b** 58.1; highest T_kb lenient: **qwen35-4b** 66.2
- smallest model with T_kb strict >= 45%: **qwen35-4b** (4B, 4.48 GB, T_kb strict 58.1)

## Per-type T_kb strict / lenient %

| model | abcd | chrono | match | open | pf |
|---|---|---|---|---|---|
| qwen35-4b | 83 / 87 | 28 / 28 | 41 / 47 | 52 / 76 | 48 / 48 |

## Per-type B strict / lenient %

| model | abcd | chrono | match | open | pf |
|---|---|---|---|---|---|
| qwen35-4b | 2 / 50 | 0 / 22 | 0 / 35 | 2 / 21 | 3 / 24 |

## Per-group lenient % (T_kb / B)

| model | T curriculum | T longtail | T histgeo | T cke | B curriculum | B longtail | B histgeo | B cke |
|---|---|---|---|---|---|---|---|---|
| qwen35-4b | 71.4 | 64.7 | 68.0 | 60.0 | 26.8 | 44.1 | 28.0 | 35.6 |

## Runs

| model | server | B mean completion tokens | wall s | run files |
|---|---|---|---|---|
| qwen35-4b | -c 32768 -np 8 -kvu -fa on --chat-template-kwargs enable_thinking=false | 249 | 264 | 20260925-220241_l40s-qwen35-4b-base-raw.jsonl, 20260925-220007_l40s-qwen35-4b-harness-kb.jsonl, 20260925-220054_l40s-qwen35-4b-harness-nokb.jsonl |

## Thinking probes (non-Qwen models, default template vs enable_thinking=false)

