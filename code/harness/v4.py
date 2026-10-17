"""Harness v4: flags and pure helpers (the LLM flows are in harness/v4_flow.py). Every fix is OFF by default;
with all V4 flags off every prompt is byte-identical to v3 (tests/test_v4.py, fixture tests/fixtures/v3_prompts.json).

Fixes (docs/error_map_v2.md, docs/cke_*_eval.md), each behind its own flag; V4=1 turns on those in V4_UMBRELLA:
  V4_ABCD_PARTS        abcd_parts ('Dokończ zdania 1. i 2.') -> one abcd call per sentence
  V4_CONTINUE          closed items whose reasoning is cut before 'Odpowiedź:' -> continue the assistant turn with
                       'Odpowiedź:' (the model finishes its own conclusion) before the v3 grammar retry
  V4_SOURCE_FIRST      items with a source: identify the source first (Kto/Co/Kiedy/Gdzie, short call), retrieve with
                       that identification + the command, never with the P/F statements or the ABCD options
  V4_TITLE_RESCORE     raw-title re-scoring of retrieval candidates: bonus for a title that the question names exactly,
                       penalty for a different Roman numeral ('II wojna punicka' vs 'I wojna punicka')
  V4_PF_EVIDENCE       P/F: every F needs a quoted contradicting sentence from the context/source, else P
  V4_PF_VALUE          P/F: statements with a number/date/quantifier judged P are re-checked value-first
  V4_NEUTRAL_EXAMPLES  answer-format examples in the question ('1-B, 2-A') -> '1-X, 2-X' before the model sees them
  V4_CHRONO_BC         chrono: ' p.n.e.' allowed after years in the grammar (2: also asked for in the prompt);
                       unsigned year -> BC when the item, stem or context says so
  V4_CHRONO_TIES       chrono: items tied on the year -> month/day question (1) or pairwise 'which was earlier' (2)
  SC_K / SC_TEMPERATURE  closed items: K answers of the SAME model (greedy + K-1 sampled), per-sub-answer majority
A flag set explicitly to 0/1 wins over V4; -1 (default) follows V4.
"""
from __future__ import annotations

import re
import unicodedata

# fixes that V4=1 turns on: the ones that helped on the error-map items (L40S, 26.09, harness/README.md "Harness v4").
# Measured and left OFF: v4_source_first, v4_pf_evidence, v4_pf_value, v4_chrono_bc, v4_chrono_ties, SC_K>1.
V4_UMBRELLA = {"v4_abcd_parts", "v4_continue", "v4_title_rescore", "v4_neutral_examples"}
V4_SC_K = 1          # SC_K under V4=1 when SC_K is not set (1 = off)
V4_CHRONO_TIES_MODE = 1


def on(s, name: str) -> bool:
    v = getattr(s, name, -1)
    if v is None or int(v) < 0:
        return bool(getattr(s, "v4", False)) and name in V4_UMBRELLA
    return int(v) > 0


def chrono_ties_mode(s) -> int:
    v = int(getattr(s, "v4_chrono_ties", -1))
    if v < 0:
        return V4_CHRONO_TIES_MODE if (getattr(s, "v4", False) and "v4_chrono_ties" in V4_UMBRELLA) else 0
    return v


def chrono_bc_mode(s) -> int:
    """1 = v3 year prompt, grammar also accepts ' p.n.e.', unsigned years fixed from item/stem/context;
    2 = additionally the prompt asks for 'p.n.e.' instead of negative numbers."""
    v = int(getattr(s, "v4_chrono_bc", -1))
    if v < 0:
        return 1 if (getattr(s, "v4", False) and "v4_chrono_bc" in V4_UMBRELLA) else 0
    return v


def sc_k(s) -> int:
    k = int(getattr(s, "sc_k", 0) or 0)
    if k <= 0:
        return V4_SC_K if getattr(s, "v4", False) else 1
    return k


def any_closed(s) -> bool:
    return (on(s, "v4_source_first") or on(s, "v4_pf_evidence") or on(s, "v4_pf_value") or
            on(s, "v4_neutral_examples") or on(s, "v4_continue") or sc_k(s) > 1)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")


