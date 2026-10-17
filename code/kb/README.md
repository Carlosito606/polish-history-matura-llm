# kb/ — Polish Wikipedia knowledge base + lexical retrieval

Offline RAG knowledge base over **all of Polish Wikipedia** (CirrusSearch dump 2025-12-29), with a pure-numpy
BM25 retriever. `kb/search.py` itself uses no neural models. Optional dense retrieval (bge-m3), hybrid RRF fusion and rerank
live in `kb/dense.py`, `kb/dense_build.py`, `kb/hybrid.py` and `kb/eval_dense.py`; see `docs/dense_retrieval.md`.

## Interface (the harness uses this)

```python
from kb.search import KB
kb = KB("kb_data/index")          # or KB() with env KB_INDEX_DIR
kb.search("W którym roku podpisano pokój w Oliwie?", k=8)
# -> [{"title", "section", "text", "score", "url"}, ...]   text = "Tytuł — Sekcja\n<chunk>"
```
CLI: `python -m kb.search --index kb_data/index "zapytanie" [-k 8] [--json]`

Extras: `kb.search_articles(q, k)` returns article-level hits, and `kb.resolve_title(t)` maps a redirect title to its article.
`KB(..., alpha, beta, gamma, per_article)` sets the fusion weights.

## Pipeline (Mac `baza`, from `~/wmt-matura`, venv active)

```bash
bash kb/run_all.sh          # = the 3 steps below (≈ 12 min download + 2 min chunks + 4 min indexes)
# 1. download (5.6 GB, 16 parallel HTTP-range segments from the ftp.acc.umu.se mirror; dumps.wikimedia.org is throttled ~60 KB/s)
bash kb/download_dump.sh kb_data/raw 16
# 2. chunks -> kb_data/chunks/part-*.parquet  (10 workers, ~2 min, peak RAM ~3 GB)
python -m kb.build_chunks --dump kb_data/raw/plwiki-20251229-cirrussearch-content.json.gz --out kb_data/chunks --workers 10
# 3. indexes (full ≈ 105 s, mini ≈ 10 s; peak RAM ≈ 3 GB)
python -m kb.build_index --chunks kb_data/chunks --out kb_data/index --workers 8
python -m kb.build_index --chunks kb_data/chunks --out kb_data/index_mini --target-chunks 40000 --max-chunks-per-article 5
# evaluation / tuning
python -m kb.eval_recall --index kb_data/index kb/sanity_questions.jsonl devset/dev-a.jsonl devset/dev-c.jsonl devset/smoke.jsonl --misses
python -m kb.tune --index kb_data/index kb/sanity_questions.jsonl devset/*.jsonl
```

## How it works

* **Source.** `plwiki-20251229-cirrussearch-content.json.gz` provides rendered plain text plus title, redirects, categories,
  headings, `opening_text`, `popularity_score` and `incoming_links`. Only namespace 0 is used. Disambiguation pages
  and pages under 20 words are dropped. That leaves 1,679,486 docs read, 1,554,413 articles kept and **3,446,110 chunks**.
* **Section recovery.** CirrusSearch `text` has no headings. For each wikitext section we crudely strip markup and
  search for 4-token windows of its opening in the rendered text. This gives exact section boundaries. The tail
  (Uwagi, Przypisy, Bibliografia, Linki zewnętrzne, navboxes, authority control) is cut by finding the *end* of the
  last content section. Wikipedia maintenance boilerplate ("Ten artykuł należy dopracować…", "[potrzebny przypis]")
  is removed.
* **Chunks.** Chunks are about 120–250 words, split on sentence boundaries inside a section. Sections under 40 words are merged with the next one.
  Each chunk starts with `"Tytuł — Sekcja"` (or `"Tytuł — Sekcja / Podsekcja"`, or `"Tytuł — Wstęp"` for the lead).
  Chunk 0 is also indexed with the article's redirect titles, so alias queries match.
* **Tokenizer** (`textnorm.py`). The pipeline is lowercase, then diacritic folding (ą→a, ł→l, …), then `\w+`, then a Polish stopword list,
  then light suffix stripping, then truncation to 7 characters. Numbers and years are kept verbatim. Query-only stopwords also remove
  exam phrasing ("Oceń prawdziwość…", "Przyporządkuj…", "Podaj literę…").
