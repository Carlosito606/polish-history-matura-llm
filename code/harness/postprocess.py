"""Parse raw model output into structured answers (robust to chatty output)."""
from __future__ import annotations

import re
from collections import Counter

from .formats import clean_short

_WORDCH = "A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż"
_ANS_LINE = re.compile(r"(odpowied[źz]|answer)\s*(\*\*)?\s*[:\-–]\s*(.*)$", re.I | re.M)


def _answer_region(text: str) -> str:
    """If the output contains 'Odpowiedź: ...', focus on the last such line; else the whole text."""
    ms = list(_ANS_LINE.finditer(text or ""))
    if ms and ms[-1].group(3).strip():
        return ms[-1].group(3)
    return text or ""


def parse_letters(text: str, allowed: list[str], n: int = 1, options: list[tuple[str, str]] | None = None) -> list[str]:
    region = _answer_region(text)
    allowed_set = set(allowed)
    pat = re.compile(rf"(?<![{_WORDCH}])([A-H])(?![{_WORDCH}])")
    found: list[str] = []
    for m in pat.finditer(region):
        c = m.group(1)
        if c in allowed_set and c not in found:
            found.append(c)
        if n and len(found) >= n:
            break
    if not found and options:
        # fall back: match option text inside output
        try:
            from rapidfuzz import fuzz
            low = region.lower()
            best = max(options, key=lambda o: fuzz.partial_ratio(o[1].lower(), low) if o[1] else 0)
            if best[1] and fuzz.partial_ratio(best[1].lower(), low) >= 80:
                found = [best[0]]
        except Exception:
            pass
    return found


_PF_TOKEN = re.compile(
    rf"(?<![{_WORDCH}])(prawda|prawdziwe|prawdziwy|prawdziwa|fałsz|falsz|fałszywe|fałszywy|fałszywa|P|F|T|N|TAK|NIE)(?![{_WORDCH}])",
    re.I,
)


def _pf_val(tok: str) -> bool | None:
    t = tok.lower()
    if t in ("p", "t", "tak") or t.startswith("prawd"):
        return True
    if t in ("f", "n", "nie") or t.startswith("fałsz") or t.startswith("falsz"):
        return False
    return None


def parse_pf(text: str, n: int) -> list[bool]:
    """Returns list of booleans (len n if n>0). Understands '1. P', 'P, F, P', 'prawda/fałsz' words."""
    region = text or ""
    # numbered lines first: '1: P', '2) fałsz'
    numbered: dict[int, bool] = {}
    for m in re.finditer(rf"(?m)^\s*(\d{{1,2}})\s*[\.\):\-–]?\s*(?:\*\*)?\s*([{_WORDCH}]+)", region):
        v = _pf_val(m.group(2))
        if v is not None:
            numbered.setdefault(int(m.group(1)), v)
    if n and all(i in numbered for i in range(1, n + 1)):
        return [numbered[i] for i in range(1, n + 1)]
    seq = []
    for m in _PF_TOKEN.finditer(_answer_region(region) if n else region):
        tok = m.group(1)
        # single letters T/N only count if uppercase
        if len(tok) == 1 and not tok.isupper():
            continue
        v = _pf_val(tok)
        if v is not None:
            seq.append(v)
    if n and len(seq) < n:
        # retry on the full text
        seq2 = [(_pf_val(m.group(1))) for m in _PF_TOKEN.finditer(region)
                if not (len(m.group(1)) == 1 and not m.group(1).isupper())]
        seq2 = [v for v in seq2 if v is not None]
        if len(seq2) >= n:
            seq = seq2
    if n:
        seq = seq[:n] + [True] * max(0, n - len(seq))  # pad unknown with P
    return seq


def parse_sequence(text: str, labels: list[str]) -> list[str]:
    """Order of labels as found in output; dedupe; append missing labels in original order."""
    region = _answer_region(text)
    is_num = all(l.isdigit() for l in labels)
    pat = re.compile(r"(?<!\d)(\d{1,2})(?!\d)") if is_num else re.compile(rf"(?<![{_WORDCH}])([A-H])(?![{_WORDCH}])")
    seq: list[str] = []
    for m in pat.finditer(region):
        l = m.group(1)
        if l in labels and l not in seq:
            seq.append(l)
    if len(seq) < len(labels):
        seq += [l for l in labels if l not in seq]
    return seq


def parse_match(text: str, left: list[str], right: list[str]) -> list[tuple[str, str]]:
    region = text or ""
    pairs: dict[str, str] = {}
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[\-–:→>\.\)]?\s*([A-H])(?![A-Za-ząćęłńóśźż])", region):
        l, r = m.group(1), m.group(2)
        if l in left and r in right and l not in pairs:
            pairs[l] = r
    # also 'B-1' style
    if len(pairs) < len(left):
        for m in re.finditer(r"(?<![A-Za-z])([A-H])\s*[\-–:→>]\s*(\d{1,2})(?!\d)", region):
            r, l = m.group(1), m.group(2)
            if l in left and r in right and l not in pairs:
                pairs[l] = r
    out = []
    for l in left:
        out.append((l, pairs.get(l, right[0] if right else "?")))
    return out


def parse_pairs(text: str, left: list[str], right: list[str]) -> list[tuple[str, str]]:
    """Direction-agnostic 'L-R' pairs (v2: '1-B' parts answers and letter->number 'A-3' matching)."""
    region = text or ""
    ralt = "|".join(re.escape(r) for r in sorted(right, key=len, reverse=True)) or "(?!)"
    pairs: dict[str, str] = {}
    for l in left:
        m = re.search(rf"(?<![A-Za-z0-9]){re.escape(l)}\s*[\-–:→>\.\)]?\s*({ralt})(?![A-Za-z0-9ąćęłńóśźż])", region)
        if m:
            pairs[l] = m.group(1)
    return [(l, pairs.get(l, right[0] if right else "?")) for l in left]


def parse_years(text: str, labels: list[str]) -> dict[str, float]:
    """'A: 1410' lines -> {label: year}. Negative / p.n.e. supported."""
    out: dict[str, float] = {}
    for m in re.finditer(r"(?m)^\s*\(?([A-H]|\d{1,2})\)?\s*[:\.\)\-–]\s*(-?\d{1,4})\s*(p\.?\s*n\.?\s*e\.?)?", text or ""):
        lab, y, bce = m.group(1), int(m.group(2)), m.group(3)
        if bce and y > 0:
            y = -y
        if lab in labels and lab not in out:
            out[lab] = y
    return out


def majority(values: list, tiebreak_first: bool = True):
    """Majority vote; ties resolved in favour of the earliest value (greedy answer is first)."""
    if not values:
        return None
    c = Counter(values)
    best = max(c.values())
    for v in values:
        if c[v] == best:
            return v
    return values[0]


def clean_open(text: str) -> str:
    return clean_short(text)
