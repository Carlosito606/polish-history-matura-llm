"""Essay mode (QTYPE_V2=1, qtype 'essay'): the CKE 'wypracowanie' (formula 2023: 0-15 pts, formula 2015: 0-12).

Rubric we write for (docs/cke_grading_rules.md, 'Essay'): up to 12 pts for the historical argument (each of the
three elements of the topic: rich 4 / satisfactory 3 / superficial 1; knowledge must serve an explicit stance
on the thesis), minus 1-3 pts for factual errors, plus up to 3 pts for coherence (0 below 300 words). With
several topics only the first explicitly chosen one is graded, so we write exactly one.

Flow (harness/pipeline.py: Pipeline._essay):
  1. every topic -> multi-query retrieval (thesis, thesis + each required aspect, entities) with a larger budget;
  2. the topic with the best retrieval coverage wins (ESSAY_TOPIC forces one);
  3. one generation (ESSAY_MAX_TOKENS, ESSAY_TEMPERATURE, DRY sampler, LoRA scale 0 when adapters are
     loaded), one expansion call when the text is under ESSAY_MIN_WORDS, then clean-up and the
     'WYPRACOWANIE na temat nr X' header.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from .qtype import ParsedQuestion, entities, essay_aspects

_WORD = re.compile(r"\w+(?:[-–]\w+)*")
_CMD = re.compile(r"\b(zajmij|ustosunkuj|scharakteryzuj|uzasadnij|rozstrzygnij|oceń|porównaj|przedstaw|wyjaśnij|"
                  r"opisz|wykaż|odpowiedz|omów|udowodnij|przeanalizuj)\b", re.I)
_STANCE = re.compile(r"\btez[aęy]\b|stanowisk|ustosunkuj|zgadzasz|rozstrzygnij|opini|\bocen|\boceń", re.I)
_MATERIALS = re.compile(r"materiał\w*\s+źródłow", re.I)
_STOP = set("""
oraz przez które który która którego których także jednak wobec swojej swoich tego tych jego jest było były była
powyższej powyższą tezy tezę tezie stanowisko zajmij uzasadnij uwzględniając argumentacji aspekty aspekt aspekcie
polityczny społeczno gospodarczy kulturowy militarny ustrojowy społeczny ekonomiczny międzynarodowy dyplomatyczny
wybrane wybranych trzech trzy przykłady przykładów okresie okresu wieku wieków latach dziejach historii
charakteryzując przedstawiając odwołując pracy wykorzystaj materiały źródłowe scharakteryzuj oceń porównaj przedstaw
wyjaśnij rozstrzygnij ustosunkuj odpowiedź odpowiedz między przede wszystkim najbardziej bardziej więcej mniej
""".split())


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")


def thesis_of(topic: str) -> str:
    """The thesis / subject: the text before the first command verb ('Zajmij stanowisko...'). A topic that starts
    with the command (formula 2015: 'Scharakteryzuj X') -> its first sentence without the verb."""
    t = " ".join((topic or "").split())
    m = _CMD.search(t)
    if m and m.start() > 15:
        return t[: m.start()].strip()
    first = re.split(r"(?<=[.?!])\s+", t, maxsplit=1)[0]
    return _CMD.sub("", first, count=1).strip(" ,.") or t


def key_terms(topic: str) -> list[str]:
    """Crude Polish stems of the thesis content words (prefix match survives most inflection)."""
    out = []
    for w in _WORD.findall(thesis_of(topic)):
        lw = w.lower()
        if len(lw) < 4 or lw in _STOP or lw.isdigit() and len(lw) < 3:
            continue
        stem = _norm(lw)[: max(4, min(7, len(lw) - 2))]
        if stem not in out:
            out.append(stem)
    return out


@dataclass
class TopicPlan:
    n: str
    topic: str
    thesis: str
    aspects: list[str]
    queries: list[tuple[str, str, float]]
    pq: ParsedQuestion
    needs_materials: bool = False
    contexts: list[dict] = field(default_factory=list)
    score: float = 0.0
    coverage: dict = field(default_factory=dict)


def plan(n: str, topic: str, full_text: str) -> TopicPlan:
    thesis = thesis_of(topic)
    aspects = essay_aspects(topic)
    short = " ".join(thesis.split()[:25])
    qs: list[tuple[str, str, float]] = [("stem", thesis, 1.0)]
    for i, a in enumerate(aspects, 1):
        qs.append((f"item:a{i}", f"{short} {a}", 1.0))
    if not aspects:  # 'charakteryzując trzy wybrane wydarzenia', 'panowanie trzech władców', formula-2015 commands
        rest = topic[len(thesis):] if topic.startswith(thesis) else topic
        rest = re.sub(r"zajmij\s+stanowisko\s+wobec\s+powyższej\s+tezy\s+i\s+je\s+uzasadnij,?", " ", rest, flags=re.I)
        rest = " ".join(rest.split())
        if len(rest) > 20:
            qs.append(("item:cmd", f"{short} {rest}", 0.8))
    ents = [e for e in entities(topic) if e.lower() not in {"zajmij", "polski"}]
    if ents:
        qs.append(("ents", " ".join(ents[:10]), 0.8))
        for i, e in enumerate([e for e in ents if not e.isdigit()][:4]):
            qs.append((f"ent:{i}", e, 0.6))
    seen, uq = set(), []
    for name, q, w in qs:
        k = q.strip().lower()
        if k and k not in seen:
            seen.add(k)
            uq.append((name, q, w))
    needs_mat = bool(_MATERIALS.search(topic)) and not re.search(rf"Materiały\s+źródłowe\s+do\s+tematu\s+{n}\b", full_text)
    tpq = ParsedQuestion(text=topic, qtype="essay", stem=" ".join([thesis] + aspects), command=topic)
    return TopicPlan(n=n, topic=topic, thesis=thesis, aspects=aspects, queries=uq, pq=tpq, needs_materials=needs_mat)


def coverage(p: TopicPlan, contexts: list[dict]) -> tuple[float, dict]:
    """How well the retrieved chunks support the topic: share of thesis terms present in the chunks, averaged
    with the mean sigmoid reranker score of the top 6 chunks (when reranked). Topics that need source
    materials missing from the input are penalised (x0.6)."""
    terms = key_terms(p.topic)
    blob = _norm(" ".join(f"{c.get('title', '')} {c.get('text', '')}" for c in contexts))
    lex = (sum(1 for t in terms if t in blob) / len(terms)) if terms else 0.5
    rr = [1.0 / (1.0 + math.exp(-float(c["rerank"]))) for c in contexts[:6] if "rerank" in c]
    rmean = sum(rr) / len(rr) if rr else None
    score = 0.5 * lex + 0.5 * rmean if rmean is not None else lex
    if not contexts:
        score = 0.0
    if p.needs_materials:
        score *= 0.6
    return round(score, 4), {"lex": round(lex, 3), "rerank": None if rmean is None else round(rmean, 3),
                             "terms": terms, "n_ctx": len(contexts), "needs_materials": p.needs_materials}


def choose(plans: list[TopicPlan], forced: int = 0) -> TopicPlan:
    if forced:
        for p in plans:
            if p.n == str(forced):
                return p
    # ties (within 0.01) go to the earlier topic
    best = plans[0]
    for p in plans[1:]:
        if p.score > best.score + 0.01:
            best = p
    return best


def choose_no_kb(plans: list[TopicPlan], forced: int = 0) -> TopicPlan:
    """No retrieval: prefer a topic with explicit aspects that needs no source materials."""
    if forced:
        return choose(plans, forced)
    ok = [p for p in plans if not p.needs_materials] or plans
    return next((p for p in ok if p.aspects), ok[0])


# ------------------------------------------------------------------ prompts
SYSTEM = (
    "Jesteś doświadczonym nauczycielem historii i egzaminatorem maturalnym. Piszesz wzorcowe wypracowania "
    "z matury z historii (poziom rozszerzony) po polsku: rzeczowo, spójnie, poprawnie językowo i z trafnie "
    "dobranymi faktami. Przed tematem mogą znajdować się fragmenty artykułów z polskiej Wikipedii — to Twoje "
    "główne źródło faktów. Nie wymyślasz faktów, dat ani nazwisk."
)


def instruction(p: TopicPlan) -> str:
    n = p.n
    stance = bool(_STANCE.search(p.topic))
    lines = [f"Napisz wypracowanie maturalne na temat nr {n}. Pisz wyłącznie o tym temacie.",
             "Wymagania (kryteria oceniania CKE):",
             f"1. Pierwsza linia musi brzmieć dokładnie: WYPRACOWANIE na temat nr {n}"]
    if stance:
        lines.append("2. Wstęp (jeden akapit): krótko wprowadź w temat i jednoznacznie zajmij stanowisko wobec tezy "
                     "(np. „Zgadzam się z tezą, że…”, „Nie zgadzam się z tezą, że…” albo „Teza jest słuszna tylko "
                     "częściowo, ponieważ…”). Całe wypracowanie ma konsekwentnie uzasadniać to stanowisko.")
    else:
        lines.append("2. Wstęp (jeden akapit): krótko wprowadź w temat i sformułuj własną tezę (ocenę), "
                     "którą całe wypracowanie konsekwentnie uzasadni.")
    tail = ("Każdy akapit zacznij od zdania, które wiąże ten element z tezą, a potem podaj konkretne fakty "
            "(wydarzenia, daty, postacie, pojęcia) i wyjaśnij, jak potwierdzają albo osłabiają tezę. "
            "Nie wyliczaj faktów bez związku z tezą.")
    if p.aspects:
        lines.append(f"3. Rozwinięcie: {len(p.aspects)} akapity po 5–7 zdań, po jednym na każdy aspekt, w tej "
                     f"kolejności: {', '.join(p.aspects)}. " + tail)
    else:
        lines.append("3. Rozwinięcie: trzy akapity po 5–7 zdań, każdy poświęcony innemu elementowi wymaganemu w temacie "
                     "(np. innej postaci, innemu wydarzeniu, państwu, etapowi albo zagadnieniu). " + tail)
    lines += [
        "4. Zakończenie (jeden akapit, 3–4 zdania): podsumuj argumenty i powtórz stanowisko. Wnioski muszą wynikać "
        "z rozwinięcia. Zakończenie jest ostatnim akapitem: nic po nim nie dopisuj.",
        "5. Długość: 450–700 wyrazów. Pisz ciągłym tekstem w akapitach, bez nagłówków, etykiet (np. „Stanowisko:”, "
        "„Interpretacja:”), numeracji, punktorów i pogrubień.",
        "6. Podawaj tylko fakty, których jesteś pewien: z powyższych fragmentów Wikipedii albo powszechnie znane. "
        "Nie zmyślaj dat, nazwisk ani liczb. Lepiej napisać mniej szczegółów niż podać błędny fakt, bo każdy "
        "błąd rzeczowy obniża ocenę.",
        "7. Wszystkie przykłady muszą mieścić się w ramach czasowych i przestrzennych tematu (np. jeśli temat dotyczy "
        "lat 50. XX wieku, nie opisuj wydarzeń z lat 60.).",
        "8. Nie powtarzaj tych samych zdań ani myśli i nie przepisuj polecenia.",
    ]
    return "\n".join(lines)


def build_user(p: TopicPlan, contexts: list[dict]) -> str:
    parts = []
    if contexts:
        parts.append("Fragmenty z Wikipedii:")
        for i, c in enumerate(contexts, 1):
            head = c.get("title", "") + (f" — {c['section']}" if c.get("section") else "")
            parts.append(f"[{i}] {head}\n{(c.get('text') or '').strip()}")
        parts.append("")
    parts.append(f"Temat nr {p.n}:\n{p.topic.strip()}")
    parts.append("")
    parts.append(instruction(p))
    return "\n".join(parts)


_ORD = ["pierwszy", "drugi", "trzeci", "czwarty"]


def section_steps(p: TopicPlan) -> list[tuple[str, str, int]]:
    """ESSAY_FALLBACK=sections: the essay written part by part (small models write 250-word single-pass essays).
    -> [(kind, instruction, max_tokens)]; every call sees the chunks, the topic and the text written so far."""
    stance = bool(_STANCE.search(p.topic))
    intro = ("Napisz wstęp wypracowania (3–4 zdania): wprowadź w temat i " +
             ("jednoznacznie zajmij stanowisko wobec tezy (np. „Zgadzam się z tezą, że…”, „Nie zgadzam się…” albo "
              "„Teza jest słuszna tylko częściowo, ponieważ…”)." if stance else
              "sformułuj własną tezę (ocenę), którą rozwinięcie uzasadni."))
    rule = ("Podaj konkretne fakty (wydarzenia, daty, postacie, pojęcia) z fragmentów Wikipedii albo powszechnie "
            "znane i wyjaśnij, jak uzasadniają stanowisko ze wstępu. Nie zmyślaj dat ani nazwisk, nie powtarzaj faktów "
            "z wcześniejszych akapitów i nie wychodź poza ramy czasowe tematu.")
    # token caps: Bielik-11B-v3 spends ~3 tokens per Polish word (450 tokens = ~150 words, cut mid-sentence)
    steps = [("intro", intro + " Napisz tylko wstęp, bez nagłówka.", 400)]
    elems = p.aspects or [None, None, None]
    for i, a in enumerate(elems[:4]):
        what = (f"o aspekcie: {a}" if a else
                f"poświęcony innemu elementowi wymaganemu w temacie niż poprzednie akapity (np. innej postaci, "
                f"innemu wydarzeniu, państwu albo etapowi)")
        steps.append((f"body{i + 1}", f"Napisz {_ORD[i]} akapit rozwinięcia (6–8 zdań) {what}. Zacznij od zdania, "
                                      f"które wiąże ten element z tezą. " + rule + " Nie przepisuj wstępu ani "
                                      f"wcześniejszych akapitów: napisz tylko ten nowy akapit.", 700))
    steps.append(("end", "Napisz zakończenie (3–4 zdania): podsumuj argumenty z rozwinięcia i powtórz stanowisko. "
                         "Nie dodawaj nowych faktów i nie przepisuj wcześniejszych akapitów. Napisz tylko zakończenie.", 400))
    return steps


def build_section_user(p: TopicPlan, contexts: list[dict], so_far: list[str], instr: str) -> str:
    base = build_user(p, contexts).rsplit(instruction(p), 1)[0].rstrip()
    done = "\n\n".join(so_far)
    return (base + "\n\n" + (f"Dotychczas napisany tekst wypracowania:\n{done}\n\n" if done else "") + instr)


# small models ignore '3–4 zdania' / '6–8 zdań' and run into the section's token cap
_PART_SENTS = {"intro": 5, "end": 5, "body1": 10, "body2": 10, "body3": 10, "body4": 10}


def clean_part(text: str, kind: str = "") -> str:
    """One section -> one paragraph (header, labels, headings and markdown removed). An unfinished last sentence
    (the section hit its max_tokens) is cut off; the intro and the conclusion keep at most 5 sentences, a body
    paragraph 10."""
    body = clean(text, "0").split("\n\n", 1)
    s = " ".join(body[1].split()) if len(body) > 1 else ""
    if s and not re.search(r"[.!?…][\"”»)]?$", s):
        cut = max(s.rfind(ch) for ch in ".!?…")
        if cut > 0:
            s = s[: cut + 1]
    cap = _PART_SENTS.get(kind, 0)
    if cap:
        s = " ".join(_SENT.split(s)[:cap])
    return s


def expand_message(p: TopicPlan, words: int) -> str:
    return (f"To wypracowanie jest za krótkie ({words} wyrazów; wymagane minimum to 300). Napisz je od nowa "
            f"w pełniejszej wersji, 500–700 wyrazów: zachowaj stanowisko i układ (wstęp, akapity rozwinięcia po 5–7 "
            f"zdań, zakończenie), a każdy akapit rozwiń o konkretne fakty z fragmentów Wikipedii. Zakończenie ma być "
            f"ostatnim akapitem: nie dopisuj po nim żadnych dodatkowych argumentów ani uwag. "
            f"Pierwsza linia: WYPRACOWANIE na temat nr {p.n}")


# ------------------------------------------------------------------ post-processing
_HEADER = re.compile(r"^\s*(wypr\w*\b(?=.{0,40}\b(temat\w*|tema|nr)\b).{0,60}|temat\w*(\s+nr)?\s*\d*\s*[:.].*|tema\w*\s*t?\s+nr\s*\d+.{0,40})$", re.I)
_TRAILER = re.compile(r"^\s*(dodatkowe\s+\w+|uwag[ia]|przypisy|bibliografia|źródła|literatura|notatk\w+|"
                      r"liczba\s+(wyrazów|słów))\b[^\n]{0,40}:?\s*$", re.I)
_SECTION = re.compile(r"^\s*(wstęp|wprowadzenie|rozwinięcie|zakończenie|podsumowanie|teza|argument\s*\d*|stanowisko|"
                      r"interpretacja|wnioski?|analiza|koniec|aspekt\s+\w+(-\w+)?)\s*[:.]?\s*$", re.I)
# inline labels at the start of a paragraph ('Interpretacja: ...', 'Aspekt polityczny: ...', 'Polityczny: ...')
_LABEL = re.compile(r"^\s*((aspekt\s+)?(polityczn|społeczn|gospodarcz|kulturow|militarn|ustrojow|międzynarodow|"
                    r"dyplomatyczn|ekonomiczn|religijn)\w*(-\w+)?|interpretacja|stanowisko|teza|wnioski?|argument\s*\d*|"
                    r"wstęp|rozwinięcie|zakończenie|podsumowanie)\s*:\s+", re.I)
# 'Przykład: W 1956 roku...' on its own line continues the paragraph above it (Bielik-4.5B writes these)
_EXAMPLE = re.compile(r"^\s*(przykład\w*(\s+\d+)?|np\.)\s*:\s+", re.I)
# sentence boundary; not after '50.' / '3.' / 'XV w.' and not before a Roman numeral ('lat 50. XX wieku'),
# but after a year ('w latach 1867–1872. Dzięki temu...')
_SENT = re.compile(r"(?<=[.!?…])(?<!\b\d\.)(?<!\b\d\d\.)(?<!\bw\.)\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„\"(])(?![IVXLC]+\b)")


def _is_heading(ln: str) -> bool:
    """'1. Kryzys kubański (1962)', 'Aspekt polityczny:' -> a short line without sentence punctuation."""
    s = ln.strip()
    return bool(s) and len(_WORD.findall(s)) <= 8 and (s.endswith(":") or not re.search(r"[.!?…;]$", s))


def _trigrams(norm_sent: str) -> set:
    w = norm_sent.split()
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def _near_dup(g: set, earlier: list[set]) -> bool:
    """>= 80% of the shorter sentence's word trigrams and >= 60% of this one's already appeared in one sentence."""
    if len(g) < 6:
        return False
    for h in earlier:
        common = len(g & h)
        if common >= 0.8 * min(len(g), len(h)) and common >= 0.6 * len(g):
            return True
    return False


def clean(text: str, n: str, truncated: bool = False) -> str:
    s = text or ""
    if "</think>" in s:
        s = s.split("</think>")[-1]
    s = s.replace("\r\n", "\n").replace("**", "").replace("__", "")
    lines = []
    for ln in s.split("\n"):
        ln = re.sub(r"^\s*#{1,6}\s*", "", ln)
        ln = re.sub(r"^\s*([-*•]|\d{1,2}[.)]|[a-e]\))\s+", "", ln)
        lines.append(ln.rstrip())
    # header-like lines at the top ('WYPRACOWANIE na temat nr 2', 'Temat: ...'), section labels and headings
    body, top = [], True
    for ln in lines:
        if top and (not ln.strip() or _HEADER.match(ln)):
            continue
        top = False
        if _TRAILER.match(ln) and body:  # 'Dodatkowe argumenty:' etc. after the conclusion -> cut the rest
            break
        if _SECTION.match(ln) or (_is_heading(ln) and not (truncated and ln is lines[-1])):
            continue
        body.append(_EXAMPLE.sub("\x00", ln) if _EXAMPLE.match(ln) else _LABEL.sub("", ln))
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n|\n(?=\S)", "\n".join(body)) if p.strip()]
    # drop verbatim repeated sentences (small models loop) and near-verbatim ones (a paragraph that restarts with
    # the intro's sentence); the conclusion may restate the stance, so it is only checked for verbatim repeats
    seen, grams, out = set(), [], []
    for pi, p in enumerate(paras):
        last = pi == len(paras) - 1 and len(paras) >= 3
        keep = []
        for sent in _SENT.split(p):
            k = _norm(re.sub(r"\W+", " ", sent)).strip()
            if len(k) >= 25 and k in seen:
                continue
            g = _trigrams(k)
            if not last and _near_dup(g, grams):
                continue
            seen.add(k)
            if len(g) >= 6:
                grams.append(g)
            keep.append(sent)
        if keep:
            out.append(" ".join(keep))
    # a one-line 'paragraph' (restated thesis, stray sentence) joins the next paragraph
    merged: list[str] = []
    for p in out:
        cont = p.startswith("\x00")  # an 'example' paragraph joins the previous one
        p = p.replace("\x00", "").strip()
        if merged and (cont or len(_WORD.findall(merged[-1])) < 15):
            merged[-1] = merged[-1] + " " + p
        elif p:
            merged.append(p)
    s = "\n\n".join(merged).replace("\x00", "").strip()
    if truncated:
        cut = max(s.rfind(ch) for ch in ".!?…")
        if cut > 0.7 * len(s):
            s = s[: cut + 1]
    return f"WYPRACOWANIE na temat nr {n}\n\n{s}".strip()


def body_words(essay_text: str) -> int:
    return word_count(re.sub(r"^\s*WYPRACOWANIE na temat nr \S+\s*", "", essay_text or ""))
