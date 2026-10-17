# Dense retrieval (bge-m3) and hybrid BM25 fusion

Status: 2026-09-26, updated 12:00 CEST. Experiments ran on the shared L40S. Code is in `kb/dense.py`, `kb/dense_build.py`, `kb/hybrid.py` and `kb/eval_dense.py`. The harness has had a `DENSE` flag since 26.09 (`harness/config.py`, `harness/retrieval.py`, section 0).

## 0. End-to-end in the harness (`DENSE=1`)

**Recommendation: turn `DENSE=1` on for the Bielik-4.5B system, with `DENSE_WEIGHT=1.0`, article mode and no head cap (the defaults below).** Two things must happen first. (1) The latency has to be re-measured once, with the faiss thread fix; the only end-to-end latency measured so far is not clean. (2) The exam image has to carry the extra pieces listed at the end of this section. If either cannot be done before the freeze, leave it off. Leaving it off is safe, because `DENSE=0` behaves exactly as before.

**Setup.** Bielik-4.5B-v3.0-Instruct Q8_0 (the base GGUF, untouched) plus the v1 adapter `final-bielik-4.5b-v3-r16-e2.gguf` on llama-server (`-c 32768 -np 8 -kvu`), with `QTYPE_V2=1 RERANK=1` (bge-reranker-v2-m3 Q8_0). `devset/eval.py --workers 8`. Dense side: bge-m3 Q8_0 on `llama-server --embedding` and the complete 1,909,896-chunk index, searched with FAISS IVF-SQfp16 (nprobe 64).

**Accuracy (strict).** The L40S session was terminated at about 09:40 UTC, in the middle of the `DENSE=1` run. `/scratch` went with it, including the run files. The numbers below come from the run's status log. `DENSE=1, w0.5` did not run.

| file | n | `DENSE=0` | `DENSE=1`, w1.0 | Δ |
|---|---|---|---|---|
| tourney160 | 160 | 0.756 | **0.794** | +3.8 |
| dev-a | 70 | 0.843 | **0.886** | +4.3 |
| dev-b | 72 | 0.819 | **0.847** | +2.8 |
| dev-c | 77 | 0.766 | **0.818** | +5.2 |
| **4 files together** | 379 | 0.786 (298) | **0.826 (313)** | **+4.0 (+15 questions)** |
| dev-d / dev-e / dev-f / dev-g / dev-h | 70/73/60/60/70 | 0.671 / 0.767 / 0.800 / 0.783 / 0.729 | not run | |
| all 9 files, `DENSE=0` | 712 | 0.768 (547) | | |

The `DENSE=0` run is reproducible. It matches last night's `final-bielik-4.5b-v3-harness-v2-lora` run exactly on tourney160, dev-a, dev-b, dev-c and dev-h, and within one question on dev-f and dev-g. The +15 questions are therefore not LLM noise, and all four files improved. Two gaps remain. dev-d and dev-e (geography) are the files most at risk, because the dense scope is `hist_score>=2 | incoming_links>=50`. dev-f was already weak for dense in section 3.

**Recall inside the harness.** This measures `retrieve()` only, with no LLM, over all 712 questions of tourney160 and dev-a..h, with `QTYPE_V2=1 RERANK=1`. R@1 means the first prompt chunk comes from the source article. R@5 means any of the 5 prompt chunks does.

| variant | R@1 | R@5 |
|---|---|---|
| `DENSE=0` (RERANK_TOPN 24) | 0.673 | 0.812 |
| `DENSE=0`, RERANK_TOPN 32 | 0.660 | 0.813 |
| **`DENSE=1` w1.0, article RRF, no head cap (default)** | **0.676** | **0.817** |
| `DENSE=1` w1.0, at most 3 chunks per article in the head (`DENSE_CAND_PER_ARTICLE=3`) | 0.653 | 0.806 |
| `DENSE=1` w0.5, head cap 3 | 0.654 | 0.803 |
| `DENSE=1` w1.0, RERANK_TOPN 40 | 0.633 | 0.791 |
| `DENSE_MODE=union`: BM25 top-24 plus 8 new dense chunks for the reranker | 0.660 | 0.810 |
| `DENSE_MODE=union`, 16 dense chunks | 0.646 | 0.808 |

