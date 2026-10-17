#!/usr/bin/env python
"""Paired comparison of harness-v2 runs on the fixed mix (devset/runs/*_<label>.jsonl from eval.py).

  python devset/compare_hv2.py A=hv2-A-defaults B=hv2-B-v2fixes-cke40+A C=hv2-C-v2-rerank D=hv2-D-...+C

'X=label+Y' = run `label` overrides run Y item-by-item (used for sub-runs on only the items whose code path
changes: QTYPE_V2 changes only the CKE items, QUERY_REWRITE=1 only the items without named entities).
Prints extract accuracy per type, per source (dev / cke), points and mean latency over the items of run A.
"""
import glob
import json
import os
import statistics
import sys
from collections import defaultdict

RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


def load(label):
    fs = sorted(glob.glob(os.path.join(RUNS, f"*_{label}.jsonl")))
    if not fs:
        raise SystemExit(f"no run file for {label}")
    with open(fs[-1], encoding="utf-8") as f:
        return {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}


specs = {}
for arg in sys.argv[1:]:
    name, _, spec = arg.partition("=")
    specs[name] = spec
res = {}
for name, spec in specs.items():
    lab, _, base = spec.partition("+")
    d = dict(res[base]) if base else {}
    d.update(load(lab))
    res[name] = d
first = next(iter(res))
ids = sorted(res[first])
names = list(res)


def row(title, sel):
    cells = []
    for n in names:
        rs = [res[n][i] for i in sel if i in res[n]]
        acc = sum(r["extract"] for r in rs) / max(1, len(rs))
        cells.append(f"{acc:.3f}")
    print(f"| {title} | {len(sel)} | " + " | ".join(cells) + " |")


print("| subset | n | " + " | ".join(names) + " |")
print("|---|---|" + "---|" * len(names))
row("overall", ids)
by_src = defaultdict(list)
by_type = defaultdict(list)
for i in ids:
    by_src["cke" if i.startswith("cke") else "dev"].append(i)
    by_type[res[first][i]["type"]].append(i)
for k in sorted(by_src):
    row(f"source {k}", by_src[k])
for k in sorted(by_type):
    row(f"type {k}", by_type[k])
pts = []
for n in names:
    rs = [res[n][i] for i in ids if i in res[n]]
    pts.append(f"{sum(r['points'] for r in rs if r['extract'])}/{sum(r['points'] for r in rs)}")
print("| points (extract) | | " + " | ".join(pts) + " |")
lat = []
for n in names:
    rs = [res[n][i] for i in ids if i in res[n] and not res[n][i].get("error")]
    lat.append(f"{statistics.mean(r['latency_s'] for r in rs):.1f}s")
print("| mean latency (shared GPU) | | " + " | ".join(lat) + " |")
errs = [str(sum(1 for i in ids if res[n].get(i, {}).get("error"))) for n in names]
print("| errors | | " + " | ".join(errs) + " |")
# item-level flips vs the first run
for n in names[1:]:
    up = [i for i in ids if res[n][i]["extract"] and not res[first][i]["extract"]]
    down = [i for i in ids if res[first][i]["extract"] and not res[n][i]["extract"]]
    print(f"{n} vs {first}: +{len(up)} {up[:12]}  -{len(down)} {down[:12]}")
