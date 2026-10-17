# harness/ — OpenAI-compatible RAG server for the matura exam

FastAPI + httpx service that sits between the organisers' exam script (`k3exam.py`) and a local
`llama-server` (llama.cpp). For every question it detects the question type, runs BM25 retrieval
over the Polish-Wikipedia KB (`kb.search.KB`), builds a Polish prompt, decodes with a llama.cpp
GBNF grammar where the format is fixed, optionally votes, and returns a normalised answer.

```
k3exam.py ──> :18000 /v1/chat/completions ──> qtype.detect ──> retrieval (kb.search.KB, BM25, RRF)
                                              └─> prompts (+grammar) ──> llama-server :18080 ──> postprocess ──> formats
          ──> :18000 /base/v1/chat/completions ──> raw passthrough to llama-server (untouched base run)
```

## Endpoints

| method | path | what |
|---|---|---|
| POST | `/v1/chat/completions` | RAG pipeline. Question = last `user` message; caller `system` messages are kept as extra instructions. Non-streaming and `stream: true` (single SSE chunk) both work; unknown fields are ignored. `model: "base"` routes to the raw passthrough instead. Optional body field `harness: {...}` = per-request config overrides. |
| POST | `/v1/completions` | same pipeline, `prompt` = question |
| GET | `/v1/models` | `wmt-matura-rag` (RAG) and `base` (passthrough) |
| POST | `/base/v1/chat/completions` | pure passthrough to the LLM (no RAG, no prompt changes), streaming ok |
| GET | `/base/v1/models` | passthrough of the LLM model list |
| POST | `/answer` | `{question, type?, config?}` -> `{answer, raw, qtype, votes, contexts, queries, parsed, latency_ms, ...}` (debug/eval) |
| GET | `/health` | LLM reachability, KB status, full effective config |

Every request is appended to `logs/harness-requests.jsonl` (question, type, raw outputs, votes, context titles, latency).

## Question types (harness/qtype.py)

`abcd` (single/multi choice), `abj` (CKE "A/B + uzasadnienie 1/2/3" -> `A2`), `pf` (prawda/fałsz list),
`chrono` (ordering), `match` (1..n -> A..m), `open` (short answer; sub-kind year/century/person/place/number/other),
`generic` (anything else). Options/statements/items are parsed from lines (`A.`, `A)`, `(A)`, `1.`, bullets,
markdown table rows) or inline (`A. x B. y C. z`).

## Output format — ONE place: `harness/formats.py`

Defaults: `B` · `B, D` · `A2` · `P, F, P` · `C, A, D, B` · `1-B, 2-A, 3-D` · short answer without trailing period
(year questions -> just the year). Change without code edits:

```bash
export FORMATS_JSON='{"pf":{"sep":"","true":"P","false":"F"},"match":{"pair":"{l}{r}"}}'
export ANSWER_WRAP='Odpowiedź: {answer}'
```

If the caller sends `response_format` json_object/json_schema, the answer is returned as JSON
(`{"<first schema property or 'answer'>": "..."}`).

## Configuration (env)

