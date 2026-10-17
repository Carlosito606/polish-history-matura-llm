"""Official exam runner: organizers' package (exam.json + images/ + answers-template.json) -> answers.json.

For every item the model input is  source_text (image placeholders resolved) + question  and an answer-format
instruction derived from the item's `answer_format`:
  --mode harness  POST <url>/answer {"question": text, "system": format instruction (free-text items only)}
                  (closed items: the harness grammar fixes the syntax, the post-formatter converts it)
  --mode raw      POST <llm-url>/v1/chat/completions, ONE user message = text + format instruction,
                  no system prompt, temperature 0 (untouched base model)
Images: '[Obraz: images/X.png]' -> '[Opis obrazu: <text>]' when --image-desc maps the path (JSON
{"images/X.png": "..."}); otherwise the placeholder (and the caption line above it) stays as is. Images listed in
`images` but not referenced in source_text are appended the same way.
Every raw model answer is POST-FORMATTED deterministically into the item's answer_format
('P, F, P' -> '1: P\\n2: F\\n3: P', '1-B, 2-A' -> '1: B\\n2: A', 'A-3, B-1' -> 'A: 3\\nB: 1', 'Odpowiedź: C' -> 'C'),
reasoning traces are stripped, answer-sheet labels ('Rozstrzygnięcie:', 'Uzasadnienie:', ...) are kept on their own
lines, the essay gets its topic number. The final file is validated against the template (ids, types, size) and
written together with a debug JSONL (input, raw output, formatting notes; resumable).

  python -m harness.exam_runner data_cke/mock2023/exam.json --out submissions/mock/X/answers.json \
      --mode harness --url http://127.0.0.1:18053 --image-desc data_cke/mock2023/image_desc.json \
      [--lora-llm-url http://127.0.0.1:18051 --lora-off-types explain,essay]   # LoRA scale 0 for those qtypes
  python -m harness.exam_runner EXAM --out OUT --mode raw --llm-url http://127.0.0.1:18050 --model bielik-4.5b-v3
  python -m harness.exam_runner EXAM --out OUT --reformat-only       # rebuild answers.json from the debug JSONL
  python -m harness.exam_runner --validate OUT --exam EXAM            # check a finished file

Stdlib only (runs from any venv); the qtype pre-detection for --lora-off-types imports harness.qtype.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MAX_FILE_BYTES = 1024 * 1024
MAX_ANSWER_CHARS = 100_000
TEXT_MAX_CHARS = 2500          # free-text (non-essay) answers are cut at a sentence end beyond this
ESSAY_MIN_WORDS = 300

PLACEHOLDER = re.compile(r"\[Obraz:\s*(images/[^\]\s]+)\s*\]")
_W = r"[^\W\d_]"  # a letter (unicode)


# ============================================================================ input building
def load_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


DESC_LABEL = "Opis obrazu"  # --desc-caveat -> "Opis obrazu (automatyczny, może zawierać błędy)"


def _desc_block(text: str) -> str:
    # one line, no square brackets inside: harness strips '[Opis obrazu ...]' from retrieval queries
    t = " ".join(text.replace("[", "(").replace("]", ")").split())
    return f"[{DESC_LABEL}: {t}]"


def resolve_images(item: dict, desc: dict | None) -> str:
    src = (item.get("source_text") or "").replace("\r\n", "\n")

    def sub(m):
        p = m.group(1)
        if desc and desc.get(p):
            return _desc_block(desc[p])
        return m.group(0)

    out = PLACEHOLDER.sub(sub, src)
    for img in item.get("images") or []:
        p = img.get("path", "")
        if p and p not in src:
            out = out.rstrip() + "\n" + (_desc_block(desc[p]) if desc and desc.get(p) else f"[Obraz: {p}]")
    return out.strip()


def item_text(item: dict, desc: dict | None) -> str:
    src = resolve_images(item, desc)
    q = (item.get("question") or "").replace("\r\n", "\n").strip()
    return (src + "\n\n" + q) if src else q


# ============================================================================ answer_format spec
def _format_pairs(af: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in re.finditer(r"(?m)^\s*([A-Za-z0-9]{1,3})\s*:\s*(\S+)\s*$", af or "")]


def _question_numbered(q: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"(?m)^\s*(\d{1,2})\.\s+\S", q or "")]


def _question_lettered(q: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"(?m)^\s*([A-H])\.\s+\S", q or "")]


def _consecutive(labels: list[str], first: str) -> list[str]:
    out, want = [], first
    for l in labels:
        if l == want:
            out.append(l)
            want = chr(ord(want) + 1) if want.isalpha() else str(int(want) + 1)
    return out


def question_labels(q: str) -> list[str]:
    """Answer-sheet labels printed in the question: lines like 'Rozstrzygnięcie:' / 'Nazwa stylu 1.:' / 'Cecha:'."""
    out = []
    for ln in (q or "").splitlines():
        m = re.match(r"^\s*([A-ZĄĆĘŁŃÓŚŹŻ][^\n:]{1,40}?)\s*:\s*$", ln)
        if m and not re.match(r"^\d", m.group(1)):
            out.append(m.group(1).strip())
    return out


def essay_topics(q: str) -> list[tuple[str, str]]:
    topics, cur = [], None
    for ln in (q or "").splitlines():
        m = re.match(r"^\s*([1-5])\.\s+(.*)$", ln)
        if m:
            cur = [m.group(1), m.group(2)]
            topics.append(cur)
        elif cur and ln.strip():
            cur[1] += " " + ln.strip()
    return [(n, t) for n, t in topics]


def spec_for(item: dict) -> dict:
    """What the final answer must look like: kind + keys + allowed values, derived from answer_format + question."""
    af = item.get("answer_format") or ""
    q = item.get("question") or ""
    low = af.lower()
    if "wypracowanie" in low or "wyraz" in low:
        return {"kind": "essay", "topics": essay_topics(q)}
    pairs = _format_pairs(af)
    if pairs:
        vals = [v for _, v in pairs]
        fmt_keys = [k for k, _ in pairs]
        if all(v in ("P", "F") for v in vals):
            keys = _consecutive(_question_numbered(q), "1") or fmt_keys
            return {"kind": "pf", "keys": keys}
        if all(re.fullmatch(r"\d{1,2}", v) for v in vals):
            keys = (_consecutive(_question_lettered(q), "A") if fmt_keys[0].isalpha() else []) or fmt_keys
            return {"kind": "keyed_num", "keys": keys}
        if all(re.fullmatch(r"[A-H]", v) for v in vals):
            keys = (_consecutive(_question_numbered(q), "1") if fmt_keys[0].isdigit() else []) or fmt_keys
            letters = sorted(set(_question_lettered(q))) or list("ABCD")
            return {"kind": "keyed_letter", "keys": keys, "letters": letters}
        return {"kind": "keyed_text", "keys": fmt_keys}
    if re.fullmatch(r"\s*[A-H]\s*", af):
        letters = _consecutive(_question_lettered(q), "A") or list("ABCD")
        return {"kind": "choice", "letters": letters}
    return {"kind": "text", "labels": question_labels(q)}


def format_instruction(item: dict, spec: dict) -> str:
    """Neutral syntax instruction (no example values that could be copied as the answer)."""
    af = (item.get("answer_format") or "").strip()
    k = spec["kind"]
    if k == "pf":
        body = "\n".join(f"{x}: P albo F" for x in spec["keys"])
        return "Podaj tylko odpowiedź, każde stwierdzenie w osobnym wierszu, dokładnie w tym formacie:\n" + body
    if k == "keyed_num":
        body = "\n".join(f"{x}: numer" for x in spec["keys"])
        return "Podaj tylko odpowiedź, każdy element w osobnym wierszu, dokładnie w tym formacie:\n" + body
    if k == "keyed_letter":
        let = ", ".join(spec["letters"])
        body = "\n".join(f"{x}: litera ({let})" for x in spec["keys"])
        return "Podaj tylko odpowiedź, każde zdanie w osobnym wierszu, dokładnie w tym formacie:\n" + body
    if k == "choice":
        return "Podaj tylko literę wybranej odpowiedzi (" + ", ".join(spec["letters"]) + ")."
    if k == "essay":
        return ("Odpowiedź po polsku: numer wybranego tematu i całe wypracowanie w jednym tekście "
                "(minimum 300 wyrazów).")
    labels = spec.get("labels") or []
    extra = (" Zachowaj etykiety z arkusza, każdą w nowym wierszu: " + ", ".join(l + ":" for l in labels) + "."
             if labels else "")
    return "Odpowiedź po polsku, bez toku rozumowania. " + af + extra


# ============================================================================ post-formatting
_THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)
_ANS_MARK = re.compile(r"(?:ostateczna\s+|końcowa\s+|prawidłowa\s+|poprawna\s+)?odpowied[źz]\w*\s*(?:to)?\s*[:\-–—]",
                       re.I)


def clean(text: str) -> str:
    s = _THINK.sub("", text or "")
    s = s.replace("\r\n", "\n").replace("**", "").replace("__", "")
    s = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", s)
    s = re.sub(r"(?m)^\s*```\w*\s*$", "", s)
    return s.strip()


def answer_region(text: str) -> str:
    """Text after the last 'Odpowiedź:' marker (reasoning before it dropped), else the whole text."""
    ms = list(_ANS_MARK.finditer(text))
    if ms:
        tail = text[ms[-1].end():].strip()
        if tail:
            return tail
    return text


def _pf_tok(tok: str) -> str | None:
    t = tok.lower()
    if t in ("p", "prawda", "tak"):
        return "P"
    if t in ("f", "fałsz", "falsz", "nie"):
        return "F"
    if t.startswith("nieprawd"):
        return "F"
    if t.startswith("prawd"):
        return "P"
    if t.startswith("fałsz") or t.startswith("falsz"):
        return "F"
    return None


_PF_WORD = r"(?:P|F|[Pp]rawda|[Ff]ałsz|[Ff]alsz|(?:[Nn]ie)?[Pp]rawdziw\w*|[Ff]ałszyw\w*)"


def parse_pf(text: str, keys: list[str]) -> tuple[dict, str]:
    region = answer_region(text)
    # 1) '1: P' / '1. F' / '1 - prawda' (value right after the number)
    d = {}
    for m in re.finditer(rf"(?<!\d)(\d{{1,2}})\s*[\.\):\-–—=]?\s*[\-–—:]?\s*({_PF_WORD})(?!\w)", region):
        v = _pf_tok(m.group(2))
        if m.group(1) in keys and v and m.group(1) not in d:
            d[m.group(1)] = v
    if len(d) == len(keys):
        return d, "keyed"
    best = d
    # 2) lines starting with a number: first P/F word anywhere in that line ('1. Wyspa ... – Prawda')
    d2 = {}
    for ln in region.splitlines():
        m = re.match(r"^\s*(\d{1,2})[\.\):]", ln)
        if m and m.group(1) in keys and m.group(1) not in d2:
            t = re.search(rf"(?<!\w)({_PF_WORD})(?!\w)", ln[m.end():])
            if t and _pf_tok(t.group(1)):
                d2[m.group(1)] = _pf_tok(t.group(1))
    if len(d2) == len(keys):
        return d2, "lines"
    best = d2 if len(d2) > len(best) else best
    # 3) bare sequence ('P, F, P' / 'PFP')
    toks = [_pf_tok(t) for t in re.findall(rf"(?<!\w)({_PF_WORD})(?!\w)", region)]
    toks = [t for t in toks if t]
    if len(toks) < len(keys):
        compact = re.fullmatch(r"\s*([PF]{2,})\s*", region)
        if compact:
            toks = list(compact.group(1))
    if len(toks) >= len(keys):
        return dict(zip(keys, toks[: len(keys)])), "sequence" + ("" if len(toks) == len(keys) else "-extra")
    seq = dict(zip(keys, toks))
    best = seq if len(seq) > len(best) else best
    return best, "partial"


def parse_keyed(text: str, keys: list[str], value_re: str, allowed: set | None = None) -> tuple[dict, str]:
    region = answer_region(text)
    d = {}
    key_re = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    # key -> value ('A: 3', 'A-3', '1-B', '1. B', 'A – fragment 3')
    for m in re.finditer(rf"(?<![\w])({key_re})\s*[\.\):\-–—=]?\s*[\-–—:=]?\s*(?:fragment\w*\s*(?:nr\.?\s*)?)?"
                         rf"\(?({value_re})(?![\wąćęłńóśźż])", region):
        k, v = m.group(1), m.group(2).upper()
        if k not in d and (allowed is None or v in allowed):
            d[k] = v
    if len(d) == len(keys):
        return d, "keyed"
    # value -> key ('3-A' when the model reversed the pair)
    d2 = {}
    for m in re.finditer(rf"(?<![\w])({value_re})\s*[\-–—:=]\s*({key_re})(?![\w])", region):
        v, k = m.group(1).upper(), m.group(2)
        if k not in d2 and (allowed is None or v in allowed):
            d2[k] = v
    if len(d2) == len(keys):
        return d2, "reversed"
    # bare sequence ('B, C' / '3, 1')
    toks = [t.upper() for t in re.findall(rf"(?<![\w])({value_re})(?![\wąćęłńóśźż])", region)]
    toks = [t for t in toks if allowed is None or t in allowed]
    if len(toks) == len(keys) and len(region) < 40:
        return dict(zip(keys, toks)), "sequence"
    return (d if len(d) >= len(d2) else d2), "partial"


def parse_choice(text: str, letters: list[str], question: str) -> tuple[str | None, str]:
    allowed = set(letters)
    s = text.strip()
    m = re.match(r"^\(?([A-H])\)?(?:[\.\):]|\s|$)", s)
    if m and m.group(1) in allowed:
        return m.group(1), "start"
    region = answer_region(s)
    m = re.match(r"^\(?([A-H])\)?(?:[\.\):]|\s|$)", region)
    if m and m.group(1) in allowed and region is not s:
        return m.group(1), "marker"
    for m in re.finditer(r"(?:odpowied\w*|prawidłow\w*|poprawn\w*|właściw\w*|wybieram|jest)[^\n]{0,40}?"
                         r"(?<![\w])\(?([A-H])\)?(?=[\.\):,\s]|$)", s, re.I):
        if m.group(1) in allowed:
            return m.group(1), "phrase"
    for m in re.finditer(r"(?m)^\s*\(?([A-H])[\.\)]", s):
        if m.group(1) in allowed:
            return m.group(1), "line"
    # option text quoted in the answer
    opts = {m.group(1): m.group(2).strip().rstrip(".").lower()
            for m in re.finditer(r"(?m)^\s*([A-H])\.\s+(.+)$", question or "")}
    hits = [k for k, v in opts.items() if len(v) >= 6 and v in s.lower() and k in allowed]
    if len(hits) == 1:
        return hits[0], "option-text"
    return None, "unparsed"


def _cut_sentences(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    cut = s[:limit]
    m = list(re.finditer(r"[.!?](\s|$)", cut))
    return (cut[: m[-1].end()] if m else cut).strip()


def format_text(text: str, labels: list[str]) -> tuple[str, str]:
    s = clean(text)
    label_low = {l.lower() for l in labels}
    m = _ANS_MARK.match(s)
    if m and not any(l.startswith("odpowied") for l in label_low):
        s = s[m.end():].strip()
    s = re.sub(r"^(oto\s+(moja\s+)?odpowiedź|odpowiadam)\s*[:.]\s*", "", s, flags=re.I)
    note = "text"
    if labels:
        found = [l for l in dict.fromkeys(labels) if re.search(rf"(?<!\w){re.escape(l)}\s*:", s, re.I)]
        if found:
            # every label occurrence starts its own line, written exactly as on the sheet
            pos, out = 0, []
            for l in labels:
                mm = re.compile(rf"\s*(?<!\w){re.escape(l)}\s*:\s*", re.I).search(s, pos)
                if not mm:
                    continue
                out.append(s[pos:mm.start()])
                out.append(("\n" if (mm.start() > 0 or out and "".join(out).strip()) else "") + f"{l}: ")
                pos = mm.end()
            out.append(s[pos:])
            s = re.sub(r"\n{2,}", "\n", "".join(out)).strip()
            note = "labels-kept"
        elif len(labels) == 2:
            parts = re.split(r"(?<=[.!?])\s+", s.strip(), maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                s = f"{labels[0]}: {parts[0].strip()}\n{labels[1]}: {parts[1].strip()}"
            else:
                s = f"{labels[0]}: {s.strip()}"
            note = "labels-added"
        else:
            note = "labels-missing"
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    if len(s) > TEXT_MAX_CHARS:
        s = _cut_sentences(s, TEXT_MAX_CHARS)
        note += ",cut"
    return s, note


def essay_words(text: str) -> int:
    lines = (text or "").strip().splitlines()
    if lines and re.match(r"^\s*(wypracowanie\s+na\s+)?temat\w*\s*(nr|numer)?\.?\s*\d", lines[0], re.I):
        lines = lines[1:]
    return len(re.findall(rf"{_W}+(?:[-'’]{_W}+)*", "\n".join(lines)))


def _stems(s: str) -> set[str]:
    return {w[:5] for w in re.findall(rf"{_W}{{5,}}", s.lower())}


def format_essay(text: str, topics: list[tuple[str, str]]) -> tuple[str, str]:
    s = clean(text)
    s = re.sub(r"^(oto\s+(moje\s+)?wypracowanie[^\n]*|poniżej[^\n]*wypracowanie[^\n]*)\n+", "", s, flags=re.I)
    head = s[:250]
    m = re.search(r"temat\w*\s*(?:nr\.?|numer)?\s*([1-5])(?!\d)", head, re.I)
    note = "essay"
    if not m:
        n = None
        if topics:
            es = _stems(s)
            scored = sorted(((len(es & _stems(t)) / max(1, len(_stems(t))), num) for num, t in topics), reverse=True)
            n = scored[0][1]
        if n:
            s = f"Temat nr {n}\n\n" + s
            note = f"essay,topic-added:{n}"
        else:
            note = "essay,topic-missing"
    w = essay_words(s)
    if w < ESSAY_MIN_WORDS:
        note += f",short:{w}"
    return s.strip(), note


def post_format(item: dict, raw_answer: str) -> tuple[str, bool, str]:
    """(final answer string, format_ok, note)."""
    spec = spec_for(item)
    k = spec["kind"]
    s = clean(raw_answer)
    if not s:
        return "", False, "empty"
    if k == "pf":
        d, how = parse_pf(s, spec["keys"])
        if len(d) == len(spec["keys"]):
            return "\n".join(f"{x}: {d[x]}" for x in spec["keys"]), True, "pf:" + how
        if d:
            return "\n".join(f"{x}: {d[x]}" for x in spec["keys"] if x in d), False, f"pf:partial {len(d)}/{len(spec['keys'])}"
        return s, False, "pf:unparsed"
    if k in ("keyed_num", "keyed_letter", "keyed_text"):
        vre = r"\d{1,2}" if k == "keyed_num" else r"[A-H]" if k == "keyed_letter" else r"[^\s,;]+"
        allowed = set(spec["letters"]) if k == "keyed_letter" else None
        d, how = parse_keyed(s, spec["keys"], vre, allowed)
        if len(d) == len(spec["keys"]):
            return "\n".join(f"{x}: {d[x]}" for x in spec["keys"]), True, f"{k}:{how}"
        if d:
            return "\n".join(f"{x}: {d[x]}" for x in spec["keys"] if x in d), False, f"{k}:partial {len(d)}/{len(spec['keys'])}"
        return s, False, f"{k}:unparsed"
    if k == "choice":
        l, how = parse_choice(s, spec["letters"], item.get("question") or "")
        if l:
            return l, True, "choice:" + how
        return _cut_sentences(s, 400), False, "choice:unparsed"
    if k == "essay":
        out, note = format_essay(s, spec.get("topics") or [])
        return out, ("short" not in note and "missing" not in note), note
    out, note = format_text(s, spec.get("labels") or [])
    return out, note != "labels-missing", note


# ============================================================================ validation
def syntax_ok(item: dict, answer: str) -> bool:
    spec = spec_for(item)
    k = spec["kind"]
    if k == "pf":
        return bool(re.fullmatch("\n".join(rf"{re.escape(x)}: [PF]" for x in spec["keys"]), answer))
    if k == "keyed_num":
        return bool(re.fullmatch("\n".join(rf"{re.escape(x)}: \d{{1,2}}" for x in spec["keys"]), answer))
    if k == "keyed_letter":
        return bool(re.fullmatch("\n".join(rf"{re.escape(x)}: [A-H]" for x in spec["keys"]), answer))
    if k == "choice":
        return bool(re.fullmatch(r"[A-H]", answer))
    if k == "essay":
        return essay_words(answer) >= ESSAY_MIN_WORDS and bool(re.search(r"temat\w*\s*(nr\.?|numer)?\s*[1-5]",
                                                                          answer[:250], re.I))
    return True


def _secret_values() -> list[str]:
    """Values from .env (repo root) that must never appear in the file; never printed."""
    out = []
    for p in (Path(__file__).resolve().parent.parent / ".env", Path(".env")):
        try:
            for ln in p.read_text(encoding="utf-8").splitlines():
                if "=" in ln and not ln.lstrip().startswith("#"):
                    v = ln.split("=", 1)[1].strip().strip("'\"")
                    if len(v) >= 8:
                        out.append(v)
        except OSError:
            pass
    return out


def validate(obj, template: dict, exam: dict | None = None, raw_bytes: bytes | None = None) -> tuple[list, list]:
    errors, warnings = [], []
    if raw_bytes is None:
        raw_bytes = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    if len(raw_bytes) > MAX_FILE_BYTES:
        errors.append(f"file is {len(raw_bytes)} bytes > 1 MiB")
    if not isinstance(obj, dict):
        return ["top level is not an object"], warnings
    if set(obj) != {"exam_id", "answers"}:
        errors.append(f"top-level keys must be exactly exam_id, answers (got {sorted(obj)})")
    if obj.get("exam_id") != template.get("exam_id"):
        errors.append(f"exam_id {obj.get('exam_id')!r} != template {template.get('exam_id')!r}")
    answers = obj.get("answers")
    if not isinstance(answers, list):
        return errors + ["answers is not a list"], warnings
    want = [a["id"] for a in template.get("answers", [])]
    seen = []
    items = {it["id"]: it for it in (exam or {}).get("items", [])}
    for a in answers:
        if not isinstance(a, dict) or set(a) != {"id", "answer"}:
            errors.append(f"entry must have exactly id, answer: {str(a)[:80]}")
            continue
        if not isinstance(a["id"], str):
            errors.append(f"id {a['id']!r} is not a string")
        if not isinstance(a["answer"], str):
            errors.append(f"answer of {a['id']} is not a string")
            continue
        seen.append(a["id"])
        if len(a["answer"]) > MAX_ANSWER_CHARS:
            errors.append(f"answer {a['id']} longer than {MAX_ANSWER_CHARS} chars")
        if not a["answer"].strip():
            warnings.append(f"{a['id']}: blank")
        elif a["id"] in items and not syntax_ok(items[a["id"]], a["answer"]):
            warnings.append(f"{a['id']}: does not match answer_format ({spec_for(items[a['id']])['kind']})")
        if re.search(r"<think>|</think>", a["answer"]):
            warnings.append(f"{a['id']}: contains a <think> trace")
    dups = sorted({i for i in seen if seen.count(i) > 1})
    if dups:
        errors.append(f"duplicate ids: {dups}")
    missing = [i for i in want if i not in seen]
    extra = [i for i in seen if i not in want]
    if missing:
        errors.append(f"missing ids: {missing}")
    if extra:
        errors.append(f"ids not in template: {extra}")
    text = raw_bytes.decode("utf-8", "replace")
    if "TEAM_KEY" in text or any(v in text for v in _secret_values()):
        errors.append("file contains TEAM_KEY or a value from .env")
    return errors, warnings


def validate_file(path, template: dict, exam: dict | None) -> tuple[list, list]:
    raw = Path(path).read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return [f"not valid UTF-8 JSON: {e}"], []
    return validate(obj, template, exam, raw)


# ============================================================================ model calls
def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url: str, timeout: float = 10) -> object:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def set_lora_scale(llm_url: str, scale: float) -> str:
    base = llm_url.rstrip("/").removesuffix("/v1")
    ads = _get(base + "/lora-adapters")
    if not isinstance(ads, list) or not ads:
        return "no adapters"
    _post(base + "/lora-adapters", [{"id": a["id"], "scale": scale} for a in ads], 30)
    return json.dumps(_get(base + "/lora-adapters"))


def call_model(args, item: dict, text: str, spec: dict) -> dict:
    hint = format_instruction(item, spec)
    t0 = time.time()
    mode = args.mode
    if mode == "hybrid":  # raw Bielik for short items, harness (v3 essay pipeline) only for the essay
        mode = "harness" if spec["kind"] == "essay" else "raw"
    if mode == "raw":
        mt = args.raw_essay_max_tokens if spec["kind"] == "essay" else args.raw_max_tokens
        body = {"model": args.model, "messages": [{"role": "user", "content": text + "\n\n" + hint}],
                "temperature": 0, "max_tokens": mt, "cache_prompt": True}
        if args.extra_body:
            body.update(json.loads(args.extra_body))
        base = args.llm_url.rstrip("/").removesuffix("/v1")
        d = _post(base + "/v1/chat/completions", body, args.timeout)
        ch = (d.get("choices") or [{}])[0]
        raw = ((ch.get("message") or {}).get("content") or ch.get("text") or "")
        return {"raw": raw, "answer": raw, "finish": ch.get("finish_reason"), "latency": round(time.time() - t0, 1),
                "usage": d.get("usage"), "route": mode}
    body = {"question": text, "id": item["id"]}
    if spec["kind"] in ("text", "essay") and args.format_hint:
        body["system"] = hint
    if args.config:
        body["config"] = json.loads(args.config)
    d = _post(args.url.rstrip("/") + "/answer", body, args.timeout)
    raw = d.get("raw")
    if isinstance(raw, list):
        raw = "\n---\n".join(str(r) for r in raw)
    return {"raw": str(raw or "")[:30000], "answer": d.get("answer") or "", "qtype": d.get("qtype"),
            "mode": d.get("mode"), "latency": round(time.time() - t0, 1), "llm_calls": d.get("llm_calls"),
            "ctx_titles": [c.get("title") for c in (d.get("contexts") or [])][:12],
            "lora_off": ((d.get("parsed") or {}).get("essay") or (d.get("parsed") or {}).get("cke") or {}).get("lora_off"),
            "route": mode}


def predict_qtype(text: str) -> str:
    try:
        from harness.qtype import detect_v2
        return detect_v2(text).qtype
    except Exception:
        low = text.lower()
        if re.search(r"wybierz jeden z nich|minimum 300 wyraz|zadanie zawiera trzy tematy", low):
            return "essay"
        if re.search(r"(?m)^\s*(wyjaśnij|uzasadnij|rozstrzygnij|porównaj|sformułuj|scharakteryzuj|oceń)", low):
            return "explain"
        return "unknown"


# ============================================================================ main run
def read_debug(path: Path) -> dict:
    recs = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    r = json.loads(ln)
                    recs[r["id"]] = r
                except Exception:
                    pass
    return recs


def build_answers(exam: dict, template: dict, recs: dict) -> tuple[dict, list]:
    items = {it["id"]: it for it in exam["items"]}
    rows, notes = [], []
    for t in template["answers"]:
        iid = t["id"]
        r = recs.get(iid)
        ans, ok, note = "", False, "no-record"
        if r and not r.get("error") and iid in items:
            ans, ok, note = post_format(items[iid], r.get("answer") or "")
        rows.append({"id": iid, "answer": ans})
        notes.append((iid, ok, note))
    return {"exam_id": template["exam_id"], "answers": rows}, notes


def run(args) -> int:
    exam = load_json(args.exam)
    tpath = Path(args.template) if args.template else Path(args.exam).with_name("answers-template.json")
    template = load_json(tpath)
    desc = load_json(args.image_desc) if args.image_desc else None
    if args.desc_caveat:
        global DESC_LABEL
        DESC_LABEL = "Opis obrazu (automatyczny, może zawierać błędy; przy sprzeczności ufaj tekstowi źródła)"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dbg = Path(args.debug) if args.debug else out.with_name("debug.jsonl")
    items = [it for it in exam["items"] if not args.ids or it["id"] in args.ids.split(",")]
    tids = {a["id"] for a in template["answers"]}
    unknown = [it["id"] for it in exam["items"] if it["id"] not in tids]
    if unknown:
        print(f"WARNING exam items not in template: {unknown}", file=sys.stderr)

    recs = read_debug(dbg)
    if not args.reformat_only:
        todo = [it for it in items if not (it["id"] in recs and not recs[it["id"]].get("error")
                                           and (recs[it["id"]].get("answer") or "").strip())]
        print(f"{len(items)} items, {len(items) - len(todo)} done (resume), {len(todo)} to run -> {dbg}")
        lock = threading.Lock()

        def work(it, lora):
            spec = spec_for(it)
            text = item_text(it, desc)
            rec = {"id": it["id"], "system": args.system_name, "mode": args.mode, "kind": spec["kind"],
                   "input": text, "input_chars": len(text), "lora_scale": lora, "ts": time.time()}
            err = None
            for attempt in range(args.retries + 1):
                try:
                    rec.update(call_model(args, it, text, spec))
                    err = None
                    if (rec.get("answer") or "").strip():
                        break
                    err = "empty answer"
                except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
                    err = f"{type(e).__name__}: {str(e)[:300]}"
                time.sleep(2 * (attempt + 1))
            rec["error"] = err
            if not err:
                rec["final"], rec["format_ok"], rec["note"] = post_format(it, rec.get("answer") or "")
            with lock:
                with dbg.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return rec

        passes = [(todo, None)]
        if args.lora_llm_url and args.lora_off_types:
            off = {t.strip() for t in args.lora_off_types.split(",") if t.strip()}
            pred = {it["id"]: predict_qtype(item_text(it, desc)) for it in todo}
            passes = [([it for it in todo if pred[it["id"]] not in off], 1.0),
                      ([it for it in todo if pred[it["id"]] in off], 0.0)]
            print("LoRA-off items:", [it["id"] for it in passes[1][0]])
        for batch, lora in passes:
            if not batch:
                continue
            if lora is not None:
                print(f"LoRA scale -> {lora}: {set_lora_scale(args.lora_llm_url, lora)}")
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                futs = [ex.submit(work, it, lora) for it in batch]
                for n, fu in enumerate(as_completed(futs), 1):
                    r = fu.result()
                    print(f"[{n}/{len(batch)}] {r['id']} {r.get('latency', '-')}s "
                          f"{'ERR ' + r['error'] if r.get('error') else r.get('note', '')}", flush=True)
        if args.lora_llm_url and args.lora_off_types:
            print(f"LoRA scale restored -> 1.0: {set_lora_scale(args.lora_llm_url, 1.0)}")
        recs = read_debug(dbg)

    obj, notes = build_answers(exam, template, recs)
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    errors, warnings = validate(obj, template, exam, data)
    out.write_bytes(data)
    bad = [f"{i}({n})" for i, ok, n in notes if not ok]
    print(f"wrote {out} ({len(data)} bytes); answered {sum(1 for a in obj['answers'] if a['answer'].strip())}/"
          f"{len(obj['answers'])}; format issues: {bad or 'none'}")
    print("VALID" if not errors else "INVALID: " + "; ".join(errors))
    for w in warnings:
        print("  warn:", w)
    return 0 if not errors else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exam", nargs="?", help="exam.json")
    ap.add_argument("--out", help="answers.json to write")
    ap.add_argument("--template", default="", help="answers-template.json (default: next to exam.json)")
    ap.add_argument("--mode", choices=["harness", "raw", "hybrid"], default="harness",
                    help="hybrid = raw for every short item, harness for the essay (final config, 26.09)")
    ap.add_argument("--url", default="http://127.0.0.1:18000", help="harness base URL (mode harness)")
    ap.add_argument("--llm-url", default="http://127.0.0.1:18080", help="llama-server base URL (mode raw)")
    ap.add_argument("--model", default="bielik-4.5b-v3")
    ap.add_argument("--image-desc", default="", help='JSON {"images/X.png": "description"}')
    ap.add_argument("--desc-caveat", action="store_true",
                    help="label descriptions as machine-written and possibly wrong (vision-model descriptions)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--debug", default="", help="debug JSONL (default: debug.jsonl next to --out); resume source")
    ap.add_argument("--config", default="", help="JSON per-request harness overrides, e.g. '{\"cke_mode\": true}'")
    ap.add_argument("--no-format-hint", dest="format_hint", action="store_false",
                    help="harness mode: do not send the answer_format instruction as 'system' for free-text items")
    ap.add_argument("--extra-body", default="", help="raw mode: JSON merged into the chat request")
    ap.add_argument("--raw-max-tokens", type=int, default=700)
    ap.add_argument("--raw-essay-max-tokens", type=int, default=2400)
    ap.add_argument("--lora-llm-url", default="", help="llama-server whose global LoRA scale is switched per pass")
    ap.add_argument("--lora-off-types", default="", help="qtypes (harness.qtype.detect_v2) answered with LoRA scale 0")
    ap.add_argument("--ids", default="", help="comma list of item ids to run (default all)")
    ap.add_argument("--system-name", default="")
    ap.add_argument("--reformat-only", action="store_true", help="no model calls: rebuild answers.json from debug")
    ap.add_argument("--validate", default="", help="validate this answers.json and exit")
    ap.add_argument("--exam", dest="exam_opt", default="", help="exam.json for --validate")
    args = ap.parse_args(argv)
    if args.validate:
        exam_path = args.exam_opt or args.exam
        exam = load_json(exam_path) if exam_path else None
        tpath = args.template or (str(Path(exam_path).with_name("answers-template.json")) if exam_path else "")
        if not tpath:
            ap.error("--validate needs --template or --exam")
        errors, warnings = validate_file(args.validate, load_json(tpath), exam)
        print("VALID" if not errors else "INVALID: " + "; ".join(errors))
        for w in warnings:
            print("  warn:", w)
        return 0 if not errors else 1
    if not args.exam or not args.out:
        ap.error("exam and --out are required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
