#!/usr/bin/env python
"""Build the fixed 150-item history mix used for harness-v2 A/B runs (seeded, reproducible).

  110 items from dev-a/c/f/g/h (22 per file, stratified by type)
  + all text-only, non-rubric items of cke-2023 (auto-gradable)
  + cke-more items (auto-gradable, stratified by type) to reach 150.
Output: devset/cke-hv2mix150.jsonl (name starts with 'cke-' -> git-ignored: contains CKE material).
"""
import json
import os
import random
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(20260925)


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def strat(rows, n):
    by = defaultdict(list)
    for r in rows:
        by[r["type"]].append(r)
    for v in by.values():
        rng.shuffle(v)
    out, types = [], sorted(by)
    while len(out) < n and any(by.values()):
        for t in types:
            if by[t] and len(out) < n:
                out.append(by[t].pop())
    return out


mix = []
for f in ["dev-a", "dev-c", "dev-f", "dev-g", "dev-h"]:
    mix += strat(load(f + ".jsonl"), 22)
cke = [r for r in load("cke-2023.jsonl") if r.get("text_only") and not r.get("rubric")]
mix += cke
mix += strat(load("cke-more.jsonl"), 150 - len(mix))
with open(os.path.join(ROOT, "cke-hv2mix150.jsonl"), "w", encoding="utf-8", newline="
") as f:
    for r in mix:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print(len(mix), Counter(r["type"] for r in mix), Counter(r["id"].split("-")[0] + "-" + r["id"].split("-")[1][:1] if r["id"].startswith("dev") else r["id"].split("-")[0] for r in mix))

# fixed sub-mixes used when the shared GPU is too slow for 4 x 150 runs:
#   cke-hv2mix60.jsonl  = every item with index % 5 in {0, 2} (60 items, same source/type proportions)
#   cke-hv2cke40.jsonl  = the 40 CKE items of the mix (the only items whose parse changes under QTYPE_V2)
with open(os.path.join(ROOT, "cke-hv2mix60.jsonl"), "w", encoding="utf-8", newline="
") as f:
    for i, r in enumerate(mix):
        if i % 5 in (0, 2):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(os.path.join(ROOT, "cke-hv2cke40.jsonl"), "w", encoding="utf-8", newline="
") as f:
    for r in mix:
        if r["id"].startswith("cke"):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
#   cke-hv2rw1.jsonl    = mix items for which QUERY_REWRITE=1 fires (no named entity/year in the command);
#                         on every other item QUERY_REWRITE=1 takes exactly the QUERY_REWRITE=0 path
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(ROOT))
from harness.pipeline import needs_rewrite  # noqa: E402
from harness.qtype import detect  # noqa: E402
with open(os.path.join(ROOT, "cke-hv2rw1.jsonl"), "w", encoding="utf-8", newline="
") as f:
    for r in mix:
        if needs_rewrite(detect(r["question"], v2=True), 1):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
