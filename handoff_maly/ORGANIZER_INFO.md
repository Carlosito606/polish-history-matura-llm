# Organizer information — Warsaw Model Trainers, Kolektyw3, 25–27.09.2026

Collected by team Vibers from the organizers' public pages and official messages (Telegram / chat), 26.09.2026 evening.
Credit/redeem codes are redacted. Always re-check the live pages and the Telegram group: rules were clarified during the event.

## Links

| What | URL |
|---|---|
| Event home | https://warsawmodeltrainers.dev/ |
| Full rules | https://warsawmodeltrainers.dev/rules |
| App: team registration, practice leaderboard (`#board`), final exam lock | https://warsawmodeltrainers.dev/matura.html (also /matura) |
| **Submission page for answers.json** (TEAM_KEY + solution name, choose Mock/Final) | https://warsawmodeltrainers.dev/submissions.html |
| JSON exam guide (how the mock/final pack looks, answer rules) | https://matura-json-guide.ania-olchowik.chatgpt.site/ |
| Organizers' benchmark / method (2023 paper, many models, per-model pages) | https://warsaw-matura-method.ania-olchowik.chatgpt.site/ |
| Telegram (official channel) | https://t.me/warsawmodeltrainers |
| Presentations (opening) | (organizers' link, not republished) |
| Model benchmark slides | (organizers' link, not republished) |
| Luma event pages | https://luma.com/Warsaw-Model-Trainers-hackathon , https://luma.com/Warsaw-Model-Trainers-w3 |
| Quesma talk (PDF) | https://www.dropbox.com/scl/fi/rto9myykq76rq95raoru4/20260925-matura-hackathon-talk.pdf?rlkey=34h9ypvx2rnz0ggv4j49z73we&dl=0 |
| Compute | Labqoat/Forgehand https://app.forgehand.app/ ; Nebius (ask Gleb on Telegram); Modal free tier; own GPUs allowed |

## Official messages (verbatim, codes redacted)

**"Warsaw Model Trainers - ALL IMPORTANT INFO"** (25.09 evening): hackathon started; join Telegram
https://t.me/warsawmodeltrainers ; presentations (Drive link above); Model Benchmark (slides link above); register your
team at https://warsawmodeltrainers.dev/matura.html ; credits: Quesma (talk PDF), Labqoat https://app.forgehand.app/ ,
Nebius (ask Gleb on Telegram), Cursor [redeem link redacted], Solari 1 month [code redacted], docs http://docs.getsolari.com .

**Model size (Piotr Migdał, organizers, Telegram, 26.09):**
> 8GB total weight size; no matter how many parameters, as long as you quantize it to be 8GB or below.
> 8gb without LORA adapter and before you start your work. Final submitted model after your work can exceed 8gb.

**Several models (organizers, confirmed to our team 26.09 ~21:45):** any number of models may be used during the exam as long as EACH model is at most 8 GB on its own (e.g. an answering LLM plus a separate vision model that only describes images). This supersedes the rules-page line "no secondary models beyond the 12B limit".

**Categories (organizers, 26.09 ~12:00):** a team may apply to ALL categories. Categories from the opening deck:
**Best matura score**, **Best progress** (gain of the trained system over the untouched base), **"Mały, ale wariat"**
(the smallest model that scores at least 35%). Whether "smallest" is measured in GB of weights or in parameters was not
stated explicitly — the registration form asks for disk size (max 8 GB), so GB is the likely unit. **Ask on Telegram.**

**Testing explained (organizers, 26.09 ~12:00):**
> each team will download a package with test questions (json + .png images) and a template for answers (also json).
> You will run your model/harness "locally" (AWS, modal, your machine) and send us back the answers.json
> https://matura-json-guide.ania-olchowik.chatgpt.site/

Grading: organizers grade the answers.json with an LLM against the CKE rubric (roughly every 30 minutes for the mock).
The mock pack = CKE May 2023 history paper, 37 items, 60 points, 19 PNGs, **no image descriptions**. Its README is in
`ORGANIZERS_MOCK_README.md` next to this file. The final is a separate pack/exam_id, unlocked Sunday 11:00.

## Rules page (https://warsawmodeltrainers.dev/rules), key points as fetched 26.09 ~21:30

- Submissions through the app; teams of 1–4; lineup by Sat 16:00; register the base model (name, weights link, size);
  submit the untouched model as benchmark AND the trained version; the app verifies the checksum of the untouched weights.
- **Stop at Sunday 11:00**; exam + stage presentations from 11:00 (2–3 min talk + 1–2 min questions, PL or EN);
  13:00 panel, 14:00 results.
- Base model: open downloadable weights; the page still says max 12B parameters — superseded by the 8 GB clarification
  above ("no matter how many parameters"). RAG knowledge bases do not count toward the limit.
- Exam conditions: models answer independently; **no closed APIs (GPT/Claude/Gemini) during the exam**; "no secondary
  models beyond the 12B limit"; no internet; RAG from local knowledge bases only.
- Training data: any legally accessible source; synthetic data from any LLM allowed; closed APIs OK for training;
  Wikipedia-derived datasets under CC BY-SA compatible licence.
- Attempting to obtain the final exam sheet = disqualification. All judged work made during the hackathon.
- **Submission by Sunday 11:00:** team list; both models (untouched + frozen trained version with harness); GitHub repo
  (public, or private with read access for organizers/jury); `SOURCE.md` with exactly
  "Made during the Warsaw Model Trainers hackathon, Kolektyw3, 25–27.09.2026"; training code, harness code, data scripts,
  source lists, reproducible README. Unpublished work is not evaluated.
- Data: no republishing of copyrighted content (textbooks, CKE papers…) — link + processing scripts instead.
- Scoring for the main ranking: 40% final exam, 40% progress over the benchmark, 20% presentation (jury: Gleb Badzeika
  (JetBrains), Jacek Migdał (Quesma), Paulina Jóśków (Kolektyw3)). "Small models with significant improvement can outscore
  larger static models."
- Disqualification: closed API in the exam harness, model over the limit, missing untouched benchmark, commercial use of
  third-party data, data rule violations, trying to get the final sheet, pre-hackathon training, missing SOURCE.md.

## App / leaderboard snapshot (26.09 ~21:30)

Practice leaderboard: 23 teams registered. Visible small-model competitors: **Tarasiuk Lab — Qwen/Qwen2.5-3B-Instruct**
(practice best 15/15), **Dry Run Team — speakleash/Bielik-1.5B-v3.0-Instruct** (8/16 tuned). Practice scores do not count.

## Organizers' benchmark (warsaw-matura-method) — text track, CKE May 2023, 55 points

| Model | Score |
|---|---|
| Ministral-3-14B | 33/55 (60.0%) |
| LLaVA-Bielik-11B | 29/55 (52.7%) |
| Bielik-4.5B | 23/55 (41.8%) |
| Qwen3-4B-Instruct-2507 | 22/55 (40.0%) |
| Gemma-3-4B | 20/55 (36.4%) |
| PLLuM-4B | 17/55 (30.9%) |
| Bielik-1.5B-v3 | 15/55 (27.3%) |
| Qwen3-1.7B (thinking) | 13/55 (23.6%) |
| Llama-3.2-3B | 10/55 (18.2%) |
| Gemma-3-1B | 8/55 (14.5%) |

Image track (original page images, 60 points): Gemma-4-12B 46 (76.7%), Qwen3.5-9B 36 (60.0%), Ministral-3-14B 29 (48.3%).
More detail and per-item notes: `docs/mentor_benchmark_notes.md` in this repo.