# ------------------------------------------------------------------ fix 4: neutral answer-format examples
_EX_CTX = re.compile(r"(w\s+formacie|formatu|np\.|na\s+przykład|przykład\w*\s*:|wzór|wzoru)", re.I)
_PAIR_NL = re.compile(r"(?<![\w-])(\d{1,2})(\s*[-–—]\s*)([A-H])(?![\wąćęłńóśźż])")
_PAIR_LN = re.compile(r"(?<![\w-])([A-H])(\s*[-–—]\s*)(\d{1,2})(?![\w.]\d)(?![\wąćęłńóśźż])")
_LETTER_SEQ = re.compile(r"(?<![\wąćęłńóśźż])[A-H](?:\s*[,;]\s*[A-H]){2,}(?![\wąćęłńóśźż])")
_PF_SEQ = re.compile(r"(?<![\wąćęłńóśźż/])[PF](?:\s*[,;]\s*[PF])+(?![\wąćęłńóśźż/])")


def neutralize_examples(text: str) -> str:
    """Answer-format examples in the question -> neutral placeholders (the model copies them): '1-B, 2-A' ->
    '1-X, 2-X', 'A-3, B-1' -> 'A-X, B-X', 'np. B, A, D, C' -> 'np. X, X, X, X', 'P, F, P' -> 'P/F, P/F, P/F'.
    Only the part of a line after a format cue ('w formacie', 'np.', 'na przykład', 'wzór') is touched."""
    out = []
    for ln in (text or "").split("\n"):
        m = _EX_CTX.search(ln)
        if not m:
            out.append(ln)
            continue
        head, tail = ln[: m.end()], ln[m.end():]
        tail = _PAIR_NL.sub(lambda x: f"{x.group(1)}{x.group(2)}X", tail)
        tail = _PAIR_LN.sub(lambda x: f"{x.group(1)}{x.group(2)}X", tail)
        tail = _LETTER_SEQ.sub(lambda x: re.sub(r"[A-H]", "X", x.group(0)), tail)
        tail = _PF_SEQ.sub(lambda x: re.sub(r"[PF]", "P/F", x.group(0)), tail)
        out.append(head + tail)
    return "\n".join(out)


# ------------------------------------------------------------------ fix 2: raw-title re-scoring
_ROMAN = re.compile(r"^(X{0,3})(IX|IV|V?I{0,3})$")
_TOK = re.compile(r"[0-9A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÀ-ÿ]+|[.;:!?()\n\[\]„”\"]")
_PAREN = re.compile(r"\s*\([^)]*\)")


def is_roman(tok: str) -> bool:
    return bool(tok) and tok.isupper() and bool(_ROMAN.match(tok)) and tok != ""


def _toks(text: str) -> list[tuple[str, object]]:
    """-> [(folded stem or numeral, kind)]: kind True = Roman numeral (a lone uppercase 'I' is the numeral, lowercase
    'i' the conjunction), 'ord' = an ordinal word mapped to its numeral, False = word; '|' = phrase boundary."""
    out = []
    for w in _TOK.findall(text or ""):
        if not w[0].isalnum():  # sentence/phrase boundary: never part of a match, stops numeral adjacency
            if out and out[-1][0] != "|":
                out.append(("|", False))
            continue
        if is_roman(w):
            out.append((w, True))
            continue
        f = fold(w)
        if len(f) >= 5 and f[:4] in ORDINALS and not f.startswith(("pierw" + "o", "trzeb", "trzes", "drugo")):
            out.append((ORDINALS[f[:4]], "ord"))  # 'pierwszej', 'trzeciego' -> the numeral (weaker: see below)
            continue
        if f in ("i", "w", "z", "o", "a", "u", "na", "do", "we", "ze", "od", "po", "pod", "nad", "przy"):
            out.append((f, False))  # function words kept as tokens (titles contain them: 'Bitwa pod Grunwaldem')
            continue
        out.append((_stem(f), False))
    return out


def _stem(f: str) -> str:
    """Crude inflection-tolerant key: the first 4 letters ('wojna'/'wojny', 'marcowa'/'marcowej')."""
    return f[:4] if len(f) > 4 and not f.isdigit() else f


