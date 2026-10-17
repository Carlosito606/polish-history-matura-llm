"""CKE_MODE (harness v3): pure helpers for a CKE-graded exam (rubric grading, no format tricks).

What the full-paper evaluation (docs/cke_full_eval.md) asked for, and where it lives:
  * closed items (abcd, abj, pf, match, abcd_parts): 2-4 sentences of reasoning, then 'Odpowiedź: ...'; the last
    explicit answer is parsed (closed_instruction, final_region);
  * 'przyporządkuj władcę/państwo', 'Fragment A –' sheets, 'wpisz obok opisu nazwę': names, not '1-B'
    (names_task, parse_labeled, render_labeled) - every multi-part answer on ONE line;
  * 'Rozstrzygnij ... Uzasadnij': variants from the command (decision_variants, match_variant), per-source
    who/what/when (split_sources, cited_sources), yes/no debiased in harness/cke_flow.py;
  * explanations / comparisons: concrete content of each indicated source + 1-2 context facts, answer-sheet
    labels, granularity rules (explain_instruction, granularity_hint).
Everything here is deterministic and unit-tested (tests/test_cke.py); the LLM calls are in harness/cke_flow.py.
"""
from __future__ import annotations

import re
import unicodedata

from .qtype import _CMD_START, ParsedQuestion

UP = "A-ZĄĆĘŁŃÓŚŹŻ"
LO = "a-ząćęłńóśźż"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")


SYSTEM = (
    "Jesteś ekspertem z historii Polski i historii powszechnej i rozwiązujesz zadania z matury z historii "
    "(poziom rozszerzony). Odpowiedzi ocenia egzaminator CKE według klucza: liczą się poprawność merytoryczna, "
    "odwołanie do treści źródeł i konkretne fakty (nazwy, daty, pojęcia), a nie forma. Odpowiadasz po polsku.\n"
    "Przed zadaniem mogą znajdować się fragmenty artykułów z polskiej Wikipedii — korzystaj z nich, jeśli dotyczą "
    "zadania; jeśli nie, opieraj się na własnej wiedzy. Nie zmyślaj faktów. Nigdy nie odmawiaj odpowiedzi."
)


def fix_command(pq: ParsedQuestion) -> tuple[str, str]:
    """(sources, command) with a wrapped command repaired: 'Rozstrzygnij, który z fragmentów 1–3 ... Odpowiedź\n
    uzasadnij, ...' split at the lowercase 'uzasadnij' line -> the command starts at the 'Rozstrzygnij' line."""
    cmd = pq.command or ""
    if not pq.sources or not cmd[:1].islower():
        return pq.sources, cmd
    lines = pq.sources.split("\n")
    for i in range(len(lines) - 1, max(-1, len(lines) - 6), -1):
        ln = lines[i].strip()
        if ln[:1].isupper() and _CMD_START.match(ln):
            return "\n".join(lines[:i]).strip(), ("\n".join(lines[i:]) + "\n" + cmd).strip()
    return pq.sources, cmd


_SRC_NOISE = re.compile(r"^\s*(na\s+podstawie|n\s+podstawie|https?://|www\.|źródło\s+\d+\.?\s*$)", re.I)


def source_query(body: str, words: int = 40) -> str:
    """Retrieval query for one source unit: its text without the header, citation and URL lines."""
    from .retrieval import strip_image_desc  # local import: retrieval imports qtype, not cke
    body = strip_image_desc(body or "")
    lines = [ln for ln in body.split("\n") if ln.strip() and not _SRC_NOISE.match(ln)]
    txt = " ".join(" ".join(lines).split())
    txt = re.sub(r"^\S+\s+(\d{1,2}|[A-H])\s*\.?\s*:?\s*", "", txt, count=1)
    return " ".join(txt.split()[:words])


def mentions_sources(cmd: str) -> bool:
    return bool(re.search(r"źród|fragmen|teks|trakta|dokument|ilustracj|map[aieęy]|rysun|karykatur|plan\w*\s|"
                          r"fotografi|plakat|monet|wykres|tabel", cmd or "", re.I))


# ------------------------------------------------------------------ answer-sheet labels
# 'Rozstrzygnięcie:', 'Nazwa stylu 1.:', 'Cecha:', 'Wystawca:', 'Wydarzenie 2.:', 'Fragment A –'
_LABEL_LINE = re.compile(rf"^\s*([{UP}][^\n:–]{{0,40}}?)\s*(:|–|—|-)\s*$")
# table rows with the description printed: 'Opis zakonu A: Bracia mniejsi...', 'Fragment biografii B: Francuski...'
_DESC_LINE = re.compile(rf"^\s*((?:Opis|Fragment|Tekst|Biogram|Charakterystyka)\b[^:\n]{{0,25}}?\b([A-H]|\d))\s*[:.]\s*\S")


