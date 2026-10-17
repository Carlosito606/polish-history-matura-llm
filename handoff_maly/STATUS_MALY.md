# "Mały, ale wariat" — what team Vibers already measured (26.09.2026, evening)

Goal of the category: the **smallest model that scores ≥ 35%** on the final (CKE history matura, formula 2023, 60 points →
35% = 21 points). All numbers below are CKE-rubric grades from blind Claude Opus examiners (same method throughout).

## Results so far

Mock = organizers' mock (CKE May 2023, 60 pts). Papers = text parts of CKE May 2024, 2025, 2026 (131 pts).

| Model (GGUF size) | Best config | Mock /60 | Papers /131 | Verdict |
|---|---|---|---|---|
| Qwen3.5-0.8B (Q8, ~0.8 GB) | harness v3 + BM25 | 12 (20.0%) | 20 (15.3%) | far below |
| Qwen3.5-2B (Q8, 2.01 GB) | raw / v3 + reranker | 15 (25.0%) | 30 (22.9%) | below |
| Bielik-1.5B-v3 (Q8, 1.70 GB) | raw (mock) / v3 (papers) | 18 (30.0%) | 31 (23.7%) | closest small one, still below |
| **Bielik-4.5B-v3 (Q8, 5.06 GB)** | raw | 24–25 (40–42%) | 51 (38.9%) | **passes with margin** |
| Bielik-4.5B-v3 (Q8) | + essay pipeline (our final "progress" system) | 25–27 | — | passes |

Full tables: `docs/maly_q08_eval.md`, `docs/maly_small_eval.md`, `docs/mock_opus_panel.md`, `docs/final_config.md`.

Per-type picture for 1.5–2B models (papers): essays 1–9 of 45, identification (names/dates) 5–13 of 29, "rozstrzygnij"
2–4 of 20, closed 4–8 of 17. Main failures: essays (no functional knowledge, >5 factual errors, bullet lists = B 0,
<300 words), "Tak" bias in decide-and-justify items, junk copied from retrieval, loops at the token cap.

## What was started but not finished

- **Quantized Bielik-4.5B** is the most promising route: 40% at Q8 (5.06 GB) leaves ~5 pp of headroom to trade for size.
  Q4_K_M (~2.8 GB) and Q3_K_M (~2.3 GB) GGUFs were built from the official HF weights with llama.cpp (convert → f16 →
  llama-quantize), but **never evaluated** (we switched all compute to the progress entry). Official speakleash GGUF repos
  may also carry smaller quants — check first.
- Organizers' benchmark says Qwen3-4B-Instruct-2507 (40.0%) and Gemma-3-4B (36.4%) pass in text mode at ~4B; not measured by us.

## Recommended plan for the colleague's agent

1. Confirm the unit of "smallest" (GB vs parameters) with organizers on Telegram. If GB: quantization is the lever.
2. Evaluate Bielik-4.5B-v3 at Q4_K_M, Q3_K_M, IQ3_XXS, IQ2_M (raw, no retrieval, text-only; the final gives PNGs only —
   use no image descriptions unless your system includes an allowed describer) on the organizers' mock + 2–3 more CKE papers
   (2024, 2025, 2026 May). Keep the smallest quant with ≥ 38% (3 pp margin for noise; single runs vary ±3–4 points).
3. Cheap gains that worked for us: essay pipeline with retrieval from Polish Wikipedia (+3.25/15 per essay over raw
   on 12 papers) — but it costs extra calls and a KB; raw Bielik answers short items as well as our harness did.
   Make sure the essay is ≥ 300 words, one topic, prose (no bullet lists), few dates (>5 factual errors = −3).
4. Also try Qwen3-4B-Instruct-2507 at Q4 (~2.5 GB) as a second candidate, and Bielik-1.5B only if a strong essay
   pipeline lifts it by ≥ 5 points.
5. Grade with the CKE rubric on full papers (not on generated QA — our LoRAs looked great there and did nothing on
   real papers). Blind, ideally 3 independent examiners for essays.
6. Submit the mock to https://warsawmodeltrainers.dev/submissions.html to calibrate against the organizers' grading.

## Assets in this repo

- `code/` — our full system (see `code/README.md`): `exam_runner.py` (official pack → answers.json; modes raw/harness/
  hybrid), harness v3 with the essay pipeline, Wikipedia KB builder (`code/kb/run_all.sh`), `run_final.sh`,
  `describe_images.py` (vision describer), L40S helpers.
- `devsets/`, `qa/`, `training/` — data (see top-level README).
- CKE papers/keys are **not** in the repo: `scripts/fetch_cke.py`, `scripts/fetch_arkusze.py` download them.
- The organizers' mock pack: download it from the JSON guide page (link in `ORGANIZER_INFO.md`).
