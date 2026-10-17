# Mentor benchmark notes: warsaw-matura-method

Source: https://warsaw-matura-method.ania-olchowik.chatgpt.site/ (by Ania Olchowik, workshop lead and mentor). Fetched 2026-09-25. Page header: "22 SEP 2026 · v0.1", "Proposed benchmark · open for discussion".

What I read: every page linked from the index (30 HTML pages), `methodology.md`, `script.js`, `gpu-generation-by-model.csv`, and all 60 downloadable run files (`<run>.json` holds the exact prompts, rendered chat templates, generation config and raw outputs; `<run>.reviews.json` holds the per-item AI grades and reasons). I also read the two CKE PDFs the site links to: the paper `MHIP-R0-100-2305.pdf` and the marking scheme `MHIP-R0-100-2305-zasady.pdf`. Both are saved in `data_cke/`, which is git-ignored. The run JSONs contain CKE question text, so they stay in a scratch directory and are not committed. For the CKE rules themselves, see `docs/cke_grading_rules.md`, which another agent wrote.

What the benchmark is: the real CKE history paper (extended level, 18 May 2023), in two input formats:

- **Text-only:** 34 items worth 55 points. Tasks 7, 8 and 15 are removed, and images are replaced by fixed Polish descriptions.
- **Original page images:** 37 items worth 60 points.

This is not the hackathon exam. The hackathon uses its own question pool (see section 6).

---

## 1. Prompts and generation settings

### Prompt template (identical for all text runs)

The system instruction below appears verbatim in every text run file (`system_prompt`):

> Rozwiąż zadanie z historii po polsku. Otrzymujesz tekst źródeł, a obrazy zastąpiono opisami. Wykorzystaj źródła i własną wiedzę zgodnie z poleceniem. Udziel tylko odpowiedzi na podane zadanie. Nie dopisuj innych zadań. Nie masz dostępu do narzędzi ani internetu.

The image runs use this system instruction:

> Rozwiąż zadanie z historii po polsku. Otrzymujesz obrazy oryginalnych stron arkusza ze źródłami i poleceniami. Wykorzystaj widoczne źródła i własną wiedzę zgodnie z poleceniem. Udziel tylko odpowiedzi na wskazane zadanie. Inne zadania widoczne na tych samych stronach pomiń. Nie masz dostępu do narzędzi ani internetu.

The user message is built like this (reconstructed from `answers[].messages`):

```
Zadanie {id} ({max_points} pkt)

{source title}
[Opis źródła Z05-S1]        <- only when an image was replaced by a description
{source text / description}

{question text, including CKE answer scaffolds such as "Rozstrzygnięcie:\nUzasadnienie:"}
```

- Each scored subtask is a fresh conversation that includes all of its task group's sources.
- Image runs send `[image(s)] + "Zadanie {id} ({pts} pkt)\n\n{question}"`, with whole PDF pages rendered at 200 dpi.
- **The system prompt goes in the native system role**, with two exceptions:
  - Gemma-3-1B and Gemma-3-4B-text have it prepended to the first user message (`system_prompt_transformation: "system instruction prepended verbatim to first user message"`).
  - PLLuM-4B's template also renders it inline, as `<bos>[INST]{system}\n\n{user}`.
- SmolLM3's template adds its own "Reasoning Mode: /think" metadata block.
- There is no few-shot, no answer-format instruction and no retrieval. The only output guidance is "Udziel tylko odpowiedzi na podane zadanie."

### Decoding and token caps

