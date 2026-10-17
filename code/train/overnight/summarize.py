#!/usr/bin/env python
"""Summarize final-<key>-{base-raw,harness-v2,harness-v2-lora} rows of devset/experiments.csv (latest row per file).
Prints a markdown table (strict / lenient %) and a last line LORA_HELPS=0|1 (pooled strict, LoRA vs harness-v2)."""
import csv
import sys

keys = sys.argv[1:]
rows = list(csv.DictReader(open(__import__("os").environ.get("CSV", "/workspace/wmt-matura/devset/experiments.csv"), encoding="utf-8")))
CFG = ("base-raw", "harness-v2", "harness-v2-lora")
ORDER = ["tourney160", "dev-a", "dev-b", "dev-c", "dev-f", "dev-g", "dev-h", "cke-2023", "cke-more"]
helps = []
print("| model | dataset | n | B strict/len | T(v2) strict/len | T(v2+LoRA) strict/len | gain T(v2)-B | gain T(v2+LoRA)-B | LoRA delta |")
print("|---|---|---|---|---|---|---|---|---|")
for key in keys:
    got = {}
    for r in rows:
        lab = r["label"]
        if int(r["errors"] or 0) > 0:
            continue
        for c in CFG:
            if lab == f"final-{key}-{c}":
                got[(c, r["files"].replace(".jsonl", ""))] = r  # later rows win
    pool = {c: [0, 0.0, 0.0] for c in CFG}
    for d in ORDER + ["ALL (pooled)"]:
        if d.startswith("ALL"):
            if not pool["harness-v2"][0]:
                continue
            v = {c: (pool[c][1] / pool[c][0] * 100, pool[c][2] / pool[c][0] * 100) if pool[c][0] else None for c in CFG}
            n = pool["harness-v2"][0]
        else:
            v, n = {}, None
            for c in CFG:
                r = got.get((c, d))
                if r:
                    n = int(r["n"])
                    s, l = float(r["acc_strict"]), float(r["acc_lenient"])
                    v[c] = (s * 100, l * 100)
                    pool[c][0] += n; pool[c][1] += s * n; pool[c][2] += l * n
                else:
                    v[c] = None
            if n is None:
                continue
        f = lambda x: f"{x[0]:.1f} / {x[1]:.1f}" if x else "–"
        g = lambda a, b: f"{a[0] - b[0]:+.1f} / {a[1] - b[1]:+.1f}" if (a and b) else "–"
        b, t, tl = v["base-raw"], v["harness-v2"], v["harness-v2-lora"]
        print(f"| {key} | {d} | {n} | {f(b)} | {f(t)} | {f(tl)} | {g(t, b)} | {g(tl, b)} | {g(tl, t)} |")
        if d.startswith("ALL") and t and tl:
            helps.append(tl[0] > t[0])
print(f"LORA_HELPS={int(bool(helps) and all(helps))}")
