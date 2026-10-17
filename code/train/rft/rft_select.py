#!/usr/bin/env python3
"""Pick RFT samples from train/rft/rft_sample.py raw chunks -> chat-format dataset + stats.

Per question: candidates = the k sampled generations (+ the greedy one), kept only if the final 'Odpowiedź:' line
matches the gold (checked at sampling time) AND the text has the harness v3 shape: short reasoning, then ONE final
'Odpowiedź: ...' line (train/rft/fmt.py). Two light repairs of the model's OWN text are allowed and flagged in meta.fix:
  * 'reorder' - answer-first output ('Odpowiedź: X' + reasoning) -> reasoning + 'Odpowiedź: X'
  * 'dedup'   - the same answer line written twice -> only the last one kept
  * 'join'    - 'Odpowiedź:' with the value on the next line -> one line
Markdown bold / italics and '###' header markers are removed. At most --per-q samples per question: reasoning that
uses the retrieved context (words / numbers present in the Wikipedia fragments but not in the question) first, then
shorter (<= 600 / <= 900 / longer chars), then unrepaired, then shortest.

  python train/rft/rft_select.py --raw /scratch/rft/out/raw --out /workspace/data/rft_v3.jsonl
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fmt import _ANS, fmt_ok, split  # noqa: E402

_W = re.compile(r"[0-9]{3,4}|[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{5,}")


def words(s: str) -> set:
    return {w.lower()[:7] for w in _W.findall(s or "")}


def ctx_mention(reason: str, user: str) -> int:
    if "Zadanie:\n" not in user or not user.startswith("Fragmenty z Wikipedii:"):
        return 0
    ctx, q = user.split("Zadanie:\n", 1)
    only_ctx = words(ctx) - words(q)
    return len(words(reason) & only_ctx)


_CITE = re.compile(r"^\s*(?:[-*]\s*)?(?:\[\d+\]\s*[„\"][^”\"]{0,120}[”\"]\s*(?:\([^)]{0,40}\))?\s*[.,;]?"
                   r"|(?:odwołanie do źródeł|źródła|fragmenty)\s*:?)\s*$", re.I)


def cite_only(reason: str) -> bool:
    """True when the reasoning is only a list of cited fragment titles (fewer than 6 words outside such lines)."""
    rest = [ln for ln in (reason or "").split("\n") if ln.strip() and not _CITE.match(ln)]
    return sum(len(ln.split()) for ln in rest) < 6


def clean(text: str) -> str:
    s = (text or "").replace("**", "").replace("\r", "")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"^[ \t]*#{1,6}[ \t]*", "", s, flags=re.M)  # '### 1. Zdanie' -> '1. Zdanie'
    lines = []
    for ln in s.split("\n"):  # markdown italics '*x*' out; a '* ' bullet at the line start stays
        m = re.match(r"^(\s*\*\s+)", ln)
        head = m.group(1) if m else ""
        lines.append(head + ln[len(head):].replace("*", ""))
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    # a bare section label opening the reasoning ('Uzasadnienie:', 'Rozumowanie:', '### Analiza') carries nothing
    s = re.sub(r"^\s*#{0,4}\s*(uzasadnienie|wyjaśnienie|rozumowanie|analiza zadania|analiza|rozwiązanie)\s*:[ \t]*\n?",
               "", s.strip(), count=1, flags=re.I)
    return s.strip()


def _akey(v: str) -> str:
    v = re.sub(r"\([^)]*\)", " ", v or "").strip()
    m = re.match(r"([A-H])(?![A-Za-ząćęłńóśźż])", v)
    if m and not re.search(r"[,;]\s*[A-H](?![A-Za-z])|\d", v[:12]):
        return m.group(1)
    return " ".join(re.sub(r"[^\w]", " ", v.lower()).split())


def repair(text: str) -> tuple[str, str] | None:
    """-> (new_text, fix) for answer-first / duplicated answer lines; None if no safe repair. A marker line with
    nothing after it ('Odpowiedź:' + value on the next line) takes the next non-empty line as its value."""
    s = clean(text)
    lines = s.split("\n")
    marks, vals, used = [], [], set()
    for i, ln in enumerate(lines):
        core = re.sub(r"^[\s>*#\-]+", "", ln)
        m = _ANS.match(core)
        if not m or i in used:
            continue
        v = core[m.end():].strip()
        used.add(i)
        if not v:
            j = next((j for j in range(i + 1, len(lines)) if lines[j].strip()), None)
            if j is None:
                return None
            v = lines[j].strip()
            used.add(j)
        marks.append(i)
        vals.append(v)
    if not marks or len({_akey(v) for v in vals}) != 1 or not vals[-1]:
        return None
    fix = "dedup" if len(marks) > 1 else ("join" if max(used) == len(lines) - 1 else "reorder")
    body_txt = "\n".join(ln for i, ln in enumerate(lines) if i not in used).strip()
    if not body_txt:
        return None
    body_txt = clean(body_txt)
    return body_txt + "\n\nOdpowiedź: " + vals[-1], fix


def pick(row: dict, per_q: int, include_greedy: bool, allow_repair: bool = True) -> tuple[list[dict], collections.Counter]:
    why = collections.Counter()
    user = row["messages"][1]["content"]
    cands = []
    for g in row["gens"]:
        if g["greedy"] and not include_greedy:
            continue
        if not g["ok"]:
            continue
        txt = clean(g["text"])
        ok, reason = fmt_ok(txt, g["finish"])
        fix = ""
        if allow_repair and not ok and reason in ("text_after_answer", "answer_repeated") and g["finish"] == "stop":
            rep = repair(txt)
            if rep and fmt_ok(rep[0], "stop")[0]:
                txt, fix, ok = rep[0], rep[1], True
        why[reason if not fix else f"repaired_{fix}"] += 1
        if not ok:
            continue
        rs = split(txt)[0]
        if cite_only(rs):  # '[1] „Tytuł — Sekcja”' list with no reasoning sentence: teaches nothing
            why["cite_only"] += 1
            continue
        cands.append({"text": txt, "fix": fix, "ctx": ctx_mention(rs, user), "chars": len(txt), "greedy": g["greedy"]})
    # brief reasoning that uses the retrieved context first; unrepaired text breaks ties within a length band
    cands.sort(key=lambda c: (c["ctx"] < 2, 0 if c["chars"] <= 600 else 1 if c["chars"] <= 900 else 2,
                              c["fix"] != "", c["chars"]))
    out, seen = [], set()
    for c in cands:
        key = " ".join(re.sub(r"\W", " ", c["text"].lower()).split())[:200]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= per_q:
            break
    return out, why


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="/scratch/rft/out/raw")
    ap.add_argument("--out", default="/scratch/rft/out/rft_v3.jsonl")
    ap.add_argument("--per-q", type=int, default=2)
    ap.add_argument("--no-greedy", action="store_true", help="do not use the greedy generation as a candidate")
    ap.add_argument("--no-repair", action="store_true")
    a = ap.parse_args()
    rows = []
    for f in sorted(glob.glob(os.path.join(a.raw, "chunk_*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            rows += [json.loads(ln) for ln in fh if ln.strip()]
    per = collections.defaultdict(collections.Counter)
    fmt_why = collections.Counter()
    fixes = collections.Counter()
    n_out = 0
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fo:
        for r in rows:
            key = r["qtype"]
            k = len(r["gens"]) - 1
            nk = sum(g["ok"] for g in r["gens"][1:])
            p = per[key]
            p["questions"] += 1
            p["greedy_ok"] += r["gens"][0]["ok"]
            p["samples"] += k
            p["samples_ok"] += nk
            p["q_any_ok"] += nk > 0
            chosen, why = pick(r, a.per_q, not a.no_greedy, not a.no_repair)
            fmt_why.update(why)
            p["q_kept"] += bool(chosen)
            p["rows"] += len(chosen)
            for c in chosen:
                fixes[c["fix"] or "none"] += 1
                meta = {"id": r["id"], "type": r["type"], "qtype": r["qtype"], "source": r["source"],
                        "n_correct_of_k": nk, "k": k, "greedy_ok": r["gens"][0]["ok"], "from_greedy": c["greedy"],
                        "fix": c["fix"], "ctx_mention": c["ctx"], "chars": c["chars"], "route": r.get("route"),
                        "ctx_titles": r.get("ctx_titles")}
                msgs = [dict(m) for m in r["messages"]] + [{"role": "assistant", "content": c["text"]}]
                fo.write(json.dumps({"messages": msgs, "meta": meta}, ensure_ascii=False) + "\n")
                n_out += 1
    os.replace(tmp, a.out)
    tot = collections.Counter()
    for p in per.values():
        tot.update(p)
    per["ALL"] = tot

    def rates(p):
        q = max(1, p["questions"])
        return {"questions": p["questions"], "greedy_acc": round(p["greedy_ok"] / q, 3),
                "sample_acc": round(p["samples_ok"] / max(1, p["samples"]), 3),
                "q_any_correct": p["q_any_ok"], "q_any_correct_rate": round(p["q_any_ok"] / q, 3),
                "q_kept": p["q_kept"], "keep_rate": round(p["q_kept"] / q, 3), "rows": p["rows"]}

    stats = {"rows": n_out, "per_qtype": {k: rates(v) for k, v in sorted(per.items())},
             "correct_candidates_format": dict(fmt_why), "fixes_in_output": dict(fixes),
             "per_q": a.per_q, "include_greedy": not a.no_greedy, "raw_rows": len(rows)}
    with open(a.out + ".stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