| Protocol | Who | Decoding | Thinking | Caps | Context |
|---|---|---|---|---|---|
| **v0.1** (original baselines) | Bielik-1.5B, Bielik-4.5B, Qwen3-4B-2507, Phi-4-mini, PLLuM-4B, Gemma-3-1B, Gemma-3-4B (text + image), Qwen3-VL-2B-Instruct | greedy (`do_sample=False`), seed 42, BF16, batch 1, L4 | off ("not enabled; requested checkpoint native default") | 2048 new tokens per short item, 4096 for the essay, shared with any thinking | 8192 |
| **v0.2 thinking** | Qwen3-1.7B, SmolLM3-3B, Qwen3-VL-2B-Thinking, InternVL3.5-8B: `temperature=0.6, top_p=0.95, top_k=20` (SmolLM3 top_k 50) | vendor sampling, seed reset before every item | on, via the native template | separate budgets: up to **8192 thinking + 2048 final** (short items), **16384 + 4096** (essay) | 32768 |
| **v0.2 large thinking** | Qwen3.5-9B: `T=1.0, top_p=0.95, top_k=20, min_p=0, presence_penalty=1.5` · Gemma-4-12B: `T=1.0, top_p=0.95, top_k=64` | vendor sampling | on (`enable_thinking: true`) | 8192/2048 and 16384/4096 | 32768, A100 80GB |
| **v0.2 non-thinking** | LLaVA-Bielik-11B, LLaVA-PLLuM-12B, Ministral-3-14B: greedy · Llama-3.2-3B: native sampling (T 0.6, top_p 0.9) | greedy or native | off | 2048 / 4096 final | 32768 |

v0.2 rules, quoted verbatim from `methodology.md`:

> "Detect the checkpoint's actual end-of-thinking boundary (</think> for this Qwen Thinking checkpoint), then start counting final-answer tokens. Never discard a fixed number of leading tokens. [...] If thinking exhausts its allowance before a final answer, record no final answer and zero points. Do not silently force a thinking-end marker, repair the response, or retry."

> "Grade only the final answer."

**Budget pilot** (Qwen3-VL-2B-Thinking, 5 items worth 20 points). With the same separate budgets:

| Configuration | Final answers produced | Score |
|---|---|---|
| Greedy decoding | 1/5 | 1/20 |
| Vendor sampling (T 1.0 / top_p 0.95 / top_k 20) | 5/5 | 4/20 |

> "Better completion did not remove historical errors."

In the full v0.2 runs, Qwen3-VL-2B-Thinking still produced no final answer on 21/34 text items and 30/37 image items. Qwen3.5-9B missed 3/37: items 13.1, 13.2 and 19 hit the 8192-token thinking cap.

Thinking budgets actually used:

| Model | Median thinking tokens per item | Max | Median final answer |
|---|---|---|---|
| Qwen3.5-9B | 1546 | 8192 | 180 tokens |
| Gemma-4-12B | 951 | 6544 (never hit the cap) | 164 tokens |

---

## 2. Grading method

- **Only an AI judge grades, against the official CKE marking scheme.** Verbatim from `methodology.md`:

  > "AI grades open answers and essays against the CKE rubric. The organizer has selected AI-only grading: these are the recorded benchmark grades, with no human grading stage planned. Keep the awarded points and written reasons for every decision."

  Every review record carries `reviewer: "AI rubric assessment"` and `grading_method: "AI"`. The judge model is not named anywhere on the site.
- **Closed items.** The rule reads:

  > "Closed responses are deterministically graded only when unambiguous. Formatting that the parser cannot interpret goes to review, not automatic zero."

  In practice the recorded reasons show the judge taking **the explicit final selection**, which it does not repair. Examples:
  - Bielik-4.5B on task 3 labels statement 1 "P", then argues the opposite. It is graded on "P": "the repeated explicit final selection remains P and is not silently repaired."
  - LLaVA-PLLuM-12B answers "2." with no choices: "The grader does not invent an answer."
  - Explanations attached to closed items are ignored, even when they are wrong. Gemma-4 on task 10: "The unrequested explanation wrongly reverses the Buczacz tribute direction, but this closed task scores the choices."