Once the reranker is in the pipeline, the source-article recall hardly moves: +0.3 R@1 and +0.5 R@5 for the default. The pre-rerank +5.6 R@1 of section 3 is mostly absorbed by the cross-encoder. The accuracy gain comes from *which chunks* reach the 5 prompt slots: better passages of the same article, and a second relevant article for questions that involve several entities.

Two variants hurt. Any change that gives the reranker more candidates (a bigger TOPN, or union mode) lowers R@1, because the cross-encoder then promotes more distractors. A per-article cap of 3 in the fused head is also worse. It pushed out chunks from the per-item BM25 queries: pf R@1 fell from 0.803 to 0.708.

Per file, R@1 / R@5 for `DENSE=0` against `DENSE=1` with head cap 3, w1.0. This was the first variant, and the one that was run end to end was the no-cap default.
- dev-d: 0.671/0.829 against 0.643/0.900
- dev-h: 0.529/0.771 against 0.500/0.800
- dev-a: 0.643/0.829 against 0.614/0.757
- tourney160: 0.506/0.606 against 0.506/0.594

**Latency and VRAM.**
- VRAM for LLM + reranker + embedder: 9.3–9.4 GB with `-c 32768 -np 8`. The bge-m3 embedder accounts for about 0.9 GB of that. The FAISS index needs about 4 GB of **RAM** in the harness process.
- In the retrieval-only runs (8 threads, faiss with 2 OpenMP threads), one dense lookup for one question took 32 ms on average: embedding plus FAISS plus record fetch. `retrieve()` as a whole had a p50 of 1.4–1.8 s under load in both modes, and most of that is the reranker.
- End-to-end latency: `DENSE=0` ran at avg 3.8–4.3 s per question (tourney160: p50 3.08 s, p90 8.79 s).
- The `DENSE=1` run was much slower. tourney160 took avg 11.6 s (p50 9.3 s), and dev-a took avg 8.1 s. Two causes are known:
  - faiss ran with its default 4 OpenMP threads inside each of 8 concurrent requests on a 4-vCPU host. That put dense at 162 ms per lookup, and the spinning OpenMP threads starved BM25 and the reranker client.
  - another agent's `train/build_sft.py` was using its own reranker on the same GPU and CPU (load 4.2).
- Fix: faiss now runs single-threaded inside the harness (`DENSE_FAISS_THREADS=1`, the default). **This fix has not been measured yet.** Re-run the latency check before turning `DENSE=1` on for the exam.

**Flags** (`harness/config.py`, all ignored while `DENSE=0`):

| flag | default | meaning |
|---|---|---|
| `DENSE` | 0 | 1 embeds the whole question (without boilerplate, first 2000 chars), searches the dense index and fuses it with the BM25 pool |
| `DENSE_WEIGHT` | 1.0 | dense weight in the article RRF (the BM25 side weighs 1.0) |
| `DENSE_INDEX_DIR` | `kb_data/dense/bge-m3` | directory with `meta.json`, `ids.npy`, `vectors.f16.npy` and `index.faiss` |
| `DENSE_URL` | `http://127.0.0.1:18096` | llama-server `--embedding --pooling cls` running bge-m3 Q8_0 |
| `DENSE_SEARCH` / `DENSE_NPROBE` / `DENSE_FAISS_THREADS` | auto / 64 / 1 | auto picks faiss when `index.faiss` exists |
| `DENSE_K` / `DENSE_DEPTH` / `DENSE_PER_ARTICLE` | 30 / 150 / 3 | dense chunks that enter the fusion; index rows scanned; at most this many chunks per article |
| `DENSE_CAND_PER_ARTICLE` | 0 | cap per article in the fused head (3 was worse, see above) |
| `DENSE_MODE` / `DENSE_UNION_K` | article / 8 | `union` was worse, kept only for experiments |

**How it works.** `retrieve()` is the only retrieval path. `answer`, `pf-split`, `chrono` and every `build_messages()` caller get their contexts from it.

