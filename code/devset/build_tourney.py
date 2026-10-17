#!/usr/bin/env python
"""Build devset/tourney160.jsonl: a deterministic, stratified HISTORY subset for the model sweep.

Groups (per-file quotas):  curriculum dev-a/b/c, long tail dev-f/g, historical geography dev-h,
real CKE (text-only, non-rubric items of cke-2023 + all gradeable cke-more items).
Geography files dev-d / dev-e are excluded (the final exam is history).
Inside every file the type mix is kept (largest-remainder allocation per type); items are picked
by the lowest sha1(id) -> fully deterministic, no RNG.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
QUOTAS = {"dev-a": 19, "dev-b": 18, "dev-c": 19, "dev-f": 17, "dev-g": 17, "dev-h": 25,
          "cke-2023": 10, "cke-more": 35}
GROUP = {"dev-a": "curriculum", "dev-b": "curriculum", "dev-c": "curriculum", "dev-f": "longtail",
         "dev-g": "longtail", "dev-h": "histgeo", "cke-2023": "cke", "cke-more": "cke"}


def h(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def eligible(name: str, it: dict) -> bool:
    if name == "cke-2023":
        return bool(it.get("text_only")) and not it.get("rubric")
    return True


def allocate(counts: Counter, n: int) -> dict:
    total = sum(counts.values())
    if n >= total:
        return dict(counts)
    raw = {t: counts[t] * n / total for t in counts}
    out = {t: int(v) for t, v in raw.items()}
    rest = n - sum(out.values())
    for t in sorted(raw, key=lambda t: (-(raw[t] - out[t]), t))[:rest]:
        out[t] += 1
    return out


def main() -> None:
    picked = []
    for name, q in QUOTAS.items():
        path = os.path.join(HERE, f"{name}.jsonl")
        with open(path, encoding="utf-8") as f:
            items = [json.loads(l) for l in f if l.strip()]
        items = [it for it in items if eligible(name, it)]
        alloc = allocate(Counter(it["type"] for it in items), q)
        for t, k in sorted(alloc.items()):
            pool = sorted((it for it in items if it["type"] == t), key=lambda it: h(it["id"]))
            for it in pool[:k]:
                it = {k2: v for k2, v in it.items() if k2 not in ("rubric_text",)}
                it["src"] = name
                it["group"] = GROUP[name]
                picked.append(it)
    picked.sort(key=lambda it: h(it["id"]))
    out = os.path.join(HERE, "tourney160.jsonl")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for it in picked:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(picked)} items -> {out}")
    print("by group:", dict(Counter(it["group"] for it in picked)))
    print("by src:  ", dict(Counter(it["src"] for it in picked)))
    print("by type: ", dict(Counter(it["type"] for it in picked)))


if __name__ == "__main__":
    main()
