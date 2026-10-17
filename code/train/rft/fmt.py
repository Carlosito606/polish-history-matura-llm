"""Format filter for RFT samples: short reasoning first, then ONE final 'Odpowiedź: ...' line (harness v3)."""
from __future__ import annotations

import re

_ANS = re.compile(r"(?:ostateczna\s+)?odpowied[źz]\s*(?:\*\*)?\s*(?:końcowa\s*)?[:\-–]\s*", re.I)
_SENT = re.compile(r"[.!?…](?:\s|$)")


def split(text: str):
    """-> (reasoning, answer_line, trailing) around the LAST 'Odpowiedź:' (None if absent)."""
    s = (text or "").strip()
    ms = list(_ANS.finditer(s))
    if not ms:
        return None
    m = ms[-1]
    # start of the line holding the marker (allow '**Odpowiedź:**' / '- Odpowiedź:')
    ls = s.rfind("\n", 0, m.start()) + 1
    prefix = s[ls:m.start()]
    if re.sub(r"[*#>\-\s]", "", prefix):
        return None  # marker in the middle of a sentence
    rest = s[m.end():]
    nl = rest.find("\n")
    line = (rest if nl < 0 else rest[:nl]).strip()
    trailing = "" if nl < 0 else rest[nl:].strip()
    return s[:ls].strip(), line, trailing


def n_sentences(t: str) -> int:
    t = re.sub(r"\b(r|w|ok|np|tzw|m\.in|św|gen|ks|pt|al|ur|zm|p\.n\.e|n\.e|tj|itd|itp|wg|im)\.", "_", t)
    t = re.sub(r"\b[IVXLC]+\.", "_", t)
    t = re.sub(r"\d\.", "_", t)
    return len(_SENT.findall(t.strip() + (" " if t.strip() and t.strip()[-1] in ".!?…" else ". ")))


def fmt_ok(text: str, finish: str, max_chars: int = 1200, max_sent: int = 8) -> tuple[bool, str]:
    if finish != "stop":
        return False, "truncated"
    sp = split(text)
    if not sp:
        return False, "no_answer_line"
    reason, line, trailing = sp
    if trailing:
        return False, "text_after_answer"
    if not line:
        return False, "empty_answer"
    if len(re.sub(r"\W", "", reason)) < 40:
        return False, "no_reasoning"
    if len(list(_ANS.finditer(reason))) > 0:
        return False, "answer_repeated"
    if len(reason) > max_chars:
        return False, "reasoning_too_long"
    if n_sentences(reason) > max_sent:
        return False, "too_many_sentences"
    # a compact per-item list (one line per statement / pair) is fine; headers and long nested lists are not
    if re.search(r"^\s*#{1,6}\s", reason, re.M) or len([ln for ln in reason.split("\n") if ln.strip()]) > 9:
        return False, "list_markdown"
    return True, "ok"