* **Index.** There are two BM25 indexes (k1=1.2, b=0.75), both term-major CSR with precomputed float16 weights, built by a
  streaming 2-pass builder with no scipy:
  1. chunk level: 3.45 M docs, 2.1 M terms, 216 M postings.
  2. article level: 1.55 M docs. The indexed text is title×2, redirects, headings and `opening_text`.
  Everything is `np.load(mmap_mode="r")`. Startup takes ~30 ms. RSS while querying is 0.7–1.4 GB, all of it mmap page cache.
* **Scoring.** `BM25_chunk + 0.35·BM25_article + 0.4·log1p(incoming_links) + 10·title_coverage`.
  `title_coverage` is the idf-weighted share of the article title (without the parenthesised part) found in the query.
  It is damped for titles made only of common words (e.g. "Polska"). Candidates are the top 300 chunks by chunk
  BM25, plus the best chunks of the top 30 articles by article BM25. The output has at most 3 chunks per article.
  Weights come from a coarse grid (`kb/tune.py`).

## Index layout (`kb_data/index/`, 5.4 GB on disk)

`tokenizer.json` holds the tokenizer config, BM25 params and stats. The rest:
- `chunks.{indptr,indices,weights,vocab,idf}.npy`: chunk-level CSR
- `articles.*.npy`: article-level CSR
- `store.bin` + `store_off.npy`: chunk records (`title␟section␟text␟url`)
- `art_store.bin` + `art_off.npy`
- `chunk_article.npy`
- `art_{pop,inlinks,first_chunk}.npy`
- `redirects.tsv`: 566k redirect→article pairs

The vocabulary is a sorted fixed-width `S16` array, looked up with binary search on the memmap.

`kb_data/index_mini/` (80 MB, 40k chunks, 10.9k articles: the most-linked articles, history-weighted, first 5
chunks each) is meant for Docker smoke tests.

## Measured (Mac M4 Max, shared machine; full question text as the query)

| set | n | R@1 | R@5 | R@10 | p50 / p95 latency |
|---|---|---|---|---|---|
| dev-a (generated) | 70 | 0.586 | 0.914 | 0.971 | 28 / 44 ms |
| dev-c (generated) | 77 | 0.636 | 0.935 | 1.000 | 31 / 46 ms |
| smoke (hand) | 51 | 0.353 | 0.647 | 0.706 | 32 / 55 ms |
| sanity (hand, kb/) | 42 | 0.548 | 0.738 | 0.857 | 20 / 30 ms |
| **all** | 240 | **0.546** | **0.833** | **0.904** | |

R@k means the source article is among the first k *distinct articles* returned. Latency is for k=20 with 400
candidates. Queries keep only their 32 rarest terms, which bounds long P/F questions and leaves recall unchanged.
With only the question stem (first line) as the query, R@5 is 0.943 on dev-a, 0.948 on dev-c and 0.471 on smoke.
Smoke questions need the answer options to find the article. Peak RSS of a querying process is about 1.4 GB, all
of it mmap page cache.

Ablations on all 240 questions:

| setting | R@1 | R@5 | R@10 |
|---|---|---|---|
| plain chunk BM25 | 0.442 | 0.767 | 0.842 |
| + title coverage (γ=10) | 0.525 | 0.825 | 0.883 |
| + article BM25 + inlink prior | 0.546 | 0.833 | 0.904 |

Tokenizer (full system):

| tokenizer | R@1 | R@5 | R@10 |
|---|---|---|---|
| stem + prefix-7 (chosen) | 0.546 | 0.833 | 0.904 |
| stem + prefix-6 | 0.521 | 0.833 | 0.896 |
| prefix-6 truncation only | 0.517 | 0.817 | 0.887 |
| folded words, no stemming | 0.433 | 0.746 | 0.846 |

## Open issues / ideas

* Questions that name no entity ("Kto był pierwszym koronowanym królem Polski?") and chronology/matching items
  whose gold is a broad overview article ("Historia Polski") are the main misses. Multi-query in the harness
  (one query per answer option) helps with these.
* The CirrusSearch text drops tables and infoboxes, which go to `auxiliary_text` and are not indexed. Lists-in-tables articles are therefore thin.
* The dump is from 2025-12-29. A fresher XML dump (2026-09-01) would need wikitext parsing and was not used.
* Rebuild takes about 4 minutes from the downloaded dump. Nothing in the pipeline needs the internet except the download.