| var | default | meaning |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:18080/v1` | llama-server OpenAI base |
| `LLM_MODEL` | `bielik-11b-v3` | model name sent to the LLM |
| `BASE_LLM_BASE_URL` | = `LLM_BASE_URL` | target of `/base/...` passthrough. Repo rule: the base benchmark runs on a SEPARATE llama-server with the untouched registered GGUF (no LoRA) — set this once the RAG model differs |
| `LLM_EXTRA_BODY` | `` | JSON merged into every LLM request, e.g. `{"chat_template_kwargs":{"enable_thinking":false}}` |
| `NO_THINK_TAG` | `0` | prefix `/no_think` (Qwen3) |
| `LLM_CONCURRENCY` | `4` | parallel LLM calls (match `-np`) |
| `HARNESS_HOST` / `HARNESS_PORT` | `127.0.0.1` / `18000` | bind (use `0.0.0.0` in Docker/VM) |
| `KB_INDEX_DIR` | auto: `kb_data/index`, `kb_data/index_full`, `kb_data/index_mini` | BM25 index for `kb.search.KB` |
| `USE_KB` | `1` | 0 = no-context mode (also automatic if KB/index missing) |
| `TOP_K` / `PER_QUERY_K` | `5` / `8` | chunks kept / hits per sub-query |
| `CTX_TOKENS` | `1200` | context budget (approx tokens, `CHARS_PER_TOKEN=3.3`) |
| `CHUNK_MAX_CHARS` | `1500` | truncate each chunk |
| `TEMPERATURE` | `0` | main answer |
| `N_VOTES` / `VOTE_TEMPERATURE` | `0` / `0.6` | extra sampled answers (one request with `n`), majority/Borda vote |
| `USE_GRAMMAR` | `1` | GBNF-constrained output for closed types |
| `THINK` / `THINK_MAX_TOKENS` | `0` / `600` | short reasoning then `Odpowiedź: …` (parsed; grammar retry on failure) |
| `PF_MODE` | `joint` | `split` = one call + own retrieval per statement |
| `CHRONO_MODE` | `hybrid` | `direct` = model orders labels; `years` = ask the year of each item (grammar), sort; `hybrid` = years + direct order as tie-break (best: 71% vs 43% direct on dev-a/c chrono with KB) |
| `KEEP_CALLER_SYSTEM` | `1` | append caller's system prompt as extra instructions |
| `FORMATS_JSON`, `ANSWER_WRAP` | | see above |

Every config key can also be overridden per request: `/answer {"question":..., "config":{"n_votes":4}}`,
or `{"harness": {...}}` in a chat-completions body; `devset/eval.py --cfg key=value` uses this.

### Harness v2 flags (all OFF by default = the behaviour above, bit-for-bit)

| var | default | meaning |
|---|---|---|
| `QTYPE_V2` | `0` | command-aware type detection (`harness/qtype.py: detect_v2`): (a) „Dokończ zdania 1. i 2.” with one A–D list per sentence -> new type `abcd_parts`, answer `1-B, 2-C` (grammar per sentence); (b) numbered/lettered items wrapped onto several lines are joined (full P/F statements); (c) letter->number table fill („obok opisu wpisz numer fragmentu”, answer `A-3, B-2`) and `Fragment N:`/`Fragment A:` blocks are `match`, never `abcd`; „Podaj literę A albo B” without option lines -> `abcd`; (d) new type `explain` for wyjaśnij / uzasadnij / rozstrzygnij+uzasadnij / porównaj / podaj nazwisko i wyjaśnij: 1–3 sentences, no newline stop, answer-sheet labels kept on their own lines (`Rozstrzygnięcie: …` / `Uzasadnienie: …`, `Nazwisko:`/`Wyjaśnienie:`, `Podobieństwo:`/`Różnica:`), `EXPLAIN_MAX_TOKENS` (400), `FORMATS["explain"].max_chars` 1500; (e) the type is detected on the final command (from the last line starting with a command verb, plus the question's own list right above it), not on the source excerpts; retrieval keeps the v1 stem (sources + command), the reranker query is command + options + sources. Identical parse to v1 on all dev-a..h items (unit-tested). |
| `RERANK` | `0` | cross-encoder rerank after BM25/RRF: top `RERANK_TOPN` (24) RRF candidates (BM25 `RERANK_PER_QUERY_K`=12 hits/query) scored against the question (stem + options/statements/items + sources, 900 chars) by **bge-reranker-v2-m3 GGUF (Q8_0, 636 MB)** on a separate `llama-server --reranking`; the prompt gets the best `RERANK_KEEP` (0 = `TOP_K`) chunks within `CTX_TOKENS`. `RERANK_ITEM_SLOTS=1` (off): each per-item query first gets its own best chunk (cross-encoder over its top-6 hits) -- measured worse (ctx recall 0.760 vs 0.868). `RERANK_TYPES` (empty = all) restricts reranking to a comma list of qtypes. Any reranker error -> falls back to the old RRF order. |
| `RERANK_URL` / `RERANK_MODEL` | `http://127.0.0.1:18092` / `bge-reranker-v2-m3` | llama-server rerank endpoint (`POST /v1/rerank`) |
| `RERANK_DOC_CHARS` / `RERANK_TIMEOUT` | `700` / `60` | chunk prefix sent to the reranker / HTTP timeout |
| `RERANK_BACKEND` | `llama` | `st` = sentence-transformers `CrossEncoder(RERANK_ST_MODEL)` on MPS/CUDA/CPU, offline (`HF_HUB_OFFLINE=1`); fallback only, needs torch + the model in the local HF cache (not installed in the Mac venv, untested) |
| `QUERY_REWRITE` | `0` | the answering LLM writes 1–2 search queries (keywords / likely article titles) that are added to the BM25 queries: `1` = only when the command has no named entity or year, `2` = always. One extra short LLM call (48 tokens). |

