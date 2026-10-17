"""Small grid search of KB fusion weights (alpha: article BM25, beta: inlink prior, gamma: title coverage).

Usage: python -m kb.tune --index kb_data/index kb/sanity_questions.jsonl devset/dev-a.jsonl devset/smoke.jsonl
Prints one line per setting: mean R@1 / R@5 / R@10 over all questions (full question text).
Keep the grid coarse -- the dev sets are small, this is only meant to avoid a bad regime.
"""
from __future__ import annotations

import argparse
import itertools
import json

from kb.eval_recall import load, match
from kb.search import KB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--index", required=True)
    ap.add_argument("--alphas", default="0,0.35,0.7,1.2")
    ap.add_argument("--betas", default="0,0.15,0.4")
    ap.add_argument("--gammas", default="0,5,10,20")
    a = ap.parse_args()
    kb = KB(a.index)
    rows = [r for f in a.files for r in load(f)]
    gold = [[kb.resolve_title(g) if not g.startswith("~") else g for g in gs] + gs for _, gs, _ in rows]
    res = []
    for al, be, ga in itertools.product(*[[float(x) for x in s.split(",")] for s in (a.alphas, a.betas, a.gammas)]):
        kb.alpha, kb.beta, kb.gamma = al, be, ga
        h1 = h5 = h10 = 0
        for (q, _, _), gs in zip(rows, gold):
            titles = [r["title"] for r in kb.search(q, k=10, per_article=1)]
            rank = next((i + 1 for i, t in enumerate(titles) if match(t, gs)), 99)
            h1 += rank <= 1
            h5 += rank <= 5
            h10 += rank <= 10
        n = len(rows)
        r = {"alpha": al, "beta": be, "gamma": ga, "R@1": round(h1 / n, 3), "R@5": round(h5 / n, 3), "R@10": round(h10 / n, 3)}
        res.append(r)
        print(json.dumps(r), flush=True)
    best = max(res, key=lambda r: (r["R@5"] + r["R@1"] + r["R@10"]))
    print("BEST", json.dumps(best))


if __name__ == "__main__":
    main()
