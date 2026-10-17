"""CKE_MODE essay helpers (pure; LLM calls in harness/cke_flow.py).

The essay is written part by part so a 4.5B model with an 8k context stays focused and grounded:
  plan (elements + alternative for 'najbardziej' theses) -> intro with an explicit stance -> one paragraph per
  element from ITS OWN retrieved passages (2-3 dated facts + a sentence tying back to the thesis) ->
  comparison with the alternative -> conclusion -> verification (sentences with dates/names absent from the
  retrieved passages are removed or their date is dropped; paragraphs keep >= 3 sentences) -> clean-up
  (exactly one 'WYPRACOWANIE na temat nr X' line, no copied prompt, no duplicated/misspelled header).
"""
from __future__ import annotations

import re

from .cke import norm
from .essay import _SENT, _WORD, word_count
from .qtype import entities

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
         "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
         "XXI": 21}
_R = r"(XXI|XX|XIX|XVIII|XVII|XVI|XV|XIV|XIII|XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)"
_ERAS = [(re.compile(r"międzywojen|II\s+Rzeczypospolit|dwudziestoleci", re.I), (1918, 1939)),
         (re.compile(r"II\s+wojn\w+\s+światow", re.I), (1939, 1945)),
         (re.compile(r"\bPRL\b|Polsk\w+\s+Ludow", re.I), (1944, 1989)),
         (re.compile(r"zimn\w+\s+wojn", re.I), (1945, 1991))]


def _century(r: str) -> tuple[int, int]:
    c = ROMAN[r]
    return (c - 1) * 100 + 1, c * 100


def time_frame(topic: str) -> tuple[int, int] | None:
    """The time frame the topic sets ('lata 50. XX wieku' -> 1950-1959, 'XI–XII wieku' -> 1001-1200,
    'Lata 1871–1914', 'Rok 1956', 'z końca XVIII wieku' -> 1770-1800); None when the topic sets none."""
    t = " ".join((topic or "").split())
    m = re.search(rf"lat\w*\s+(\d0)\.?\s*(?:[–-]\s*(\d0)\.?\s*)?{_R}\s*(?:w\b|wiek)", t)
    if m:
        base = (ROMAN[m.group(3)] - 1) * 100
        lo = base + int(m.group(1))
        hi = base + int(m.group(2) or m.group(1)) + 9
        return lo, hi
    m = re.search(r"(?<!\d)(\d{3,4})\s*[–-]\s*(\d{3,4})(?!\d)", t)
    if m and int(m.group(1)) < int(m.group(2)):
        return int(m.group(1)), int(m.group(2))
    m = re.search(rf"\b{_R}\s*[–-]\s*{_R}\s*(?:w\b|wiek)", t)
    if m:
        return _century(m.group(1))[0], _century(m.group(2))[1]
    m = re.search(rf"(końc\w*|schyłk\w*|począt\w*|(?:pierwsz\w*|drug\w*)?\s*połow\w*)?\s*{_R}\s*(?:w\b|wiek)", t)
    if m and m.group(2):
        lo, hi = _century(m.group(2))
        q = norm(m.group(1) or "")
        if q.startswith(("konc", "schyl")):
            return hi - 30, hi
        if q.startswith("pocz"):
            return lo - 1, lo + 30
        if "pierwsz" in q:
            return lo - 1, lo + 50
        if "drug" in q:
            return lo + 49, hi
        if "polow" in q:
            return lo + 30, hi - 30
        return lo, hi
    m = re.search(r"\b(?:rok|roku|w\s+roku)\s+(\d{3,4})\b", t, re.I)
    if m:
        y = int(m.group(1))
        return y, y
    for r, fr in _ERAS:
        if r.search(t):
            return fr
    return None


def frame_margin(fr: tuple[int, int]) -> int:
    """Years allowed outside the frame: a single year (1956) admits its background, a decade is strict."""
    span = fr[1] - fr[0]
    return 3 if span == 0 else 1 if span <= 15 else 10


def frame_text(fr: tuple[int, int] | None) -> str:
    if not fr:
        return ""
    return f"{fr[0]}" if fr[0] == fr[1] else f"{fr[0]}–{fr[1]}"


_SUPER = re.compile(r"\bnaj(?:bardziej|mniej|wybitniejsz|ważniejsz|większ|lepsz|skuteczniejsz|słabsz|gorsz|"
                    r"istotniejsz|trwalsz|groźniejsz|poważniejsz)\w*|\bnaj\w{3,}(?:szy|sza|sze|szym|szego|szej)\b", re.I)


def superlative(thesis: str) -> bool:
    return bool(_SUPER.search(thesis or ""))