#### Essay mode (`QTYPE_V2=1`, type `essay`, `harness/essay.py`)

Detection (`qtype.is_essay`, on the whole text because CKE prints source materials after the topics): one strong
signal — „minimum/co najmniej N wyrazów”, „Zadanie zawiera trzy/pięć tematów”, „Wybierz jeden z nich do
opracowania”, „Zajmij stanowisko wobec … tezy … uwzględniając”, „Napisz wypracowanie/esej/rozprawkę/wypowiedź
argumentacyjną”, „w formie eseju/rozprawki”, a `WYPRACOWANIE` line, `(0–12)`/`(0–15)`/`(15 pkt)` — or two weak ones
(a bare „esej”/„rozprawka”/„wypracowanie”/„zajmij stanowisko”/„tematy”/„300 wyrazów”). A short item that only
quotes „fragment eseju” stays a short item. Topics = the numbered `1.`–`5.` items (`pq.topics`); aspects are parsed
from „aspekty: polityczny, społeczno-gospodarczy i kulturowy” / „w aspekcie …”.

Per topic: BM25 (+ reranker) queries = thesis, thesis + each aspect (`item:` slots, so each aspect gets its own
best chunk), the rest of the command when there are no aspects, entities; budget `ESSAY_CTX_TOKENS` (4500),
`ESSAY_TOP_K` (12) chunks, `ESSAY_RERANK_TOPN` (40). The topic with the best coverage (share of thesis terms found
in the chunks, averaged with the mean sigmoid rerank score of the top 6; ×0.6 when the topic needs source
materials that are not in the input) is written; `ESSAY_TOPIC=N` forces one. One call: essay system prompt +
chunks + the chosen topic + a rubric-shaped instruction (header line, stance in the intro, one 5–7-sentence
paragraph per aspect with facts tied to the thesis, conclusion, 450–700 words, only supported facts, stay inside
the topic's period). `ESSAY_MAX_TOKENS` 1400, `ESSAY_TEMPERATURE` 0.3, DRY sampler (`ESSAY_DRY_MULTIPLIER` 0.5,
`ESSAY_DRY_ALLOWED` 6; `ESSAY_REPEAT_PENALTY` 1.0 — a token repeat penalty made Bielik-4.5B misspell repeated
names), seed 42. Under `ESSAY_MIN_WORDS` (350; the CKE floor is 300, our count may differ slightly) `ESSAY_FALLBACK=sections` (default) writes it again part by part — intro with the stance (400 tokens), one 6–8-sentence call per aspect paragraph (700 tokens; each call sees the text so far and is told not to copy it), conclusion (400) — and the longer version is kept (`rewrite` = one "write it longer" call, `none` = off).
Clean-up: header/labels/headings/bullets removed, verbatim repeated sentences dropped (near-verbatim ones too,
>= 80% shared word trigrams, except in the conclusion), unfinished last sentence of a section cut, intro and
conclusion sections capped at 5 sentences (body 10), a „Przykład:” paragraph joined to the one above, text after the
conclusion („Dodatkowe argumenty:”) cut, `WYPRACOWANIE na temat nr X` prepended. `ESSAY_LORA_OFF=1` (default)
sends `"lora": [{"id": i, "scale": 0}]` for every adapter listed at `GET /lora-adapters` (the adapters were trained
on short answers only); nothing is sent when none is loaded. Needs ≥ ~8k tokens of context per llama-server
slot. `/answer` returns `parsed.essay` (topic, per-topic scores, words, expanded, finish, lora_off).
Dev set: `python devset/build_cke_essays.py` → `devset/cke-essays.jsonl` (git-ignored); generation:
`devset/run_essays.py --mode raw|harness`; tests: `python -m unittest tests.test_essay`.

Reranker server (Mac; on the VM use the CUDA build, same flags):

```bash
# model: gpustack/bge-reranker-v2-m3-GGUF, file bge-reranker-v2-m3-Q8_0.gguf -> models/bge-reranker-v2-m3/
bin/llama/llama-b11185/llama-server -m models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf --reranking \
  --host 127.0.0.1 --port 18092 -ngl 999 -c 32768 -b 8192 -ub 8192 -np 16 --alias bge-reranker-v2-m3
RERANK=1 QTYPE_V2=1 harness/scripts/start_harness.sh
python -m kb.eval_rerank devset/dev-a.jsonl devset/dev-b.jsonl --topn 24,48     # source-article recall with/without rerank
python -m unittest tests.test_qtype -v                                          # type-detection tests (CKE cases need devset/cke-*.jsonl)
```