# event / document nouns: only titles that name an event get the exact-title bonus (a bonus for every person or
# place named in the question pushed the source article out: 'Imre Nagy' over 'Powstanie węgierskie 1956')
EVENT_STEMS = {"bitw", "wojn", "pows", "konf", "rewo", "poko", "trak", "rozb", "unia", "unii", "sejm", "kons", "wypr",
               "kong", "ukla", "zjaz", "bunt", "roko", "poto", "stat", "edyk", "bull", "dekr", "mani", "ofen", "oper",
               "obro", "oble", "zama", "rzez", "kryz", "refo", "sobo", "syno", "koro", "elek", "abdy", "przy",
               "czar", "wiel", "kamp", "blok", "desa", "inwa", "naja", "napa", "odsi", "prze", "stra", "maso", "pucz",
               "okra", "akcj", "nocy", "noc", "hołd", "hold", "sobó", "lini", "plan", "dokt", "konk", "auto", "wyda"}
# Polish ordinal words stand for the numeral ('pierwszej wyprawy krzyżowej' = 'I wyprawa krzyżowa')
ORDINALS = {"pier": "I", "drug": "II", "trze": "III", "czwa": "IV", "piat": "V", "szos": "VI", "siod": "VII",
            "osma": "VIII", "osme": "VIII", "osmy": "VIII", "dzie": "IX"}


def title_delta(title: str, ref_toks: list[tuple[str, bool]], ref_caps: set[str], bonus: float,
                penalty: float) -> tuple[float, str]:
    """Score change for one candidate title against the reference text (question [+ identification]).
    exact  : an event/document title ('Wojna trzydziestoletnia', 'III rozbiór Polski', 'Konstytucja marcowa') occurs
             whole (numerals included) in the reference, with no other numeral next to it -> +bonus
    roman  : the title's words occur in the reference but with a different numeral next to them ('I wojna punicka'
             vs 'II wojna punicka', 'Rozbiory Polski' vs 'III rozbiór Polski'), or the title starts with a numeral
             the reference does not have ('II wojna trzydziestoletnia' vs 'wojna trzydziestoletnia') -> -penalty.
             A numeral inside a ruler's name that the question leaves out ('Bolesław I Chrobry' vs 'Bolesław
             Chrobry') is not penalised. Ordinal words count as numerals ('trzecim rozbiorze' = 'III rozbiór')."""
    tt = _toks(_PAREN.sub("", title or ""))
    words = [w for w, r in tt if not r]
    nums = {w for w, r in tt if r}
    if not words or not ref_toks:
        return 0.0, ""
    leading = bool(tt) and tt[0][1]
    full = [w for w, _ in tt]
    seq = [w for w, _ in ref_toks]
    n = len(full)
    if len(words) >= 2 and words[0] in EVENT_STEMS or (nums and words[0] in EVENT_STEMS):
        for i in range(0, len(seq) - n + 1):
            if seq[i:i + n] == full:
                around = [j for j in (i - 1, i + n) if 0 <= j < len(seq) and ref_toks[j][1]]
                if not around:
                    return bonus, "exact"
    # numeral-free comparison
    idx = [j for j, (w, r) in enumerate(ref_toks) if not r and w != "|"]
    rw = [ref_toks[j][0] for j in idx]
    m = len(words)
    for i in range(0, len(rw) - m + 1):
        if rw[i:i + m] != words:
            continue
        a, b = idx[i], idx[i + m - 1]
        if any(ref_toks[j][0] == "|" for j in range(a, b + 1)):
            continue
        span = range(max(0, a - 1), min(len(ref_toks), b + 2))
        if nums:  # the title has a numeral: any other numeral (or ordinal word) next to the words -> penalty
            near = {ref_toks[j][0] for j in span if ref_toks[j][1]}
            if (near and near != nums) or (not near and leading):
                return -penalty, "roman"
        elif a >= 1 and ref_toks[a - 1][1] is True:  # 'III rozbiór Polski' in the question, title 'Rozbiory Polski'
            return -penalty, "roman"  # (ordinal words and trailing numerals - 'Kleopatra VII' - do not count here)
    return 0.0, ""


def ref_index(ref: str) -> tuple[list[tuple[str, bool]], set[str]]:
    toks = _toks(ref)
    caps = {_stem(fold(w)) for w in _TOK.findall(ref or "") if w[:1].isupper() and len(w) >= 4}
    return toks, caps