- **Closed items in this paper** (11 points, 7 items):

  | Item(s) | Type | Credit rule |
  |---|---|---|
  | 2.2 | matching | both matches required for 1 point |
  | 3, 10, 19 | true/false triples | 2 points for 3 correct, 1 point for 2 correct |
  | 11.2, 13.2 | single A–D choice | 1 point |
  | 21 | two A–D choices | 1 point each |

  The other 29 points are open answers, and the essay (item 26) is worth 15.
- **Open items:** 1 point for a correct verdict plus a justification that cites the source. Wording other than the sample answer is accepted if it is correct ("Akceptowane są wszystkie odpowiedzi merytorycznie poprawne i spełniające warunki zadania"). A wrong verdict with a good justification scores 0.
- **Essay (CKE rubric).**
  - **Argument (up to 12 points).** Each of the 3 topic elements is scored: rich 4, satisfactory 3, superficial 1.
  - **Factual-error deductions:** 1–2 errors −1, 3–5 errors −2, more than 5 errors −3. The argument score cannot go below 0.
  - **Coherence (up to 3 points):** 0 if the essay is under 300 words. Otherwise it depends on the intro, body, conclusion structure.
  - **Benchmark rule:**

    > "assess the first explicitly selected topic only, including its word count."

    Bielik-4.5B wrote all three topics, so only the first was graded.
  - **Word count uses the final answer only**, not the thinking.
- **Failure rules.** Empty answer: 0. Truncated answers are "graded as produced". A missing final answer after thinking scores 0. Scores are published per category, and the essay is always shown separately.
- **Subsets.**
  - "Originally text only": tasks 2, 6, 11, 12, 16, 22, 23, 25, 26 (13 items, 28 points).
  - "+ task 10 table": 30 points.
  - "Shared 34 items / 55" is used to compare image runs with text runs.

CKE instruction worth copying into our harness prompt, from page 2 of the paper: "Udzielaj tylu odpowiedzi, o ile Cię poproszono."

---

## 3. Per-model results

Points are AI-graded. C = closed /11, O = open (/29 for text, /34 for images), E = essay /15.

My extra split of the 55-point item set (item groups chosen by me, not by the site):

- **Recall** (16 points): the answer is mainly background knowledge, which is what Wikipedia RAG supplies. Items 4.1, 5.1, 9.1–9.3, 11.1, 11.2, 13.2, 14.1, 14.2, 16.2, 21, 23, 25.1, 25.2.
- **Reading** (15 points): the answer is mainly in the provided sources. Items 1, 2.1, 2.2, 4.2, 5.2, 5.3, 6, 12, 13.1, 16.1, 17, 20, 22, 24.
- **Mixed** (9 points): the true/false triples plus the cartoon. Items 3, 10, 19, 18.

### Text-only input (55 points)

