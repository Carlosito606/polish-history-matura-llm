"""Polish prompts and llama.cpp GBNF grammars per question type."""
from __future__ import annotations

import re

from .qtype import ParsedQuestion

SYSTEM = (
    "Jesteś ekspertem z historii Polski i historii powszechnej. Pomagasz maturzyście rozwiązywać "
    "zadania z matury z historii. Odpowiadasz po polsku, precyzyjnie i zwięźle.\n"
    "Przed zadaniem mogą znajdować się fragmenty artykułów z polskiej Wikipedii. Jeśli zawierają "
    "informacje potrzebne do odpowiedzi, opieraj się na nich. Jeśli są nieistotne lub niewystarczające, "
    "odpowiedz na podstawie własnej wiedzy historycznej. Nigdy nie odmawiaj odpowiedzi — zawsze wskaż "
    "najbardziej prawdopodobną odpowiedź i trzymaj się dokładnie wymaganego formatu."
)

THINK_SUFFIX = (
    "\n\nNajpierw krótko przeanalizuj zadanie (najwyżej 5 zdań, powołując się na fakty i daty), "
    "a w ostatniej linii napisz: „Odpowiedź: …” w wymaganym formacie."
)


def _labels(items) -> str:
    return ", ".join(l for l, _ in items)


def instruction(pq: ParsedQuestion) -> str:
    t = pq.qtype
    if t == "abcd":
        if pq.n_select > 1:
            return (f"Zadanie zamknięte wielokrotnego wyboru. Wybierz dokładnie {pq.n_select} poprawne odpowiedzi "
                    f"spośród: {_labels(pq.options)}. Odpowiedz wyłącznie literami oddzielonymi przecinkami, bez wyjaśnień.")
        return (f"Zadanie zamknięte jednokrotnego wyboru. Tylko jedna odpowiedź jest poprawna. "
                f"Odpowiedz wyłącznie jedną literą ({_labels(pq.options)}), bez wyjaśnień.")
    if t == "abj":
        return ("Wybierz odpowiedź A albo B oraz jej poprawne uzasadnienie (numer). "
                "Odpowiedz wyłącznie literą i numerem, np. A2, bez wyjaśnień.")
    if t == "pf":
        n = len(pq.statements)
        if n:
            return (f"Oceń prawdziwość każdego z {n} zdań. Dla każdego zdania, w podanej kolejności, napisz P "
                    f"(prawda) albo F (fałsz). Odpowiedz w formacie:\n1: P\n2: F\n… (bez wyjaśnień).")
        return "Oceń prawdziwość zdań. Dla każdego zdania napisz P (prawda) albo F (fałsz), w kolejności, bez wyjaśnień."
    if t == "chrono":
        return (f"Uporządkuj elementy ({_labels(pq.items)}) chronologicznie, od najwcześniejszego do najpóźniejszego. "
                f"Odpowiedz wyłącznie oznaczeniami oddzielonymi przecinkami, np. {', '.join(l for l, _ in pq.items[::-1])}, bez wyjaśnień.")
    if t == "match" and pq.left and pq.left[0][0].isalpha():  # v2: letter -> number (CKE table fill)
        ex = ", ".join(f"{l}-{pq.right[0][0] if pq.right else '1'}" for l, _ in pq.left[:2])
        return (f"Przyporządkuj każdemu elementowi oznaczonemu literą ({_labels(pq.left)}) właściwy numer "
                f"({_labels(pq.right)}). Odpowiedz wyłącznie w formacie par, np. {ex}, bez wyjaśnień.")
    if t == "abcd_parts":
        ex = ", ".join(f"{p[0]}-X" for p in pq.parts)
        return (f"Zadanie składa się z {len(pq.parts)} zdań do dokończenia; każde zdanie ma własną listę odpowiedzi. "
                f"Dla każdego zdania wybierz jedną poprawną odpowiedź. Odpowiedz wyłącznie w formacie: {ex} "
                f"(X = litera), bez wyjaśnień.")
    if t == "explain":
        return instruction_explain(pq)
    if t == "match":
        ex = ", ".join(f"{l}-{pq.right[0][0] if pq.right else 'A'}" for l, _ in pq.left[:2])
        return (f"Przyporządkuj każdemu elementowi oznaczonemu cyfrą ({_labels(pq.left)}) właściwy element oznaczony literą "
                f"({_labels(pq.right)}). Odpowiedz wyłącznie w formacie par, np. {ex}, …, bez wyjaśnień.")
    if t == "open":
        kind = {
            "year": "Podaj sam rok (liczbę), bez dodatkowych słów.",
            "century": "Podaj sam wiek (cyframi rzymskimi, np. XV w.).",
            "person": "Podaj samo imię i nazwisko (lub imię z przydomkiem/numerem władcy).",
            "place": "Podaj samą nazwę miejsca.",
            "number": "Podaj samą liczbę.",
        }.get(pq.open_kind, "Podaj samą nazwę, termin lub wartość.")
        return f"Odpowiedz jak najkrócej: jednym słowem lub krótką frazą, bez pełnego zdania i bez wyjaśnień. {kind}"
    return "Odpowiedz zwięźle i konkretnie (najwyżej 3 zdania)."


