"""Recall@k of the *source article* for a question set + query latency.

Usage:
  python -m kb.eval_recall --index kb_data/index kb/sanity_questions.jsonl devset/dev-a.jsonl devset/smoke.jsonl
  options: --variants full,stem   (full = whole question incl. options/instructions; stem = first line)
           --alpha/--beta/--per-article to override KB scoring params, --misses to print failures

Input jsonl rows need "question" and "source_title" (str or list; a leading "~" means substring match).
Recall is measured on the ordered list of distinct article titles among the top-K chunks (K=max(ks)*3 chunks,
per_article=1 so every slot is a different article), i.e. "is the source article among the first k articles".
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

from kb.search import KB


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            q = d.get("question") or d.get("prompt") or d.get("q")
            g = d.get("source_title") or d.get("title") or d.get("source")
            if not q or not g:
                continue
            rows.append((q, [g] if isinstance(g, str) else list(g), d.get("id", "")))
    return rows


def match(title: str, golds: list[str]) -> bool:
    t = title.lower()
    for g in golds:
        gl = g.lower()
        if gl.startswith("~"):
            if gl[1:] in t:
                return True
        elif t == gl:
            return True
    return False


def variant(q: str, v: str) -> str:
    if v == "stem":
        return q.strip().split("\n")[0]
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--index", required=True)
    ap.add_argument("--variants", default="full,stem")
    ap.add_argument("--ks", default="1,3,5,10,20")
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--beta", type=float, default=None)
    ap.add_argument("--gamma", type=float, default=None)
    ap.add_argument("--misses", action="store_true")
    a = ap.parse_args()
    kb = KB(a.index)
    if a.alpha is not None:
        kb.alpha = a.alpha
    if a.beta is not None:
        kb.beta = a.beta
    if a.gamma is not None:
        kb.gamma = a.gamma
    ks = [int(x) for x in a.ks.split(",")]
    K = max(ks)
    kb.search("rozgrzewka indeksu bitwa pod Grunwaldem", k=5)  # warm page cache
    summary = {}
    for path in a.files:
        rows = load(path)
        for v in a.variants.split(","):
            hits_at = {k: 0 for k in ks}
            lat = []
            misses = []
            for q, golds, qid in rows:
                # gold titles may be redirects (e.g. "Bitwa Warszawska (1920)") -> add the target article
                golds = golds + [kb.resolve_title(g) for g in golds if not g.startswith("~")]
                t0 = time.perf_counter()
                res = kb.search(variant(q, v), k=K, per_article=1, candidates=max(300, 20 * K))
                lat.append(1000 * (time.perf_counter() - t0))
                titles = [r["title"] for r in res]
                rank = next((i + 1 for i, t in enumerate(titles) if match(t, golds)), None)
                for k in ks:
                    if rank is not None and rank <= k:
                        hits_at[k] += 1
                if rank is None or rank > 5:
                    misses.append((qid, rank, golds, variant(q, v)[:90].replace("\n", " "), titles[:3]))
            n = max(1, len(rows))
            key = f"{path.split('/')[-1]}[{v}]"
            summary[key] = {**{f"R@{k}": round(hits_at[k] / n, 3) for k in ks}, "n": len(rows),
                            "lat_p50_ms": round(statistics.median(lat), 1),
                            "lat_p95_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 1)}
            print(key, json.dumps(summary[key]))
            if a.misses:
                for m in misses:
                    print("   MISS", m)
    print(json.dumps({"index": a.index, "alpha": kb.alpha, "beta": kb.beta, "gamma": kb.gamma, "results": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