def title_rescore(order: list[str], hits: dict, scores: dict | None, ref: str, bonus: float = 3.0,
                  penalty: float = 4.0, pos_scale: float = 1.0) -> tuple[list[str], dict]:
    """Re-sort candidate keys: score = reranker score (or -position * pos_scale when there is none) + title delta.
    Returns (new order, {key: reason}) for the keys that moved."""
    toks, caps = ref_index(ref)
    base = {}
    for i, k in enumerate(order):
        base[k] = scores[k] if (scores is not None and k in scores) else -i * pos_scale
    why = {}
    adj = {}
    cache: dict[str, tuple[float, str]] = {}
    for k in order:
        t = hits[k].get("title", "")
        if t not in cache:
            cache[t] = title_delta(t, toks, caps, bonus, penalty)
        d, r = cache[t]
        adj[k] = base[k] + d
        if r:
            why[k] = r
    new = sorted(order, key=lambda k: -adj[k])  # stable: ties keep the old order
    return new, why


# ------------------------------------------------------------------ fix 3: P/F evidence
_QUANT = re.compile(r"\b(ostatecznie|wyłącznie|jedynie|tylko|wszys\w*|żad\w+|nigdy|zawsze|po\s+raz\s+pierwszy|"
                    r"jako\s+pierws\w+|pierws\w+|bez\s+żadnych|całkowici\w*|natychmiast|najwię\w+|najmniej\w*|"
                    r"jedyn\w+|nikt|każd\w+|stycz\w+|lut\w+|marc\w+|kwietni\w+|maj[au]?|czerw\w+|lip\w+|sierpni\w+|"
                    r"wrze[sś]\w+|październik\w*|listopad\w*|grud\w+)\b", re.I)


def has_value(stmt: str) -> bool:
    """A number / date / quantifier the model tends to accept or reject from memory."""
    return bool(re.search(r"\d", stmt or "")) or bool(_QUANT.search(stmt or ""))


def pf_check_instruction(label: str, stmt: str, initial: bool | None, value: bool) -> str:
    """Second pass for one statement: value from the context first (numbers/dates/quantifiers), then a verbatim
    contradicting sentence, then the verdict. initial False = judged F (needs evidence), True = judged P."""
    was = "fałszywe (F)" if initial is False else "prawdziwe (P)"
    val = ("Najpierw wypisz, co na ten temat podają fragmenty z Wikipedii albo źródło (liczbę, datę, nazwę, zakres, "
           "kolejność) — dokładnie tak, jak tam zapisano. ") if value else ""
    fmt = ("Wartość w kontekście: …\n" if value else "") + "Cytat: „…” albo Cytat: BRAK\nOcena: P albo F"
    return (f"Sprawdź stwierdzenie {label}: „{stmt}”. Wstępnie oceniono je jako {was}. Stwierdzenie jest fałszywe "
            f"tylko wtedy, gdy fragmenty z Wikipedii albo źródło zawierają informację, która mu przeczy (inna data, "
            f"liczba, osoba, miejsce, inny skutek). {val}Następnie przytocz dosłownie jedno zdanie z fragmentów albo ze "
            f"źródła, które przeczy stwierdzeniu. Jeśli żadne zdanie mu nie przeczy, napisz „Cytat: BRAK”.\n"
            f"Odpowiedz dokładnie w formacie:\n{fmt}")


def parse_pf_check(text: str) -> tuple[str, bool | None]:
    """-> (quote or '', verdict True=P / False=F / None)."""
    s = (text or "").replace("**", "")
    q = ""
    m = re.search(r"cytat\s*:\s*(.*?)(?:\n\s*ocena\s*:|\Z)", s, re.I | re.S)
    if m:
        q = m.group(1).strip().strip("„”\"'»« ").strip()
        if re.match(r"^\W*brak\b", q, re.I) or len(q) < 8:
            q = ""
    v = None
    mv = list(re.finditer(r"ocena\s*:\s*\**\s*(P|F|prawda|fałsz)\b", s, re.I))
    if mv:
        v = mv[-1].group(1).upper().startswith("P")
    return q, v


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(s))


