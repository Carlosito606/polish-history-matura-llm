"""Question type detection and parsing (options, statements, items, matching lists).

Types:
  abcd    - single (or multi) choice, lettered options A-H
  abj     - CKE "A/B + justification 1/2/3" (answer like "A2")
  pf      - list of statements, each true/false (P/F)
  chrono  - put items in chronological order
  match   - match numbered items (1..n) with lettered items (A..m)
  open    - short open answer (name / year / term ...)
  generic - anything else (free short answer)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

Item = tuple[str, str]  # (label, text)

_LETTER_LINE = re.compile(r"^\s*(?:\(([A-Ha-h])\)|([A-Ha-h])\s*[\.\):\-–—])\s*(\S.*)$")
_NUM_LINE = re.compile(r"^\s*(?:\((\d{1,2})\)|(\d{1,2})\s*[\.\):\-–—])\s*(\S.*)$")
_BULLET_LINE = re.compile(r"^\s*[\-•\*–]\s+(\S.*)$")
_PF_CELL = re.compile(r"^\s*(p|f|prawda|fałsz|falsz|tak|nie|p\s*/\s*f)\s*$", re.I)

KW_PF = re.compile(r"prawdziw|fałszyw|prawda\s*(?:/|czy|albo|lub)\s*fałsz|\bP\s*/\s*F\b|\(P\)|oceń prawdziwość", re.I)
KW_PF_STRONG = re.compile(r"(prawd\w*.{0,80}fałsz)|(fałsz\w*.{0,80}prawd)|\bP\s*/\s*F\b|oceń prawdziwość|\bP\b.{0,40}\bF\b", re.I | re.S)
KW_CHRONO = re.compile(r"chronologi|uporządkuj|uszereguj|w kolejności|od najwcześniejsz|od najdawniejsz|od najstarsz|od najpóźniejsz", re.I)
KW_MATCH = re.compile(r"przyporządkuj|dopasuj|połącz\w* w pary|przypisz|połącz\s", re.I)
KW_JUST = re.compile(r"uzasadnieni|ponieważ|dlatego że", re.I)
KW_MULTI = {
    2: re.compile(r"\b(dwie|dwa|2)\s+(poprawne\s+|prawidłowe\s+|właściwe\s+)?(odpowiedzi|odpowiedź|elementy|zdania|określenia|nazwy|postaci)", re.I),
    3: re.compile(r"\b(trzy|3)\s+(poprawne\s+|prawidłowe\s+|właściwe\s+)?(odpowiedzi|elementy|zdania|określenia|nazwy|postaci)", re.I),
}

OPEN_KIND = [
    ("year", re.compile(r"w którym roku|którego roku|w jakim roku|podaj rok\b|podaj datę roczną|data roczn|^\s*kiedy\b", re.I)),
    ("century", re.compile(r"w którym wieku|które stulecie|w jakim wieku|podaj wiek\b", re.I)),
    ("person", re.compile(r"\bkto\b|\bkogo\b|imię i nazwisko|podaj imię|podaj nazwisko|który (władca|król|książę|polityk|papież|cesarz|dowódca|hetman|prezydent|premier)|któr(ego|y) (władc|król)", re.I)),
    ("place", re.compile(r"\bgdzie\b|w jakim mieście|w którym mieście|miejscowoś|nazwę miasta", re.I)),
    ("number", re.compile(r"\bile\b|ilu\b|liczb", re.I)),
]

BOILERPLATE = [
    r"(zaznacz|wybierz|podkreśl)\s+(poprawną|właściwą|prawidłową)\s+odpowiedź[^.\n]*[.:]?",
    r"(zaznacz|wybierz)\s+(dwie|trzy|wszystkie)[^.\n]*[.:]?",
    r"oceń prawdziwość\s+(podanych\s+|poniższych\s+|następujących\s+)?(zdań|informacji|stwierdzeń)(\s+dotyczących|\s+odnoszących się do|\s+na temat)?",
    r"zaznacz\s+p,?\s+jeśli[^.\n]*[.:]?",
    r"wybierz\s+p,?\s+jeśli[^.\n]*[.:]?",
    r"(albo|lub)\s+f,?\s+(jeśli|–|-)[^.\n]*[.:]?",
    r"odpowiedz[^.\n]*(literą|jednym słowem|krótko|tylko)[^.\n]*[.:]?",
    r"uporządkuj\s+(chronologicznie\s+)?",
    r",?\s*od najwcześniejszego do najpóźniejszego\.?",
    r"przyporządkuj\s+",
    r"podaj\s+(tylko|jedynie)\s+[^.\n]*[.:]?",
]
_BOILER_RE = [re.compile(p, re.I) for p in BOILERPLATE]


@dataclass
class ParsedQuestion:
    text: str
    qtype: str = "generic"
    stem: str = ""
    options: list[Item] = field(default_factory=list)       # abcd / abj (letters)
    justifications: list[Item] = field(default_factory=list)  # abj (numbers)
    n_select: int = 1
    statements: list[Item] = field(default_factory=list)    # pf
    items: list[Item] = field(default_factory=list)         # chrono
    left: list[Item] = field(default_factory=list)          # match (to be assigned)
    right: list[Item] = field(default_factory=list)         # match (targets)
    open_kind: str = "other"
    # v2 only (QTYPE_V2=1)
    parts: list = field(default_factory=list)       # abcd_parts: [(label, sentence, [(letter, option), ...]), ...]
    labels: list[str] = field(default_factory=list)  # explain: answer-sheet labels ("Rozstrzygnięcie", ...)
    command: str = ""                                # final command/instruction part (sources stripped)
    sources: str = ""                                # everything before the command (source excerpts)
    topics: list = field(default_factory=list)       # essay: [(number, topic text), ...] in the printed order

    def to_dict(self) -> dict:
        d = {
            "qtype": self.qtype, "stem": self.stem, "options": self.options,
            "justifications": self.justifications, "n_select": self.n_select,
            "statements": self.statements, "items": self.items, "left": self.left,
            "right": self.right, "open_kind": self.open_kind,
        }
        if self.parts or self.labels or self.command:
            d.update(parts=self.parts, labels=self.labels, command_chars=len(self.command),
                     sources_chars=len(self.sources))
        if self.topics:
            d["topics"] = self.topics
        return d


def _clean_table_line(line: str) -> str:
    """Turn markdown table rows like '| 1. | Zdanie ... | P | F |' into '1. Zdanie ...'."""
    s = line.strip()
    if not (s.startswith("|") or s.count("|") >= 2):
        return line
    cells = [c.strip() for c in s.strip("|").split("|")]
    cells = [c for c in cells if c and not _PF_CELL.match(c) and not re.fullmatch(r"[-:\s]+", c)]
    if not cells:
        return ""
    if re.fullmatch(r"\(?[A-Ha-h0-9]{1,2}[\.\)]?", cells[0]) and len(cells) > 1:
        lab = cells[0].strip("().")
        return f"{lab}. " + " ".join(cells[1:])
    return " ".join(cells)


def _inline_letters(text: str) -> list[Item]:
    """Options written inline on one line: 'A. foo B. bar C. baz D. qux' or 'A) foo, B) bar'."""
    pat = re.compile(r"(?:(?<=\s)|^)\(?([A-H])[\.\)]\s+")
    ms = list(pat.finditer(text))
    # need consecutive letters starting at A
    seq = []
    expect = "A"
    for m in ms:
        if m.group(1) == expect:
            seq.append(m)
            expect = chr(ord(expect) + 1)
    if len(seq) < 2:
        return []
    out = []
    for i, m in enumerate(seq):
        end = seq[i + 1].start() if i + 1 < len(seq) else len(text)
        chunk = text[m.end():end].strip().rstrip(",;")
        chunk = chunk.split("\n")[0].strip()
        out.append((m.group(1), chunk))
    return out


def _consecutive(items: list[Item], first: str) -> list[Item]:
    """Keep the longest run of consecutive labels starting at `first` (A.. or 1..)."""
    out: list[Item] = []
    expect = first
    for lab, txt in items:
        if lab == expect:
            out.append((lab, txt))
            expect = chr(ord(expect) + 1) if expect.isalpha() else str(int(expect) + 1)
        elif out and lab == out[0][0]:
            # restart of a new list with same labels -> stop at first list
            break
    return out


def _collect_lines(text: str):
    letters: list[Item] = []
    numbers: list[Item] = []
    bullets: list[str] = []
    stem_lines: list[str] = []
    for raw in text.splitlines():
        line = _clean_table_line(raw)
        if not line.strip():
            continue
        m = _LETTER_LINE.match(line)
        if m and (m.group(1) or m.group(2)):
            lab = (m.group(1) or m.group(2)).upper()
            # avoid false positives like 'W. Jagiełło' - require uppercase label in raw or '(' form
            letters.append((lab, m.group(3).strip()))
            continue
        m = _NUM_LINE.match(line)
        if m and (m.group(1) or m.group(2)):
            txt = m.group(3).strip()
            # a line like '1410 r.' is not a list item; labels are small numbers
            numbers.append((str(int(m.group(1) or m.group(2))), txt))
            continue
        m = _BULLET_LINE.match(line)
        if m:
            bullets.append(m.group(1).strip())
            continue
        stem_lines.append(line.strip())
    return letters, numbers, bullets, stem_lines


def strip_boilerplate(s: str) -> str:
    out = s
    for r in _BOILER_RE:
        out = r.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip()


def detect(text: str, forced_type: str | None = None, v2: bool = False) -> ParsedQuestion:
    """v2=False reproduces the original detector exactly; v2=True -> detect_v2 (QTYPE_V2=1)."""
    if v2:
        return detect_v2(text, forced_type)
    text = (text or "").replace("\r\n", "\n").strip()
    letters, numbers, bullets, stem_lines = _collect_lines(text)
    letters_c = _consecutive(letters, "A")
    numbers_c = _consecutive(numbers, "1")
    stem = " ".join(stem_lines).strip() or text
    low = text.lower()
    pq = ParsedQuestion(text=text, stem=stem)

    if not letters_c:
        inl = _inline_letters(text)
        if inl:
            letters_c = inl
            # stem = text before first inline option
            first = re.search(r"(?:(?<=\s)|^)\(?A[\.\)]\s+", text)
            if first:
                pq.stem = text[: first.start()].strip() or stem

    t = forced_type
    if t is None:
        has_pf = bool(KW_PF_STRONG.search(text)) or bool(re.search(r"prawda\s*/\s*fałsz|\(P/F\)", low))
        if has_pf and (numbers_c or bullets or letters_c or KW_PF.search(text)):
            t = "pf"
        elif KW_CHRONO.search(text) and (letters_c or numbers_c or bullets) and not (
                len(letters_c) >= 2 and all(re.fullmatch(r"[\dIVXivx,;\s\-–—→>.]+", o) for _, o in letters_c)):
            # (options that are themselves sequences like "A. 2, 1, 3" -> it is an abcd question)
            t = "chrono"
        elif KW_MATCH.search(text) and letters_c and numbers_c:
            t = "match"
        elif len(letters_c) == 2 and len(numbers_c) >= 2 and KW_JUST.search(text):
            t = "abj"
        elif len(letters_c) >= 2:
            t = "abcd"
        elif len(text) <= 600 and not numbers_c:
            t = "open"
        else:
            t = "generic"

    pq.qtype = t
    if t in ("abcd", "abj"):
        pq.options = letters_c or _inline_letters(text)
        if t == "abj":
            pq.justifications = numbers_c
        else:
            for n, r in KW_MULTI.items():
                if r.search(text):
                    pq.n_select = n
                    break
        if not pq.options:  # forced abcd without parsable options
            pq.options = [(c, "") for c in "ABCD"]
    elif t == "pf":
        if numbers_c:
            pq.statements = numbers_c
        elif letters_c:
            pq.statements = letters_c
        elif bullets:
            pq.statements = [(str(i + 1), b) for i, b in enumerate(bullets)]
        else:
            pq.statements = []
    elif t == "chrono":
        if letters_c and (len(letters_c) >= len(numbers_c)):
            pq.items = letters_c
        elif numbers_c:
            pq.items = numbers_c
        else:
            pq.items = [(str(i + 1), b) for i, b in enumerate(bullets)]
    elif t == "match":
        # convention: numbered list is assigned letters ("1-B, 2-A")
        pq.left = numbers_c
        pq.right = letters_c
    elif t == "open":
        # the interrogative that starts the question wins over later mentions (e.g. "Który król ... w 1364 roku?")
        first = re.split(r"[?.]", text, maxsplit=1)[0]
        head = " ".join(first.split()[:4])
        for scope in (head, text):
            for kind, r in OPEN_KIND:
                if r.search(scope):
                    pq.open_kind = kind
                    break
            if pq.open_kind != "other":
                break
    return pq


# ============================================================================ v2 (QTYPE_V2=1)
# Fixes: (a) "Dokończ zdania 1. i 2." with one A-D list per sentence -> abcd_parts ("1-B, 2-C");
# (b) numbered/lettered items wrapped onto several lines are joined; (c) letter->number table fill
# ("A-3, B-2") and "Fragment N:" matching are match, not abcd; (d) wyjaśnij/uzasadnij/porównaj/
# rozstrzygnij+uzasadnij -> explain (multi-sentence, no newline stop); (e) the type is detected on the
# final command, not on the source excerpts that precede it.

_CMD_VERBS = (r"rozstrzygnij|oceń|dokończ|podaj|wyjaśnij|porównaj|przedstaw|sformułuj|na\s+podstawie(?!\s*:)|"
              r"przyporządkuj|każdemu|każdej|uporządkuj|uszereguj|zaznacz|wybierz|wskaż|określ|scharakteryzuj|"
              r"uzasadnij|wymień|napisz|uzupełnij|dopasuj|połącz|zapisz|ustal|rozpoznaj|nazwij|oblicz")
_CMD_START = re.compile(rf"^\s*(?:zadanie\s+\d+(?:\.\d+)*\.?\s*)?(?:{_CMD_VERBS})(?![\wąćęłńóśźż])", re.I)
_SHEET_LABEL = re.compile(
    r"^\s*(rozstrzygnięcie|uzasadnienie|nazwisko|imię|wyjaśnienie|podobieństwo|różnica|nazwa[^:\n]{0,30}|"
    r"cecha[^:\n]{0,20}|argument[^:\n]{0,10}|przyczyna[^:\n]{0,10}|skutek[^:\n]{0,10}|odpowiedź)\s*:\s*$", re.I)
_HINT = re.compile(
    r"^\s*(odpowiedz\b|odpowiedź\s+(podaj|zapisz)|zapisz\s+odpowiedź|"
    r"(podaj|wpisz|napisz|zaznacz|wybierz)\b[^.\n]{0,40}?(liter|cyfr|numer|przecink|kolejności|ciąg|oceny|odpowied|"
    r"odpowiedzi\s+w|\bp\b|„p”))", re.I)
_SENT_END = re.compile(r"[.!?:;…\"”»)]\s*$")
_FRAG_LINE = re.compile(r"^\s*(?:[Ff]ragment|[Tt]ekst|[Źź]ródło|[Dd]okument)\s+(\d{1,2}|[A-H])\.?\s*[:.]\s*(.*)$")
_LETTER_HINT = re.compile(r"podaj\s+liter[ęy]\s+([A-H])((?:\s*,\s*[A-H])*)\s*(?:,|albo|lub|czy)\s*([A-H])\b", re.I)
KW_EXPLAIN = re.compile(
    r"wyjaśnij|uzasadnij|uzasadnieni|porównaj|scharakteryzuj|sformułuj|oceń(?!\s+prawdziwo)|"
    r"przedstaw\b.{0,80}(przyczyn|skut|argument|podobieństw|różnic|cel\b|okoliczno)|w jaki sposób|dlaczego|"
    r"odwołując się|odwołaj się", re.I | re.S)
KW_DECIDE = re.compile(r"rozstrzygnij", re.I)
KW_TABLE_REV = re.compile(r"(obok|przy)\s+(każdego\s+)?opis\w*\s+wpisz\s+numer|wpisz\s+numer\w*\s+fragment|"
                          r"(opisom|opisowi)\s+[A-H]\s*[–-]\s*[A-H]\b", re.I)

# ---- essay / wypracowanie (v2 only). One strong signal, or two weak ones, makes an essay. A bare mention of
# "esej" / "wypracowanie" is weak on purpose: short items quote essays as sources ("Na podstawie fragmentu eseju...").
_ESSAY_STRONG = re.compile(
    r"(minimum|co\s+najmniej|min\.)\s*\d{3}\s*(wyraz|słów|slow)|"
    r"zadanie\s+zawiera\s+(dwa|trzy|cztery|pięć|\d)\s+temat|"
    r"wybierz\s+jeden\s+z\s+(nich|tematów|podanych\s+tematów)\s+do\s+opracowania|"
    r"zajmij\s+stanowisko\s+wobec\s+(powyższej\s+|tej\s+|podanej\s+|przytoczonej\s+|następującej\s+)?tezy\b"
    r"[^\n]{0,60}\n?[^\n]{0,80}uwzględniając|"
    r"napisz\s+(wypracowanie|esej|rozprawkę|wypowiedź\s+argumentacyjną)|"
    r"w\s+formie\s+(eseju|rozprawki|wypracowania|wypowiedzi\s+argumentacyjnej)|"
    r"^\s*wypracowanie\s*(na\s+temat|$)|"
    r"\((0\s*[–-]\s*1[0-5]|1[0-5]\s*(pkt|punkt\w*))\)", re.I | re.M)
_ESSAY_WEAK = [re.compile(p, re.I) for p in (
    r"\bwypracowani\w*", r"\brozprawk\w*", r"\besej\w*", r"wypowied\w*\s+argumentacyjn\w*",
    r"zajmij\s+stanowisko", r"\b(tematów|tematy)\b", r"\b[3-9]00\s+(wyraz|słów)")]
_TOPICS_END = re.compile(r"^\s*(Materiały\s+źródłowe\s+do|WYPRACOWANIE\b|Wypełnia\s+egzaminator)", re.M)
_TOPIC_LINE = re.compile(r"^\s*(?:temat\s+(?:nr\s+)?)?([1-5])\.\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„\"«(])", re.I | re.M)
_ASPECTS = re.compile(r"aspek(?:t|ci)\w*\s*:?\s*([^.\n]+)|uwzględniając\s+w\s+swojej\s+argumentacji\s*:\s*([^.\n]+)", re.I)


def is_essay(text: str) -> bool:
    t = text or ""
    if _ESSAY_STRONG.search(t):
        return True
    return sum(1 for r in _ESSAY_WEAK if r.search(t)) >= 2


def essay_topics(text: str) -> list[tuple[str, str]]:
    """Numbered topics (1., 2., ...) in the printed order; the region ends at the source materials or the
    'WYPRACOWANIE' answer line. One unnumbered topic -> [("1", whole command)]."""
    t = (text or "").replace("\r\n", "\n")
    ms = list(_TOPIC_LINE.finditer(t))
    seq, expect = [], 1
    for m in ms:
        if int(m.group(1)) == expect:
            seq.append(m)
            expect += 1
    if len(seq) >= 2:
        out = []
        for i, m in enumerate(seq):
            end = seq[i + 1].start() if i + 1 < len(seq) else len(t)
            chunk = t[m.end():end]
            stop = _TOPICS_END.search(chunk)
            if stop:
                chunk = chunk[: stop.start()]
            out.append((m.group(1), " ".join(chunk.split()).replace("- -", "-").replace("-  -", "-")))
        return out
    body = t[: m.start()] if (m := _TOPICS_END.search(t)) and m.start() > 40 else t
    return [("1", " ".join(body.split()))]


def essay_aspects(topic: str) -> list[str]:
    """'... uwzględniając w swojej argumentacji aspekty: polityczny, społeczno-gospodarczy i kulturowy.'
    -> ['polityczny', 'społeczno-gospodarczy', 'kulturowy'] ([] when the topic lists no elements)."""
    m = _ASPECTS.search(" ".join((topic or "").split()))
    if not m:
        return []
    raw = re.sub(r"-\s+-?", "-", m.group(1) or m.group(2))
    parts = [p.strip(" ,;:") for p in re.split(r",|\s+i\s+|\s+oraz\s+|\s+a\s+także\s+", raw)]
    parts = [p for p in parts if 2 <= len(p) <= 80 and len(p.split()) <= 6]
    return parts if 2 <= len(parts) <= 5 else []


def split_command(text: str) -> tuple[str, str]:
    """(sources, command): command = from the last line that starts with a command verb to the end
    (format hints like 'Odpowiedz w formacie' / 'Podaj literę' and sheet labels never start a command).
    No command line (or it is the first line) -> ("", text)."""
    lines = text.split("\n")
    idx = None
    for i, raw in enumerate(lines):
        ln = raw.strip()
        if not ln or _HINT.match(ln) or _SHEET_LABEL.match(ln):
            continue
        if _CMD_START.match(ln):
            idx = i
    if not idx:
        return "", text
    # the question's own list often precedes the command ("Poniżej wymieniono...\nA. ...\nD. ...\nUporządkuj ...")
    j = idx
    while j > 0 and lines[j - 1].strip() and (
            _LETTER_LINE.match(_clean_table_line(lines[j - 1])) or _NUM_LINE.match(_clean_table_line(lines[j - 1]))
            or _BULLET_LINE.match(lines[j - 1]) or lines[j - 1].strip()[0].islower()):
        j -= 1
    if 0 < j < idx and lines[j - 1].strip() and len(lines[j - 1]) <= 200:
        j -= 1  # lead-in line of that list ("Poniższe zdania dotyczą ...")
    if j == 0:
        return "", text
    return "\n".join(lines[:j]).strip(), "\n".join(lines[j:]).strip()


def _entries_v2(text: str) -> list[tuple[str, str, str]]:
    """Ordered line entries ('L'|'N'|'B'|'S', label, text); wrapped continuation lines are joined to the
    previous list item (CKE statements wrap mid-sentence onto the next line)."""
    out: list[list[str]] = []
    for raw in text.splitlines():
        line = _clean_table_line(raw)
        s = line.strip()
        if not s:
            continue
        m = _LETTER_LINE.match(line)
        if m and (m.group(1) or m.group(2)):
            out.append(["L", (m.group(1) or m.group(2)).upper(), m.group(3).strip()])
            continue
        m = _NUM_LINE.match(line)
        if m and (m.group(1) or m.group(2)):
            out.append(["N", str(int(m.group(1) or m.group(2))), m.group(3).strip()])
            continue
        m = _BULLET_LINE.match(line)
        if m:
            out.append(["B", "", m.group(1).strip()])
            continue
        if out and out[-1][0] in ("L", "N", "B") and not (
                _HINT.match(s) or _SHEET_LABEL.match(s) or _CMD_START.match(s) or s.endswith("?")):
            prev = out[-1][2]
            lower = s[0].islower() or s[0].isdigit()
            # options (letters) are short: join only clear lowercase wraps; statements: also unfinished sentences
            if lower or (out[-1][0] != "L" and not _SENT_END.search(prev)):
                out[-1][2] = (prev + " " + s).strip()
                continue
        out.append(["S", "", s])
    return [tuple(e) for e in out]


def _lists_v2(entries):
    letters = [(l, t) for k, l, t in entries if k == "L"]
    numbers = [(l, t) for k, l, t in entries if k == "N"]
    bullets = [t for k, _, t in entries if k == "B"]
    stem = " ".join(t for k, _, t in entries if k == "S")
    return letters, numbers, bullets, stem


def _last_letter_run(entries) -> list[Item]:
    """The last run of consecutive lettered lines A, B, C... anywhere in the text."""
    runs, cur = [], []
    for k, l, t in entries:
        if k == "L" and l == chr(ord("A") + len(cur)):
            cur.append((l, t))
        elif k == "L" and l == "A":
            if cur:
                runs.append(cur)
            cur = [(l, t)]
        else:
            if k != "S" and cur:  # a numbered line interrupts a letter run
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    runs = [r for r in runs if len(r) >= 2]
    return runs[-1] if runs else []


def _parts_v2(entries) -> list:
    """'1. sentence' followed by its own A.. list, repeated -> [(label, sentence, options)]."""
    parts, cur = [], None
    for k, l, t in entries:
        if k == "N":
            cur = [l, t, []]
            parts.append(cur)
        elif k == "L" and cur is not None:
            if l == chr(ord("A") + len(cur[2])):
                cur[2].append((l, t))
    parts = [p for p in parts if len(p[2]) >= 2]
    labels = [p[0] for p in parts]
    if len(parts) >= 2 and labels == [str(i + 1) for i in range(len(parts))]:
        return [(p[0], p[1], p[2]) for p in parts]
    return []


def _range_labels(cmd: str) -> list[str]:
    m = re.search(r"(?<![\d.])(\d)\s*[–—-]\s*(\d)(?![\d.])", cmd)
    if m and int(m.group(1)) < int(m.group(2)) <= 9:
        return [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
    xs = re.findall(r"(?<![\d])(\d{1,2})\s*[-–]\s*X\b", cmd)
    return xs if len(xs) >= 2 else []


def _open_kind(cmd: str) -> str:
    first = re.split(r"[?.]", cmd, maxsplit=1)[0]
    head = " ".join(first.split()[:4])
    for scope in (head, cmd):
        for kind, r in OPEN_KIND:
            if r.search(scope):
                return kind
    return "other"


def detect_v2(text: str, forced_type: str | None = None) -> ParsedQuestion:
    text = (text or "").replace("\r\n", "\n").strip()
    sources, cmd = split_command(text)
    all_entries = _entries_v2(text)
    entries = _entries_v2(cmd) if sources else all_entries
    letters, numbers, bullets, stem = _lists_v2(entries)
    letters_c = _consecutive(letters, "A")
    numbers_c = _consecutive(numbers, "1")
    # retrieval stem = the v1 stem (all non-list lines incl. the sources): a command-only stem measurably hurt
    # retrieval on CKE items (the command says "źródło 1." while the content words live in the sources)
    v1_stem = " ".join(_collect_lines(text)[3]).strip()
    pq = ParsedQuestion(text=text, stem=(v1_stem if sources else stem) or cmd, command=cmd, sources=sources)
    if not letters_c:
        inl = _inline_letters(cmd)
        if inl:
            letters_c = inl
            first = re.search(r"(?:(?<=\s)|^)\(?A[\.\)]\s+", cmd)
            if first and not sources:
                pq.stem = cmd[: first.start()].strip() or pq.stem
    low = cmd.lower()
    labels = [m.group(1).strip().capitalize() for ln in cmd.splitlines() if (m := _SHEET_LABEL.match(ln))]
    wants_just = bool(re.search(r"uzasadni", low)) or any(l.lower().startswith("uzasadnienie") for l in labels)
    parts = _parts_v2(entries)
    hint = _LETTER_HINT.search(cmd)

    t = forced_type
    match_lr = None
    if t in (None, "match"):
        match_lr = _match_lists_v2(cmd, entries, all_entries, sources, letters_c, numbers_c)
    if t is None:
        has_pf = bool(KW_PF_STRONG.search(cmd)) or bool(re.search(r"prawda\s*/\s*fałsz|\(P/F\)", low))
        if is_essay(text):  # checked on the whole text: CKE prints the source materials after the topics
            t = "essay"
        elif has_pf and (numbers_c or bullets or letters_c or KW_PF.search(cmd)):
            t = "pf"
        elif KW_CHRONO.search(cmd) and (letters_c or numbers_c or bullets) and not (
                len(letters_c) >= 2 and all(re.fullmatch(r"[\dIVXivx,;\s\-–—→>.]+", o) for _, o in letters_c)):
            t = "chrono"
        elif parts:
            t = "abcd_parts"
        elif (KW_MATCH.search(cmd) or re.search(r"uzupełnij\s+tabel", low)) and match_lr:
            t = "match"
        elif len(letters_c) == 2 and len(numbers_c) >= 2 and KW_JUST.search(cmd):
            t = "abj"
        elif (len(letters_c) >= 2 or hint) and not wants_just:
            t = "abcd"
        elif KW_EXPLAIN.search(cmd) or labels or (KW_DECIDE.search(cmd) and wants_just):
            t = "explain"
        elif len(letters_c) >= 2:
            t = "abcd"
        elif (len(cmd) <= 600 or re.match(r"\s*(podaj|wymień|nazwij|określ|rozstrzygnij)\b", cmd, re.I)) \
                and not numbers_c:
            t = "open"
        else:
            t = "generic"

    pq.qtype = t
    if t in ("abcd", "abj"):
        pq.options = letters_c or _inline_letters(cmd)
        if not pq.options and hint:
            ls = [hint.group(1)] + re.findall(r"[A-H]", hint.group(2) or "") + [hint.group(3)]
            pq.options = [(c.upper(), "") for c in ls]
        if t == "abj":
            pq.justifications = numbers_c
        else:
            for n, r in KW_MULTI.items():
                if r.search(cmd):
                    pq.n_select = n
                    break
        if not pq.options:
            pq.options = [(c, "") for c in "ABCD"]
    elif t == "abcd_parts":
        pq.parts = parts
        pq.left = [(p[0], p[1]) for p in parts]
        pq.right = [(l, "") for l in sorted({l for p in parts for l, _ in p[2]})]
    elif t == "pf":
        if numbers_c:
            pq.statements = numbers_c
        elif letters_c:
            pq.statements = letters_c
        elif bullets:
            pq.statements = [(str(i + 1), b) for i, b in enumerate(bullets)]
    elif t == "chrono":
        if letters_c and (len(letters_c) >= len(numbers_c)):
            pq.items = letters_c
        elif numbers_c:
            pq.items = numbers_c
        else:
            pq.items = [(str(i + 1), b) for i, b in enumerate(bullets)]
    elif t == "match":
        if match_lr:
            pq.left, pq.right = match_lr
        else:
            pq.left, pq.right = numbers_c, letters_c
    elif t == "explain":
        if not labels:
            if KW_DECIDE.search(cmd) and wants_just:
                labels = ["Rozstrzygnięcie", "Uzasadnienie"]
            elif re.search(r"podobieństw", low) and re.search(r"różnic", low):
                labels = ["Podobieństwo", "Różnica"]
            elif re.search(r"podaj\s+(nazwisko|imię)", low) and re.search(r"wyjaśnij|uzasadnij", low):
                labels = ["Nazwisko", "Wyjaśnienie"]
        pq.labels = labels
        pq.open_kind = ("decision" if labels[:1] == ["Rozstrzygnięcie"] else
                        "compare" if "Podobieństwo" in labels else
                        "name_explain" if labels[:1] in (["Nazwisko"], ["Imię"]) else "explain")
    elif t == "open":
        pq.open_kind = _open_kind(cmd)
    elif t == "essay":
        pq.topics = essay_topics(text)
    return pq


def _match_lists_v2(cmd, entries, all_entries, sources, letters_c, numbers_c):
    """(left, right) for matching tasks, keeping the question's direction.
    numbers -> letters ('1-B'): left = numbered items / 'Fragment N:' blocks, right = lettered list.
    letters -> numbers ('A-3', CKE 'obok opisu wpisz numer fragmentu'): left = lettered items, right = numbers."""
    frags, lfrags = [], []
    for k, l, t in all_entries:
        m = _FRAG_LINE.match(t) if k == "S" else None
        if m:
            dst = lfrags if m.group(1).isalpha() else frags
            if m.group(1) not in [f[0] for f in dst]:
                dst.append((m.group(1), m.group(2).strip()[:300]))
    if KW_TABLE_REV.search(cmd) or re.search(r"\b[A-H]\s*[-–]\s*X\b", cmd):
        left = letters_c or _last_letter_run(entries)
        right = frags or numbers_c or [(x, "") for x in _range_labels(cmd)]
        if left and len(right) >= 2:
            return left, right
        return None
    right = letters_c if len(letters_c) >= 2 else (_last_letter_run(all_entries) or lfrags)
    left = numbers_c
    if not left:
        rl = _range_labels(cmd)
        fd = dict(frags)
        left = [(x, fd.get(x, "")) for x in rl] if rl else frags
    if left and len(right) >= 2:
        return left, right
    return None


_STOP_CAPS = {"który", "która", "które", "którego", "kto", "podaj", "wybierz", "zaznacz", "oceń", "uporządkuj",
              "przyporządkuj", "prawda", "fałsz", "odpowiedź", "zadanie", "pytanie", "wskaż", "jak", "jaki", "jaka",
              "gdzie", "kiedy", "dlaczego", "czy", "w którym", "the"}
_ENT = re.compile(r"(?<![\w])([A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż\-]+(?:[ 	]+(?:[A-ZĄĆĘŁŃÓŚŹŻIVX][\wąćęłńóśźż\-]*|z|ze|von|de|du|i|nad|pod|w|we)){0,4})")
_YEAR = re.compile(r"(?<!\d)(\d{3,4})(?!\d)\s*(?:r\.|roku|rok)?")


def entities(text: str) -> list[str]:
    """Capitalised multi-word names (not sentence-initial when possible) and years."""
    ents: list[str] = []
    for m in _ENT.finditer(text):
        e = m.group(1).strip()
        # drop trailing function words
        e = re.sub(r"(\s+(z|ze|i|w|we|nad|pod|von|de|du))+$", "", e)
        start = m.start()
        before = text[:start].rstrip(" \t\"'„(")
        sentence_start = before == "" or before[-1] in ".?!:\n" or before.endswith((")", "–", "-"))
        if sentence_start and " " not in e:
            continue
        if len(e) < 3 or e.lower() in _STOP_CAPS or e.split()[0].lower() in _STOP_CAPS:
            continue
        if re.fullmatch(r"[A-H]", e.split()[-1]) and len(e.split()) > 1:  # 'Zaznacz P', trailing option label
            e = " ".join(e.split()[:-1])
        ents.append(e)
    for m in _YEAR.finditer(text):
        y = int(m.group(1))
        if 300 <= y <= 2030:
            ents.append(m.group(1))
    seen, out = set(), []
    for e in ents:
        k = e.lower()
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out