| Model | Protocol | Total | C | O | E | Recall/16 | Reading/15 | Mixed/9 | Closed items lost |
|---|---|---|---|---|---|---|---|---|---|
| Gemma-3-1B | v0.1 greedy | 8 (14.5%) | 4 | 4 | 0 | 3 | 3 | 2 | 2.2, 3, 19, 21 |
| Bielik-1.5B-v3 | v0.1 greedy | 15 (27.3%) | 5 | 9 | 1 | 5 | 6 | 3 | 2.2, 3, 11.2, 19 (1/2), 21 (1/2) |
| Qwen3-1.7B (think) | v0.2 T0.6 | 13 (23.6%) | 4 | 8 | 1 | 5 | 5 | 2 | 2.2, 3 (1/2), 10, 13.2, 19 (1/2), 21 (1/2) |
| Llama-3.2-3B | v0.2 | 10 (18.2%) | 3 | 7 | 0 | 6 | 3 | 1 | 2.2, 3, 10, 13.2, 19 (1/2), 21 (1/2) |
| SmolLM3-3B (think) | v0.2 T0.6 | 10 (18.2%) | 5 | 5 | 0 | 4 | 5 | 1 | 2.2, 3 (1/2), 10, 19 |
| Phi-4-mini | v0.1 greedy | 10 (18.2%) | 5 | 5 | 0 | 4 | 4 | 2 | 2.2, 10, 19, 21 (1/2) |
| **Qwen3-4B-Instruct-2507** | v0.1 greedy | **22 (40.0%)** | 7 | 12 | 3 | **5** | 8 | 6 | 3 (1/2), 10 (1/2), 11.2, 21 (1/2) |
| **Bielik-4.5B-v3.0** | v0.1 greedy | **23 (41.8%)** | 6 | 15 | 2 | **11** | 8 | 2 | 3 (0/2), 19 (0/2), 21 (1/2) |
| **PLLuM-4B-2512** | v0.1 greedy | **17 (30.9%)** | 5 | 12 | 0 | 6 | 7 | 4 | 2.2, 3 (1/2), 10 (1/2), 11.2, 19 |
| **Gemma-3-4B** | v0.1/"v0.2" greedy, no think | **20 (36.4%)** | **10** | 7 | 3 | **5** | 7 | 5 | 10 (1/2) only |
| Qwen3-VL-2B-Instruct | v0.1 greedy | 6 (10.9%) | 3 | 3 | 0 | 3 | 2 | 1 | 2.2, 3, 10 (1/2), 13.2, 19, 21 (1/2) |
| Qwen3-VL-2B-Thinking | v0.2 T0.6 | 7 (12.7%) | 3 | 4 | 0 | 3 | 4 | 0 | 21 of 34 items had no final answer |
| **LLaVA-Bielik-11B-v2.6** (text) | v0.2 greedy | **29 (52.7%)** | 5 | 21 | 3 | **14** | 8 | 4 | 2.2, 10, 19, 21 (1/2) |
| LLaVA-PLLuM-12B (text) | v0.2 greedy | 19 (34.5%) | **1** | 18 | 0 | 13 | 6 | 0 | 6 of 7 closed items lost to **format collapse** |
| Ministral-3-14B (text) | v0.2 greedy | 33 (60.0%) | 5 | 25 | 3 | 13 | 13 | 4 | 3 (1/2), 10, 19, 21 (1/2) |

The format collapse behind LLaVA-PLLuM-12B's closed score: it answered 2.2 with "A", task 3 with "1. F", task 10 with "F", and tasks 19 and 21 with "2.".

### Original page images (60 points; the "shared" column is the 34-item /55 subset)

| Model | Total /60 | Shared /55 | C | O /34 | E | Closed items lost |
|---|---|---|---|---|---|---|
| Qwen3-VL-2B-Thinking | 4 | 4 | 1 | 3 | 0 | 30/37 items had no final answer |
| Qwen3-VL-2B-Instruct | 9 | 7 | 5 | 4 | 0 | 2.2, 3, 13.2, 19 (1/2), 21 (1/2) |
| PLLuM-4B | 13 | 11 | 3 | 9 | 1 | 2.2, 3, 11.2, 19, 21 |
| Gemma-3-4B | 16 | 14 | 4 | 9 | 3 | 3, 10, 19, 21 (1/2) |
| InternVL3.5-8B (think) | 22 | 20 | 5 | 16 | 1 | 2.2 (no final answer), 10, 13.2, 21 |
| **Qwen3.5-9B (think)** | **36** | **34** | 5 | 23 | 8 | 3 (1/2), 10 (1/2), 11.2, 13.2 (no final answer), 19 (no final answer) |
| LLaVA-Bielik-11B | 14 | 12 | 6 | 8 | 0 | 2.2, 10 (1/2), 19 (1/2), 21 |
| **Gemma-4-12B (think)** | **46** | **44** | **10** | 24 | **12** | 19 (1/2) only |
| LLaVA-PLLuM-12B | 14 | 12 | 3 | 11 | 0 | 2.2, 3, 10, 19, 21 (1/2) |
| Ministral-3-14B | 29 | 27 | 7 | 19 | 3 | 10, 19 (1/2), 21 (1/2) |
| GPT "Astra" agent (reference) | 60 | 55 | 11 | 34 | 15 | none (not a controlled run) |