(Port 18090 is taken by the panel on the Mac, hence 18092.)

Source-article recall, dev-a,b,c,f,g,h (409 q, `python -m kb.eval_rerank`, 25.09 23:10, shared GPU):

| retrieval | R@1 | R@5 | R@10 | source article in the prompt (TOP_K=5, 1200 tok) | extra latency / q |
|---|---|---|---|---|---|
| BM25 multi-query + RRF + item/option slots (current) | 0.489 | 0.861 | 0.936 | 0.729 | – (BM25 ~0.25 s) |
| + rerank top-24, no item slots (**default when RERANK=1**) | **0.709** | **0.914** | 0.946 | **0.868** | ~2.8 s p50 on the shared M4 Max (incl. slot calls below) |
| + rerank top-48, no item slots | 0.689 | 0.914 | 0.954 | 0.866 | |
| + rerank top-24 with per-item slots | 0.504 | 0.885 | 0.946 | 0.760 | |

R@5 by type (BM25 -> rerank24): chrono 0.76 -> 0.94, match 0.63 -> 0.88, pf 0.95 -> 1.00, abcd 0.92 -> 0.90, open 0.87 -> 0.85.

`QUERY_REWRITE` (Bielik 11B writes the queries): mode 1 fires on 38/409 dev questions; on those R@5 0.763 -> 0.763,
R@10 0.895 -> 0.868, in-prompt 0.526 -> 0.474. Mode 2 (always, 60-q sample): R@1 0.550 -> 0.517, R@5 0.883 -> 0.867.
Bielik often answers the task or adds a preamble instead of queries. No gain -> keep `QUERY_REWRITE=0`.

End-to-end, fixed 150-item mix (`devset/cke-hv2mix150.jsonl`: 110 dev-a/c/f/g/h + 40 auto-gradable CKE items),
Bielik-11B-v3 Q4_K_M on :18080, extract accuracy, `devset/compare_hv2.py`, rows `hv2-*` in `devset/experiments.csv`:

| type (n) | defaults | + `QTYPE_V2` | + `QTYPE_V2` + `RERANK` |
|---|---|---|---|
| abcd (35) | 0.943 | 0.943 | 0.914 |
| chrono (25) | 0.640 | 0.640 | 0.800 |
| match (28) | 0.536 | 0.643 | 0.714 |
| open (34) | 0.676 | 0.794 | 0.765 |
| pf (28) | 0.679 | 0.679 | 0.714 |
| dev items (110) | 0.764 | 0.764 | 0.818 |
| CKE items (40) | 0.550 | 0.725 | 0.700 |
| **overall (150)** | **0.707** | **0.753** | **0.787** |
| points | 152/223 | 161/223 | 173/223 |

QTYPE_V2 was run on the 40 CKE items only: on the 110 dev items its parse, queries and prompts are identical to v1
(unit test + old-vs-new dump over 656 items with all flags off: 0 differences), so those rows reuse the defaults run.
Latency on the shared Mac GPU was 66–104 s/question (queueing behind other agents); the reranker adds ~2.8 s p50/question there. Fixed A/B mix: `python devset/build_hv2_mix.py` ->
`devset/cke-hv2mix150.jsonl` (+ `cke-hv2mix60`, `cke-hv2cke40`; git-ignored because they contain CKE items).

### Harness v3: `CKE_MODE=1` (OFF by default; every v1/v2 path is unchanged when off)

For an exam graded like CKE (rubric, essay), where correctness, source use and essay quality score and format
tricks do not. Builds on the v2 detector (implies `QTYPE_V2` detection). Code: `harness/cke.py` (pure helpers),
`harness/cke_essay.py` (essay helpers), `harness/cke_flow.py` (LLM flows); tests: `tests/test_cke.py`.