With `DENSE=1`, `retrieve()` does four things:
1. It builds the BM25 pool exactly as before, using the multi-query chunk RRF.
2. `hybrid_scores()` ranks articles: score(article) = 1/(60 + r_BM25) + w/(60 + r_dense). Here r_BM25 is the article's rank in the BM25 pool's chunk-RRF order, and r_dense its rank in the dense list.
3. It sorts chunks by their article's score, and by chunk RRF within an article.
4. The existing reranker then takes the first `RERANK_TOPN` of that order. With `RERANK=0`, `pack` takes them directly.

Each question's embedding is cached, so `pf-split`'s repeated calls embed once. Any dense failure falls back to BM25 only: the index cannot load, the embedder is down, or the search fails. The failure is logged and counted in `/health` → `kb.dense`.

**Exam packaging** (all local, no internet):
- bge-m3 Q8_0 GGUF, 606 MB, on a second small llama-server (`--embedding --pooling cls`, about 0.9 GB of VRAM).
- `index.faiss`, 3.9 GB, plus `ids.npy` and `meta.json`. `vectors.f16.npy` (3.9 GB) is needed only by the numpy, torch or mmap backends.
- `faiss-cpu` in `docker/requirements.in`, relocked with `docker/lock.sh`.
- about 4 GB more RAM for the harness.

**Finish on the next GPU session.** The complete index and FAISS index are on `/workspace/kb_data/dense/bge-m3/` (synced 09:23 UTC). The broken NFS merge from the night was replaced.
1. Copy the laptop's `harness/{config,retrieval}.py` and `kb/dense.py` to the session.
2. Run `CFGS="0:1.0 1:1.0 1:0.5"` over the 9 files with the same labels.
3. Run a `--workers 1` latency pass of `DENSE=0` against `DENSE=1`.

The run scripts were in `/scratch/hyb` and are gone. Their logic: the embedder on port 18096, the reranker on 18097, the LLM on 18095 and the harness on 18098, all from local `/scratch` copies.

## TL;DR (retrieval study, 25/26.09 night)

- **Winner: bge-m3** (dense), with article-level RRF fusion to BM25. On the full KB, over the 460 questions of dev-a,b,c,f,g,h and smoke, hybrid improves on BM25:

  | metric | BM25 | hybrid | gain |
  |---|---|---|---|
  | R@1 | 0.635 | **0.691** | +5.6 points |
  | R@5 | 0.898 | 0.907 | |
  | R@10 | 0.939 | 0.946 | |
  | R@50 | 0.972 | 0.980 | |
  | entity-less R@10 (n=41) | 0.707 | **0.829** | +12 points |

  Dense alone (0.591 / 0.874 / 0.913 / 0.946) is worse than BM25. It helps only as a second opinion in the fusion.
- **Full index:** 1.9M chunks (`hist_score>=2` or `incoming_links>=50`), float16, 3.9 GB, in `/workspace/kb_data/dense/bge-m3/`. The build took about 62 min on the shared L40S. At exam time the only extra model is the 606 MB bge-m3 Q8_0 GGUF on `llama-server --embedding`. Its query vectors match the fp16 document vectors to cos 0.999.
- **Rerank:** the standalone `finish.sh` evaluation never ran. Its merge died with SIGBUS on NFS, and then `/workspace` became unreachable. It was replaced by the in-harness measurement with the reranker in section 0.
- **Recommendation (night):** add the dense list at the article level and keep BM25 as the backbone. That is now implemented as `DENSE=1`. For the end-to-end verdict, see section 0.

## 1. Bake-off: which embedder

**Sample.** The sample has 60,000 chunks: all 4,525 chunks of the 242 source articles of dev-a,b,c,f,g,h, plus 55,475 random history chunks (`hist_score>=2`) as distractors. Two gold titles are not in the KB: *Skarb żelaznych grzywien* and *Stanisław Badoń*. The plan said about 150k chunks. That was cut to 60k because the GPU was shared with the overnight sweep, which made Qwen3 embed at only about 100 chunks/s. BM25 was restricted to the same chunk ids (`--restrict`), so both methods see the same candidates.