def sheet_labels(cmd: str) -> list[tuple[str, str]]:
    """Answer-sheet labels printed at the end of the command -> [(label, sep)] in order, sep ': ' or ' – '.
    Only the trailing block of short label lines counts (the command sentence itself never does)."""
    lines = [ln for ln in (cmd or "").split("\n") if ln.strip()]
    out: list[tuple[str, str]] = []
    for ln in reversed(lines):
        m = _LABEL_LINE.match(ln)
        if not m or len(m.group(1).split()) > 5 or m.group(1).lower().startswith(("odpowiedz", "zapisz")):
            break
        out.append((" ".join(m.group(1).split()), ": " if m.group(2) == ":" else " – "))
    return out[::-1]


def desc_labels(cmd: str) -> list[tuple[str, str]]:
    """'Opis zakonu A: ...' rows of a table to fill -> [('Opis zakonu A', ' – '), ...] (>= 2 rows)."""
    out = []
    for ln in (cmd or "").split("\n"):
        m = _DESC_LINE.match(ln)
        if m and m.group(1) not in [l for l, _ in out]:
            out.append((" ".join(m.group(1).split()), " – "))
    return out if len(out) >= 2 else []


_NAMES_CMD = re.compile(
    r"(przyporządkuj|wpisz\s+obok|obok\s+\w+\s+wpisz|uzupełnij\s+tabel|podaj\s+nazw|podaj\s+imi|podaj\s+nazwisk)"
    r"[^.]{0,120}?\b(władc|państw|nazw|nazwisk|imi|postać|postaci|miast|król|papież|cesarz|dynasti|zakon|polityk|"
    r"styl|epok|wydarzen)", re.I | re.S)
_CODE_CMD = re.compile(r"\b(numer|liter[ęyą]|cyfr|oznaczeni)", re.I)