The site says the text-only runs for InternVL, Qwen3.5-9B and Gemma-4-12B "were stopped before completion and are not graded."

### Which item types fail

- **True/false triples that mix sources with knowledge (3, 10, 19)** are the most common closed loss for every model up to 14B.
  - Task 19 (a 1921 source plus a map): only 3 of 25 runs scored 2/2 (Qwen3-4B-2507, Gemma-3-4B-text, InternVL-image). Gemma-4-12B scored 1/2.
  - Task 3: 7 of 25 runs scored 2/2. Typical errors are a wrong island or war, and misunderstanding the censor's role.
- **Pure-recall closed items.** On task 21 (who the AK telegram was addressed to), Qwen3-4B, Bielik-4.5B and Ministral all picked Komorowski instead of Rowecki; only 5 of 25 runs scored 2/2. Task 11.2 (liberum veto abolished by the Great Sejm) was lost by Qwen3-4B (who said Sejm Niemy), PLLuM-4B and Qwen3.5-9B. **Wikipedia retrieval should fix these directly.**
- **Matching and format items (2.2).** Small models give incomplete or unparseable answers. PLLuM-4B wrote "Opis A najtrafniej oddaje sens fragmentu 3"; LLaVA-Bielik wrote "Fragment 1." after restating both descriptions.
- **Open items most often lost by all models:** 20 (Versailles), 24 (PRL propaganda campaigns), 13.1 (a battle plan), 18 (a 3-point cartoon), 9.x (Polish–Swedish wars and the Vasa succession), 5.2 (Edward III's claim to the French throne from the genealogy).
- **Essay.** Small models score 0–3 of 15. The 3 points usually come from coherence (≥300 words, structured), while the argument scores near 0 because of factual errors in 11th–12th century Piast history (invented reigns, conflated rulers). The two best essays chose topic 2 (the 18th-century revolutions):
  - Gemma-4 scored 12/15: 9/12 for argument and 3/3 for coherence.
  - Qwen3.5-9B scored 8/15.

  PLLuM-4B wrote 1851 repetitive words and scored 0/15.

---

## 4. Candidate models: closed-book baselines (B proxies)

| Candidate | Size (per the site) | Closed-book result on the mentor benchmark | Closed /11 | Recall /16 | Notes |
|---|---|---|---|---|---|
| Bielik-4.5B-v3.0-Instruct | 4.5B | **23/55 text (41.8%)** | 6 | 11 | Knows the most Polish history among models up to 5B; loses true/false triples. Peak reserved memory 9.1 GiB in BF16 |
| Qwen3-4B-Instruct-2507 | 4B | **22/55 text (40.0%)** | 7 | 5 | Low recall but decent reading (8/15) and mixed (6/9). Non-thinking only |
| Gemma-3-4B-it | 4B | **20/55 text (36.4%)**; 16/60 images | **10** | 5 | Very clean closed-format answers ("1. F 2. P 3. P"); weak open answers (7/29) |
| PLLuM-4B-instruct-2512 | 4B | **17/55 text (30.9%)**; 13/60 images | 5 | 6 | Some format slop; essay degenerates into repetition. Loads as Gemma3ForConditionalGeneration |
| Qwen3.5-9B | 9.65B total | images only: 36/60; **34/55 on the shared subset (61.8%)** | 5 | 11 | Text run not graded. Thinking cost: 83 GPU-minutes on an A100 for 37 items; 3 items had no final answer |
| Gemma-4-12B-it | 11.96B total | images only: 46/60; **44/55 on the shared subset (80.0%)** | 10 | 13 | Text run not graded. Best model overall |
| Bielik-11B (text) | ~11B | **not tested.** Proxy: LLaVA-Bielik-11b-v2.6 in text mode, **29/55 (52.7%)** | 5 | 14 | The proxy is the vision-language wrapper of Bielik-11B-v2.6 and carries a non-commercial licence; the plain Bielik-11B text model may differ |
| Qwen3-8B | 8B | **not tested** | – | – | Closest data points: Qwen3-4B-2507 at 22/55 and Qwen3-1.7B (thinking) at 13/55 |

Caveats:

- All numbers come from one run per model and are AI-graded.
- The public 2023 paper may be in the models' training data.
- Decoding differs between runs.
- n = 7 closed items, so the closed column is very noisy.
- These are CKE-paper scores. Our hackathon exam is "matura-style questions generated from Polish Wikipedia", graded automatically.

---

## 5. What this means for our choice (objective 0.8·T − 0.4·B)

1. **Switching rule.** Prefer model Y over model X only if `T_Y − T_X > 0.5 · (B_Y − B_X)`.
   - Example: Gemma-4-12B (B ≈ 80%) against Qwen3-4B-2507 (B ≈ 40%). Gemma-4 wins only if its RAG score beats Qwen3-4B+RAG by more than about 20 points. If Gemma-4+RAG reaches 90%, Qwen3-4B+RAG needs only about 70% to tie.
   - A strong closed-book model is penalised half as hard as T is rewarded, but the penalty is real.
2. **Where RAG helps, and the "low B, good reader" candidates.** Wikipedia-generated questions are mostly recall, so the RAG headroom is roughly each model's recall deficit.
   - Among models up to 5B, **Qwen3-4B-Instruct-2507** (recall 5/16, reading 8/15, mixed 6/9) and **Gemma-3-4B** (recall 5/16, reading 7/15, closed 10/11) fit the profile best: low recall but good use of provided text and good closed-answer format. They should gain the most per retrieved passage.
   - **PLLuM-4B** (B 30.9%, recall 6/16, reading 7/15) has the lowest B of the four small candidates. Its answers are sloppier, so a strict output-format harness could recover a lot.
   - **Bielik-4.5B** already knows the facts (recall 11/16), so its B on Wikipedia facts will probably be higher and its gain smaller. Its strength is Polish fluency on open answers, not headroom.
3. **Larger candidates.**
   - **Bielik-11B** (proxy recall 14/16) and **Gemma-4-12B** (recall 13/16, closed 10/11) will probably post high B. They only make sense if T approaches the ceiling.
   - **Qwen3.5-9B** (shared subset 62%) is in between, but its default thinking mode is costly and sometimes never produces a final answer. Use non-thinking mode, or cap thinking and force an answer in our harness. The mentor refuses to force an answer; we are free to.
   - Note that 12B models in BF16 exceed 8 GB on disk; see the size-rule conflict in section 6.
4. **Format sensitivity raises the gain.** B is measured on untouched output, and the graders take the explicit final selection without repairing it, so a model that is sloppy about format (LLaVA-PLLuM text: 1/11 closed; PLLuM-4B: 2.2 incomplete) posts a low B. A harness that enforces one explicit final line per sub-item (for example "1. P 2. F 3. P" or "A–3 B–2", with no self-contradiction) turns that into T. That is legitimate harness work, and it counts as gain.
5. **Thinking: off for models up to 4B.** The Qwen3-VL-2B-Thinking and Qwen3-1.7B results show small thinking models burning their budget. If we enable thinking, use vendor sampling (not greedy), cap the budget, and force a final answer after the cap.
6. **Essay** (if the final exam contains one):
   - Answer exactly one topic.
   - Write at least 300 words with an intro, body and conclusion; the 3 coherence points are nearly free.
   - Choose the topic whose facts retrieval can best support.
   - Minimise dates and names the model is unsure of, because factual errors cost up to −3.
7. **Mentor's training guidance** (verbatim):

   > "Start with 1–4.5B models and LoRA/QLoRA."

   > "Budget $30–50 per team for several small-model experiments and evaluations."

   > "Before committing funds, measure 50–100 training steps on representative small and large models."
8. **Open question to confirm with the organizers: does the "untouched" benchmark run include our harness?** The rules say "Benchmark | the score of the untouched base model ... The app checks the checksum of the untouched weights". Teams run `k3exam.py --kind base` themselves. If the benchmark must use the same harness, RAG gains cancel out of the gain term and only weight changes count. Our plan assumes B is closed-book.

---

## 6. What the sites say about the hackathon (verbatim)

**The mentor site does not mention a "geography final" or `github.com/jchnk/matura-exam`.** I searched all 30 pages, `methodology.md` and every run JSON; the only hits for "geograph" are inside model answers. `api.github.com/repos/jchnk/matura-exam` returns 404, so the repo is private or does not exist.

Hackathon-related statements on the mentor site:

- "The competition comes next. Teams choose their small model and train on their own GPUs. Final size limits, training-data rules and any tool-enabled track still need a separate decision."
- "Recommended: report both final points and improvement over the same starting checkpoint, using the same evaluation settings."
- "Use this 2023 paper to develop the benchmark and measure baselines. Reserve a separate, unreleased evaluation set for the competition."
- `methodology.md`: "## Competition decisions still open. Model size caps and whether they use parameters, weight-file size or memory; training-data rules; tool-enabled track rules; final test set; tie-break rules. Teams use their own GPUs and choose a small model."
- `methodology.md`: "The existing event website describes Wikipedia-generated questions. This real-paper proposal does not silently replace that public commitment."
- Index footer: "This methods page is a proposal for discussion. The main event site currently describes Wikipedia-generated questions; these approaches have not yet been reconciled."
- Size wording: "B means billions of parameters, not GB of memory." Also: "SmolLM3 3B and Llama 3.2 3B slightly exceed 3B total parameters. Put them in the up-to-5B category if the cutoff is strict."

The event site (warsawmodeltrainers.dev), included for context:

- Landing page: "Teams take any open model with weights up to 8 GB on disk, teach it Polish history and sit the matura live on Sunday." Also: "Pick any open model with downloadable weights up to 8 GB on disk — quantized is fine".
- FAQ and `/rules`: "Any model with downloadable open weights, up to 12B parameters". Also: "Size limit | up to 12B parameters. A RAG knowledge base doesn't count towards the limit".
- The app registration form (`/matura`) asks for "Weights size on disk (GB, max 8)".

  **The size rules conflict: 8 GB on disk versus 12B parameters.** Both are stated.
- `/rules`: "Exam | the model answers on its own. During the exam the harness may not call a closed API (GPT, Claude, Gemini etc.) or a second model beyond the limit. No internet during the exam — RAG on a local knowledge base only"
- `/rules`: "Leaderboard | from Friday 21:05 to Sunday 11:00, max one submission per hour per team. Questions are drawn from a large pool for each submission. Leaderboard scores don't count towards the result — only the benchmark and the final exam do"
- `/rules`: "Final exam sheet | separate from the practice sheet; teams see it only on Sunday at 11:00."
- `/rules`: "Benchmark | the score of the untouched base model. [...] The app checks the checksum of the untouched weights; a trained model doesn't count as a benchmark. You may switch models during the event: on Sunday the benchmark of the model that sits the exam counts"
- `/rules`: "Presentation — 20%, scored by the jury right after you present, on a card with three questions: do you know what worked and why; quality of data and method; can it be reproduced."
- The app (`/matura`) runs `python k3exam.py --set probny --kind base --key <TEAM_KEY> --label "untouched model"`. Per-question results are shown as correct or incorrect ("Green means correct, red means wrong"). Organizers upload questions "in the pytania-FORMAT.json format". The sheets are named `probny` (practice) and `finalny` (final).
