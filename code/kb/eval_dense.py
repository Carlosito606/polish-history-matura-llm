"""Recall@k of the source article for BM25 / dense / hybrid (RRF) / hybrid+rerank, per file, per question type,
and for "entity-less" questions (no content token of the gold title occurs in the question).

  python -m kb.eval_dense devset/dev-a.jsonl ... devset/smoke.jsonl --index kb_data/index \
      --dense kb_data/dense/qwen3-emb-0.6b=http://127.0.0.1:18093 [--dense DIR2=URL2 ...] \
      [--restrict] [--rerank-url http://127.0.0.1:18092 --rerank-top 50] [--variants full,stem] [--out res.json]

--restrict  evaluate on the dense index's chunk set only (bake-off sample): BM25 chunk scores are masked to the
            same chunk ids, so BM25 and dense see the same candidates. Without it BM25 uses the full KB.
Dense "DIR=URL": URL is a llama-server --embedding endpoint; "DIR" alone uses the backend in meta.json
(sentence-transformers for presets without GGUF).
R@k is measured on the ordered list of distinct article titles (like kb/eval_recall.py).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.dense import DenseIndex, format_query  # noqa: E402
from kb.hybrid import LlamaReranker, cap_per_article, rrf_fuse  # noqa: E402
from kb.search import KB  # noqa: E402

_PAREN = re.compile(r"\s*\([^)]*\)")


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            d = json.loads(ln)
            g = d.get("source_title")
            if not d.get("question") or not g:
                continue
            d["_golds"] = [g] if isinstance(g, str) else list(g)
            d["_file"] = os.path.basename(path).replace(".jsonl", "")
            rows.append(d)
    return rows


def variant(q: str, v: str) -> str:
    return q.strip().split("\n")[0] if v == "stem" else q


def match(title: str, golds: list[str]) -> bool:
    t = title.lower()
    for g in golds:
        gl = g.lower()
        if (gl.startswith("~") and gl[1:] in t) or t == gl:
            return True
    return False


def article_rank(hits: list[dict], golds: list[str]) -> int | None:
    seen = []
    for h in hits:
        t = h["title"]
        if t in seen:
            continue
        seen.append(t)
        if match(t, golds):
            return len(seen)
    return None


def entityless(kb: KB, q: str, golds: list[str]) -> bool:
    qt = set(kb.tk.tokens(q, query=False))
    for g in golds:
        gt = set(kb.tk.tokens(_PAREN.sub("", g.lstrip("~")), query=False))
        if gt & qt:
            return False
    return True


def restrict_kb(kb: KB, ids: np.ndarray) -> KB:
    mask = np.zeros(kb.n_chunks, np.float32)
    mask[np.asarray(ids, np.int64)] = 1.0
    orig = kb.cidx.scores

    def scores(tids, n, *a, **kw):
        return orig(tids, n, *a, **kw) * mask
    kb.cidx.scores = scores
    return kb


def dense_hits(di: DenseIndex, qv: np.ndarray, n_chunks: int, per_article: int, pre=None) -> list[dict]:
    sc, rows = pre if pre is not None else di.search_vec(qv, n_chunks)
    out, seen = [], {}
    for s, r in zip(sc, rows):
        cid = int(di.ids[int(r)])
        art = int(di.kb.chunk_article[cid])
        if per_article and seen.get(art, 0) >= per_article:
            continue
        seen[art] = seen.get(art, 0) + 1
        rec = di.kb._record(cid)
        rec["score"] = float(s)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--index", required=True)
    ap.add_argument("--dense", action="append", default=[], help="DIR[=URL], repeatable")
    ap.add_argument("--restrict", action="store_true")
    ap.add_argument("--variants", default="full,stem")
    ap.add_argument("--ks", default="1,5,10,50")
    ap.add_argument("--depth", type=int, default=100, help="chunks per list fed into RRF")
    ap.add_argument("--rrf-k", type=int, default=60)
    ap.add_argument("--w-dense", default="1.0", help="comma list of dense weights for hybrid (bm25 weight = 1)")
    ap.add_argument("--rerank-url", default=None)
    ap.add_argument("--rerank-top", type=int, default=50)
    ap.add_argument("--rerank-doc-chars", type=int, default=700)
    ap.add_argument("--rerank-bm25", action="store_true", help="also report BM25 top-N + rerank")
    ap.add_argument("--rerank-variants", default="full")
    ap.add_argument("--rerank-per-article", type=int, default=2, help="max chunks per article in the rerank head")
    ap.add_argument("--fusion", default="article", help="comma list of RRF levels: article,chunk")
    ap.add_argument("--search-backend", default="numpy", choices=["numpy", "torch", "faiss", "mmap"])
    ap.add_argument("--nprobe", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ks = [int(x) for x in a.ks.split(",")]
    K = max(ks)
    wds = [float(x) for x in a.w_dense.split(",")]
    kb_full = KB(a.index)
    rows = [r for f in a.files for r in load(f)]
    if a.limit:
        rows = rows[: a.limit]
    for r in rows:
        r["_golds"] = r["_golds"] + [kb_full.resolve_title(g) for g in r["_golds"] if not g.startswith("~")]
        r["_entityless"] = entityless(kb_full, r["question"], r["_golds"])
    variants = a.variants.split(",")
    reranker = LlamaReranker(a.rerank_url) if a.rerank_url else None

    denses = []
    for spec in a.dense:
        d, _, url = spec.partition("=")
        kbx = KB(a.index)
        di = DenseIndex(d, url=url or None, kb=kbx, search_backend=a.search_backend, nprobe=a.nprobe)
        denses.append((di.preset, di))
    kb_bm = KB(a.index)
    if a.restrict and denses:
        restrict_kb(kb_bm, denses[0][1].ids)
        for _, di in denses[1:]:
            assert np.array_equal(di.ids, denses[0][1].ids), "restricted eval needs identical chunk sets"
    kb_bm.search("rozgrzewka indeksu bitwa pod Grunwaldem", k=5)

    ranks: dict[str, list] = defaultdict(list)   # method -> [(row_idx, variant, rank)]
    lat: dict[str, list] = defaultdict(list)
    t_start = time.time()
    # --- BM25
    bm25_cache = {}
    for v in variants:
        for i, r in enumerate(rows):
            q = variant(r["question"], v)
            t0 = time.perf_counter()
            art = kb_bm.search(q, k=K, per_article=1, candidates=max(300, 20 * K))
            lat["bm25"].append(1000 * (time.perf_counter() - t0))
            ranks["bm25"].append((i, v, article_rank(art, r["_golds"])))
            bh = kb_bm.search(q, k=a.depth, per_article=3, candidates=max(400, 8 * a.depth))
            bm25_cache[(i, v)] = bh
            if reranker is not None and a.rerank_bm25 and v in a.rerank_variants.split(","):
                bhead = bh[: a.rerank_top]
                t1 = time.perf_counter()
                sc2 = reranker(q[:1200], [h["text"][: a.rerank_doc_chars] for h in bhead])
                lat["rerank"].append(1000 * (time.perf_counter() - t1))
                order2 = [bhead[j] for j in sorted(range(len(bhead)), key=lambda j: -sc2[j])]
                ranks[f"bm25+rr{a.rerank_top}"].append((i, v, article_rank(order2 + bh, r["_golds"])))
            if a.restrict:
                full = kb_full.search(q, k=K, per_article=1, candidates=max(300, 20 * K))
                ranks["bm25-fullKB"].append((i, v, article_rank(full, r["_golds"])))
    print(f"bm25 done {time.time()-t_start:.0f}s", flush=True)
    # --- dense + hybrid (+ rerank)
    for name, di in denses:
        for v in variants:
            qs = [format_query(di.preset, variant(r["question"], v)) for r in rows]
            t0 = time.perf_counter()
            Q = np.concatenate([di.embedder.embed(qs[j:j + 16]) for j in range(0, len(qs), 16)])
            print(f"{name}[{v}] embedded {len(qs)} queries in {time.perf_counter()-t0:.1f}s", flush=True)
            pre = None
            if di.search_backend == "mmap":   # one blocked pass over the vectors for all queries
                t0 = time.perf_counter()
                PS, PI = di.search_batch(Q, max(1000, 10 * K))
                pre = list(zip(PS, PI))
                print(f"{name}[{v}] batched exact search {time.perf_counter()-t0:.1f}s", flush=True)
            for i, r in enumerate(rows):
                dh = dense_hits(di, Q[i], max(1000, 10 * K), per_article=3, pre=pre[i] if pre else None)
                ranks[name].append((i, v, article_rank(dh, r["_golds"])))
                bh = bm25_cache[(i, v)]
                for lv in a.fusion.split(","):
                  for wd in wds:
                    tag = f"hyb-{name}" + ("" if lv == "article" else "-" + lv) + ("" if wd == 1.0 else f"-wd{wd:g}")
                    fused = rrf_fuse(bh, dh[: a.depth], 1.0, wd, a.rrf_k, level=lv)
                    ranks[tag].append((i, v, article_rank(fused, r["_golds"])))
                    if reranker is not None and wd == wds[0] and lv == a.fusion.split(",")[0]                             and v in a.rerank_variants.split(","):
                        head = cap_per_article(fused, a.rerank_per_article)[: a.rerank_top]
                        q = variant(r["question"], v)
                        t1 = time.perf_counter()
                        sc = reranker(q[:1200], [h["text"][: a.rerank_doc_chars] for h in head])
                        lat["rerank"].append(1000 * (time.perf_counter() - t1))
                        order = [head[j] for j in sorted(range(len(head)), key=lambda j: -sc[j])]
                        ranks[f"hyb-{name}+rr{a.rerank_top}"].append((i, v, article_rank(order + fused, r["_golds"])))
            print(f"{name}[{v}] done {time.time()-t_start:.0f}s", flush=True)
        # single-query latency of the dense path (embedding call + search)
        for r in (rows[:30] if di.search_backend != "mmap" else []):
            t0 = time.perf_counter()
            di.search(r["question"], k=8)
            lat[f"{name}-query"].append(1000 * (time.perf_counter() - t0))

    # --- aggregate
    def agg(sel):
        n = len(sel)
        if not n:
            return None
        o = {f"R@{k}": round(sum(1 for x in sel if x is not None and x <= k) / n, 3) for k in ks}
        o["n"] = n
        return o

    groups = {"ALL": lambda r: True, "entityless": lambda r: r["_entityless"]}
    for f in sorted({r["_file"] for r in rows}):
        groups[f] = (lambda ff: (lambda r: r["_file"] == ff))(f)
    for t in sorted({r.get("type", "?") for r in rows}):
        groups["type=" + t] = (lambda tt: (lambda r: r.get("type", "?") == tt))(t)
    res = {}
    for m, lst in ranks.items():
        for v in variants:
            for gname, gf in groups.items():
                sel = [rk for (i, vv, rk) in lst if vv == v and gf(rows[i])]
                o = agg(sel)
                if o:
                    res[f"{m}|{v}|{gname}"] = o
    lat_s = {k: {"p50_ms": round(statistics.median(v), 1), "p95_ms": round(sorted(v)[int(0.95 * (len(v) - 1))], 1),
                 "n": len(v)} for k, v in lat.items() if v}
    out = {"restrict": a.restrict, "n_rows": len(rows), "n_entityless": sum(r["_entityless"] for r in rows),
           "dense": {n: {"n": len(di), "meta": di.meta} for n, di in denses}, "latency": lat_s, "results": res}
    for v in variants:
        print(f"\n== variant {v}  (n={len(rows)}, entityless={out['n_entityless']})")
        for gname in groups:
            print(f"  [{gname}]")
            for m in ranks:
                o = res.get(f"{m}|{v}|{gname}")
                if o:
                    print(f"    {m:32s} " + " ".join(f"R@{k}={o[f'R@{k}']:.3f}" for k in ks) + f"  n={o['n']}")
    print(json.dumps(lat_s))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