**Candidates.** Each model used the prefixes from its model card:

| model | query format | doc format | pooling |
|---|---|---|---|
| `sdadas/mmlw-retrieval-roberta-large` | `zapytanie: {q}` | as is | CLS |
| `BAAI/bge-m3` (dense) | as is | as is | CLS |
| `Qwen/Qwen3-Embedding-0.6B` | `Instruct: Given a question about history, retrieve Wikipedia passages that answer the question\nQuery:{q}` | as is | last token |

All three ran as sentence-transformers fp16 with `max_seq_length=512` on the shared L40S (the sweep's llama-server was running at the same time).

Recall of the source article is measured over the list of distinct articles. There are n=409 questions, 30 of them entity-less. The "full" query is the whole question text. The "stem" query is only its first line.

| method | full R@1 | R@5 | R@10 | R@50 | stem R@1 | R@5 | R@10 | entity-less (full) R@1 / R@5 / R@10 |
|---|---|---|---|---|---|---|---|---|
| BM25 (restricted to sample) | 0.917 | 0.993 | 0.993 | 0.993 | 0.927 | 0.983 | 0.988 | 0.833 / 1.000 / 1.000 |
| mmlw-roberta-large | 0.910 | 0.980 | 0.985 | 0.993 | 0.902 | 0.971 | 0.980 | 0.667 / 0.900 / 0.967 |
| **bge-m3** | 0.907 | 0.983 | 0.983 | 0.990 | 0.902 | 0.966 | 0.983 | 0.633 / 0.900 / 0.900 |
| Qwen3-Embedding-0.6B | 0.875 | 0.961 | 0.973 | 0.985 | 0.875 | 0.961 | 0.976 | 0.367 / 0.767 / 0.833 |
| hybrid BM25+mmlw (article RRF) | 0.929 | 0.990 | 0.993 | 0.993 | 0.941 | 0.988 | 0.993 | 0.800 / 1.000 / 1.000 |
| hybrid BM25+bge-m3 (article RRF) | 0.932 | 0.985 | 0.993 | 0.993 | 0.936 | 0.983 | 0.993 | 0.833 / 0.933 / 1.000 |
| hybrid BM25+Qwen3 (article RRF) | 0.905 | 0.983 | 0.990 | 0.993 | 0.919 | 0.978 | 0.993 | 0.633 / 0.933 / 1.000 |
| hybrid BM25+bge-m3 (chunk RRF) | 0.914 | 0.976 | 0.983 | 0.993 | 0.880 | 0.944 | 0.961 | 0.833 / 0.933 / 0.967 |

| model | embed throughput (chunks/s, shared GPU) | mean tokens / chunk | params | GGUF for llama-server |
|---|---|---|---|---|
| mmlw-roberta-large | 407 | 190 (Polish tokenizer) | 435M | none. Its Unigram `tokenizer.json` is not handled by the llama.cpp RoBERTa converter (BPE only). |
| bge-m3 | 383 | 269 | 568M | `gpustack/bge-m3-GGUF` Q8_0, 606 MB. Cosine vs the ST fp16 vectors: mean 0.9991, p05 0.9987 (4,096 chunks). |
| Qwen3-Embedding-0.6B | 102 | 363 | 596M | official Q8_0, 610 MB |

**Decision: bge-m3.** mmlw and bge-m3 are tied on quality. mmlw is slightly better on entity-less R@10 with the full query (0.967 vs 0.900), but that is 2 of 30 questions. bge-m3 won for three reasons:
- At exam time it runs on a plain `llama-server --embedding`, the same stack as the bge-reranker. Q8_0 query vectors match the fp16 document vectors to cos 0.999.
- mmlw would need torch and sentence-transformers in the harness image.
- Qwen3 was worst on every metric and about 4× slower to index, because it splits Polish into many more tokens.

The sample is near the ceiling: BM25 restricted to it has R@5 0.993, against 0.929 on the full KB. It therefore cannot separate the methods well. The full-KB numbers in section 3 are the ones that matter.

**Fusion finding.** The fusion is now reciprocal-rank fusion at the article level. The chunk-level version from the first draft of `kb/hybrid.py` lost 4–6 R@5 points on stem queries, dropping below BM25 alone. Two different chunks of the gold article split its votes, and a distractor chunk that sat mid-list in both rankings then beat them. With bge-m3 or mmlw, article-level hybrid has the best R@1 of all methods (0.93–0.94) and matches BM25 at R@10. A dense weight of 0.5 vs 1.0 made no significant difference, and 2.0 was worse.

## 2. Full index

**Scope.** The scope is `hist_score>=2` (1,086,491 chunks) plus chunks of articles with `incoming_links>=50` (823,405 more), 1,909,896 chunks in total. That is 55% of the 3.45M KB chunks. It covers 98.8% of the 260 gold articles of dev-a,b,c,f,g,h and smoke. The other scopes that were measured:

| scope | chunks | gold-article coverage |
|---|---|---|
| `hist>=2` only | 1.09M | 0.908 |
| `hist>=2` or `inlinks>=500` | 1.19M | 0.958 |
| `hist>=2` or `inlinks>=200` | 1.34M | 0.969 |

All 3.45M chunks did not fit: bge-m3 ran at about 410 chunks/s on the shared GPU, so 3.45M would have taken about 2.3 h.

**Build.** bge-m3 (sentence-transformers fp16, `max_seq_length` 512, batch 64, blocks of 8,192 chunks sorted by length):
- Two processes ran in parallel on the shared L40S, one for the core scope and one for the extension. Together they reached about 510 chunks/s, against 410–430 chunks/s for a single process.
- Wall time was about 62 min, from 23:32 to 00:34 UTC.
- The extension (823,405 chunks) took 48.7 min at 282 chunks/s while running next to the core.
- VRAM was 2.7 GB per process.
- Text is read from a local copy of the KB store on `/scratch`. Random record reads straight from the NFS `store.bin` managed only about 440 records/s, and that is what made the first attempt slow.

**Interrupted by the LoRA run.** `train_lora.py` (Qwen3-8B) started at 00:34 UTC. Following the sharing rule, the watchdog stopped the core embedding at 131 of 133 blocks. The current index therefore has **1,896,557** vectors. The missing 13,339 chunks are the last 1.2% of the core scope in chunk-id order. The chunk-id order follows the dump's article order, not title or topic.

**Completed 26.09 08:44–08:50 UTC.** The core part had finished its last 2 blocks. `finish.sh`'s merge onto NFS then crashed with SIGBUS, which left inconsistent files on `/workspace`: 1.91M vectors against the old 1.897M `ids.npy`. The merge was therefore redone on local NVMe (26 s), and FAISS IVF-SQfp16 was built there (nlist 4096, 4 min, 3.94 GB). The whole directory was then synced back to `/workspace/kb_data/dense/bge-m3/`, which now holds **1,909,896** rows plus `index.faiss`.

The original plan, kept for reference, was for `/scratch/dense/finish.sh` to complete the index without further input once the LoRA ended:
1. It resumes the last 2 blocks, about 1 min of GPU.
2. It re-merges all 1,909,896 vectors into the same directory.
3. It builds the FAISS index.
4. It runs the GPU evaluation including rerank.

Results go to `/workspace/kb_data/dense/bge-m3/eval/` (`eval_full.md`, `eval_faiss.md`).

**Files** (`/workspace/kb_data/dense/bge-m3/`):

| file | contents | size |
|---|---|---|
| `vectors.f16.npy` | float16, L2-normalised, shape (N, 1024) | 3.88 GB for 1.9M rows |
| `ids.npy` | int32 KB chunk id for each row, the id map | 7.6 MB |
| `meta.json` | preset, templates, model path, parts, embed seconds, scope | |
| `index.faiss` | `IndexIVFScalarQuantizer`, nlist 4096, fp16 codes, inner product. Built 26.09 08:50 UTC on local NVMe, then synced to NFS. | 3.94 GB |

A test on the 60k sample (nlist 980) gave overlap@50 of 0.95 with exact search at nprobe 64, and 0.9 at nprobe 32, at 0.2–0.4 ms per query.

## 3. Recall on the dev sets (full KB)

The table below covers dev-a,b,c,f,g,h and smoke: n=460 questions, 41 of them entity-less. "Entity-less" means that no content token of the gold title occurs in the question. The evaluation used:
- the whole KB for BM25, and the 1.9M-chunk dense index (N = 1,896,557);
- query embedding by bge-m3 Q8_0 on llama-server, on the CPU;
- exact dense search;
- R@k of the source article over distinct articles;
- hybrid = article-level RRF, rrf_k 60, the top-100 chunks of each list, at most 3 per article;
- `wd0.5` = dense weight 0.5.

Output files are `/scratch/dense/eval_cpu.json` and `/workspace/kb_data/dense/bge-m3/eval/`.

| method | full R@1 | R@5 | R@10 | R@50 | stem R@1 | R@5 | R@10 | R@50 | entity-less (full) R@1 / R@5 / R@10 |
|---|---|---|---|---|---|---|---|---|---|
| BM25 | 0.635 | 0.898 | 0.939 | 0.972 | 0.650 | 0.880 | 0.900 | 0.941 | 0.268 / 0.610 / 0.707 |
| dense bge-m3 | 0.591 | 0.874 | 0.913 | 0.946 | 0.576 | 0.809 | 0.863 | 0.904 | 0.122 / 0.585 / 0.683 |
| **hybrid** | **0.691** | 0.907 | 0.946 | **0.980** | 0.698 | 0.876 | 0.922 | 0.952 | 0.220 / 0.659 / **0.829** |
| hybrid, wd0.5 | 0.680 | **0.909** | **0.948** | 0.974 | **0.707** | 0.876 | 0.920 | 0.948 | 0.268 / 0.659 / 0.805 |
| hybrid + rerank top-50 | pending (`finish.sh`) | | | | | | | | |
| BM25 + rerank top-50 | pending (`finish.sh`) | | | | | | | | |

Per question type, full query, R@1 / R@10:

| method | abcd (154) | chrono (72) | match (51) | open (93) | pf (90) |
|---|---|---|---|---|---|
| BM25 | 0.617 / 0.955 | 0.556 / 0.903 | 0.608 / 0.980 | 0.645 / 0.871 | 0.733 / 0.989 |
| dense | 0.532 / 0.922 | 0.583 / 0.917 | 0.549 / 0.843 | 0.548 / 0.882 | 0.767 / 0.967 |
| hybrid | 0.617 / 0.955 | **0.694** / 0.889 | **0.725** / 0.922 | **0.667 / 0.935** | **0.822 / 1.000** |
| hybrid, wd0.5 | 0.630 / 0.955 | 0.639 / 0.903 | 0.686 / 0.941 | 0.656 / 0.925 | 0.822 / 1.000 |

Per file, full query, R@1 / R@10:

| method | dev-a (70) | dev-b (72) | dev-c (77) | dev-f (60) | dev-g (60) | dev-h (70) | smoke (51) |
|---|---|---|---|---|---|---|---|
| BM25 | 0.586 / 0.971 | 0.611 / 0.986 | 0.636 / 1.000 | 0.867 / 0.950 | 0.700 / 0.983 | 0.657 / 0.914 | 0.353 / 0.706 |
| dense | 0.543 / 0.957 | 0.667 / 0.972 | 0.597 / 0.987 | 0.717 / 0.800 | 0.767 / 0.967 | 0.500 / 0.929 | 0.314 / 0.706 |
| hybrid | 0.671 / 0.971 | 0.750 / 1.000 | 0.740 / 0.987 | 0.767 / 0.867 | 0.833 / 1.000 | 0.629 / 0.971 | 0.392 / 0.765 |
| hybrid, wd0.5 | 0.629 / 0.971 | 0.764 / 1.000 | 0.701 / 0.987 | 0.767 / 0.883 | 0.783 / 1.000 | 0.671 / 0.957 | 0.392 / 0.784 |

What the numbers say:
- The fusion mostly buys R@1: chrono +14 points, match +12, pf +9. That is where the right article sits at #2–#5 under BM25.
- For entity-less questions it buys depth: R@10 goes from 0.707 to 0.829.
- abcd questions do not change.
- **dev-f is the exception.** Dense alone reaches only R@10 0.800 there, and hybrid falls to 0.867, below BM25's 0.950. With wd0.5 it is 0.883. These questions need a closer look: the gold article may be outside the dense scope or lack a matching chunk.
- A dense weight of 0.5 is safer for the depth metrics, and 1.0 is best for R@1.

## 4. Latency and VRAM

| component | measured |
|---|---|
| BM25 (`KB.search`, full KB, 4-vCPU L40S host) | p50 25–33 ms, p95 41–73 ms |
| bge-m3 query embedding, llama-server Q8_0 on GPU | ≈0.9 GB VRAM (`-c 8192 -np 4 -ub 4096`) |
| bge-m3 query embedding, llama-server Q8_0 on CPU (3 threads, CPU shared with the LoRA job) | ≈0.8–0.9 s per query (460 queries in 360–433 s, batches of 16, 2 slots) |
| bge-m3 query embedding, ST fp16 on GPU, including search over 60k chunks | p50 22.5 ms |
| dense search over 1.9M × 1024, exact, blocked over the fp16 memmap (`search_backend="mmap"`, about 0.5 GB RAM) | 460 queries in one pass took 33–92 s, about 70–200 ms per query amortised |
| dense search, FAISS IVF-SQfp16 | 0.2–0.4 ms per query on the 60k test (nprobe 32–64). The 1.9M index is still to be timed by `finish.sh`. |
| dense search, `torch` fp16 on GPU | 3.9 GB of VRAM for 1.9M rows |
| bge-reranker-v2-m3 Q8_0 llama-server | ≈1.0 GB VRAM (`-c 16384 -np 8 -ub 4096`) |
| building with ST fp16, bge-m3 | 2.7 GB VRAM per process, 410–430 chunks/s alone on the shared L40S, about 510 chunks/s with two processes |

At exam time the dense path needs:
- one more llama-server of 606 MB (bge-m3 Q8_0), using ≈0.9 GB of VRAM or running on the CPU;
- about 4 GB of disk for the vectors or the FAISS index, next to the 5.4 GB BM25 index.

Nothing touches the internet.

## 5. How to use it

```python
from kb.search import KB
from kb.dense import DenseIndex
from kb.hybrid import HybridRetriever
kb = KB("kb_data/index")
di = DenseIndex("kb_data/dense/bge-m3", url="http://127.0.0.1:18096", kb=kb)      # GGUF query embedder
di.search("Kto był pierwszym koronowanym królem Polski?", k=8)                      # same dicts as KB.search (+chunk_id)
hy = HybridRetriever(kb, di, w_dense=1.0, rrf_k=60, depth=50,
                     rerank_url="http://127.0.0.1:18097", rerank_top=50)          # rerank_url=None -> RRF only
hy.search(question, k=8)
```

Servers. Use the same llama.cpp build as the harness. Each model is under 1 GB on disk.

```bash
llama-server -m models/bge-m3/gguf/bge-m3-Q8_0.gguf --embedding --pooling cls --host 127.0.0.1 --port 18096 \
  -ngl 999 -c 8192 -np 4 -b 4096 -ub 4096 --alias bge-m3
llama-server -m models/bge-reranker-v2-m3/bge-reranker-v2-m3-Q8_0.gguf --reranking --host 127.0.0.1 --port 18097 \
  -ngl 999 -c 16384 -np 8 -b 4096 -ub 4096 --alias bge-reranker-v2-m3
```

Search backends for `DenseIndex(search_backend=...)`:
- `faiss`: used when `index.faiss` exists, with `nprobe` = 64.
- `torch`: fp16 matrix on the GPU.
- `numpy`: fp32 brute force in RAM.

Without a `url`, the query is embedded in-process with sentence-transformers, using `meta.json:model_path` or the hub id.

**Harness integration:** done as `DENSE=1`. `harness.retrieval.hybrid_scores` does the article-level RRF of the harness BM25 pool and the dense list, before the reranker (section 0).

### Rebuild commands (L40S, from `/workspace/wmt-matura`)

```bash
# venv (local NVMe, ~2 min): torch 2.12.1 cu130, sentence-transformers 5.x, faiss-cpu 1.15
uv venv /scratch/venvs/dense --python 3.12 && uv pip install -p /scratch/venvs/dense/bin/python "torch==2.12.1" \
  sentence-transformers faiss-cpu pyarrow numpy httpx pandas
cp /workspace/kb_data/index/* /scratch/kb_index/       # random record reads over NFS ran at ~440/s, locally ~40k/s
PY=/scratch/venvs/dense/bin/python
# bake-off sample + candidates
$PY -m kb.dense_build select --chunks /workspace/kb_data/chunks --index /scratch/kb_index --out sample60k_ids.npy \
    --sample-devsets devset/dev-{a,b,c,f,g,h}.jsonl --target 60000
DENSE_VRAM_GB=11 $PY -m kb.dense_build embed --preset bge-m3 --backend st --model /workspace/models/bge-m3/hf \
    --ids sample60k_ids.npy --index /scratch/kb_index --out bake/bge-m3 --batch 64 --block 8192 --max-seq 512
$PY -m kb.eval_dense devset/dev-{a,b,c,f,g,h}.jsonl --index /scratch/kb_index --restrict \
    --dense bake/mmlw-roberta-large --dense bake/bge-m3 --dense bake/qwen3-emb-0.6b --fusion article,chunk --w-dense 1.0,0.5,2.0
# full index: ids_core_hist2.npy (hist_score>=2) + ids_ext_inl50.npy (incoming_links>=50, most-linked first)
DENSE_VRAM_GB=11 $PY -m kb.dense_build embed --preset bge-m3 --backend st --model /workspace/models/bge-m3/hf \
    --ids ids_core_hist2.npy --index /scratch/kb_index --out full/bge-m3-core_hist2 --batch 64 --block 8192 --resume
#   (same for ids_ext_inl50.npy -> full/bge-m3-ext_inl50)
$PY -m kb.dense_build merge full/bge-m3-core_hist2 full/bge-m3-ext_inl50 --out /workspace/kb_data/dense/bge-m3 \
    --kb-index /workspace/kb_data/index --scope "hist_score>=2 | incoming_links>=50"
$PY -m kb.dense_build faiss --out /workspace/kb_data/dense/bge-m3 --kind ivfsq --nlist 4096
# evaluation (starts the two llama-servers on 18096/18097 if needed)
/scratch/dense/eval_full.sh /workspace/kb_data/dense/bge-m3 full torch 1
```

`embed` can be resumed (`--resume`, from `progress.json`). `merge` also accepts a part that was stopped early. The L40S wrapper `/scratch/dense/full_part.sh` stops the embedding while a `train_lora.py` job is running and resumes it afterwards.

## 6. Caveats and next steps

- **Harness wiring is done, and the end-to-end result is partial** (section 0). Still open:
  - dev-d..h with `DENSE=1`
  - the w0.5 end-to-end run
  - a clean latency run with `DENSE_FAISS_THREADS=1`
  - the exam packaging: `faiss-cpu` in the docker lock, the embedder server and the 3.9 GB `index.faiss`
- **dev-f regression.** Check which gold articles dense misses there (outside the scope? a list or table article?).
- **Size.** The vectors plus a FAISS index are 3.9 GB each. For shipping, keep only `index.faiss`, or an IVF-PQ variant of about 0.2 GB (`--kind ivfpq`), and measure the recall loss.
- **Bake-off sample.** Its 60k chunks put BM25 at the ceiling (R@5 0.99 vs 0.90 on the full KB). A harder sample, with all chunks of the 50 nearest BM25 articles as distractors, would separate the embedders better. mmlw-roberta-large stays the backup if bge-m3 disappoints end to end. It needs torch or ONNX in the harness image.
- **Environment.** `/scratch/venvs/dense` and `/scratch/kb_index` are on local NVMe and are wiped when the instance stops. Rebuild them with the commands in section 5. The embedding models are in `/workspace/models/{bge-m3,mmlw-roberta-large,qwen3-emb-0.6b}/`.