| type | v3 behaviour |
|---|---|
| abcd, abj, pf, match, abcd_parts | assistant turn prefilled `Rozumowanie:` (Bielik otherwise answers first, justifies after), 2–4 sentences with source + retrieved facts, final line `Odpowiedź: …`; the LAST explicit answer is parsed; grammar-constrained answer (reasoning kept as context) only when it cannot be parsed. No newline stop. |
| names (`Fragment A –` sheet, `przyporządkuj władcę/państwo`, `wpisz obok opisu nazwę`, colon-labelled short answers) | names, not `1-B`: `Fragment A – Wacław II; Fragment B – Brzetysław I` on ONE line |
| `Rozstrzygnij … uzasadnij` | variants read from the command (`(A czy B)`, `– A czy B –`, `przed reformą … czy po niej`, `który z fragmentów 1–3`, `baroku czy klasycyzmu`, else yes/no) -> per cited source a separate retrieval + `Kto/Co/Kiedy/Gdzie` call (prefilled `Kto:`) -> ONE call with those findings (default `CKE_DECIDE_MODE=summaries`): verdict line prefilled `Rozstrzygnięcie:` (similar-topic/different-event warning, BC/AD rule), justification naming concrete elements of each cited source; yes/no: `Tak` only if P(Tak) of the verdict token >= `CKE_YES_THRESHOLD`, otherwise the justification is rewritten for `Nie`. The sheet label always gets the variant (`Rozstrzygnięcie: po reformie`), never a bare `Tak` for a non-yes/no command. `compare` (a written comparison, then a constrained verdict) was worse on the dev decisions (yes/no 3/8 vs 5/8 on mentor 2023 + CKE 2025; summaries: 17/24 decisions right on the first 24 of 30 dev items). |
| explain / compare / `podaj nazwisko i wyjaśnij` | quote or paraphrase each indicated source + 1–2 context facts, sheet labels kept (repeated labels ok), similarity/difference stated in own words first, granularity hints (state not city, name + epithet, dynasty, full historiographic name) |
| open / generic | short reasoning, `Odpowiedź: …`, granularity hints |
| essay | topic with best retrieval coverage (topics whose frame the passages miss lose 10%) -> plan (concrete elements for `trzy wybrane …` topics, `n+3` candidates filtered to the topic's time frame, fill from in-frame article titles; aspects otherwise) + alternative for `najbardziej`-type theses -> intro (explicit stance appended when the model hedges) -> one paragraph per element from its OWN retrieval (2–3 dated facts, tie-back sentence; aspect paragraphs prefilled `W aspekcie militarnym`) -> comparison with the alternative -> conclusion -> verification (sentences with years/names absent from the passages or outside the frame are dropped; the first sentence and paragraphs under 3 sentences keep the sentence with the date removed) -> one `WYPRACOWANIE na temat nr X` line, no copied prompt, trimmed to ~650 words. Every call stays far below 8k tokens. |

LoRA: every CKE generation sends per-request `lora` scale 0 (`CKE_LORA_TYPES` lists qtypes that keep the adapter;
default none). The v2 year-grammar chrono path is kept as is.

| var | default | meaning |
|---|---|---|
| `CKE_MODE` | `0` | harness v3 |
| `CKE_REASON_MAX_TOKENS` / `CKE_EXPLAIN_MAX_TOKENS` | `300` / `380` | reasoning (closed/open/names) / explanation and justification budgets |
| `CKE_SOURCE_CTX_TOKENS` / `CKE_SOURCE_TOP_K` | `700` / `3` | per-source retrieval for decisions |
| `CKE_DECIDE_MODE` | `summaries` | decisions: `summaries` (per-source findings + one verdict/justification call), `direct` (one call, no per-source step), `compare` (findings -> written comparison -> constrained verdict -> justification) |
| `CKE_YES_THRESHOLD` | `0.7` | min P(Tak)/(P(Tak)+P(Nie)) for `Tak` (0 = free answer) |
| `CKE_LORA_TYPES` | `` | qtypes that keep the LoRA adapter in CKE mode |
| `CKE_ESSAY_PART_CTX_TOKENS` / `CKE_ESSAY_PART_TOP_K` | `1900` / `6` | per-paragraph retrieval |
| `CKE_ESSAY_VERIFY` / `CKE_ESSAY_MAX_WORDS` | `1` / `650` | verification pass / trim target |
| `ESSAY_SAFE` | `0` | essay safe mode (off = essay output byte-identical, `tests/test_essay_safe.py`): a month/day must stand next to its year in one retrieved passage and a year within 250 chars of an entity of the sentence (else cut out, sentence dropped when nothing concrete is left); body prompts ask for at most 2 plain years; best of two topics by unsupported claims per 100 words (`parsed.essay.safe`) |
| `ESSAY_SAFE_MIN_WORDS` / `ESSAY_SAFE_BUDGET` | `450` / `90` | candidates below this length lose the comparison / the second topic is skipped when the first took over half the budget (s) |

Run on the Mac: `devset/cke_full/run_v3.sh start|run PAPER…|stop` (llama-server :18089 with the LoRA loaded,
harness :18009, shared reranker :18092).

### Harness v4: fixes from `docs/error_map_v2.md` on top of v3 (all OFF by default)

Code: `harness/v4.py` (flags, pure helpers), `harness/v4_flow.py` (LLM flows), hooks in `cke_flow.run`,
`retrieval.retrieve` and `pipeline._chrono_years`. With every v4 flag off the prompts are byte-identical to v3:
`tests/test_v4.py` replays 11 synthetic items x 4 configs (v1, v2+rerank, v3, v3 no-KB) against
`tests/fixtures/v3_prompts.json`, recorded from the pre-v4 code (`tests/v3_golden.py`). `V4=1` turns on the fixes in
`harness.v4.V4_UMBRELLA`; a flag set to `0`/`1` wins over `V4`, `-1` (default) follows it. Every flag is also a
per-request override (`--cfg v4=1`, `--cfg v4_title_rescore=1`).

| var | in `V4=1` | what |
|---|---|---|
| `V4_ABCD_PARTS` | yes | `abcd_parts` ('Dokończ zdania 1. i 2.') -> each sentence as its own abcd item (own retrieval + reasoning), answers joined `1-B, 2-C` |
| `V4_CONTINUE` | yes | closed item whose reasoning is cut before `Odpowiedź:` -> the assistant turn is continued with `Odpowiedź:` (the model finishes its own conclusion) before the v3 grammar retry (which answered `A` after long option-by-option reasoning) |
| `V4_TITLE_RESCORE` | yes | raw-title re-scoring of the reranked candidates: `+V4_TITLE_BONUS` (1.5 logit) for an event/document title the question names whole ('Wojna trzydziestoletnia', 'III rozbiór Polski'; ordinal words = numerals), `-V4_TITLE_PENALTY` (4) for a different Roman numeral ('I wojna punicka' for 'II wojny punickiej', 'Rozbiory Polski' for 'III rozbiór Polski', 'II wojna trzydziestoletnia' for 'wojny trzydziestoletniej'); a ruler's inner numeral the question omits ('Bolesław I Chrobry') is not penalised. No index rebuild (the BM25 tokenizer drops a lone 'I'). P/F statements are not used as the reference (a false statement names the distractor). |
| `V4_NEUTRAL_EXAMPLES` | yes | answer-format examples in the question and in our own instruction -> placeholders before the model sees them (`1-B, 2-A` -> `1-X, 2-X`, `np. B, A, D, C` -> `np. X, X, X, X`, `P, F, P` -> `P/F, P/F, P/F`) |
| `V4_SOURCE_FIRST` | no | items with a source: short Kto/Co/Kiedy/Gdzie call on the source alone, then BM25/reranker queries from that identification + the command (no P/F statements, no ABCD options) |
| `V4_PF_EVIDENCE` | no | every F needs a verbatim contradicting sentence from the context/source (checked against the passages), else P; value-first line for statements with a number/date/quantifier |
| `V4_PF_VALUE` | no | statements with a number/date/quantifier judged P are re-checked value-first (P->F only with a verified quote) |
| `V4_CHRONO_BC` | no | `1`: year grammar also accepts ` p.n.e.`, unsigned year -> BC when the item/stem says p.n.e. or the context writes that year as 'Y p.n.e.'; `2`: the prompt asks for 'p.n.e.' too |
| `V4_CHRONO_TIES` | no | items tied on the year: `1` month/day question, then pairwise 'which was earlier' with context; `2` pairwise only |
| `SC_K` / `SC_TEMPERATURE` | no (`1`) | closed items: greedy + K-1 samples of the same model at T, per-sub-answer majority |

Measured on the L40S (26.09, Bielik-4.5B Q8_0 on the shared :18093, v3 = `CKE_MODE=1 QTYPE_V2=1 RERANK=1`) on the
items the error map lists; each run once. The shared server is non-deterministic at T=0 (4 of 12 items with
identical prompts flipped between two runs of the same retrieval), so differences of 1-3 items are noise:

| fix | test | v3 | v4 |
|---|---|---|---|
| abcd_parts | 20 synthetic 2-part items from dev abcd | 18/20 | 14/20 without `V4_CONTINUE` (split calls fell back to grammar 'A'), 18/20 with it |
| title rescore | source article in the prompt, all 409 dev items (no LLM) | 354 | 362 (+10/-2; bonus 3: +10/-2, penalty only: +1/0) |
| title rescore | 19 error-map items without the source article | 8/19 | 7/19; context changed on 7 items: fixed dev-a-010, dev-h-011, broke dev-h-042; the other flips had identical prompts |
| neutral examples | 12 failing match items | 1/12, pairs 0.39 | 2/12, pairs 0.48 (v3's own `1-A, 2-A, 3-A` example made 7/12 answers start with `1-A`) |
| neutral examples | all 62 dev chrono items (no example in the direct-order prompt either) | 18/62 | 21/62 |
| `V4=1` | 5 passing match items with a format example | 2/5 | 3/5 |
| `V4=1` | 13 closed CKE 2025 items | 9/13, 12/16 pts | 10/13, 13/16 pts |
| `V4=1` | 11 held-out CKE 2023/24/26 closed items (one run, no tuning) | 1/11, part 0.39 | 0/11, part 0.46; cke23-21 `1-D, 2-B` -> `1-A, 2-C` (gold `1-B, 2-C`) |
| source first | 13 closed CKE 2025 items | 9/13, 12/16 pts | 7/13, 8/16 pts |
| P/F evidence | 22 failing P/F items | 4/22, stmt 0.667 | 3/22, stmt 0.655 (the model nearly always finds some verbatim sentence, so few F change) |
| P/F value | 22 failing P/F items | 4/22, stmt 0.667 | 2/22, stmt 0.553 |
| chrono BC | 32 failing chrono items | 5/32 | 5/32 (`2`: 4/32); v3 without LoRA already writes negative years (dev-a-009 correct in v3) |
| chrono ties | 32 failing chrono items (28 tied groups) | 5/32, direct order right in 16/28 groups | month/day+pairwise 4/32 (13/28 groups), pairwise only 4/32 |
| SC_K=5, T=0.7 | 20 failing P/F + match items / 20 passing P/F items | 0/20 / 13/20 (stmt 0.896) | 3/20 / 14/20 (stmt 0.887): +4 of 40, inside the rerun noise, 5x closed-item calls -> off |

## Run (Mac, dev)

```bash
cd ~/wmt-matura
harness/scripts/start_llama.sh bielik          # llama-server :18080 (Metal, -ngl 999 -c 16384 -np 4 -kvu)
harness/scripts/start_llama.sh qwen3           # optional, :18081, thinking disabled via chat-template-kwargs
harness/scripts/start_harness.sh               # harness :18000 -> :18080
HARNESS_PORT=18001 TAG=qwen LLM_BASE_URL=http://127.0.0.1:18081/v1 LLM_MODEL=qwen3-8b harness/scripts/start_harness.sh

curl -s localhost:18000/health | python -m json.tool
curl -s localhost:18000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"wmt-matura-rag","messages":[{"role":"user","content":"W którym roku odbyła się bitwa pod Grunwaldem?"}]}'
```

`SNAPSHOT_KB=1 harness/scripts/start_harness.sh` clones `kb_data/index` (APFS `cp -c`, instant) into `harness/_kb_snapshot/` first:
the KB is numpy-memmapped and an in-place rebuild of `kb_data/index` kills a running harness (SIGBUS).

Laptop -> Mac sync: `bash harness/scripts/sync_to_mac.sh` (harness/ + devset/eval.py + devset/smoke.jsonl).

## Evaluate

```bash
python devset/eval.py --files devset/smoke.jsonl --endpoint base   --label base-raw      # untouched model
python devset/eval.py --files devset/smoke.jsonl --endpoint answer --label harness       # RAG pipeline
python devset/eval.py --endpoint answer --cfg use_kb=0 --cfg n_votes=4 --label nokb-v4    # A/B without restart
python devset/eval.py --endpoint chat   --label via-openai-api                             # through /v1/chat/completions
python devset/eval.py --endpoint openai --url http://127.0.0.1:18080/v1 --label llama-direct
```

Scores: `strict` (exact after trivial normalisation), `extract` (answer parsed out of free text), `lenient`
(open answers: gold contained in prediction). Per-question output -> `devset/runs/`, summary row -> `devset/experiments.csv`.
`harness/scripts/run_smoke.sh` runs base vs harness on the smoke set.

## Production (L40S VM)

Same code; start llama-server from a CUDA build with the same flags (`LLAMA_BIN=... HOST=127.0.0.1 harness/scripts/start_llama.sh bielik`),
then `HARNESS_HOST=0.0.0.0 harness/scripts/start_harness.sh`. Consider `NP=8`, larger `CTX_TOKENS` and `N_VOTES`
(prompt processing is ~10x faster than on the Mac).

## Measured (Mac M4 Max, Bielik-11B-v3 Q4_K_M, shared GPU, 25.09 evening)

dev-a + dev-c (147 q, 211 pts, generated from Wikipedia):

| run | strict acc | points | avg latency |
|---|---|---|---|
| base raw passthrough (`--endpoint base`, max 160 tok) | 0.163 (extract 0.510, lenient 0.612) | 39 (extract 103) | 2.9 s |
| harness, no KB | 0.633 | 126 | 5.5 s |
| harness, KB (CTX_TOKENS=1200, TOP_K=5), chrono direct | 0.844 | 168 | 18.8 s |
| chrono+match subset (36 q), KB, chrono direct -> hybrid | 0.611 -> 0.778 | 44 -> 56 /72 | 17.5 -> 29.7 s |

Per type with KB: abcd 1.00, open 0.90, match 0.87, pf 0.79, chrono 0.43 (0.71 with `hybrid`, now default).
Latency is dominated by prompt processing (~420 tok/s on the Mac, shared with other agents' requests);
the L40S should be >10x faster. Full rows: `devset/experiments.csv`.

## Tryb wsadowy / exam runner (`harness/batch.py`, `scripts/run_exam.sh`)

Organizatorzy ogłaszają dokładną procedurę egzaminu dopiero rano w dniu egzaminu, więc `batch.py` nie
zakłada ich formatu -- czyta JSON (lista albo `{"questions":[...]}`), JSONL, CSV i zwykły `.txt`
(pytania oddzielone pustą linią), z tolerancją na nazwy pól: `id`/`qid`/`nr`, `question`/`text`/`tresc`/`pytanie`,
`type`/`typ`, `points`/`pkt`.

```bash
python -m harness.batch questions.json  --mode harness --out results/run1        # RAG, POST /answer
python -m harness.batch questions.jsonl --mode base    --out results/run1        # goły model: /base/v1/chat/completions,
                                                                                  # bez system promptu, temp 0, <think> ucięty
python -m harness.batch questions.csv   --both --concurrency 8 --out results/run1  # oba tryby, dwa komplety plików
```

Ich `type` mapowany jest na nasze typy i wysyłany jako podpowiedź do `/answer`: `single`/`choice`/`abcd`
-> `abcd`, `truefalse`/`tf`/`pf` -> `pf`, `order`/`chronology` -> `chrono`, `match`/`matching` -> `match`,
`open`/`short` -> `open`; nieznany `type` przechodzi bez zmian (log dostaje `type_note`).

Wynik na tryb: `<out>_<mode>.json` (`{"answers":[{id,answer,raw,latency_s,error}],"meta":{mode,model,started,
finished,n,errors,...}}`, albo `--format simple` -> `{id: answer}`), `<out>_<mode>.csv` (`id,answer`) i
`<out>_<mode>.jsonl` (log na bieżąco -- to on jest źródłem resume: ponowne uruchomienie z tym samym `--out`
pomija już odpowiedziane id, powtarza tylko te z błędem, chyba że `--resume-errors-too` (też pomiń) albo
`--no-resume` (od zera)). Timeout per pytanie (`--timeout`, domyślnie 120 s) -> pusta odpowiedź + błąd w logu,
reszta batcha jedzie dalej.

`scripts/run_exam.sh questions.json <etykieta> [-- dodatkowe flagi batch.py]` w jednym poleceniu: sprawdza
`/health` llama-servera i harnessu, odpala `batch.py --both`, i zapisuje `results/<timestamp>_<etykieta>/`
z README: dokładne ustawienia, health w chwili uruchomienia i sha256 + rozmiar każdego `*.gguf` pod `models/`
(ostrzeżenie, gdyby ktoś przekroczył limit 8 GB z CLAUDE.md).

Przetestowane na żywym harnessie (Bielik 11B, `:18000`) na osobnej kopii `~/wmt-matura-batchtest` na Macu
(tar-over-ssh, `~/wmt-matura/harness` nietknięty): 10 pytań z `devset/dev-a.jsonl` zbudowanych w formacie
JSON/JSONL/TXT organizatorów z przemapowanymi typami -- parsowanie, aliasing i resume działają poprawnie;
odpowiedzi ocenione `devset/eval.py`'s `grade()` (8/10 `extract`, pomyłki na `pf`/`chrono` zgodne z sekcją
"Measured" powyżej, nie z formatem) potwierdzają, że wyjście jest w kanonicznym formacie do oceny.
