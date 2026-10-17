#!/usr/bin/env python
"""v2 table from devset/experiments.csv (latest errors=0 row per (label, file)); strict / lenient %.
   CSV=... python train/v2/summarize_v2.py bielik|qwen [--gain]"""
import csv
import os
import sys

ORDER = ["tourney160", "dev-a", "dev-b", "dev-c", "dev-f", "dev-g", "dev-h", "cke-2023", "cke-more"]
COLS = {
    "bielik": [("B", "final-bielik-4.5b-v3-base-raw"), ("T(v2)", "final-bielik-4.5b-v3-harness-v2"),
               ("v1 (noc)", "final-bielik-4.5b-v3-harness-v2-lora"), ("v1 (powt.)", "bielik45-v2-harness-v2-lora-v1"),
               ("v2 r16e2", "bielik45-v2-harness-v2-lora-r16e2"), ("v2 r16e3", "bielik45-v2-harness-v2-lora-r16e3"),
               ("merged v2 r16e2", "bielik45-v2-harness-v2-merged-r16e2"),
               ("B(merged)", "bielik45-v2-merged-r16e2-base-raw")]
              + [(f"{k}+DENSE", f"bielik45-v2-harness-v2-lora-{k}-dense1") for k in ("v1", "r16e2", "r16e3")],
    "qwen": [("B", "qwen08-v2-base-raw"), ("T(v2)", "qwen08-v2-harness-v2"),
             ("T(v2+LoRA)", "qwen08-v2-harness-v2-lora-r16e2")],
}
which = sys.argv[1]
cols = COLS[which]
got = {}
for r in csv.DictReader(open(os.environ.get("CSV", "devset/experiments.csv"), encoding="utf-8")):
    if int(r["errors"] or 0) or not int(r["n"] or 0):
        continue
    got[(r["label"], r["files"].replace(".jsonl", ""))] = r
cols = [(h, l) for h, l in cols if any((l, d) in got for d in ORDER)]
if not cols:
    sys.exit("no rows")
print("| zbiór | n | " + " | ".join(h for h, _ in cols) + " |")
print("|---|---|" + "---|" * len(cols))
pool = {l: [0, 0.0, 0.0] for _, l in cols}
for d in ORDER:
    cells, n = [], None
    for _, l in cols:
        r = got.get((l, d))
        if not r:
            cells.append("–"); continue
        n = int(r["n"]); s, le = float(r["acc_strict"]) * 100, float(r["acc_lenient"]) * 100
        pool[l][0] += n; pool[l][1] += s * n; pool[l][2] += le * n
        cells.append(f"{s:.1f} / {le:.1f}")
    if n:
        print(f"| {d} | {n} | " + " | ".join(cells) + " |")
tot = max(p[0] for p in pool.values())
print(f"| **łącznie** | {tot} | " + " | ".join(
    (f"**{p[1] / p[0]:.1f}** / {p[2] / p[0]:.1f}" + ("" if p[0] == tot else f" (n={p[0]})")) if p[0] else "–"
    for p in (pool[l] for _, l in cols)) + " |")
b = pool[cols[0][1]]
if b[0] == tot:
    print("\ngain strict vs B (pp, łącznie): " + ", ".join(
        f"{h} {pool[l][1] / pool[l][0] - b[1] / b[0]:+.1f}" for h, l in cols[1:] if pool[l][0] == tot))
