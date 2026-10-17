"""Build devset/cke-essays.jsonl: the essay task (all topics, full command) and the official scoring rules of
formula-2015 and formula-2023 extended history papers, for evaluation only (never training).

Input: the local CKE archive (git-ignored) data_cke/arkusze/<slug>/*.txt + manifest.json, and
data_cke/cke-2023-essay.jsonl (the mentor benchmark's frozen input for May 2023). The output is git-ignored
(devset/cke-*.jsonl); this script holds no CKE text.

    python devset/build_cke_essays.py            # -> devset/cke-essays.jsonl
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness.qtype import essay_aspects, essay_topics  # noqa: E402

ARCH = os.path.join(ROOT, "data_cke", "arkusze")
OUT = os.path.join(ROOT, "devset", "cke-essays.jsonl")

# formula 2015 (12 pts, five topics): May sessions 2015-2022; formula 2023 (15 pts, three topics): every paper
F2015 = [f"matura-historia-{y}-maj-poziom-rozszerzony" for y in range(2015, 2023)]
F2023 = [f"matura-historia-{y}-{s}-poziom-rozszerzony" for y in range(2023, 2027) for s in ("maj", "czerwiec")] + [
    "matura-historia-2023-przykladowy-arkusz-cke-poziom-rozszerzony",
    "matura-probna-historia-2022-grudzien-poziom-rozszerzony",
    "matura-probna-historia-2024-grudzien-poziom-rozszerzony",
    "matura-probna-historia-2026-styczen-poziom-rozszerzony",
]

_JUNK = re.compile(
    r"^\s*(więcej arkuszy znajdziesz.*|=== page \d+ ===|strona \d+ z \d+|[em]hi\w*[_-]\w*|wypełnia|egzaminator|"
    r"nr zadania|maks\. liczba pkt|uzyskana liczba pkt|[.…\s]{8,}|\d{1,2}\.?|(\d{1,2}\.\d\.?\s*)+|\d+\s*[–-]\s*\d+|"
    r"strona\s+\d+\s+z\s+\d+.*)\s*$", re.I)
_HEAD = re.compile(r"^\s*Zadanie\s+(\d+)\.\s*\(0\s*[–-]\s*(12|15)\)", re.M)


def clean(lines: list[str]) -> str:
    out = []
    for ln in lines:
        if _JUNK.match(ln):
            continue
        out.append(ln.rstrip())
    s = "\n".join(out)
    s = re.sub(r"\n\s*\n(\s*\n)+", "\n\n", s)
    return s.strip()


def sheet_task(txt: str) -> tuple[str, str, str, str]:
    """(task number, max points, question = header line + topics, materials text or '')."""
    heads = list(_HEAD.finditer(txt))
    if not heads:
        raise ValueError("no essay header")
    h = heads[-1]
    body = txt[h.end():]
    lines = body.split("\n")
    end = next((i for i, ln in enumerate(lines) if re.match(r"^\s*WYPRACOWANIE\s*$", ln)), len(lines))
    region = lines[:end]
    mat = next((i for i, ln in enumerate(region) if re.match(r"^\s*Materiały źródłowe do", ln)), None)
    topics = clean(region[:mat] if mat is not None else region)
    materials = clean(region[mat:]) if mat is not None else ""
    return h.group(1), h.group(2), topics, materials


def key_rubric(txt: str, task_no: str, pts: str) -> str:
    hs = list(re.finditer(rf"^\s*Zadanie\s+{task_no}\.\s*\(0\s*[–-]\s*{pts}\)", txt, re.M))
    if not hs:  # key numbering can differ from the sheet (May 2025: sheet 25, key 26)
        hs = list(re.finditer(rf"^\s*Zadanie\s+\d+\.\s*\(0\s*[–-]\s*{pts}\)", txt, re.M))
    if not hs:
        raise ValueError(f"no rubric for task {task_no}")
    return clean(txt[hs[0].start():].split("\n"))


def main() -> None:
    man = {e["slug"]: e for e in json.load(open(os.path.join(ARCH, "manifest.json"), encoding="utf-8"))}
    mentor = {}
    p23 = os.path.join(ROOT, "data_cke", "cke-2023-essay.jsonl")
    if os.path.exists(p23):
        for ln in open(p23, encoding="utf-8"):
            if ln.strip():
                d = json.loads(ln)
                mentor["matura-historia-2023-maj-poziom-rozszerzony"] = d
    recs = []
    for formula, slugs in (("2015", F2015), ("2023", F2023)):
        for slug in slugs:
            e = man.get(slug)
            if not e:
                print("missing in manifest:", slug)
                continue
            files = {f["role"]: f for f in e["files"]}
            d = os.path.join(ARCH, slug)
            sheet = os.path.join(d, os.path.splitext(files["arkusz"]["filename"])[0] + ".txt")
            key = os.path.join(d, os.path.splitext(files["key"]["filename"])[0] + ".txt")
            st = open(sheet, encoding="utf-8").read()
            kt = open(key, encoding="utf-8").read()
            try:
                task_no, pts, question, materials = sheet_task(st)
                rubric = key_rubric(kt, task_no, pts)
            except ValueError as ex:
                print("skip", slug, ex)
                continue
            src = "mentor-frozen" if slug in mentor else "arkusz-txt"
            if slug in mentor:  # the mentor benchmark's exact input + its condensed official rubric
                question = mentor[slug]["question"].strip()
                rubric = mentor[slug].get("rubric_text", "").strip() + "\n\n--- pełne zasady oceniania ---\n" + rubric
            kind = e["kind"]
            sess = e["session"]
            rid = f"cke-essay-{e['year']}-{sess}" + ("-probna" if kind == "probna" else "")
            topics = essay_topics(question)
            recs.append({
                "id": rid, "era": f"cke-{e['year']}", "formula": formula, "type": "essay",
                "split": "eval" if formula == "2023" else "dev",
                "task_no": task_no, "points": int(pts),
                "question": question,
                "topics": [{"n": n, "text": t, "aspects": essay_aspects(t),
                            "needs_materials": bool(re.search(r"materiał\w*\s+źródłow", t, re.I))} for n, t in topics],
                "materials": materials, "materials_in_question": False,
                "rubric_text": rubric, "rubric": True, "essay": True, "answer": "",
                "source_title": f"CKE {sess} {e['year']} ({kind}, formuła {formula}) zad. {task_no}",
                "source_url": files["arkusz"]["url"], "key_url": files["key"]["url"], "page_url": e["url"],
                "text_source": src,
            })
    recs.sort(key=lambda r: (r["split"] != "eval", r["id"]))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(recs)} essays -> {OUT}")
    for r in recs:
        print(f"  {r['id']:32s} {r['split']:5s} {r['points']:2d} pkt  topics={len(r['topics'])} "
              f"q={len(r['question'])}ch rubric={len(r['rubric_text'])}ch mat={len(r['materials'])}ch")


if __name__ == "__main__":
    main()