_KINDS = [(re.compile(r"władc|panowani|król|monarch", re.I), "władca", "władców"),
          (re.compile(r"państw", re.I), "państwo", "państw"),
          (re.compile(r"postaci|osób|polityk", re.I), "postać", "postaci"),
          (re.compile(r"wydarze|bitw|konflikt", re.I), "wydarzenie", "wydarzeń"),
          (re.compile(r"reform", re.I), "reforma", "reform")]
_NUM = {"dwóch": 2, "dwa": 2, "dwie": 2, "trzech": 3, "trzy": 3, "czterech": 4, "cztery": 4}


def element_kind(topic: str) -> tuple[str, str, int]:
    """'panowanie trzech wybranych władców' -> ('władca', 'władców', 3); default ('element', 'elementów', 3)."""
    t = " ".join((topic or "").split())
    m = re.search(r"(?:uwzględniając|charakteryzując|odwołując\s+się\s+do)[^.]*", t, re.I)
    tail = m.group(0) if m else t
    n = 3
    mn = re.search(r"\b(dwóch|dwa|dwie|trzech|trzy|czterech|cztery)\b", tail, re.I)
    if mn:
        n = _NUM[mn.group(1).lower()]
    for r, sg, pl in _KINDS:
        if r.search(tail):
            return sg, pl, n
    return "element", "elementów", n


def plan_instruction(topic_n: str, kind_pl: str, n: int, fr, sup: bool, aspects: list[str]) -> str:
    lines = []
    if not aspects:
        k = n + 3 if fr else n  # extra candidates: out-of-frame picks are dropped by parse_plan
        lines.append(f"Wypisz {k} {kind_pl}, które najlepiej pozwolą uzasadnić stanowisko w temacie nr {topic_n} "
                     f"(najważniejsze i najbardziej znane najpierw)" +
                     (f"; każde musi mieć miejsce wyłącznie w latach {frame_text(fr)} — nie podawaj niczego "
                      f"sprzed {fr[0]} ani po {fr[1]} roku" if fr else "") + f". Wypisz je w {k} liniach w formacie: "
                     f"nazwa (rok lub lata).")
    if sup:
        lines.append("Teza zawiera stopień najwyższy („najbardziej”, „najwybitniejszy”…), więc wskaż też jedną "
                     "alternatywę do porównania (inną postać, wydarzenie lub zjawisko tego samego rodzaju). Napisz ją "
                     "w osobnej linii: Alternatywa: nazwa")
    lines.append("Nie pisz nic więcej.")
    return " ".join(lines)


