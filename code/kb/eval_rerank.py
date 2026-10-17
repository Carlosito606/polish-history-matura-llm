"""Recall of the *source article* for the harness retrieval, with and without cross-encoder reranking
(and optionally with LLM query rewrite). Uses the harness code paths (qtype.detect -> build_queries ->
kb.search per query -> RRF / rerank_order -> pack).

  python -m kb.eval_rerank devset/dev-a.jsonl devset/dev-b.jsonl ... [--rerank-url http://127.0.0.1:18092]
         [--qtype-v2] [--rewrite 0|1|2 --llm-url http://127.0.0.1:18080/v1] [--limit N] [--out file.jsonl]

Reported per method: R@1/5/10 over the ordered list of distinct article titles, ctx@ = source article among
the chunks actually packed into the prompt (TOP_K / CTX_TOKENS budget), and retrieval latency per question.
Methods: bm25 (current RRF + guaranteed item/option slots), rr{N} (rerank top-N RRF candidates, per-item slots),
rr{N}-noslot (global rerank only). One global cross-encoder call per question; subsets are exact (pointwise).
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.config import Settings  # noqa: E402
from harness.qtype import detect  # noqa: E402
from harness.retrieval import (Reranker, Retriever, _doc, _key, _rrf, base_order, build_queries, pack,  # noqa: E402
                               rerank_query)


def load(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                d = json.loads(ln)
                g = d.get("source_title")
                if d.get("question") and g:
                    out.append(d)
    return out


def rank_of(titles, golds):
    seen = []
    for t in titles:
        if t not in seen:
            seen.append(t)
    gl = {g.lower() for g in golds}
    for i, t in enumerate(seen):
        if t.lower() in gl:
            return i + 1
    return None


async def rewrite_all(s: Settings, pqs: list, mode: int, conc: int = 8) -> list:
    """Rewrite queries for every question that triggers QUERY_REWRITE=mode, concurrently."""
    from harness.llm import LLM
    from harness.pipeline import needs_rewrite, parse_rewrite, rewrite_prompt
    llm = LLM(s)
    sem = asyncio.Semaphore(conc)

    async def one(pq):
        if not needs_rewrite(pq, mode):
            return []
        async with sem:
            t = time.time()
            try:
                r = await llm.chat(rewrite_prompt(pq), max_tokens=s.rewrite_max_tokens, temperature=0.0)
                return parse_rewrite(LLM.texts(r)[0] if r else "")
            except Exception as e:
                print("rewrite failed", e, flush=True)
                return []
            finally:
                one.lat.append(time.time() - t)
    one.lat = []
    try:
        out = await asyncio.gather(*(one(pq) for pq in pqs))
    finally:
        await llm.close()
    return out, one.lat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--rerank-url", default=os.environ.get("RERANK_URL", "http://127.0.0.1:18092"))
    ap.add_argument("--topn", default="24,48")
    ap.add_argument("--qtype-v2", action="store_true")
    ap.add_argument("--rewrite", type=int, default=0)
    ap.add_argument("--llm-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:18080/v1"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--only-triggered", action="store_true", help="keep only questions where the rewrite fires")
    a = ap.parse_args()
    topns = [int(x) for x in a.topn.split(",")]
    s = Settings()
    s = dataclasses.replace(s, rerank_url=a.rerank_url.rstrip("/"), llm_base_url=a.llm_url.rstrip("/"),
                            qtype_v2=a.qtype_v2, rerank_topn=max(topns))
    ret = Retriever(s)
    assert ret.available, ret.status()
    rer = Reranker(s)
    kb = ret.kb
    rows = []
    for f in a.files:
        items = load(f)
        if a.limit:
            items = items[: a.limit]
        rows += [(os.path.basename(f), it) for it in items]
    pqs_all = [detect(it["question"], v2=a.qtype_v2) for _, it in rows]
    rw_all, lat_rw = ([[] for _ in rows], [])
    if a.rewrite:
        rw_all, lat_rw = asyncio.run(rewrite_all(s, pqs_all, a.rewrite))
        if a.only_triggered:
            keep = [i for i, r in enumerate(rw_all) if r]
            rows, pqs_all, rw_all = [rows[i] for i in keep], [pqs_all[i] for i in keep], [rw_all[i] for i in keep]
    methods = ["bm25"] + (["bm25-norw"] if a.rewrite else []) +         ([] if a.no_rerank else [m for n in topns for m in (f"rr{n}", f"rr{n}-noslot")])
    per = {m: [] for m in methods}
    ctx = {m: [] for m in methods}
    lat_bm25, lat_rr = [], []
    recs = []
    for (fi, it), pq, rw in zip(rows, pqs_all, rw_all):
        g = it["source_title"]
        golds = [g] if isinstance(g, str) else list(g)
        golds = golds + [kb.resolve_title(x) for x in golds]
        queries = build_queries(pq, v2=a.qtype_v2)
        if rw:
            seen = {q.strip().lower() for _, q, _ in queries}
            queries += [x for x in rw if x[1].strip().lower() not in seen]
        t = time.time()
        res8 = [(n, w, ret.search(q, s.per_query_k)) for n, q, w in queries]
        sc8, h8 = _rrf(res8)
        o8 = base_order(res8, sc8)
        lat_bm25.append(time.time() - t)
        r = rank_of([h8[k]["title"] for k in o8], golds)
        per["bm25"].append(r)
        ctx["bm25"].append(any(c["title"].lower() in {x.lower() for x in golds}
                               for c in pack(o8, h8, sc8, s, s.top_k)))
        rec = {"id": it["id"], "file": fi, "qtype": pq.qtype, "gold": golds[0], "bm25": r, "rw": [x[1] for x in rw]}
        if a.rewrite:  # same question without the rewritten queries
            q0 = build_queries(pq, v2=a.qtype_v2)
            r0 = [(n, w, ret.search(q, s.per_query_k)) for n, q, w in q0]
            sc0, h0 = _rrf(r0)
            o0 = base_order(r0, sc0)
            rec["bm25-norw"] = rank_of([h0[k]["title"] for k in o0], golds)
            per["bm25-norw"].append(rec["bm25-norw"])
            ctx["bm25-norw"].append(any(c["title"].lower() in {x.lower() for x in golds}
                                        for c in pack(o0, h0, sc0, s, s.top_k)))
        if not a.no_rerank:
            t = time.time()
            res = [(n, w, ret.search(q, max(s.per_query_k, s.rerank_per_query_k))) for n, q, w in queries]
            sc, hh = _rrf(res)
            cand = sorted(sc, key=lambda x: -sc[x])[: max(topns)]
            rq = rerank_query(pq)
            scores = rer.score(rq, [_doc(hh[k], s.rerank_doc_chars) for k in cand])
            rr_all = dict(zip(cand, scores))
            slots = []
            qtext = {n: q for n, q, _ in queries}
            for n, w, hs in res:
                if n.startswith("item:") and hs:
                    sub = list(dict.fromkeys(_key(h) for h in hs[:6]))
                    ss = rer.score(qtext[n][:600], [_doc(hh[k], s.rerank_doc_chars) for k in sub])
                    b = sub[max(zip(ss, range(len(sub))))[1]]
                    if b not in slots:
                        slots.append(b)
            lat_rr.append(time.time() - t)
            for n in topns:
                sub = {k: rr_all[k] for k in cand[:n]}
                glob_order = sorted(sub, key=lambda x: -sub[x])
                for m, order in ((f"rr{n}", slots + [k for k in glob_order if k not in slots]),
                                 (f"rr{n}-noslot", glob_order)):
                    rk = rank_of([hh[k]["title"] for k in order], golds)
                    per[m].append(rk)
                    ctx[m].append(any(c["title"].lower() in {x.lower() for x in golds}
                                      for c in pack(order, hh, sc, s, s.top_k)))
                    rec[m] = rk
        recs.append(rec)
        if len(recs) % 50 == 0:
            print(f"... {len(recs)}/{len(rows)}", flush=True)

    def rec_at(ranks, k):
        return round(sum(1 for r in ranks if r is not None and r <= k) / max(1, len(ranks)), 3)

    summary = {}
    for m in methods:
        summary[m] = {"R@1": rec_at(per[m], 1), "R@5": rec_at(per[m], 5), "R@10": rec_at(per[m], 10),
                      "ctx@top_k": round(sum(ctx[m]) / max(1, len(ctx[m])), 3), "n": len(per[m])}
    lat = {"bm25_ms_p50": round(1000 * statistics.median(lat_bm25), 1) if lat_bm25 else None,
           "rerank_ms_p50": round(1000 * statistics.median(lat_rr), 1) if lat_rr else None,
           "rerank_ms_mean": round(1000 * statistics.mean(lat_rr), 1) if lat_rr else None,
           "rewrite_s_mean": round(statistics.mean(lat_rw), 2) if lat_rw else None,
           "rewrite_triggered": sum(1 for r in recs if r["rw"]) if a.rewrite else None}
    # per qtype
    byt = {}
    for m in methods:
        for t in sorted({r["qtype"] for r in recs}):
            rs = [r.get(m) for r in recs if r["qtype"] == t]
            byt.setdefault(t, {})[m] = rec_at(rs, 5)
    print(json.dumps({"files": [os.path.basename(f) for f in a.files], "qtype_v2": a.qtype_v2, "rewrite": a.rewrite,
                      "summary": summary, "latency": lat, "R@5_by_type": byt}, ensure_ascii=False, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
