# Model sweep ("go lower") on devset/tourney160.jsonl

Updated 2026-09-25 23:26. 160 history items (curriculum 56, long tail 34, historical geography 25, real CKE 45). B = raw untouched base via /base (no system prompt, max_tokens 256, template default; hybrid-thinking Qwen models: thinking OFF, see 'base thinks'). T = harness defaults (frozen copy), thinking off. Latencies are under heavy shared-GPU load (3 other llama-servers active) and concurrent phases -> only relative. obj_s = 0.8*T_strict - 0.4*B_strict, obj_l = 0.8*T_len - 0.4*B_len (percentage points; gain term counted as 0.4*(T-B) + 0.4*T final). Sorted by obj_l.

| model | params | GB | B_strict | B_len | T_kb strict | T_kb len | T_nokb | gain T-B_len | obj_s | obj_l | harness p50 s | raw p50 s | base thinks | pass>=35% (T strict/len) | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen35-4b | 4B | 4.48 | 2.5 | 28.1 | 58.1 | 65.0 | 36.2 | 36.9 | 45.5 | 40.8 | 49.70 | 69.05 | yes (template default); base run with thinking OFF | yes/yes | base hit cap=70; base thought on 0/160 |
| qwen3-4b-2507 | 4.0B | 4.28 | – | – | 53.8 | 61.3 | – | – | – | – | 23.34 | – | no | yes/yes |  |

## Per-type T_kb lenient %

| model | abcd | chrono | match | open | pf |
|---|---|---|---|---|---|
| qwen35-4b | 85.2 | 27.8 | 41.2 | 76.2 | 48.3 |
| qwen3-4b-2507 | 88.9 | 27.8 | 29.4 | 73.8 | 31.0 |

## Per-type B lenient %

| model | abcd | chrono | match | open | pf |
|---|---|---|---|---|---|
| qwen35-4b | 38.9 | 11.1 | 23.5 | 21.4 | 31.0 |

## Per-group lenient % (T_kb / B)

| model | T curriculum | T longtail | T histgeo | T cke | B curriculum | B longtail | B histgeo | B cke |
|---|---|---|---|---|---|---|---|---|
| qwen35-4b | 71.4 | 64.7 | 68.0 | 55.6 | 25.0 | 41.2 | 12.0 | 31.1 |
| qwen3-4b-2507 | 62.5 | 61.8 | 68.0 | 55.6 | – | – | – | – |

## Reference: Bielik-11B on the 56-item overlap (dev-a/b/c curriculum items of tourney160 that are also in dev_all; other agent's integ-devall-* runs, current harness)

| system | strict | lenient |
|---|---|---|
| bielik-11b harness-kb | 80.4 | 83.9 |
| bielik-11b harness-nokb | 62.5 | 64.3 |
| bielik-11b base-raw | 21.4 | 62.5 |
| qwen35-4b harness-kb | 69.6 | 71.4 |
| qwen35-4b harness-nokb | 33.9 | 33.9 |
| qwen35-4b base-raw | 0.0 | 25.0 |
| qwen3-4b-2507 harness-kb | 62.5 | 62.5 |

## Thinking probes

- qwen35-4b: {"default": {"reasoning_chars": 1692, "think_tag_in_content": false, "content": "", "completion_tokens": 600}, "no_think": {"reasoning_chars": 0, "think_tag_in_content": false, "content": "Bitwa pod Grunwaldem odbyła się w roku **1410**.", "completion_tokens": 19}}
- qwen3-4b-2507: {"default": {"reasoning_chars": 0, "think_tag_in_content": false, "content": "Bitwa pod Grunwaldem odbyła się w roku 1410.", "completion_tokens": 19}, "no_think": {"reasoning_chars": 0, "think_tag_in_content": false, "content": "Bitwa pod Grunwaldem odbyła się w roku 1410.", "completion_tokens": 19}}
