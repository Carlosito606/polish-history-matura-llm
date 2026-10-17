"""THE single place that defines how final answers are rendered for the grader.

Once we see k3exam.py / the grader, adapt FORMATS (or set env FORMATS_JSON='{"pf":{"sep":""}}'
to override any key without touching code, and ANSWER_WRAP='Odpowiedź: {answer}' to wrap).

Canonical defaults:
  abcd    "B"              (multi-select: "B, D")
  abj     "A2"
  pf      "P, F, P"
  chrono  "C, A, D, B"     (labels exactly as they appear in the question)
  match   "1-B, 2-A, 3-D"
  open    "Kazimierz Wielki" / "1410"   (trimmed, no trailing period)
  generic short free text
"""
from __future__ import annotations

import json
import os
import re

FORMATS: dict[str, dict] = {
    "abcd": {"sep": ", "},
    "abj": {"template": "{choice}{just}"},
    "pf": {"true": "P", "false": "F", "sep": ", ", "numbered": False, "num_template": "{n}. {v}"},
    "chrono": {"sep": ", "},
    "match": {"pair": "{l}-{r}", "sep": ", "},
    "open": {"strip_period": True, "max_chars": 200, "year_only": True},
    "generic": {"strip_period": False, "max_chars": 1200},
    "explain": {"max_chars": 1500},  # v2 explanation mode: labelled lines kept ("Rozstrzygnięcie: ...")
    "essay": {"max_chars": 12000},   # v2 essay mode: "WYPRACOWANIE na temat nr X" + paragraphs
}
ANSWER_WRAP = os.environ.get("ANSWER_WRAP", "{answer}")


def _merge_env() -> None:
    raw = os.environ.get("FORMATS_JSON", "")
    if not raw:
        return
    try:
        over = json.loads(raw)
        for k, v in over.items():
            FORMATS.setdefault(k, {}).update(v)
    except Exception as e:  # pragma: no cover
        print(f"[formats] bad FORMATS_JSON: {e}")


_merge_env()


def wrap(answer: str) -> str:
    return ANSWER_WRAP.replace("{answer}", answer)


def render_abcd(letters: list[str]) -> str:
    return FORMATS["abcd"]["sep"].join(letters)


def render_abj(choice: str, just: str) -> str:
    return FORMATS["abj"]["template"].format(choice=choice, just=just)


def render_pf(values: list[bool], labels: list[str] | None = None) -> str:
    f = FORMATS["pf"]
    toks = [f["true"] if v else f["false"] for v in values]
    if f.get("numbered"):
        labels = labels or [str(i + 1) for i in range(len(toks))]
        toks = [f["num_template"].format(n=l, v=t) for l, t in zip(labels, toks)]
    return f["sep"].join(toks)


def render_chrono(order: list[str]) -> str:
    return FORMATS["chrono"]["sep"].join(order)


def render_match(pairs: list[tuple[str, str]]) -> str:
    f = FORMATS["match"]
    return f["sep"].join(f["pair"].format(l=l, r=r) for l, r in pairs)


def render_open(text: str, kind: str = "other") -> str:
    f = FORMATS["open"]
    s = clean_short(text)
    if kind == "year" and f.get("year_only"):
        m = re.search(r"(?<!\d)(\d{1,4})(?!\d)(\s*(r\.)?\s*p\.\s*n\.\s*e\.)?", s)
        if m:
            s = m.group(1) + (" p.n.e." if m.group(2) else "")
    if f.get("strip_period"):
        s = s.rstrip(" .")
        if s.endswith(" w") or s.endswith(" r") or s.endswith("p.n.e"):  # keep abbreviations intact
            s += "."
    return s[: f["max_chars"]].strip()


def render_explain(text: str, labels: list[str] | None = None) -> str:
    """Multi-sentence answer; every answer-sheet label starts its own line ("Rozstrzygnięcie: Tak\nUzasadnienie: ...")."""
    s = (text or "").replace("**", "").strip()
    if not labels:
        s = _PREFIX.sub("", s).strip()
    for l in labels or []:
        s = re.sub(rf"\s*\b{re.escape(l)}\s*:\s*", f"\n{l}: ", s, count=1, flags=re.I)
    s = s.strip()
    return s[: FORMATS["explain"]["max_chars"]].strip()


def render_essay(text: str) -> str:
    return (text or "").strip()[: FORMATS["essay"]["max_chars"]].strip()


def render_generic(text: str) -> str:
    f = FORMATS["generic"]
    s = text.strip()
    if f.get("strip_period"):
        s = s.rstrip(" .")
    return s[: f["max_chars"]].strip()


_PREFIX = re.compile(r"^\s*(\*\*)?\s*(ostateczna\s+)?(odpowiedź|odpowiedz|answer)\s*(\*\*)?\s*[:\-–]\s*(\*\*)?", re.I)


def clean_short(text: str) -> str:
    """First meaningful line, without 'Odpowiedź:' prefix, markdown or quotes."""
    s = (text or "").strip()
    lines = [l for l in s.splitlines() if l.strip()]
    # prefer an explicit 'Odpowiedź:' line if present
    for l in reversed(lines):
        if _PREFIX.match(l):
            s = l
            break
    else:
        s = lines[0] if lines else ""
    s = _PREFIX.sub("", s)
    s = s.replace("**", "").replace("__", "").strip()
    s = s.strip(" \t\"'„”“`*")
    return s.strip()