def quote_supported(quote: str, text: str, min_share: float = 0.6) -> bool:
    """Is the quote really in the text (context + source)? Share of its word trigrams (bigrams for short quotes)
    found in the text >= min_share."""
    qw, tw = _words(quote), _words(text)
    if len(qw) < 3 or not tw:
        return False
    n = 3 if len(qw) >= 6 else 2
    grams = [tuple(qw[i:i + n]) for i in range(len(qw) - n + 1)]
    tset = {tuple(tw[i:i + n]) for i in range(len(tw) - n + 1)}
    return sum(1 for g in grams if g in tset) / len(grams) >= min_share


def pf_decide(initial: bool, quote: str, verdict: bool | None, evidence_text: str) -> tuple[bool, str]:
    """Final P/F after the check: F only with a verified contradicting quote."""
    ok = bool(quote) and quote_supported(quote, evidence_text)
    if initial is False:  # F stays only with evidence
        if ok and verdict is not True:
            return False, "F-kept"
        return True, "F->P" if not ok else "F->P(verdict)"
    if ok and verdict is False:  # P -> F only with evidence
        return False, "P->F"
    return True, "P-kept"


# ------------------------------------------------------------------ fix 5: chronology
BC_RE = re.compile(r"p\.?\s*n\.?\s*e\.?|przed\s+naszą\s+erą|przed\s+Chr", re.I)


def instruction_chrono_years_bc(items: list[tuple[str, str]]) -> str:
    return ("Dla każdego elementu podaj rok, w którym miało miejsce wydarzenie (dla okresów i panowań — rok początku). "
            "Lata przed naszą erą zapisz z dopiskiem „p.n.e.” (np. 216 p.n.e.). Odpowiedz wyłącznie w formacie:\n"
            + "\n".join(f"{l}: rok" for l, _ in items))


def grammar_years_bc(items: list[tuple[str, str]]) -> str:
    body = ' "\\n" '.join(f'"{l}: " Y' for l, _ in items)
    return f'root ::= {body}\nY ::= "-"? [0-9] [0-9]? [0-9]? [0-9]? " p.n.e."?\n'


def bc_fix(years: dict, raw_signed: dict, items: list[tuple[str, str]], stem: str, ctx_text: str) -> tuple[dict, list]:
    """Unsigned years -> negative when the item says 'p.n.e.', when the context writes that very year as 'Y p.n.e.'
    (and never as 'Y n.e.'), or when the stem is BC-only ('VI w. p.n.e.') and the year is < 1000.
    raw_signed: {label: True if the model wrote a sign / 'p.n.e.' itself}."""
    out, log = dict(years), []
    stem_bc = bool(BC_RE.search(stem or "")) and not re.search(r"(?<!p\.)(?<!p\. )\bn\.\s?e\.", stem or "")
    for l, txt in items:
        y = out.get(l)
        if y is None or y <= 0 or raw_signed.get(l):
            continue
        why = ""
        if BC_RE.search(txt or ""):
            why = "item"
        elif re.search(rf"(?<!\d){int(y)}\s*(?:r\.\s*)?p\.\s?n\.\s?e\.", ctx_text or "") and not re.search(
                rf"(?<!\d){int(y)}\s*(?:r\.\s*)?n\.\s?e\.", ctx_text or ""):
            why = "context"
        elif stem_bc and y < 1000:
            why = "stem"
        if why:
            out[l] = -y
            log.append(f"{l}:{int(y)}->BC({why})")
    return out, log


def signed_labels(text: str, labels: list[str]) -> dict:
    out = {}
    for m in re.finditer(r"(?m)^\s*\(?([A-H]|\d{1,2})\)?\s*[:\.\)\-–]\s*(-)?\d{1,4}\s*(p\.?\s*n\.?\s*e\.?)?", text or ""):
        if m.group(1) in labels and m.group(1) not in out:
            out[m.group(1)] = bool(m.group(2) or m.group(3))
    return out


def tie_groups(years: dict, labels: list[str]) -> list[list[str]]:
    by: dict = {}
    for l in labels:
        y = years.get(l)
        if y is not None and y != 99999:
            by.setdefault(y, []).append(l)
    return [g for g in by.values() if len(g) >= 2]