def elements_from_contexts(contexts: list[dict], fr, n: int, thesis: str = "", have: list[str] | None = None) -> list[str]:
    """Fallback plan: article titles of the retrieved passages, ranked by how many of their years fall inside the
    topic's frame (reranked order when there is no frame); the thesis subject itself and duplicates are skipped."""
    have = list(have or [])
    ts = norm(thesis)
    scored = []
    for i, c in enumerate(contexts):
        title = (c.get("title") or "").split(" — ")[0].strip()
        if not title:
            continue
        yrs = [int(y) for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", c.get("text", "")) if 300 <= int(y) <= 2030]
        m = frame_margin(fr) if fr else 0
        inside = sum(1 for y in yrs if fr and fr[0] - m <= y <= fr[1] + m) if fr else 1
        if fr and not inside:
            continue
        scored.append((-inside, i, title))
    out = []
    for _, _, title in sorted(scored):
        tw = [w[:5] for w in re.findall(r"\w{4,}", norm(title))]
        if tw and all(w in ts for w in tw):  # 'Zimna wojna' for a thesis about the cold war
            continue
        if any(norm(title)[:12] == norm(h)[:12] for h in have + out):
            continue
        out.append(title)
        if len(have) + len(out) >= n:
            break
    return out


def alt_instruction(thesis: str) -> str:
    return (f"Teza: „{thesis.strip()}”. Teza zawiera stopień najwyższy, więc wypracowanie musi porównać jej przedmiot "
            "z alternatywą tego samego rodzaju (np. innym władcą tej samej dynastii, innym wydarzeniem lub zjawiskiem "
            "z tego samego okresu). Podaj jedną taką alternatywę — samą nazwę, bez komentarza.")


def parse_alt(text: str, thesis: str = "") -> str:
    """'Alternatywa: Kazimierz Jagiellończyk (1447–1492)' -> 'Kazimierz Jagiellończyk (1447–1492)'; '' when the
    model repeats the thesis subject or writes a sentence."""
    s = (text or "").replace("**", "").strip()
    s = re.sub(r"^\s*alternatyw\w*\s*[:\-–]\s*", "", s, flags=re.I)
    s = s.split("\n")[0].strip(" .,;*\"'„”«»")
    if not s or len(s) > 80 or len(s.split()) > 8:
        return ""
    ts = norm(thesis)
    if all(w[:5] in ts for w in re.findall(r"\w{4,}", norm(s))):  # the thesis subject itself
        return ""
    return s


_STANCE_RE = re.compile(r"zgadzam\s+się|nie\s+zgadzam|podzielam|zaj(?:ął|ęł|mu)\w*\s+stanowisko|stanowisko,?\s+(?:że|iż)|teza\s+(jest|ta\s+jest)\s+(słuszn|trafn|prawdziw|"
                        r"częściowo|niesłuszn|błędn|fałszyw)|uważam,?\s+że|moim\s+zdaniem|stoję\s+na\s+stanowisku|"
                        r"należy\s+uznać|nie\s+sposób\s+się\s+nie\s+zgodzić", re.I)
_COMMON_START = {"lata", "rok", "w", "we", "na", "zimna", "rewolucja", "rewolucje", "polityka", "reformy", "reforma",
                 "powstanie", "powstania", "wojna", "wojny", "okres", "epoka", "czasy", "ustroj", "gospodarka",
                 "kultura", "społeczeństwo", "państwo", "przemiany", "odrodzenie", "oświecenie", "dzieje", "przyczyny",
                 "skutki", "największym", "najważniejszym", "głównym", "decydujący", "o", "od", "do", "po", "za"}


def stance_sentence(intro: str) -> str:
    for x in _SENT.split(intro or ""):
        if _STANCE_RE.search(x):
            return x.strip()
    return ""


def ensure_stance(intro: str, thesis: str) -> tuple[str, bool]:
    """An intro without an explicit stance gets 'Zgadzam się z tezą, że <thesis>.' (CKE: the stance must be
    explicit; the parts written next argue for the thesis)."""
    if stance_sentence(intro):
        return intro, False
    t = " ".join((thesis or "").split()).rstrip(" .")
    if not t:
        return intro, False
    first = t.split()[0]
    if norm(first).rstrip(",") in {norm(w) for w in _COMMON_START}:
        t = first.lower() + t[len(first):]
    return (intro.rstrip() + " " if intro.strip() else "") + f"Zgadzam się z tezą, że {t}.", True


def aspect_prefill(aspect: str) -> str:
    """'militarny' -> 'W aspekcie militarnym' (the paragraph starts on its aspect instead of re-writing the intro)."""
    a = (aspect or "").strip()
    if re.search(r"[yi]$", a) and len(a.split()) == 1:
        return f"W aspekcie {a}m"
    return ""


_PLAN_LINE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])?\s*(.+?)\s*$")


