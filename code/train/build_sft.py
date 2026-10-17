#!/usr/bin/env python3
"""Build the SFT dataset: the exact chat messages the harness sends at exam time (QTYPE_V2=1, RERANK=1)
-> canonical short answer (harness/formats.py rendering).

Sources (never devset/*, never CKE split=='eval'):
  * Claude-verified items   train/datagen/claude_verified/*.jsonl, zpe_verified/*.jsonl  (verified == true)
  * CKE items               train/datagen/cke_items/*.jsonl         (split == 'train' and verified == true)
Decontamination against every devset/**/*.jsonl: drop items whose source_title is a dev source_title, or whose
question has >= --overlap token overlap (|A&B| / min(|A|,|B|), lowercase word tokens) with a dev question.

Prompts come from the harness itself: qtype.detect(v2) -> retrieval.retrieve (BM25 + bge-reranker-v2-m3 rerank)
-> prompts.instruction -> pipeline.build_messages (the helper the pipeline uses). No LLM call is needed
(QUERY_REWRITE=0). Chrono uses the direct-order prompt (the hybrid mode's second call), whose target is the
canonical order. ~--closed-frac of the items get an extra closed-book copy (KB off -> no context block).

Two steps (the harness venv has no transformers; token stats run in the train venv):
  /workspace/venvs/wmt/bin/python train/build_sft.py build --kb /workspace/kb_data/index \
      --rerank-url http://127.0.0.1:18092 --out /workspace/data/sft_v1.jsonl
  /workspace/venvs/train/bin/python train/build_sft.py stats --data /workspace/data/sft_v1.jsonl \
      --tokenizer speakleash/Bielik-11B-v3.0-Instruct
Output rows: {"messages": [system, user, assistant], "meta": {...}}; stats in <out>.stats.json.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import dataclasses
import glob
import json
import os
import random
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

COMPAT = {  # item type -> detected harness types whose prompt/format fits the gold answer
    "abcd": {"abcd", "abj"},
    "pf": {"pf"},
    "chrono": {"chrono"},
    "match": {"match", "abcd_parts"},
    "open": {"open", "generic", "explain"},
}
CKE_PREFIX = re.compile(r"^\s*Egzamin maturalny z historii\b[^\n]{0,160}?zadanie\s+[\w.]+(?:\s*\(\s*\d+\s*pkt\.?\s*\))?"
                        r"\s*[.:]?\s*")
_TOK = re.compile(r"\w+", re.U)
_WORDCH = "A-Za-z0-9ĄĆĘŁŃÓŚŹŻąćęłńóśźż"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                yield json.loads(ln)


def toks(s: str) -> frozenset:
    return frozenset(_TOK.findall((s or "").lower()))


def norm_title(s: str) -> str:
    return " ".join((s or "").replace("_", " ").lower().split())


# ----------------------------------------------------------------------------- inputs + decontamination
def load_items(claude_dirs, cke_dir: str) -> tuple[list[dict], collections.Counter]:
    """claude_dirs: one or more dirs of Claude-verified items; a dir whose name starts with 'zpe' is tagged 'zpe'."""
    drops = collections.Counter()
    items = []
    for cdir in ([claude_dirs] if isinstance(claude_dirs, str) else claude_dirs):
        src = "zpe" if os.path.basename(os.path.normpath(cdir)).lower().startswith("zpe") else "claude"
        for f in sorted(glob.glob(os.path.join(cdir, "*.jsonl"))):
            for d in read_jsonl(f):
                if d.get("verified") is not True:
                    drops[f"{src}_unverified"] += 1
                    continue
                d["_source"] = src
                items.append(d)
    for f in sorted(glob.glob(os.path.join(cke_dir, "*.jsonl"))):
        for d in read_jsonl(f):
            if d.get("split") != "train":
                drops["cke_not_train_split"] += 1
                continue
            if d.get("verified") is not True:
                drops["cke_unverified"] += 1
                continue
            d["_source"] = "cke"
            q = d["question"]
            d["question"] = CKE_PREFIX.sub("", q, count=1)
            d["_prefix_stripped"] = d["question"] != q
            items.append(d)
    return items, drops


def load_dev(dev_dir: str):
    titles, qsets, files = set(), [], 0
    for f in sorted(glob.glob(os.path.join(dev_dir, "**", "*.jsonl"), recursive=True)):
        files += 1
        for d in read_jsonl(f):
            if d.get("source_title"):
                titles.add(norm_title(d["source_title"]))
            q = d.get("question") or ""
            if q:
                qsets.append(toks(CKE_PREFIX.sub("", q, count=1)))
    qsets = list({q for q in qsets if q})
    return titles, qsets, files


def contaminated(item: dict, dev_titles: set, dev_q: list, inv: dict, thr: float) -> str | None:
    if norm_title(item.get("source_title")) in dev_titles:
        return "dev_source_title"
    a = toks(item["question"])
    if not a:
        return None
    cand = set()
    for t in a:
        cand.update(inv.get(t, ()))
    for i in cand:
        b = dev_q[i]
        if len(a & b) / min(len(a), len(b)) >= thr:
            return "dev_question_overlap"
    return None


# ----------------------------------------------------------------------------- canonical target
def _letters_in(text: str, allowed: list[str]) -> list[str]:
    from harness.postprocess import _answer_region
    out = []
    for m in re.finditer(rf"(?<![{_WORDCH}])([A-H])(?![{_WORDCH}])", _answer_region(text)):
        if m.group(1) in allowed and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _strict_pairs(text: str, left: list[str], right: list[str], numeric_left: bool) -> dict:
    from harness.postprocess import parse_match, parse_pairs
    got = (parse_match if numeric_left else parse_pairs)(text, left, right)
    ok = {}
    for l, r in got:  # the parsers fill unmatched labels with a default; keep only pairs present in the text
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(l)}\s*[\-–:→>\.\)]?\s*{re.escape(r)}(?![A-Za-z0-9])", text) or \
           re.search(rf"(?<![A-Za-z0-9]){re.escape(r)}\s*[\-–:→>]\s*{re.escape(l)}(?![A-Za-z0-9])", text):
            ok[l] = r
    return ok


def canonical(pq, gold: str) -> str | None:
    """Gold answer -> the exact string the harness would output for the detected type; None if it does not fit."""
    from harness import formats
    from harness.postprocess import clean_open, parse_pf, parse_sequence
    t = pq.qtype
    gold = (gold or "").strip()
    if not gold:
        return None
    if t == "abcd":
        labels = [l for l, _ in pq.options]
        got = _letters_in(gold, labels)
        if not labels or len(got) != max(1, pq.n_select):
            return None
        return formats.render_abcd(sorted(got))
    if t == "abj":
        a = _letters_in(gold, [l for l, _ in pq.options])
        j = parse_sequence(gold, [l for l, _ in pq.justifications])[:1] if pq.justifications else []
        if len(a) != 1 or not j or j[0] not in gold:
            return None
        return formats.render_abj(a[0], j[0])
    if t == "pf":
        n = len(pq.statements)
        vals = parse_pf(gold, n) if n else []
        if not n or len(vals) != n:
            return None
        return formats.render_pf(vals, [l for l, _ in pq.statements])
    if t == "chrono":
        labels = [l for l, _ in pq.items]
        if not labels:
            return None
        is_num = all(l.isdigit() for l in labels)
        pat = r"(?<!\d)(\d{1,2})(?!\d)" if is_num else rf"(?<![{_WORDCH}])([A-H])(?![{_WORDCH}])"
        seen = []
        for m in re.finditer(pat, gold):
            if m.group(1) in labels and m.group(1) not in seen:
                seen.append(m.group(1))
        if sorted(seen) != sorted(labels):
            return None
        return formats.render_chrono(seen)
    if t in ("match", "abcd_parts"):
        left = [l for l, _ in pq.left] if t == "match" else [p[0] for p in pq.parts]
        right = [l for l, _ in pq.right]
        if not left or not right:
            return None
        numeric_left = t == "match" and not left[0].isalpha()
        ok = _strict_pairs(gold, left, right, numeric_left)
        if len(ok) != len(left):
            return None
        return formats.render_match([(l, ok[l]) for l in left])
    if t == "open":
        c = clean_open(gold)
        return formats.render_open(c, pq.open_kind) if c else None
    if t == "explain":
        return formats.render_explain(gold, pq.labels) or None
    return formats.render_generic(gold) or None


# ----------------------------------------------------------------------------- build
def cmd_build(a):
    from harness import formats, prompts
    from harness.config import Settings
    from harness.pipeline import build_messages
    from harness.qtype import detect
    from harness.retrieval import Retriever, retrieve

    t0 = time.time()
    s = dataclasses.replace(Settings(), qtype_v2=True, rerank=True, use_kb=True, kb_index_dir=a.kb,
                            rerank_url=a.rerank_url.rstrip("/"), query_rewrite=0, think=False)
    system = prompts.SYSTEM  # exam caller's own system text (if any) is unknown -> harness system only
    items, drops = load_items(a.claude_dir, a.cke_dir)
    dev_titles, dev_q, n_dev_files = load_dev(a.dev_dir)
    inv = collections.defaultdict(list)
    for i, q in enumerate(dev_q):
        for t in q:
            inv[t].append(i)
    kept = []
    for it in items:
        why = contaminated(it, dev_titles, dev_q, inv, a.overlap)
        if why:
            drops[f"{it['_source']}:{why}"] += 1
        else:
            kept.append(it)
    if a.limit:
        random.Random(a.seed).shuffle(kept)
        kept = kept[: a.limit]
    print(f"[build] items={len(items)} dev_files={n_dev_files} dev_titles={len(dev_titles)} dev_q={len(dev_q)} "
          f"after_decontam={len(kept)} ({time.time() - t0:.0f}s)", flush=True)

    retr = Retriever(s)
    if not retr.available:
        sys.exit(f"KB not available: {retr.error}")
    print(f"[build] KB loaded ({time.time() - t0:.0f}s)", flush=True)
    rr_fail = collections.Counter()

    def one(it):
        pq = detect(it["question"], None, v2=True)
        if pq.qtype not in COMPAT.get(it.get("type"), set()):
            return it, pq, None, None, f"type_mismatch:{it.get('type')}->{pq.qtype}"
        target = None
        for g in [it.get("answer")] + list(it.get("accept") or []):
            target = canonical(pq, g if isinstance(g, str) else str(g))
            if target:
                break
        if not target:
            return it, pq, None, None, f"gold_unparsable:{pq.qtype}"
        ctx, _ = retrieve(retr, pq, s)
        if not any("rerank" in c for c in ctx):
            rr_fail["no_rerank_score"] += 1
        return it, pq, ctx, formats.wrap(target), None

    rows, n_done = [], 0
    rng = random.Random(a.seed)
    out_tmp = a.out + ".tmp"
    with open(out_tmp, "w", encoding="utf-8") as fo, cf.ThreadPoolExecutor(a.workers) as ex:
        for it, pq, ctx, target, err in ex.map(one, kept):
            n_done += 1
            if n_done % 100 == 0:
                print(f"[build] {n_done}/{len(kept)} rows={len(rows)} {time.time() - t0:.0f}s", flush=True)
            if err:
                drops[f"{it['_source']}:{err}"] += 1
                continue
            st = norm_title(it.get("source_title"))
            titles = [c.get("title", "") for c in ctx]
            ev = [e for e in (it.get("evidence") or []) if isinstance(e, str) and len(e) > 20]
            joined = " ".join(" ".join(c.get("text", "").split()) for c in ctx).lower()
            meta = {"id": it["id"], "source": it["_source"], "item_type": it.get("type"), "qtype": pq.qtype,
                    "kb": True, "n_ctx": len(ctx), "ctx_titles": titles,
                    "has_gold_ctx": (st in {norm_title(x) for x in titles}) if it["_source"] != "cke" else None,
                    "has_evidence": (any(" ".join(e.split()).lower()[:60] in joined for e in ev)
                                     if it["_source"] != "cke" and ev else None),
                    "source_title": it.get("source_title") if it["_source"] != "cke" else None,
                    "difficulty": it.get("difficulty"), "era": it.get("era")}
            variants = [(ctx, meta)]
            if rng.random() < a.closed_frac:
                variants.append(([], dict(meta, kb=False, n_ctx=0, ctx_titles=[], has_gold_ctx=None,
                                          has_evidence=None)))
            for c, m in variants:
                msgs = build_messages(system, pq.text, c, prompts.instruction(pq))
                msgs.append({"role": "assistant", "content": target})
                row = {"messages": msgs, "meta": m}
                fo.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
    os.replace(out_tmp, a.out)

    stats = summarize(rows)
    stats.update({"inputs": len(items), "after_decontam": len(kept), "drops": dict(sorted(drops.items())),
                  "rerank_missing": dict(rr_fail), "dev_files": n_dev_files,
                  "cke_prefix_stripped": sum(1 for it in items if it.get("_prefix_stripped")),
                  "settings": {"qtype_v2": s.qtype_v2, "rerank": s.rerank, "top_k": s.top_k, "ctx_tokens": s.ctx_tokens,
                               "rerank_topn": s.rerank_topn, "kb": a.kb, "closed_frac": a.closed_frac,
                               "overlap": a.overlap},
                  "build_s": int(time.time() - t0)})
    with open(a.out + ".stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    if a.samples_md:
        write_samples(rows, a.samples_md, a.n_samples, a.seed)
    print(json.dumps({k: stats[k] for k in ("rows", "by_source_type", "has_gold_ctx", "has_evidence", "drops")},
                     ensure_ascii=False), flush=True)


def summarize(rows: list[dict]) -> dict:
    by = collections.Counter()
    kb = collections.Counter()
    for r in rows:
        m = r["meta"]
        by[f"{m['source']}/{m['qtype']}"] += 1
        kb["kb" if m["kb"] else "closed_book"] += 1
    g = [r["meta"]["has_gold_ctx"] for r in rows if r["meta"]["has_gold_ctx"] is not None]
    e = [r["meta"]["has_evidence"] for r in rows if r["meta"]["has_evidence"] is not None]
    return {"rows": len(rows), "by_source_type": dict(sorted(by.items())), "kb_vs_closed": dict(kb),
            "has_gold_ctx": round(sum(g) / len(g), 3) if g else None, "has_gold_ctx_n": len(g),
            "has_evidence": round(sum(e) / len(e), 3) if e else None}


def write_samples(rows: list[dict], path: str, n: int, seed: int, ctx_chars: int = 400):
    pool = [r for r in rows if r["meta"]["source"] == "claude"]  # never CKE text in the repo
    by = collections.defaultdict(list)
    for r in pool:
        by[(r["meta"]["qtype"], r["meta"]["kb"])].append(r)
    rng = random.Random(seed)
    keys = sorted(by)
    pick = []
    while len(pick) < min(n, len(pool)):
        for k in keys:
            if by[k] and len(pick) < n:
                pick.append(by[k].pop(rng.randrange(len(by[k]))))
    sysmsg = pick[0]["messages"][0]["content"] if pick else ""
    out = ["# SFT samples (sft_v1, Claude-verified items only)", "",
           "Generated by `train/build_sft.py`. Each row is the exact harness prompt (QTYPE_V2=1, RERANK=1) and the "
           f"canonical target. Wikipedia fragments are cut to {ctx_chars} characters here; the dataset has them in full.",
           "", "System message (identical in every row):", "", "```text", sysmsg, "```", ""]
    for i, r in enumerate(pick, 1):
        m = r["meta"]
        user = r["messages"][1]["content"]
        user = re.sub(r"(\[\d+\] [^\n]*\n)([^\n]{%d})[^\n]+" % ctx_chars, r"\1\2 […]", user)
        out += [f"## {i}. `{m['id']}` · {m['qtype']} · {'KB' if m['kb'] else 'closed-book'}"
                + (f" · gold ctx: {'yes' if m['has_gold_ctx'] else 'no'}" if m["kb"] else ""), "",
                f"Source article: {m.get('source_title')}", "", "User:", "", "```text", user, "```", "",
                f"Assistant (target): `{r['messages'][2]['content']}`", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))


# ----------------------------------------------------------------------------- token stats (train venv)
def cmd_stats(a):
    rows = list(read_jsonl(a.data))
    lens, src = [], ""
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(a.tokenizer)
        for r in rows:
            text = tok.apply_chat_template(r["messages"], tokenize=False)
            lens.append(len(tok(text, add_special_tokens=False)["input_ids"]))
        src = a.tokenizer
    except Exception as e:
        print(f"[stats] tokenizer unavailable ({type(e).__name__}: {e}) -> chars/3.3", flush=True)
        lens = [int(sum(len(m["content"]) for m in r["messages"]) / 3.3) for r in rows]
        src = "approx chars/3.3"

    def pct(v, p):
        v = sorted(v)
        return v[min(len(v) - 1, int(p / 100 * len(v)))] if v else 0

    kb = [n for n, r in zip(lens, rows) if r["meta"]["kb"]]
    res = {"tokenizer": src, "p50": pct(lens, 50), "p95": pct(lens, 95), "max": max(lens) if lens else 0,
           "kb_p50": pct(kb, 50), "kb_p95": pct(kb, 95), "over_3072": sum(n > 3072 for n in lens)}
    sp = a.data + ".stats.json"
    stats = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else summarize(rows)
    stats["tokens"] = res
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(res), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--claude-dir", nargs="+", default=[os.path.join(ROOT, "train/datagen/claude_verified")],
                   help="Claude-verified item dirs (a dir named zpe* is tagged source 'zpe')")
    b.add_argument("--cke-dir", default=os.path.join(ROOT, "train/datagen/cke_items"))
    b.add_argument("--dev-dir", default=os.path.join(ROOT, "devset"))
    b.add_argument("--kb", default=os.environ.get("KB_INDEX_DIR", "/workspace/kb_data/index"))
    b.add_argument("--rerank-url", default=os.environ.get("RERANK_URL", "http://127.0.0.1:18092"))
    b.add_argument("--out", default="/workspace/data/sft_v1.jsonl")
    b.add_argument("--samples-md", default=os.path.join(ROOT, "docs/sft_samples.md"))
    b.add_argument("--n-samples", type=int, default=20)
    b.add_argument("--closed-frac", type=float, default=0.10)
    b.add_argument("--overlap", type=float, default=0.8)
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--limit", type=int, default=0, help="debug: only N random items")
    b.add_argument("--seed", type=int, default=13)
    st = sub.add_parser("stats")
    st.add_argument("--data", default="/workspace/data/sft_v1.jsonl")
    st.add_argument("--tokenizer", default="speakleash/Bielik-11B-v3.0-Instruct")
    a = ap.parse_args()
    cmd_build(a) if a.cmd == "build" else cmd_stats(a)


if __name__ == "__main__":
    main()
