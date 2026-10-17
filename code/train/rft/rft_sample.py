#!/usr/bin/env python3
"""RFT (rejection sampling) data for Bielik-4.5B-v3 in the harness v3 CKE_MODE format.

For every training item (never devset/*; decontaminated exactly like train/build_sft.py) the harness v3 prompt is
built with the harness's own code (qtype.detect v2 -> retrieval.retrieve with RERANK -> the CKE_MODE closed/open
instruction -> cke_flow._msgs with cke.SYSTEM, routing mirrored from cke_flow.run), then the UNTOUCHED base model
(no LoRA) answers:
  * 1 greedy generation (temperature 0)            -> greedy-accuracy baseline
  * k sampled generations (temperature, top_p)     -> candidates
Every generation is parsed from its LAST 'Odpowiedź:' line (harness.cke.final_region) and compared with the gold
canonical answer. Raw generations go to <out-dir>/raw/chunk_XXXX.jsonl (resumable); train/rft/rft_select.py
picks <= 2 correct samples per question and writes the chat-format dataset.

  /scratch/ovl/venvs/wmt/bin/python train/rft/rft_sample.py --kb /scratch/kb_index \
      --llm-url http://127.0.0.1:18093/v1 --rerank-url http://127.0.0.1:18094 --out-dir /scratch/rft/out
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
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "train"))

try:
    import httpx  # noqa: E402
except ImportError:  # prep runs without it
    httpx = None

import build_sft  # noqa: E402  (load_items, load_dev, contaminated, canonical, COMPAT)
from harness import cke, cke_flow  # noqa: E402
from harness.config import Settings  # noqa: E402
from harness.postprocess import parse_pf  # noqa: E402
from harness.qtype import detect  # noqa: E402

_WORDCH = "A-Za-z0-9ĄĆĘŁŃÓŚŹŻąćęłńóśźż"
CLOSED_T = {"abcd", "pf", "chrono", "match", "abcd_parts", "abj"}


# ----------------------------------------------------------------------------- v3 prompt (harness code only)
def v3_settings(a) -> Settings:
    # exam config of the progress system: QTYPE_V2=1 RERANK=1 CKE_MODE=1 (retrieval reads only these + defaults)
    return dataclasses.replace(Settings(), qtype_v2=True, rerank=True, use_kb=True, kb_index_dir=a.kb,
                               rerank_url=a.rerank_url.rstrip("/"), query_rewrite=0, think=False, cke_mode=True)


def v3_route(pq) -> str | None:
    """Mirror of harness.cke_flow.run routing (CKE_MODE=1). Returns 'closed' / 'open' for the reasoning paths
    whose final answer is verifiable by exact match; None for essay, names tasks, chrono (v3 keeps the v2
    year-grammar path, no reasoning), explanations and decisions. Mutates pq like run() (cke.fix_command)."""
    src, cmd = cke.fix_command(pq)
    pq.sources, pq.command = src, cmd
    labels = cke.sheet_labels(pq.command or pq.text)
    if pq.qtype == "essay":
        return None
    names = cke.names_task(pq, labels) if pq.qtype in ("match", "open", "generic", "explain") else []
    if not names and pq.qtype in ("open", "generic") and labels:
        names = labels
    if names:
        return None
    if pq.qtype in cke_flow.CLOSED:
        return "closed"
    if pq.qtype == "open":
        return "open"
    return None


def v3_messages(pq, ctx, route: str) -> list[dict]:
    """Exactly closed_flow / open_flow: cke.SYSTEM (no caller system) + prompts.build_user(question, ctx, instr)."""
    instr = cke.closed_instruction(pq) if route == "closed" else cke.open_instruction(pq)
    return cke_flow._msgs(cke.SYSTEM, pq.text, ctx, instr)


# ----------------------------------------------------------------------------- strict answer check
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s).split())


def answer_line(text: str) -> str | None:
    """First line of the text after the LAST explicit 'Odpowiedź:'; None when there is no explicit answer."""
    s = (text or "").replace("**", "")
    if not list(cke._ANS.finditer(s)):
        return None
    reg = cke.final_region(s)
    return reg.split("\n")[0].strip() if reg else None


def _labels_in_order(line: str, labels: list[str]) -> list[str]:
    is_num = all(l.isdigit() for l in labels)
    pat = r"(?<!\d)(\d{1,2})(?!\d)" if is_num else rf"(?<![{_WORDCH}])([A-H])(?![{_WORDCH}])"
    out = []
    for m in re.finditer(pat, line):
        if m.group(1) in labels and m.group(1) not in out:
            out.append(m.group(1))
    return out


_YEAR = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
_ROMAN = re.compile(r"\b([IVXL]{1,6})\b")


def open_ok(pred: str, golds: list[str], kind: str) -> bool:
    p = norm(re.sub(r"\([^)]*\)", " ", pred))
    p = re.sub(r"^(to|jest|byl[aoy]?|w|we|na)\s+", "", p)
    if not p:
        return False
    for g in golds:
        gn = norm(g)
        if not gn:
            continue
        if p == gn:
            return True
        if kind == "year":
            yp, yg = _YEAR.findall(pred), _YEAR.findall(g)
            if yp and yg and yp[0] == yg[0] and len(set(yp)) == 1:
                return True
        if kind == "century":
            rp, rg = _ROMAN.findall(pred.upper()), _ROMAN.findall(g.upper())
            if rp and rg and rp[0] == rg[0] and len(set(rp)) == 1:
                return True
        pt, gt = p.split(), gn.split()
        if set(gt) <= set(pt) and len(pt) <= len(gt) + 2:  # 'Kazimierz III Wielki' vs gold 'Kazimierz Wielki'
            return True
    return False


def check(pq, text: str, gold: dict) -> tuple[bool, str | None]:
    """-> (correct, parsed answer). Strict: only the final 'Odpowiedź:' line counts; the full label set must be
    present exactly (no padding / default-filling as the tolerant exam parsers do)."""
    line = answer_line(text)
    if not line:
        return False, None
    t = pq.qtype
    if t == "abcd":
        labels = [l for l, _ in pq.options]
        got = sorted(_labels_in_order(line, labels))
        return got == gold["letters"], ",".join(got)
    if t == "pf":
        n = len(pq.statements)
        toks = [m.group(1) for m in re.finditer(r"(?<![A-Za-z])([PF])(?![A-Za-z])", line)]
        vals = [x == "P" for x in toks]
        if len(vals) != n:
            words = parse_pf(line, 0)
            vals = words if len(words) == n else vals
        return (len(vals) == n and vals == gold["pf"]), "".join("P" if v else "F" for v in vals)
    if t == "chrono":
        labels = [l for l, _ in pq.items]
        seq = _labels_in_order(line, labels)
        return (len(seq) == len(labels) and seq == gold["seq"]), ",".join(seq)
    if t in ("match", "abcd_parts"):
        left = [l for l, _ in pq.left] if t == "match" else [p[0] for p in pq.parts]
        right = [l for l, _ in pq.right]
        ok = build_sft._strict_pairs(line, left, right, t == "match" and not left[0].isalpha())
        return (len(ok) == len(left) and ok == gold["pairs"]), ",".join(f"{k}-{v}" for k, v in ok.items())
    if t == "abj":
        m = re.search(r"(?<![A-Za-z])([AB])\s*[-–,]?\s*(\d)(?!\d)", line)
        got = (m.group(1), m.group(2)) if m else None
        return got == gold.get("abj"), ("".join(got) if got else None)
    if t == "open":
        return open_ok(line, gold["open"], pq.open_kind), line[:120]
    return False, None


def gold_struct(pq, canon: str, item: dict) -> dict | None:
    """Canonical gold string (build_sft.canonical) -> comparable structure."""
    t = pq.qtype
    if t == "abcd":
        return {"letters": sorted(_labels_in_order(canon, [l for l, _ in pq.options]))}
    if t == "pf":
        n = len(pq.statements)
        v = parse_pf(canon, n)
        return {"pf": v} if len(v) == n else None
    if t == "chrono":
        return {"seq": _labels_in_order(canon, [l for l, _ in pq.items])}
    if t in ("match", "abcd_parts"):
        left = [l for l, _ in pq.left] if t == "match" else [p[0] for p in pq.parts]
        right = [l for l, _ in pq.right]
        ok = build_sft._strict_pairs(canon, left, right, t == "match" and not left[0].isalpha())
        return {"pairs": ok} if len(ok) == len(left) else None
    if t == "abj":
        m = re.search(r"([AB])\s*(\d)", canon)
        return {"abj": (m.group(1), m.group(2))} if m else None
    if t == "open":
        golds = [g for g in [item.get("answer")] + list(item.get("accept") or []) if isinstance(g, str) and g.strip()]
        if not golds or max(len(g.split()) for g in golds[:1]) > 8:  # 'open (short)' only
            return None
        return {"open": golds}
    return None


# ----------------------------------------------------------------------------- prepare (items -> prompts)
def prepare(a):
    items, drops = build_sft.load_items(a.claude_dir, a.cke_dir)
    dev_titles, dev_q, n_dev = build_sft.load_dev(a.dev_dir)
    inv = collections.defaultdict(list)
    for i, q in enumerate(dev_q):
        for t in q:
            inv[t].append(i)
    out = []
    for it in items:
        why = build_sft.contaminated(it, dev_titles, dev_q, inv, a.overlap)
        if why:
            drops[f"{it['_source']}:{why}"] += 1
            continue
        pq = detect(it["question"], None, v2=True)
        if pq.qtype not in build_sft.COMPAT.get(it.get("type"), set()):
            drops[f"{it['_source']}:type_mismatch"] += 1
            continue
        route = v3_route(pq)
        if not route:
            drops[f"{it['_source']}:not_verifiable:{pq.qtype}"] += 1
            continue
        canon = None
        for g in [it.get("answer")] + list(it.get("accept") or []):
            canon = build_sft.canonical(pq, g if isinstance(g, str) else str(g))
            if canon:
                break
        gs = gold_struct(pq, canon, it) if canon else None
        if not gs:
            drops[f"{it['_source']}:gold_unparsable:{pq.qtype}"] += 1
            continue
        out.append((it, pq, route, gs))
    info = {"inputs": len(items), "dev_files": n_dev, "usable": len(out), "drops": dict(sorted(drops.items()))}
    return out, info


# ----------------------------------------------------------------------------- generation
class Client:
    def __init__(self, url: str, model: str):
        self.c = httpx.Client(base_url=url.rstrip("/"), timeout=httpx.Timeout(900.0, connect=10.0),
                              limits=httpx.Limits(max_connections=64, max_keepalive_connections=32))
        self.model = model

    def chat(self, messages, *, max_tokens, temperature, n=1, top_p=None, seed=None) -> list[tuple[str, str]]:
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                "cache_prompt": True}
        if n > 1:
            body["n"] = n
        if top_p is not None:
            body["top_p"] = top_p
        if seed is not None:
            body["seed"] = seed
        for attempt in range(4):
            try:
                r = self.c.post("/chat/completions", json=body)
                if r.status_code == 200:
                    j = r.json()
                    return [((ch.get("message") or {}).get("content") or "", ch.get("finish_reason") or "")
                            for ch in j.get("choices", [])]
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code == 400:
                    raise RuntimeError(err)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                err = f"{type(e).__name__}: {e}"
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(err)


def cmd_sample(a):
    t0 = time.time()
    s = v3_settings(a)
    work, info = prepare(a)
    print(f"[prep] {json.dumps(info, ensure_ascii=False)}", flush=True)
    rng = random.Random(a.seed)
    rng.shuffle(work)
    if a.types:
        keep = set(a.types.split(","))
        work = [w for w in work if w[1].qtype in keep or w[0].get("type") in keep]
    if a.limit:
        work = work[: a.limit]
    raw_dir = os.path.join(a.out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "prep_info.json"), "w", encoding="utf-8") as f:
        json.dump(dict(info, n_work=len(work), settings={"k": a.k, "temperature": a.temperature, "top_p": a.top_p,
                                                          "max_tokens": a.max_tokens}), f, ensure_ascii=False, indent=1)
    done = set()
    for f in glob.glob(os.path.join(raw_dir, "chunk_*.jsonl")):
        for d in build_sft.read_jsonl(f):
            done.add(d["id"])
    work = [w for w in work if w[0]["id"] not in done]
    print(f"[sample] todo={len(work)} done_before={len(done)}", flush=True)

    from harness.retrieval import Retriever, retrieve
    retr = Retriever(s)
    if not retr.available:
        sys.exit(f"KB not available: {retr.error}")
    print(f"[sample] KB loaded {time.time() - t0:.0f}s", flush=True)
    cli = Client(a.llm_url, a.model)

    def one(w):
        it, pq, route, gs = w
        ctx, _ = retrieve(retr, pq, s)
        msgs = v3_messages(pq, ctx, route)
        gens = cli.chat(msgs, max_tokens=a.max_tokens, temperature=0.0)[:1]
        gens += cli.chat(msgs, max_tokens=a.max_tokens, temperature=a.temperature, top_p=a.top_p, n=a.k)
        outs = []
        for i, (txt, fin) in enumerate(gens):
            ok, parsed = check(pq, txt, gs)
            outs.append({"greedy": i == 0, "text": txt, "finish": fin, "ok": ok, "parsed": parsed})
        gold_disp = {k: (v if not isinstance(v, dict) else v) for k, v in gs.items()}
        return {"id": it["id"], "source": it["_source"], "type": it.get("type"), "qtype": pq.qtype, "route": route,
                "open_kind": pq.open_kind if pq.qtype == "open" else None, "gold": gold_disp,
                "messages": msgs, "ctx_titles": [c.get("title", "") for c in ctx], "gens": outs,
                "source_title": it.get("source_title") if it["_source"] != "cke" else None}

    n_chunks = 0
    existing = len(glob.glob(os.path.join(raw_dir, "chunk_*.jsonl")))
    for c0 in range(0, len(work), a.chunk):
        part = work[c0: c0 + a.chunk]
        path = os.path.join(raw_dir, f"chunk_{existing + n_chunks:04d}.jsonl")
        tmp = path + ".tmp"
        n_ok = n_g = n_q1 = 0
        with open(tmp, "w", encoding="utf-8") as fo, cf.ThreadPoolExecutor(a.workers) as ex:
            futs = [ex.submit(one, w) for w in part]
            for fu in cf.as_completed(futs):
                try:
                    r = fu.result()
                except Exception as e:
                    print(f"[warn] {type(e).__name__}: {str(e)[:200]}", flush=True)
                    continue
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                n_g += r["gens"][0]["ok"]
                n_ok += sum(g["ok"] for g in r["gens"][1:])
                n_q1 += any(g["ok"] for g in r["gens"][1:])
        os.replace(tmp, path)
        n_chunks += 1
        m = len(part)
        print(f"[chunk] {path} n={m} greedy_acc={n_g / max(1, m):.3f} q_any_ok={n_q1 / max(1, m):.3f} "
              f"sample_acc={n_ok / max(1, m * a.k):.3f} elapsed={time.time() - t0:.0f}s "
              f"done={c0 + m}/{len(work)}", flush=True)
        if a.copy_to:
            os.makedirs(os.path.join(a.copy_to, "raw"), exist_ok=True)
            os.system(f"cp '{path}' '{os.path.join(a.copy_to, 'raw')}/' 2>/dev/null || echo '[warn] copy failed'")
    print(f"[sample] DONE {time.time() - t0:.0f}s", flush=True)


def cmd_prep(a):
    work, info = prepare(a)
    by = collections.Counter(f"{w[0]['_source']}/{w[1].qtype}" for w in work)
    print(json.dumps(dict(info, by_source_qtype=dict(sorted(by.items()))), ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prep", "sample"])
    ap.add_argument("--claude-dir", nargs="+", default=[os.path.join(ROOT, "train/datagen/claude_verified"),
                                                        os.path.join(ROOT, "train/datagen/zpe_verified")])
    ap.add_argument("--cke-dir", default=os.path.join(ROOT, "train/datagen/cke_items"))
    ap.add_argument("--dev-dir", default=os.path.join(ROOT, "devset"))
    ap.add_argument("--overlap", type=float, default=0.8)
    ap.add_argument("--kb", default=os.environ.get("KB_INDEX_DIR", "/scratch/kb_index"))
    ap.add_argument("--rerank-url", default="http://127.0.0.1:18094")
    ap.add_argument("--llm-url", default="http://127.0.0.1:18093/v1")
    ap.add_argument("--model", default="bielik-4.5b-v3")
    ap.add_argument("--out-dir", default="/scratch/rft/out")
    ap.add_argument("--copy-to", default="/workspace/data/rft_v3_work")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-tokens", type=int, default=350)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--chunk", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--types", default="")
    ap.add_argument("--seed", type=int, default=13)
    a = ap.parse_args()
    cmd_prep(a) if a.cmd == "prep" else cmd_sample(a)


if __name__ == "__main__":
    main()
