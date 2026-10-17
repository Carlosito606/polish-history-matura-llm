#!/usr/bin/env python
"""Pick the best adapter from devset/experiments.csv: pooled strict over DEVS (latest errors=0 row per file; every
   file required). The first candidate (v1) is the incumbent: a challenger must beat its pooled strict and not lose on
   tourney160. Prints "KEY LABEL" (nothing if no candidate is complete).
   CSV=... DEVS="..." python pick_best.py v1=label r16e2=label ..."""
import csv
import os
import sys

devs = os.environ.get("DEVS", "tourney160 dev-a dev-b dev-c dev-f dev-g dev-h cke-2023 cke-more").split()
got = {}
for r in csv.DictReader(open(os.environ.get("CSV", "devset/experiments.csv"), encoding="utf-8")):
    if int(r["errors"] or 0) or not int(r["n"] or 0):
        continue
    got[(r["label"], r["files"].replace(".jsonl", ""))] = (int(r["n"]), float(r["acc_strict"]))
score = {}
for kv in sys.argv[1:]:
    k, lab = kv.split("=", 1)
    if all((lab, d) in got for d in devs):
        n = sum(got[(lab, d)][0] for d in devs)
        score[k] = (sum(got[(lab, d)][0] * got[(lab, d)][1] for d in devs) / n, got[(lab, "tourney160")][1], lab)
    print(f"# {k}: {score.get(k)}", file=sys.stderr)
if score:
    keys = [kv.split("=", 1)[0] for kv in sys.argv[1:] if kv.split("=", 1)[0] in score]
    best = keys[0]
    for k in keys[1:]:
        if score[k][0] > score[best][0] and score[k][1] >= score[keys[0]][1]:
            best = k
    print(best, score[best][2])