def instruction_explain(pq: ParsedQuestion) -> str:
    """v2 explanation mode (wyjaśnij / uzasadnij / rozstrzygnij + uzasadnij / porównaj / podaj nazwisko i wyjaśnij)."""
    k = pq.open_kind
    if k == "decision":
        base = ("Najpierw podaj jedno, jednoznaczne rozstrzygnięcie (np. Tak/Nie, wskazany fragment, plan lub epokę). "
                "Następnie uzasadnij je w 1–3 zdaniach: odwołaj się do konkretnych informacji ze wszystkich źródeł "
                "wskazanych w poleceniu oraz do własnej wiedzy (nazwy, daty, pojęcia).")
    elif k == "compare":
        base = ("Podaj jedno podobieństwo i jedną różnicę (każde w 1–2 zdaniach), odnosząc się do treści obu źródeł.")
    elif k == "name_explain":
        base = ("Podaj jedno nazwisko, a następnie wyjaśnienie w 1–3 zdaniach z odwołaniem do faktografii "
                "(konkretne wydarzenia, daty).")
    else:
        base = ("Odpowiedz rzeczowo, własnymi słowami, w 1–3 pełnych zdaniach. Podaj konkretne fakty historyczne "
                "(nazwy, daty, postacie, pojęcia) i związek przyczynowo-skutkowy. Jeśli polecenie odwołuje się do "
                "źródła, wskaż konkretną informację z tego źródła.")
    base += " Odpowiedz tylko na to polecenie, nie dopisuj innych zadań."
    if pq.labels:
        base += " Zachowaj dokładnie format:\n" + "\n".join(f"{l}: …" for l in pq.labels)
    return base


def instruction_pf_single() -> str:
    return "Oceń, czy powyższe zdanie jest prawdziwe. Odpowiedz jedną literą: P (prawda) albo F (fałsz)."


def instruction_chrono_years(pq: ParsedQuestion) -> str:
    return ("Dla każdego elementu podaj rok, w którym miało miejsce wydarzenie (dla okresów i panowań — rok początku). "
            "Lata przed naszą erą zapisz jako liczby ujemne. Odpowiedz wyłącznie w formacie:\n"
            + "\n".join(f"{l}: rok" for l, _ in pq.items))


def build_user(question: str, contexts: list[dict], instr: str, think: bool = False) -> str:
    parts = []
    if contexts:
        parts.append("Fragmenty z Wikipedii:")
        for i, c in enumerate(contexts, 1):
            head = c.get("title", "")
            if c.get("section"):
                head += f" — {c['section']}"
            parts.append(f"[{i}] {head}\n{c.get('text', '').strip()}")
        parts.append("")
    parts.append("Zadanie:\n" + question.strip())
    parts.append("")
    parts.append(instr + (THINK_SUFFIX if think else ""))
    return "\n".join(parts)


# ---------------- GBNF grammars ----------------

def _alt(labels: list[str]) -> str:
    return "(" + " | ".join(f'"{l}"' for l in labels) + ")"


def grammar_for(pq: ParsedQuestion) -> str | None:
    t = pq.qtype
    if t == "abcd" and pq.options:
        L = _alt([l for l, _ in pq.options])
        if pq.n_select > 1:
            return f"root ::= L" + ' ", " L' * (pq.n_select - 1) + f"\nL ::= {L}\n"
        return f"root ::= {L}\n"
    if t == "abcd_parts" and pq.parts:
        body = ' ", " '.join(f'"{pl}-" {_alt([l for l, _ in opts])}' for pl, _, opts in pq.parts)
        return f"root ::= {body}\n"
    if t == "abj" and pq.options and pq.justifications:
        return f"root ::= {_alt([l for l, _ in pq.options])} {_alt([l for l, _ in pq.justifications])}\n"
    if t == "pf" and pq.statements:
        n = len(pq.statements)
        body = ' "\\n" '.join(f'"{i}: " V' for i in range(1, n + 1))
        return f'root ::= {body}\nV ::= "P" | "F"\n'
    if t == "chrono" and pq.items:
        labels = [l for l, _ in pq.items]
        if PERMUTATION_GRAMMAR and len(labels) <= 6:
            return "root ::= " + _perm_rule(labels, len(labels), lambda i, l: ("" if i == 0 else ", ") + l) + "\n"
        n = len(labels)
        return "root ::= L" + ' ", " L' * (n - 1) + f"\nL ::= {_alt(labels)}\n"
    if t == "match" and pq.left and pq.right:
        left = [l for l, _ in pq.left]
        right = [l for l, _ in pq.right]
        reuse = bool(re.search(r"więcej niż (jeden raz|raz)|wielokrotnie|kilkakrotnie|można wykorzystać kilka", pq.text, re.I))
        if PERMUTATION_GRAMMAR and not reuse and len(right) >= len(left) and _n_perm(len(right), len(left)) <= 720:
            return "root ::= " + _perm_rule(right, len(left),
                                            lambda i, r: ("" if i == 0 else ", ") + f"{left[i]}-{r}") + "\n"
        body = ' ", " '.join(f'"{l}-" R' for l in left)
        return f"root ::= {body}\nR ::= {_alt(right)}\n"
    return None


# injective answers only (each label once) for chrono / match — enumerated as a GBNF trie
PERMUTATION_GRAMMAR = True


def _n_perm(n: int, k: int) -> int:
    out = 1
    for i in range(k):
        out *= n - i
    return out


def _perm_rule(pool: list[str], k: int, token, i: int = 0) -> str:
    """GBNF expression generating every ordered selection of k distinct items from pool."""
    if i == k:
        return '""'
    alts = []
    for p in pool:
        rest = [q for q in pool if q != p]
        tail = _perm_rule(rest, k, token, i + 1)
        lit = '"' + token(i, p) + '"'
        alts.append(lit if tail == '""' else f"{lit} {tail}")
    return "(" + " | ".join(alts) + ")"


def grammar_pf_single() -> str:
    return 'root ::= "P" | "F"\n'


def grammar_years(pq: ParsedQuestion) -> str:
    body = ' "\\n" '.join(f'"{l}: " Y' for l, _ in pq.items)
    return f'root ::= {body}\nY ::= "-"? [0-9] [0-9]? [0-9]? [0-9]?\n'