def names_task(pq: ParsedQuestion, labels: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Labels of a 'write names next to A, B, ...' task, or [] when it is not one. 'Przyporządkuj władcę /
    państwo / nazwę' with 'Fragment A –' lines or described rows -> names (a grader wants 'Fragment A – Kazimierz
    Wielki', not '1-B'); 'wpisz numer/literę' stays a code-matching task."""
    cmd = pq.command or pq.text
    labels = labels if labels is not None else sheet_labels(cmd)
    if pq.qtype == "essay" or any(l.lower().startswith(("rozstrzygni", "uzasadni", "podobie", "różnic", "wyjaśni"))
                                  for l, _ in labels):
        return []
    dash = [x for x in labels if x[1] == " – "]
    if len(dash) >= 2 and not _CODE_CMD.search(cmd.split("\n")[0]):
        return dash
    rows = desc_labels(cmd)
    if rows and _NAMES_CMD.search(cmd) and not re.search(r"wpisz\s+(numer|liter)", cmd, re.I):
        return rows
    if _NAMES_CMD.search(cmd) and re.search(r"przyporządkuj", cmd, re.I) and not _CODE_CMD.search(cmd):
        rl = re.search(r"\b(fragment\w*|opis\w*|tekst\w*|źródł\w*)\s*\(?\s*([A-H])\s*[–—-]\s*([A-H])\b", cmd, re.I)
        if rl:
            noun = _NOUN.get(norm(rl.group(1))[:5], "Fragment")
            return [(f"{noun} {chr(c)}", " – ") for c in range(ord(rl.group(2)), ord(rl.group(3)) + 1)]
    return []


_LBL_SPLIT = re.compile(r"\s*(?:;|\n)\s*")


def parse_labeled(text: str, labels: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Model output -> [(label, sep, value)] in label order. Values are found after each label (': ', ' – ',
    '-'); labels may repeat ('Cecha:' twice) - they are matched left to right. Missing -> ''."""
    s = (text or "").replace("**", "")
    out, pos = [], 0
    spans = []
    for lab, sep in labels:
        # 'Nazwa stylu 1.:' also matches 'Nazwa stylu 1:' and the model's inflected 'Nazwę stylu 1.:'
        ws = lab.rstrip(".").split()
        core = r"\s+".join(re.escape(w[:4]) + r"[^\s:]*" if w.isalpha() and len(w) >= 5 else re.escape(w)
                           for w in ws) + r"\.?"
        # 'Fragment A' also matches a bare 'A' at the start of a line / after ';'
        short = re.escape(lab.split()[-1]) if len(lab.split()) > 1 and len(lab.split()[-1]) <= 2 else None
        pat = rf"(?:{core}|(?:(?<=^)|(?<=\n)|(?<=;\s)|(?<=,\s)){short})" if short else core
        m = re.compile(rf"{pat}\s*[\.\)]?\s*(?::|–|—|-)\s*", re.I | re.M).search(s, pos)
        if m:
            spans.append((lab, sep, m.start(), m.end()))
            pos = m.end()
        else:
            spans.append((lab, sep, None, None))
    found = [x for x in spans if x[2] is not None]
    for i, (lab, sep, st, en) in enumerate(spans):
        if st is None:
            out.append((lab, sep, ""))
            continue
        nxt = next((f[2] for f in found if f[2] > st), len(s))
        val = s[en:nxt]
        if sep == " – ":
            val = _LBL_SPLIT.split(val.strip())[0]
        else:  # an extra section the model appends ('\n\nFakty historyczne:\n- ...') is not part of the value
            val = re.split(rf"\n\s*\n(?=\s*\**[{UP}][^\n:]{{2,40}}\**\s*:)", val.strip())[0].strip()
        out.append((lab, sep, val.strip(" ;,\t").rstrip()))
    return out


def render_labeled(triples: list[tuple[str, str, str]], one_line: bool = True) -> str:
    parts = [f"{lab}{sep}{val}".strip() for lab, sep, val in triples]
    return "; ".join(parts) if one_line else "\n".join(parts)


# ------------------------------------------------------------------ final answer region
_ANS = re.compile(r"(?:ostateczna\s+)?odpowied[źz]\s*(?:\*\*)?\s*(?:końcowa\s*)?[:\-–]\s*", re.I)


def final_region(text: str) -> str:
    """Text after the LAST explicit 'Odpowiedź:' (reasoning stays out of parsing); without one: the last
    non-empty line."""
    s = (text or "").replace("**", "")
    if "</think>" in s:
        s = s.split("</think>")[-1]
    ms = list(_ANS.finditer(s))
    for m in reversed(ms):
        tail = s[m.end():].strip()
        if tail:
            return tail[:600]
    lines = [ln for ln in s.split("\n") if ln.strip()]
    return lines[-1].strip() if lines else ""


def reasoning_part(text: str) -> str:
    s = (text or "").replace("**", "")
    ms = list(_ANS.finditer(s))
    return (s[: ms[-1].start()] if ms else s).strip()


# ------------------------------------------------------------------ sources
_NOUN = {"zrodl": "Źródło", "fragm": "Fragment", "teks": "Tekst", "dokum": "Dokument", "plan": "Plan",
         "planu": "Plan", "plano": "Plan", "wersj": "Wersja", "trakt": "Traktat", "opis": "Opis", "opisu": "Opis",
         "ilust": "Ilustracja", "mapa": "Mapa", "mapy": "Mapa"}
_SRC_HEAD = re.compile(
    rf"^\s*(Źródło|Fragment\w*|Tekst|Dokument|Plan|Wersja|Ilustracja|Mapa|Traktat)"
    rf"((?:\s+[{LO}]+){{0,2}})\s+(\d{{1,2}}|[A-H])\s*\.?\s*(?=[:.\s]|$)", re.M)


def _kind(word: str) -> str:
    n = norm(word)
    for k, v in _NOUN.items():
        if n.startswith(k):
            return v
    return word.capitalize()


def split_sources(sources: str) -> list[tuple[str, str]]:
    """Source excerpts -> [('Źródło 1', text), ('Fragment A', text), ...]. A nested 'Fragment A:' inside
    'Źródło 2.' becomes its own unit; a header-only unit (< 60 chars of text) is dropped."""
    s = sources or ""
    heads = []
    for m in _SRC_HEAD.finditer(s):
        kind = _kind(m.group(1))
        mid = norm(m.group(2) or "")
        if kind == "Fragment" and re.search(r"traktat", mid):
            kind = "Traktat"
        heads.append((f"{kind} {m.group(3)}", m.start()))
    out = []
    for i, (lab, st) in enumerate(heads):
        en = heads[i + 1][1] if i + 1 < len(heads) else len(s)
        body = s[st:en].strip()
        if len(body) - len(lab) >= 60 and lab not in [o[0] for o in out]:
            out.append((lab, body))
    return out


_CITE = re.compile(r"\b(źród\w*|fragmen\w*|teks\w*|trakta\w*|dokumen\w*|plan\w*|wersj\w*)\b"
                   r"((?:[^.;]|(?<=\d)\.){0,30})", re.I)


def _labels_in(s: str) -> list[str]:
    s = re.sub(r"\b(?:ze|z|w|we|na)\s+(?:źród|fragmen|teks)\w*.*$", "", s, flags=re.I)  # 'B ze źródła 2.'
    m = re.match(r"\s*(?:[–—-]\s*|\(\s*|[\w ]{0,25}?[\s(]+)?(\d{1,2}|[A-H])\s*\.?\s*[–—-]\s*(\d{1,2}|[A-H])\b", s)
    if m and m.group(1).isdigit() == m.group(2).isdigit():
        a, b = m.group(1), m.group(2)
        if a.isdigit():
            return [str(i) for i in range(int(a), int(b) + 1)] if int(a) < int(b) <= 9 else []
        return [chr(c) for c in range(ord(a), ord(b) + 1)] if a < b else []
    head = re.match(r"\s*(?:[–—(]\s*)?((?:(?:\d{1,2}|[A-H])\.?\s*(?:,|i|oraz|czy|albo|lub|–)?\s*){1,4})", s)
    if not head:
        return []
    return re.findall(r"(?<![\wąćęłńóśźż])(\d{1,2}|[A-H])(?![\wąćęłńóśźż])", head.group(1))


def cited_sources(cmd: str, units: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The source units the command points at ('źródła 1. i 2.', 'fragmencie B ze źródła 2.', 'traktatów A i B',
    'obu źródeł'). Nothing explicit -> every unit (at most 3)."""
    if not units:
        return []
    by = {lab: body for lab, body in units}
    want: list[str] = []
    c = " ".join((cmd or "").split())
    for m in _CITE.finditer(c):
        kind = _kind(m.group(1))
        for lab in _labels_in(m.group(2)):
            key = f"{kind} {lab}"
            if key in by and key not in want:
                want.append(key)
            elif kind in ("Dokument", "Traktat", "Tekst", "Plan", "Wersja"):  # 'traktatów A i B' = 'Fragment A'
                alt = next((u for u in by if u.endswith(f" {lab}") and u not in want), None)
                if alt:
                    want.append(alt)
    if re.search(r"\bob(u|a|ydwu)\s+(źródeł|źródłach|źródła|fragment|tekst|traktat|dokument)", c, re.I) and len(want) < 2:
        kinds = {w.split()[0] for w in want} or {units[0][0].split()[0]}
        want += [u for u, _ in units if u.split()[0] in kinds and u not in want]
    if not want:
        want = [u for u, _ in units][:3]
    order = [u for u, _ in units]
    return [(w, by[w]) for w in sorted(want, key=order.index)][:4]


# ------------------------------------------------------------------ decisions ('Rozstrzygnij ...')
def _loc(w: str) -> str:
    """Instrumental -> locative for the 'przed X ... czy po niej' variant ('reformą' -> 'reformie')."""
    lw = w.lower()
    if lw.endswith("ią"):
        return w[:-2] + "ii"
    if lw.endswith(("rą", "tą", "ną", "wą", "mą", "pą", "bą", "dą", "łą", "są", "zą")):
        stem = w[:-1]
        if lw.endswith("łą"):
            return stem[:-1] + "le"
        if lw.endswith("rą"):
            return stem[:-1] + "rze"
        if lw.endswith("tą"):
            return stem[:-1] + "cie"
        if lw.endswith("dą"):
            return stem[:-1] + "dzie"
        return stem + "ie"
    if lw.endswith("em"):
        return w[:-2] + "u"
    return w


def decision_variants(cmd: str) -> dict:
    """What the 'Rozstrzygnięcie:' line may contain, read from the command.
    -> {'kind': 'yesno'|'choice', 'variants': [(key, display)], 'noun': str}.
    Patterns: '(A czy B)', '– A czy B –', '– Stanisławie czy Wojciechu –', 'przed reformą ... czy po niej',
    'który z fragmentów 1–3', 'który z dokumentów ... A–C', '... paleolitu czy neolitu', otherwise yes/no."""
    c = " ".join((cmd or "").split())
    # the 'Rozstrzygnij' sentence; '1.' / '2.' after a source number is not a sentence end
    m0 = re.search(rf"rozstrzygnij.*?(?:(?<![\d\s])\.(?=\s+[{UP}])|(?<=\d\.)(?=\s+(?:Odpowied|W\s+uzasadnieniu|Uzasadnij))|$)",
                   c, re.I)
    sent = (m0.group(0) if m0 else c).rstrip(".")
    noun = ""
    mn = re.search(r"\b(?:w\s+)?któr\w+\s+(?:z\s+)?(\w+)", sent, re.I)
    if mn:
        noun = _kind(mn.group(1)) if norm(mn.group(1))[:4] in {k[:4] for k in _NOUN} else ""

    def lab_variants(labels):
        return {"kind": "choice", "variants": [(l, f"{noun} {l}".strip() if noun else l) for l in labels],
                "noun": noun}

    m = re.search(r"\(\s*([^()]{1,40}?)\s+czy\s+([^()]{1,40}?)\s*\)", sent)
    if not m:
        m = re.search(r"[–—]\s*([^–—,]{1,40}?)\s+czy\s+([^–—,]{1,40}?)\s*[–—]", sent)
    if m:
        a, b = m.group(1).strip(" ."), m.group(2).strip(" .")
        if re.fullmatch(r"\d{1,2}|[A-H]", a) and re.fullmatch(r"\d{1,2}|[A-H]", b):
            return lab_variants([a, b])
        return {"kind": "choice", "variants": [(a, a), (b, b)], "noun": noun}
    m = re.search(rf"\bprzed\s+([{LO}]+)\b.*?\bczy\s+po\s+(niej|nim|nich)\b", sent, re.I)
    if m:
        w = m.group(1)
        return {"kind": "choice", "variants": [("przed", f"przed {w}"), ("po", f"po {_loc(w)}")], "noun": ""}
    m = re.search(r"\bktór\w+\s+z\s+(\w+)[^.]{0,60}?\b(\d|[A-H])\.?\s*[–—-]\s*(\d|[A-H])\b", sent)
    if m:
        noun = noun or _kind(m.group(1))
        labs = _labels_in(f"{m.group(2)}–{m.group(3)}")
        if labs:
            return lab_variants(labs)
    czys = [x for x in re.finditer(r"\s+czy\s+", sent)]
    if len(czys) >= 2 or (czys and not re.match(r"rozstrzygnij,?\s+czy\b", sent, re.I)):
        last = czys[-1]
        right = re.split(r"[,;–—]|\s+(?:jest|są|był|była|było|zostały|został|została)\b", sent[last.end():])[0]
        yw = right.split()[:5]
        before = sent[: last.start()].split()
        lw = [w for w in before[-6:]]
        if yw and yw[0].lower() in [w.lower() for w in lw]:
            k = max(i for i, w in enumerate(lw) if w.lower() == yw[0].lower())
            xw = lw[k:]
        else:
            xw = before[-min(max(1, len(yw)), 3):]
        a, b = " ".join(xw).strip(" .,"), " ".join(yw).strip(" .,")
        if a and b and not re.match(r"rozstrzygnij", a, re.I):
            return {"kind": "choice", "variants": [(a, a), (b, b)], "noun": noun}
    return {"kind": "yesno", "variants": [("tak", "Tak"), ("nie", "Nie")], "noun": ""}


def _stems(s: str) -> list[str]:
    ws = re.findall(r"[a-z0-9]+", norm(s))
    return [w[:5] if len(w) > 5 else w for w in ws]


def match_variant(text: str, dv: dict) -> int | None:
    """Index of the variant named in `text` (an answer line), None when unclear."""
    t = norm(text or "").strip()
    if not t:
        return None
    vs = dv["variants"]
    if dv["kind"] == "yesno":
        m = re.match(r"\W*(tak|nie)\b", t)
        if m:
            return 0 if m.group(1) == "tak" else 1
        return None
    if all(re.fullmatch(r"\d{1,2}|[A-H]", k) for k, _ in vs):
        noun = norm(dv.get("noun") or "")
        cands = []
        for i, (k, _) in enumerate(vs):
            pat = rf"(?<![a-z0-9]){re.escape(k.lower())}(?![a-z0-9])"
            m = re.search(pat, t)
            if m:
                cands.append((m.start(), i))
        if not cands:
            return None
        if noun:
            near = [x for x in cands if re.search(rf"{re.escape(noun[:5])}\w*\s*$", t[: x[0]])]
            if near:
                return near[0][1]
        return min(cands)[1]
    tw = set(_stems(t))
    sets = [set(_stems(k)) for k, _ in vs]
    scores = []
    for i, st in enumerate(sets):
        others = set().union(*[x for j, x in enumerate(sets) if j != i])
        dist = st - others or st
        scores.append(sum(1 for w in dist if w in tw) / max(1, len(dist)))
    best = max(scores)
    if best == 0 or scores.count(best) > 1:
        return None
    return scores.index(best)


# ------------------------------------------------------------------ prompts
GRANULARITY = [
    (re.compile(r"państw", re.I), "Gdy pytanie dotyczy państwa, podaj nazwę państwa (nie miasta, regionu ani dynastii)."),
    (re.compile(r"imię\s+i\s+przydomek|imię\s+oraz\s+przydomek", re.I), "Podaj oba człony: imię i przydomek (np. „Bolesław Chrobry”)."),
    (re.compile(r"imi(ę|ona)\s+władc|imię\s+wystawc|imi(ę|ona)\b", re.I), "Władcę podaj z imieniem i numerem lub przydomkiem (np. „Zygmunt III Waza”, „Kazimierz Wielki”)."),
    (re.compile(r"nazwisk", re.I), "Podaj imię i nazwisko."),
    (re.compile(r"dynasti", re.I), "Podaj nazwę dynastii (np. „Piastowie”, „Andegawenowie”)."),
    (re.compile(r"w\s+historiografii|stosowan\w+\s+nazw", re.I), "Podaj pełną nazwę stosowaną w podręcznikach historii."),
    (re.compile(r"datę\s+dzienn", re.I), "Podaj dzień, miesiąc i rok."),
    (re.compile(r"\bwiek\b|stuleci", re.I), "Wiek zapisz cyframi rzymskimi."),
]


def granularity_hint(cmd: str) -> str:
    return " ".join(h for r, h in GRANULARITY if r.search(cmd or ""))


REASON = ("Najpierw krótko rozumuj (2–4 zdania): odwołaj się do treści źródła i do faktów z fragmentów Wikipedii "
          "(nazwy, daty), sprawdź każdą możliwość. ")


def closed_instruction(pq: ParsedQuestion) -> str:
    """Reason first, then ONE final line 'Odpowiedź: ...' in the canonical format (parsed from that line)."""
    t = pq.qtype
    labs = lambda items: ", ".join(l for l, _ in items)  # noqa: E731
    if t == "abcd" and pq.n_select > 1:
        fmt = f"Odpowiedź: {', '.join(l for l, _ in pq.options[:pq.n_select])}"
        task = f"Zadanie wielokrotnego wyboru: wybierz dokładnie {pq.n_select} poprawne odpowiedzi spośród: {labs(pq.options)}."
    elif t == "abcd":
        fmt = "Odpowiedź: X (jedna litera)"
        task = f"Zadanie jednokrotnego wyboru: tylko jedna z odpowiedzi {labs(pq.options)} jest poprawna."
    elif t == "abj":
        fmt = "Odpowiedź: A2 (litera i numer uzasadnienia)"
        task = "Wybierz odpowiedź A albo B oraz jej poprawne uzasadnienie (numer)."
    elif t == "pf":
        n = len(pq.statements) or 2
        fmt = "Odpowiedź: " + ", ".join(["P"] * n) + " (P albo F dla każdego zdania, w kolejności)"
        task = (f"Oceń prawdziwość każdego z {n} zdań: P (prawda) albo F (fałsz). Zdanie jest fałszywe, jeśli "
                f"którakolwiek jego część jest niezgodna ze źródłem lub z faktami.")
    elif t == "abcd_parts":
        fmt = "Odpowiedź: " + ", ".join(f"{p[0]}-X" for p in pq.parts) + " (X = litera)"
        task = f"Zadanie ma {len(pq.parts)} zdania do dokończenia; dla każdego wybierz jedną poprawną odpowiedź."
    elif t == "match":
        ex = ", ".join(f"{l}-{pq.right[0][0] if pq.right else 'X'}" for l, _ in pq.left[:3])
        fmt = f"Odpowiedź: {ex}, … (pary oddzielone przecinkami, w jednej linii)"
        task = f"Przyporządkuj każdemu elementowi ({labs(pq.left)}) właściwy element ({labs(pq.right)})."
    elif t == "chrono":
        fmt = "Odpowiedź: " + ", ".join(l for l, _ in pq.items) + " (w poprawnej kolejności)"
        task = "Uporządkuj elementy chronologicznie, od najwcześniejszego do najpóźniejszego."
    else:
        return ""
    return (f"{task}\n{REASON}Nie przepisuj zadania. W ostatniej linii napisz dokładnie jedną odpowiedź w formacie:\n"
            f"{fmt}")


def open_instruction(pq: ParsedQuestion) -> str:
    g = granularity_hint(pq.command or pq.text)
    return ("Najpierw w 1–3 zdaniach ustal odpowiedź, odwołując się do treści źródła i do faktów z fragmentów "
            "Wikipedii. " + (g + " " if g else "") +
            "Jeśli polecenie wymaga kilku elementów, podaj je wszystkie w jednej linii, oddzielone przecinkami. "
            "W ostatniej linii napisz: „Odpowiedź: …” — samą odpowiedź (nazwę, termin, nazwisko, datę), bez uzasadnienia.")


def names_instruction(pq: ParsedQuestion, labels: list[tuple[str, str]]) -> str:
    g = granularity_hint(pq.command or pq.text)
    fmt = "; ".join(f"{l}{sep}…" for l, sep in labels)
    return ("Najpierw krótko (2–4 zdania) ustal, czego dotyczy każdy z elementów, odwołując się do jego treści "
            "(nazwy, daty, wydarzenia) i do fragmentów Wikipedii. Wpisz pełne nazwy (nie numery ani litery z listy). "
            + (g + " " if g else "") +
            f"W ostatniej linii napisz wszystkie odpowiedzi w jednej linii, w formacie:\nOdpowiedź: {fmt}")


def explain_instruction(pq: ParsedQuestion, labels: list[tuple[str, str]], cited: list[str]) -> str:
    """Explanations / comparisons / 'podaj nazwisko i wyjaśnij': concrete content of each indicated source,
    1-2 context facts, the answer-sheet labels kept, no lists."""
    cmd = pq.command or pq.text
    lab_names = [l.lower() for l, _ in labels]
    src = (" W odpowiedzi przywołaj konkretną informację z każdego wskazanego źródła (" + ", ".join(cited) +
           "): krótki cytat w cudzysłowie albo wierną parafrazę.") if cited else ""
    body = ("Odpowiedz rzeczowo w 2–4 pełnych zdaniach, bez list i punktorów." + src +
            " Dodaj 1–2 fakty z wiedzy historycznej (nazwy, daty, pojęcia) z fragmentów Wikipedii, które wyjaśniają "
            "związek przyczynowo-skutkowy. Nie dopisuj informacji, których nie jesteś pewien; każde zmyślone "
            "szczegóły obniżają ocenę.")
    if "podobieństwo" in lab_names:
        body = ("Podaj jedno podobieństwo i jedną różnicę między źródłami. Każde z nich najpierw nazwij własnymi "
                "słowami w jednym zdaniu (np. „Oba źródła oceniają … jako …”, „Źródło 1 podkreśla …, a źródło 2 …”), "
                "a potem poprzyj je krótkim odwołaniem do treści obu źródeł. Porównuj te same kwestie. Nie podawaj "
                "podobieństwa, które przeczy treści któregoś źródła. Bez list i punktorów.")
    g = granularity_hint(cmd) if any(x in norm(cmd) for x in ("podaj", "wymien", "nazw")) else ""
    if g:
        body += " " + g
    if re.search(r"elemen\w+\s+graficzn|ilustracj|fotografi|rysun|karykatur|plakat|monet|obraz", cmd, re.I):
        body += " Odwołuj się tylko do elementów opisanych w treści zadania; nie wymyślaj szczegółów obrazu."
    body += " Odpowiedz tylko na to polecenie."
    if labels:
        body += " Zachowaj dokładnie format karty odpowiedzi (każda etykieta w osobnej linii):\n" + \
                "\n".join(f"{l}{sep.strip() if sep.strip() == ':' else ' –'} …" for l, sep in labels)
    return body


def analysis_instruction(label: str) -> str:
    return (f"Ustal na podstawie treści: {label} (i fragmentów Wikipedii, jeśli dotyczą tego samego). "
            "Odpowiedz dokładnie w czterech krótkich liniach:\n"
            "Kto: autor lub główne postacie\nCo: jakie wydarzenie, dokument, zjawisko lub instytucja\n"
            "Kiedy: data lub okres (rok, dekada, wiek)\nGdzie: miejsce lub państwo\n"
            "Jeśli czegoś nie da się ustalić, napisz „nie wiadomo”. Nie zgaduj.")


_WHO = re.compile(r"^\W*(kto|co|kiedy|gdzie)\W*\s*[:\-–]\s*(.*)$", re.I)


def parse_analysis(text: str) -> str:
    """'Kto: …\nCo: …\nKiedy: …\nGdzie: …' (prefilled 'Kto:') -> 'Kto: …; Co: …; Kiedy: …; Gdzie: …'.
    Values may continue on bullet lines under the key; a repeated key (a second source) ends the parse."""
    got: dict[str, list[str]] = {}
    cur = None
    for ln in (text or "").replace("**", "").split("\n"):
        t = ln.strip()
        if not t:
            continue
        m = _WHO.match(t)
        if m:
            k = m.group(1).lower()
            if k in got:
                break
            cur = k
            got[k] = [m.group(2).strip(" *-")] if m.group(2).strip(" *-") else []
        elif cur and re.match(r"^[-*•]|\d+[.)]\s", t):
            got[cur].append(re.sub(r"^([-*•]|\d+[.)])\s*", "", t))
        elif cur:
            break
    got = {k: v for k, v in got.items() if v}
    if not got:
        return " ".join((text or "").split())[:200]
    return "; ".join(f"{k.capitalize()}: {', '.join(got[k])[:160]}" for k in ("kto", "co", "kiedy", "gdzie") if k in got)


def clean_justification(text: str) -> str:
    """Justification text: no verdict line, no inline 'Uzasadnienie:' / 'Fakt historyczny:' labels."""
    s = re.sub(r"(?im)^\s*\**\s*(rozstrzygnięcie|odpowiedź)\s*\**\s*:.*$", "", (text or "").replace("**", ""))
    s = re.sub(r"(?i)\b(uzasadnienie(\s+rozstrzygnięcia)?|fakty?(\s+historyczn\w*)?(\s+z\s+wikipedii)?|"
               r"wiedza\s+własna|wniosek|kontekst(\s+historyczny)?)\s*(\([^)]{0,40}\))?\s*:\s*", "", s)
    return flatten_prose(s)


def compare_instruction(dv: dict, cmd: str) -> str:
    if dv["kind"] == "yesno":
        rule = ("Arkusze maturalne celowo zestawiają źródła o podobnej tematyce, które dotyczą RÓŻNYCH wydarzeń, "
                "dokumentów lub okresów. Porównaj daty, osoby i miejsca z ustaleń. Odpowiedź „Tak” jest poprawna "
                "tylko wtedy, gdy warunek z polecenia jest spełniony dokładnie (np. oba źródła dotyczą tego samego "
                "wydarzenia, dokumentu, okresu lub zaboru); jeśli daty, osoby lub miejsca się nie zgadzają albo "
                "brakuje dowodu — odpowiedź brzmi „Nie”.")
        fmt = "Odpowiedź: Tak albo Nie"
    else:
        opts = " albo ".join(f"„{d}”" for _, d in dv["variants"])
        rule = f"Rozstrzygnięcie musi być jednym z wariantów z polecenia: {opts}."
        fmt = "Odpowiedź: " + " albo ".join(d for _, d in dv["variants"])
    rule += (" Porównując daty, ustaw je na osi czasu: każda data p.n.e. jest wcześniejsza niż każda data n.e. "
             "(np. 462 p.n.e. jest wcześniej niż 50 n.e.).")
    return (rule + "\nNapisz 2–3 zdania porównania (co wynika z każdego źródła i czy to się zgadza), a w ostatniej "
            f"linii:\n{fmt}")


def decide_instruction(dv: dict, labels: list[tuple[str, str]], cited: list[str], cmd: str) -> str:
    """One-call decision (CKE_DECIDE_MODE=summaries|direct): the verdict line is prefilled 'Rozstrzygnięcie:' so
    its first token's probability can be read (yes/no debias), then the justification follows."""
    src = ("każdego ze wskazanych źródeł (" + ", ".join(cited) + ")") if cited else "źródła"
    if dv["kind"] == "yesno":
        rule = ("Rozstrzygnięcie: napisz „Tak” albo „Nie”. Arkusze maturalne celowo zestawiają źródła o podobnej "
                "tematyce, które dotyczą RÓŻNYCH wydarzeń, dokumentów lub okresów — „Tak” napisz tylko wtedy, gdy "
                "warunek z polecenia jest spełniony dokładnie (zgadzają się daty, osoby, miejsca); w przeciwnym razie "
                "„Nie”.")
    else:
        rule = ("Rozstrzygnięcie: wpisz jeden z wariantów z polecenia: " +
                " albo ".join(f"„{d}”" for _, d in dv["variants"]) + " (nie „Tak” ani „Nie”).")
    rule += " Daty p.n.e. są wcześniejsze niż daty n.e."
    extra = [l for l, _ in labels if not l.lower().startswith(("rozstrzygni", "uzasadni"))]
    fmt = "Rozstrzygnięcie: …\nUzasadnienie: …" + "".join(f"\n{l}: …" for l in extra)
    ask = ""
    if re.search(r"podaj\s+nazw\w+\s+(bitwy|wydarzenia|dokumentu|traktatu)", cmd, re.I):
        ask = " Podaj w uzasadnieniu nazwę, o którą prosi polecenie."
    if re.search(r"wyjaśnij|scharakteryzuj", cmd, re.I) and not re.search(r"odpowiedź\s+uzasadnij", cmd, re.I):
        ask += " Wykonaj też drugą część polecenia (wyjaśnienie)."
    return (rule + f"\nUzasadnienie (2–4 zdania): przywołaj konkretne elementy {src} (nazwy, daty, cytowane "
            f"sformułowania w cudzysłowie) i — jeśli pomaga — jeden fakt z wiedzy historycznej, który wyjaśnia "
            f"rozstrzygnięcie.{ask} Bez list i punktorów.\nFormat odpowiedzi:\n{fmt}")


def justify_instruction(dv: dict, choice: str, labels: list[tuple[str, str]], cited: list[str], cmd: str) -> str:
    src = ("każdego ze wskazanych źródeł (" + ", ".join(cited) + ")") if cited else "źródła"
    extra = [l for l, _ in labels if not l.lower().startswith(("rozstrzygni", "uzasadni"))]
    ask_name = bool(re.search(r"podaj\s+nazw\w+\s+(bitwy|wydarzenia|dokumentu|traktatu)", cmd, re.I))
    lines = (f"Rozstrzygnięcie jest już ustalone: {choice}. Napisz uzasadnienie tego rozstrzygnięcia w 2–4 zdaniach: "
             f"przywołaj konkretne elementy {src} (nazwy, daty, cytowane sformułowania w cudzysłowie) oraz — jeśli "
             f"to pomaga — jeden fakt z wiedzy historycznej, który bezpośrednio wyjaśnia rozstrzygnięcie (np. datę lub "
             f"nazwę wydarzenia). Nie dodawaj faktów niezwiązanych z rozstrzygnięciem.")
    if ask_name:
        lines += " Podaj w uzasadnieniu nazwę, o którą prosi polecenie."
    if re.search(r"wyjaśnij|scharakteryzuj|przedstaw", cmd, re.I) and not re.search(r"odpowiedź\s+uzasadnij", cmd, re.I):
        lines += " Wykonaj też drugą część polecenia (wyjaśnienie)."
    lines += " Nie zmieniaj rozstrzygnięcia, nie powtarzaj go i nie dopisuj innych zadań."
    if extra:
        lines += " Na końcu dopisz osobne linie: " + "; ".join(f"{l}: …" for l in extra) + "."
    return lines + "\nNapisz samo uzasadnienie (bez etykiety „Uzasadnienie:”)."


# ------------------------------------------------------------------ output clean-up
_LIST_LINE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")


def flatten_prose(text: str) -> str:
    """Model prose -> one paragraph: markdown/list markers removed, lines joined ('1. Oczyszczenie: ...');
    a trailing 'Źródła:' / 'Klucz odpowiedzi' section is cut."""
    s = (text or "").replace("**", "").replace("__", "")
    s = re.split(r"(?im)^\s*(?:źródła|bibliografia|przypisy|klucz\s+odpowiedzi)\s*:?.*$", s)[0]
    s = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]{1,200}?)\*(?![\w*])", r"\1", s)  # *emphasis*
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.M)
    lines = [_LIST_LINE.sub("", ln).strip() for ln in s.split("\n")]
    lines = [ln for ln in lines if ln]
    out = []
    for ln in lines:
        if out and not re.search(r"[.!?…:;\"”»)]$", out[-1]):
            out[-1] = out[-1] + ("; " if ln[:1].isupper() and out[-1].endswith(tuple("abcdefghijklmnopqrstuvwxyząćęłńóśźż0123456789")) else " ") + ln
        else:
            out.append(ln)
    return " ".join(out).strip()


def render_explain_cke(text: str, labels: list[tuple[str, str]]) -> str:
    """Labelled explanation -> 'Label: value' lines in sheet order (repeated labels ok); no labels -> prose."""
    if not labels:
        return flatten_prose(re.sub(r"^\s*(odpowiedź|odpowiedz)\s*:\s*", "", text or "", flags=re.I))
    triples = parse_labeled(text, labels)
    if not any(v for _, _, v in triples):
        body = flatten_prose(text)
        return render_labeled([(labels[0][0], labels[0][1], body)] + [(l, s, "") for l, s in labels[1:]],
                              one_line=False)
    triples = [(l, s if s.strip() == ":" else " – ", flatten_prose(v)) for l, s, v in triples]
    return "\n".join(f"{l}{': ' if s.strip() == ':' else ' – '}{v}".rstrip() for l, s, v in triples)