def instruction_monthday(group: list[tuple[str, str]], year: int) -> str:
    ys = f"{-year} p.n.e." if year < 0 else str(year)
    names = " i ".join(l for l, _ in group) if len(group) == 2 else ", ".join(l for l, _ in group)
    return (f"Wydarzenia {names} miały miejsce w tym samym roku ({ys}):\n" +
            "\n".join(f"{l}. {t}" for l, t in group) +
            "\nDla każdego z nich podaj miesiąc i dzień w formacie MM-DD; jeśli znasz tylko miesiąc, napisz MM; jeśli "
            "nie wiesz, napisz ?. Korzystaj z fragmentów z Wikipedii. Odpowiedz wyłącznie w formacie:\n" +
            "\n".join(f"{l}: MM-DD" for l, _ in group))


def grammar_monthday(labels: list[str]) -> str:
    body = ' "\\n" '.join(f'"{l}: " D' for l in labels)
    return (f'root ::= {body}\nD ::= M "-" DD | M | "?"\nM ::= "0" [1-9] | "1" [0-2]\n'
            f'DD ::= "0" [1-9] | [12] [0-9] | "3" [01]\n')


def parse_monthday(text: str, labels: list[str]) -> dict:
    out = {}
    for m in re.finditer(r"(?m)^\s*([A-H]|\d{1,2})\s*:\s*(\d{1,2})?(?:-(\d{1,2}))?", text or ""):
        lab = m.group(1)
        if lab in labels and lab not in out:
            out[lab] = (int(m.group(2)) if m.group(2) else None, int(m.group(3)) if m.group(3) else None)
    return out


def instruction_pair(a: tuple[str, str], b: tuple[str, str]) -> str:
    return (f"Które z tych dwóch wydarzeń nastąpiło wcześniej?\n{a[0]}. {a[1]}\n{b[0]}. {b[1]}\n"
            f"Korzystaj z fragmentów z Wikipedii i z własnej wiedzy. Odpowiedz jedną literą: {a[0]} albo {b[0]}.")


def order_group(group: list[str], md: dict | None, wins: dict | None, direct: list[str]) -> tuple[list[str], str]:
    """Order one tied group: by (month, day) when every member has a month and the keys differ; otherwise by
    pairwise wins (Copeland); remaining ties -> the direct order."""
    if md is not None and all(md.get(l, (None, None))[0] for l in group):
        keys = {l: (md[l][0], md[l][1] or 0) for l in group}
        if len(set(keys.values())) == len(group):
            return sorted(group, key=lambda l: keys[l]), "monthday"
    if wins:
        return sorted(group, key=lambda l: (-wins.get(l, 0), direct.index(l) if l in direct else 99)), "pairwise"
    return sorted(group, key=lambda l: direct.index(l) if l in direct else 99), "direct"


# ------------------------------------------------------------------ fix 1: abcd_parts -> separate abcd items
_PARTS_CMD = re.compile(r"(?i)dokończ\s+zdani[ae]\s+(?:\d\.?\s*(?:,|i|oraz|–|-)?\s*)+\.?")


def part_question(pq, i: int) -> str:
    """Sub-question for sentence i of an abcd_parts item: everything before the first part (sources + command,
    'Dokończ zdania 1. i 2.' -> 'Dokończ zdanie.'), then this sentence and its own options."""
    pl, sent, opts = pq.parts[i]
    text = pq.text
    first_sent = pq.parts[0][1]
    pos = text.find(first_sent)
    head = text[:pos] if pos > 0 else (pq.sources + "\n" + (pq.command.split("\n")[0] if pq.command else ""))
    head = re.sub(r"(?m)^\s*1\s*[.)]?\s*$", "", head).rstrip()
    head = re.sub(r"\s*\b1\s*[.)]\s*$", "", head).rstrip()
    head = _PARTS_CMD.sub("Dokończ zdanie. ", head).rstrip()
    body = sent.strip() + "\n" + "\n".join(f"{l}. {o}" for l, o in opts)
    return (head + "\n" + body).strip()


def default_title_ref(pq) -> str:
    """Text the retrieved titles are matched against: the question without its P/F statements (a false statement
    names the distractor, e.g. 'Konstytucja kwietniowa' in a question about the March constitution)."""
    if pq.qtype == "pf" and pq.statements:
        return f"{pq.sources}\n{pq.stem}" if pq.sources else (pq.stem or "")
    return pq.text or ""