def parse_plan(text: str, n: int, fr=None) -> tuple[list[tuple[str, list[int]]], str]:
    """-> ([(element, years)], alternative). Elements whose years all fall outside the frame are dropped."""
    els, alt = [], ""
    for ln in (text or "").replace("**", "").split("\n"):
        if not ln.strip():
            continue
        m = re.match(r"\s*alternatyw\w*\s*[:\-–]\s*(.+)$", ln, re.I)
        if m:
            alt = m.group(1).strip(" .")
            continue
        m = _PLAN_LINE.match(ln)
        name = m.group(1).strip(" .") if m else ""
        if not name or len(name) > 120 or re.match(r"(oto|wybrane|elementy|temat)\b", name, re.I):
            continue
        yrs = [int(y) for y in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", name) if 300 <= int(y) <= 2030]
        m = frame_margin(fr) if fr else 0
        if fr and yrs and all(not (fr[0] - m <= y <= fr[1] + m) for y in yrs):
            continue
        if name.lower() not in [e[0].lower() for e in els]:
            els.append((name, yrs))
    return els[:n], alt


# ------------------------------------------------------------------ verification
def _year_ok(y: str, blob: str) -> bool:
    return re.search(rf"(?<!\d){y}(?!\d)", blob) is not None


def _name_ok(name: str, blob_n: str) -> bool:
    ws = [w for w in re.findall(r"\w+", norm(name)) if len(w) >= 4]
    if not ws:
        return True
    hits = sum(1 for w in ws if w[:5] in blob_n)
    return hits * 2 >= len(ws)


def sentence_issues(sent: str, blob: str, blob_n: str, fr=None) -> dict:
    yrs = [y for y in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", sent) if 300 <= int(y) <= 2030]
    bad_y = [y for y in yrs if not _year_ok(y, blob)]
    ents = [e for e in entities(sent) if not e.isdigit()]
    multi = [e for e in ents if " " in e and not _name_ok(e, blob_n)]
    single = [e for e in ents if " " not in e and not _name_ok(e, blob_n)]
    out_frame = []
    if fr and yrs:
        margin = frame_margin(fr)
        out_frame = [y for y in yrs if not (fr[0] - margin <= int(y) <= fr[1] + margin)]
        if len(out_frame) < len(yrs):  # background date next to an in-frame one is fine
            out_frame = []
    return {"bad_years": bad_y, "bad_multi": multi, "bad_single": single, "out_frame": out_frame,
            "flag": bool(bad_y or multi or len(single) >= 2 or out_frame)}


def strip_dates(sent: str, years: list[str]) -> str:
    s = sent
    for y in years:
        s = re.sub(rf"\s*\((?:w\s+)?(?:\d{{3,4}}\s*[–-]\s*)?{y}(?:\s*[–-]\s*\d{{3,4}})?(?:\s*r\.)?\)", "", s)
        s = re.sub(rf",?\s+(?:w\s+latach|w\s+roku|w|od|do|około|ok\.)\s+(?:\d{{3,4}}\s*[–-]\s*)?{y}"
                   rf"(?:\s*[–-]\s*\d{{3,4}})?(?:\s*(?:r\.|roku))?", "", s)
    return re.sub(r"\s{2,}", " ", s).replace(" ,", ",").replace(" .", ".")


def verify_paragraph(par: str, blob: str, fr=None, min_sents: int = 3) -> tuple[str, list[dict]]:
    """Drop sentences whose dates/names are absent from the retrieved passages (the first sentence and
    paragraphs that would fall under `min_sents` keep the sentence with its unsupported dates removed)."""
    blob_n = norm(blob)
    sents = [x for x in _SENT.split(par) if x.strip()]
    keep, log = [], []
    issues = [sentence_issues(x, blob, blob_n, fr) for x in sents]
    n_flag = sum(1 for i in issues if i["flag"])
    budget = max(0, len(sents) - min_sents)
    for i, (x, iss) in enumerate(zip(sents, issues)):
        if not iss["flag"]:
            keep.append(x)
            continue
        if i > 0 and budget > 0:
            budget -= 1
            log.append({"removed": x[:160], **{k: v for k, v in iss.items() if v and k != "flag"}})
            continue
        dates = iss["bad_years"] + iss["out_frame"]
        y = strip_dates(x, dates) if dates else x
        log.append({"kept": y[:160], "dates_dropped": dates, **({"names": iss["bad_multi"] + iss["bad_single"]}
                                                               if iss["bad_multi"] or iss["bad_single"] else {})})
        keep.append(y)
    del n_flag
    return " ".join(keep).strip(), log


# ------------------------------------------------------------------ ESSAY_SAFE=1: stricter date verification
# (a) a month / day+month next to a year must occur with that year (within SAFE_WINDOW chars) in ONE retrieved
#     passage, else the day / month is dropped ('25 października 1956' -> 'w październiku 1956' -> 'w 1956');
# (b) a year counts as supported only if some passage has it within SAFE_WINDOW chars of a content entity of the
#     sentence (a capitalised name or an event noun: blokada, powstanie, wojna, kryzys, ...), else it is removed
#     and the sentence is dropped when it then says nothing concrete;
# (c) every removal / flag counts as one unsupported claim (the best-of-two topic choice ranks on them).
SAFE_WINDOW = 250
_MONTHS = {1: ("styczeń", "stycznia", "styczniu"), 2: ("luty", "lutego", "lutym"), 3: ("marzec", "marca", "marcu"),
           4: ("kwiecień", "kwietnia", "kwietniu"), 5: ("maj", "maja", "maju"), 6: ("czerwiec", "czerwca", "czerwcu"),
           7: ("lipiec", "lipca", "lipcu"), 8: ("sierpień", "sierpnia", "sierpniu"),
           9: ("wrzesień", "września", "wrześniu"), 10: ("październik", "października", "październiku"),
           11: ("listopad", "listopada", "listopadzie"), 12: ("grudzień", "grudnia", "grudniu")}
_MONTH_OF = {}
for _m, _forms in _MONTHS.items():
    for _f in _forms:
        _MONTH_OF[_f] = _MONTH_OF[norm(_f)] = _m
_MON_ALT = "|".join(sorted(_MONTH_OF, key=len, reverse=True))
_ROMAN_M = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
            "XII": 12}
_ROM_ALT = "XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I"
_PREP = r"(?:(?P<prep>w|we|dnia|od|do|z|ze)\s+)?"
_YR_TAIL = r"(?P<year>\d{3,4})(?!\d)"
_DATE_MONTH = re.compile(rf"(?<!\w){_PREP}(?:(?P<day>\d{{1,2}})\s+)?(?P<mon>{_MON_ALT})\s+{_YR_TAIL}", re.I)
_DATE_ROMAN = re.compile(rf"(?<![\w.])(?:(?P<prep>(?i:w|we|dnia|od|do|z|ze))\s+)?(?:(?P<day>\d{{1,2}})\s+)?(?P<rom>{_ROM_ALT})\.?\s+{_YR_TAIL}")
_DATE_NUM = re.compile(rf"(?<![\w.]){_PREP}(?P<day>\d{{1,2}})\.(?P<mnum>\d{{1,2}})\.{_YR_TAIL}", re.I)
_EVENTS = re.compile(r"\b(blokad|powsta[nń]|wojn|wojen|kryzys|bitw|bitew|traktat|pokoj|pokój|rozejm|unii\b|uni[aąęe]\b|"
                     r"rozbior|rozbiór|strajk|rewoluc|konstytuc|reform|konferenc|uklad|układ|ultimat|zamach|przewrot|"
                     r"przewrót|koronac|hold(?:u|em|zie)?\b|hołd|sobor|sobór|najazd|inwazj|agresj|interwenc|konfedera|"
                     r"sejm|przywilej|statut|edykt|zjazd|kongres|rokosz|insurekc|odwil|wybor|wybór|referend|manifest|"
                     r"deklarac|porozumien|pakt|sojusz|kapitulac|obleze|oblęże|bunt|protest|zjednocz|abdykac|elekc|"
                     r"aneksj|okupac|deportac|kolektywiz|industrializ|nacjonaliz|uwlaszcz|uwłaszcz|demonstrac|ofensyw|"
                     r"desant|chrzt|chrzest|lokac|wypraw|krucjat|schizm|pogrom|zabor|zabór|embarg|pucz|puczu)\w*",
                     re.I)
_CAP = re.compile(r"(?<![\w])([A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż\-]{2,})")
_SAFE_STOP = {norm(w) for w in ("Jednak", "Dzięki", "Następnie", "Ponadto", "Również", "Także", "Tym", "Ten", "Ta",
                                "Te", "To", "Tego", "Tej", "Był", "Była", "Było", "Były", "Jego", "Jej", "Ich",
                                "Wówczas", "Wtedy", "Choć", "Chociaż", "Gdy", "Kiedy", "Po", "Przed", "Pod", "Nad",
                                "Dla", "Dlatego", "Warto", "Należy", "Kolejnym", "Kolejny", "Innym", "Inny", "Oprócz",
                                "Mimo", "Podczas", "Wraz", "Około", "Okres", "Rok", "Roku", "Lata", "Latach", "Wiek",
                                "Wieku", "Autor", "Teza", "Tezy", "Tezę", "Zgadzam", "Uważam", "Moim", "Podsumowując")}
_NON_YEAR_AFTER = re.compile(r"\s*(?:tys|mln|mld|osób|ludzi|żołnierzy|zabitych|km|kilometr|proc|%|zł|złotych)", re.I)


def _stem(w: str) -> str:
    w = norm(w)
    return w if len(w) < 4 else w[: max(4, min(6, len(w) - 2))]


def safe_index(passages: list[str]) -> dict:
    """Prepare the retrieved passages once per essay: normalised texts + the capitalised words that occur
    mid-sentence somewhere (proper names, so a sentence-initial 'Chruszczow' counts, 'Kolejnym' does not)."""
    ps = [p for p in passages if p and p.strip()]
    caps = set()
    for p in ps:
        for m in re.finditer(r"(?<=[\wąćęłńóśźż,;:)] )([A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż\-]{2,})", p):
            caps.add(_stem(m.group(1)))
    blob = "\n".join(ps)
    return {"raw": ps, "norm": [norm(p) for p in ps], "caps": caps, "blob": blob, "blob_n": norm(blob)}


def content_keys(sent: str, idx: dict | None = None) -> list[str]:
    """Normalised patterns of the sentence's content entities: capitalised names (a sentence-initial word only when
    it is followed by another capitalised word or occurs mid-sentence in the passages) and event nouns."""
    keys: list[str] = []
    s = sent.strip()
    lead = len(s) - len(s.lstrip(" \"'„(«"))
    for m in _CAP.finditer(s):
        w = m.group(1)
        if w in _ROMAN_M or re.fullmatch(r"[IVXLC]+", w) or norm(w) in _MONTH_OF or norm(w) in _SAFE_STOP:
            continue
        if m.start() <= lead:  # sentence-initial
            nxt = s[m.end():m.end() + 2]
            if not (re.match(r" [A-ZĄĆĘŁŃÓŚŹŻ]", nxt) or (idx and _stem(w) in idx["caps"])):
                continue
        k = r"\b" + re.escape(_stem(w))
        if k not in keys:
            keys.append(k)
    for m in _EVENTS.finditer(norm(s)):
        k = r"\b" + re.escape(norm(m.group(1)))
        if k not in keys:
            keys.append(k)
    return keys


def _years_in(sent: str) -> list[str]:
    out = []
    for m in re.finditer(r"(?<![\d.])(\d{3,4})(?!\d)", sent):
        y = m.group(1)
        if 300 <= int(y) <= 2030 and not _NON_YEAR_AFTER.match(sent[m.end():]) and y not in out:
            out.append(y)
    return out


def year_supported(year: str, keys: list[str], idx: dict, window: int = SAFE_WINDOW) -> bool:
    """(b): some passage has `year` within `window` chars of at least one of the sentence's content entities."""
    if not keys:
        return False
    rx = re.compile("|".join(keys))
    for pn in idx["norm"]:
        for m in re.finditer(rf"(?<!\d){year}(?!\d)", pn):
            if rx.search(pn[max(0, m.start() - window): m.end() + window]):
                return True
    return False


def _month_rx(month: int, day: str | None = None) -> str:
    forms = "|".join(sorted({norm(f) for f in _MONTHS[month]}, key=len, reverse=True))
    rom = [r for r, v in _ROMAN_M.items() if v == month][0]
    if day:
        d = str(int(day))
        return (rf"(?<!\d)0?{d}\s+(?:{forms})\b|(?<!\d)0?{d}\s+{rom.lower()}\.?\s+\d{{3,4}}|"
                rf"(?<!\d)0?{d}\.0?{month}\.\d{{3,4}}")
    return rf"\b(?:{forms})\b|(?<![\w.]){rom.lower()}\.?\s+\d{{3,4}}|(?<!\d)\d{{1,2}}\.0?{month}\.\d{{3,4}}"


def month_supported(month: int, year: str, idx: dict, day: str | None = None, window: int = SAFE_WINDOW) -> bool:
    """(a): the month (and the day, when given) occurs next to `year` (within `window` chars) in one passage."""
    rx = re.compile(_month_rx(month, day))
    for pn in idx["norm"]:
        for m in re.finditer(rf"(?<!\d){year}(?!\d)", pn):
            if rx.search(pn[max(0, m.start() - window): m.end() + window]):
                return True
    return False


def _date_mentions(sent: str) -> list[dict]:
    out, taken = [], []
    for kind, rx in (("month", _DATE_MONTH), ("roman", _DATE_ROMAN), ("num", _DATE_NUM)):
        for m in rx.finditer(sent):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            if kind == "month":
                mon = _MONTH_OF.get(m.group("mon").lower()) or _MONTH_OF.get(norm(m.group("mon")))
                if mon and not m.group("day") and not m.group("prep") and \
                        norm(m.group("mon")) == norm(_MONTHS[mon][0]):  # 'Marzec 1968', 'Czerwiec 1956': event names
                    continue
            elif kind == "roman":
                mon = _ROMAN_M[m.group("rom")]
                before = sent[:m.start()].split()
                if not m.group("day") and not m.group("prep") and before and \
                        re.match(r"[A-ZĄĆĘŁŃÓŚŹŻ]", before[-1]):  # 'Jan III 1683': a ruler's ordinal, not a month
                    continue
            else:
                mon = int(m.group("mnum"))
            if not mon or not 1 <= mon <= 12 or not 300 <= int(m.group("year")) <= 2030:
                continue
            day = m.group("day")
            if day and not 1 <= int(day) <= 31:
                continue
            taken.append((m.start(), m.end()))
            out.append({"start": m.start(), "end": m.end(), "prep": m.group("prep") or "", "day": day, "month": mon,
                        "year": m.group("year"), "text": m.group(0)})
    return sorted(out, key=lambda d: d["start"])


def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _rewrite_date(sent: str, d: dict, keep_month: bool) -> str:
    """Drop the day (keep_month) or the day and the month of one date mention, keeping a grammatical preposition:
    '25 października 1956 roku' -> 'w październiku 1956 roku'; 'W czerwcu 1958' -> 'W 1958'; 'od 3 V 1791' ->
    'od maja 1791' / 'od 1791'."""
    prep = d["prep"]
    lp = prep.lower()
    if keep_month:
        if lp in ("od", "do", "z", "ze"):
            new = f"{prep} {_MONTHS[d['month']][1]} {d['year']}"
        else:
            new = f"w {_MONTHS[d['month']][2]} {d['year']}"
    else:
        new = f"{prep if lp in ('od', 'do', 'z', 'ze') else 'w'} {d['year']}"
    before = sent[:d["start"]].rstrip(" \"'„(«")
    at_start = not before or before[-1] in ".!?…"  # '... węgierskie. 25 października' is one _SENT sentence
    if at_start or (prep[:1].isupper()):
        new = _cap_first(new)
    return sent[:d["start"]] + new + sent[d["end"]:]


def strip_years_safe(sent: str, years: list[str]) -> str:
    """strip_dates plus the sentence-initial forms it misses ('W 1953 roku wybuchło...' -> 'Wybuchło...')."""
    s = sent
    for y in years:
        yr = rf"(?:\d{{3,4}}\s*[–-]\s*)?{y}(?:\s*[–-]\s*\d{{3,4}})?(?:\s*(?:r\.|roku))?"
        m = re.match(rf"^(\W*)(?:w\s+latach|w\s+roku|w|we|od|do|około|ok\.|na\s+przełomie)\s+{yr}\s*,?\s*", s, re.I)
        if m:
            s = m.group(1) + _cap_first(s[m.end():])
            continue
        m = re.match(rf"^(\W*){yr}\s*,?\s+", s)
        if m and not re.match(r"(?:r\.|rok\b)", s[m.end():]):
            s = m.group(1) + _cap_first(s[m.end():])
            continue
        s = strip_dates(s, [y])
        s = re.sub(rf",?\s+(?:we|na\s+przełomie|około)\s+{yr}", "", s, flags=re.I)
    return re.sub(r"\s{2,}", " ", s).replace(" ,", ",").replace(" .", ".").replace("(,", "(").strip()


def _concrete(sent: str, idx: dict) -> bool:
    return bool(_years_in(sent) or content_keys(sent, idx))


def verify_sentence_safe(sent: str, idx: dict, fr=None) -> tuple[str, list[dict], bool]:
    """-> (rewritten sentence, issues, drop). Issues: {'kind': 'day'|'month'|'year'|'out_frame'|'names', ...}.
    Unsupported days / months / years are cut out; `drop` = the sentence should go (names absent from the
    passages, an out-of-frame event, nothing concrete left after its dates were removed, or a year that could not
    be cut out cleanly)."""
    s, issues = sent, []
    for d in reversed(_date_mentions(s)):  # right to left: earlier spans stay valid
        if month_supported(d["month"], d["year"], idx):
            if d["day"] and not month_supported(d["month"], d["year"], idx, day=d["day"]):
                s = _rewrite_date(s, d, keep_month=True)
                issues.append({"kind": "day", "date": d["text"]})
        else:
            s = _rewrite_date(s, d, keep_month=False)
            issues.append({"kind": "month", "date": d["text"]})
    keys = content_keys(s, idx)
    bad = [y for y in _years_in(s) if not year_supported(y, keys, idx)]
    iss = sentence_issues(s, idx["blob"], idx["blob_n"], fr)
    out_frame = [y for y in iss["out_frame"] if y not in bad]
    names = iss["bad_multi"] + (iss["bad_single"] if len(iss["bad_single"]) >= 2 else [])
    issues += [{"kind": "year", "year": y} for y in bad] + [{"kind": "out_frame", "year": y} for y in out_frame]
    if names:
        issues.append({"kind": "names", "names": names})
    drop = bool(names or out_frame)
    if bad or out_frame:
        s2 = strip_years_safe(s, bad + out_frame)
        left = any(re.search(rf"(?<!\d){y}(?!\d)", s2) for y in bad + out_frame)
        if left or not _concrete(s2, idx):
            drop = True
        if not left:
            s = s2
    return s, issues, drop


def verify_paragraph_safe(par: str, idx: dict, fr=None, min_sents: int = 3,
                          allow_drop: bool = True) -> tuple[str, list[dict], int]:
    """ESSAY_SAFE verification of one paragraph -> (text, log, n_unsupported). Sentences are rewritten by
    verify_sentence_safe; one that should go is dropped unless it is the first one or the paragraph would fall
    under `min_sents` sentences (allow_drop=False never drops: intro / conclusion keep their stance)."""
    sents = [x for x in _SENT.split(par) if x.strip()]
    budget = max(0, len(sents) - min_sents) if allow_drop else 0
    keep, log, n_bad = [], [], 0
    for i, x in enumerate(sents):
        y, issues, drop = verify_sentence_safe(x, idx, fr)
        if not issues:
            keep.append(x)
            continue
        n_bad += len(issues)
        if drop and i > 0 and budget > 0:
            budget -= 1
            log.append({"removed": x[:160], "issues": issues})
            continue
        log.append({"kept": y[:160], "issues": issues})
        keep.append(y)
    return " ".join(keep).strip(), log, n_bad


def count_unsupported(text: str, passages: list[str], fr=None) -> dict:
    """Offline audit of a finished essay with the ESSAY_SAFE checker (nothing is rewritten): unsupported claims,
    words and claims per 100 words. The header line is skipped."""
    idx = safe_index(passages)
    body = re.sub(r"^\s*WYPRACOWANIE na temat nr \S+\s*", "", text or "")
    n, kinds = 0, {}
    for par in [p for p in body.split("\n") if p.strip()]:
        for x in [s for s in _SENT.split(par) if s.strip()]:
            _, issues, _ = verify_sentence_safe(x, idx, fr)
            n += len(issues)
            for it in issues:
                kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
    w = body_words(text)
    return {"unsupported": n, "words": w, "per100": round(100.0 * n / w, 2) if w else None, "kinds": kinds}


def pick_candidate(cands: list[dict], min_words: int = 450) -> int:
    """Best of two topics: among essays with >= min_words words the one with the fewest unsupported claims per 100
    words (ties -> the earlier = better-covered topic); when none is long enough, the longer one."""
    ok = [i for i, c in enumerate(cands) if c.get("words", 0) >= min_words and c.get("unsupported") is not None]
    if ok:
        return min(ok, key=lambda i: (cands[i]["unsupported"] / max(1, cands[i]["words"]), i))
    return max(range(len(cands)), key=lambda i: (cands[i].get("words", 0), -i))


# ------------------------------------------------------------------ clean-up
_HDR_ANY = re.compile(r"^\W*(wyp\w{3,}|wypr\w*|temat)\b[^\n]{0,30}\b(temat\w*|tema|nr)\b[^\n]{0,20}$|"
                      r"^\W*temat\s*(nr\s*)?\d+\W*$", re.I)
_PROMPT_BITS = re.compile(r"zajmij\s+stanowisko|uwzględniając\s+w\s+swojej\s+argumentacji|twoja\s+wypowied|"
                          r"wybierz\s+jeden\s+z\s+(nich|tematów)|minimum\s+300", re.I)


def _tri(s: str) -> set:
    w = re.findall(r"\w+", norm(s))
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def strip_prompt_copy(par: str, topic: str) -> str:
    """Drop sentences that copy the topic/prompt ('... Zajmij stanowisko wobec powyższej tezy ...')."""
    tt = _tri(topic)
    out = []
    for x in _SENT.split(par):
        g = _tri(x)
        if _PROMPT_BITS.search(x) or (len(g) >= 4 and len(g & tt) >= 0.6 * len(g)):
            continue
        out.append(x)
    return " ".join(out).strip()


def clean_header_lines(text: str) -> str:
    return "\n".join(ln for ln in (text or "").split("\n") if not _HDR_ANY.match(ln.replace("*", "")))


def assemble(n: str, paragraphs: list[str]) -> str:
    body = "\n\n".join(p.strip() for p in paragraphs if p and p.strip())
    return f"WYPRACOWANIE na temat nr {n}\n\n{body}".strip()


def body_words(text: str) -> int:
    return word_count(re.sub(r"^\s*WYPRACOWANIE na temat nr \S+\s*", "", text or ""))


def trim_to_words(paragraphs: list[str], max_words: int, protect: set[int]) -> list[str]:
    """Over the limit -> drop the last sentences of the longest unprotected paragraphs (never below 4)."""
    pars = list(paragraphs)
    while sum(word_count(p) for p in pars) > max_words:
        cands = [(word_count(p), i) for i, p in enumerate(pars) if i not in protect and len(_SENT.split(p)) > 4]
        if not cands:
            break
        _, i = max(cands)
        pars[i] = " ".join(_SENT.split(pars[i])[:-1])
    return pars


__all__ = ["time_frame", "frame_text", "superlative", "element_kind", "plan_instruction", "parse_plan",
           "sentence_issues", "strip_dates", "verify_paragraph", "strip_prompt_copy", "clean_header_lines",
           "assemble", "body_words", "trim_to_words", "_WORD", "safe_index", "verify_paragraph_safe",
           "verify_sentence_safe", "count_unsupported", "pick_candidate"]
