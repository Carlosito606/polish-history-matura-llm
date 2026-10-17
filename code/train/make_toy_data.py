#!/usr/bin/env python
"""Toy SFT data for testing the LoRA pipeline end to end (NOT for real training).

Builds fresh matura-style questions from a small hand-written fact bank (no dev-set questions), renders
them with the harness prompt code (same SYSTEM + instruction + "Zadanie:" layout the harness sends to
llama-server) and writes chat JSONL:
    {"messages": [system, user, assistant], "meta": {"type": ..., "toy": true}}
The assistant content is the short canonical answer ("B", "P, F, P", "C, A, D, B", "1-B, 2-A", "1410").

    python train/make_toy_data.py --n 200 --out /workspace/data/toy/train.jsonl --eval-n 24 --eval-out .../eval.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness import prompts  # noqa: E402
from harness.qtype import detect  # noqa: E402

# (event phrase in the nominative, year, person or None, one-line context)
FACTS = [
    ("bitwa pod Cedynią", 972, "Mieszko I", "Wojska Mieszka I pokonały pod Cedynią margrabiego Hodona."),
    ("zjazd gnieźnieński", 1000, "Bolesław Chrobry", "Cesarz Otton III przybył do Gniezna do grobu św. Wojciecha."),
    ("sprowadzenie Krzyżaków na ziemię chełmińską", 1226, "Konrad Mazowiecki", "Książę mazowiecki wezwał zakon do walki z Prusami."),
    ("bitwa pod Legnicą", 1241, "Henryk Pobożny", "Rycerstwo śląskie starło się z Mongołami."),
    ("koronacja Władysława Łokietka", 1320, "Władysław Łokietek", "Koronacja odbyła się w katedrze wawelskiej."),
    ("bitwa pod Płowcami", 1331, "Władysław Łokietek", "Starcie polsko-krzyżackie na Kujawach."),
    ("pokój kaliski", 1343, "Kazimierz Wielki", "Polska odzyskała Kujawy i ziemię dobrzyńską."),
    ("przywilej koszycki", 1374, "Ludwik Węgierski", "Szlachta uzyskała zwolnienie z większości podatków."),
    ("bitwa pod Grunwaldem", 1410, "Władysław Jagiełło", "Wojska polsko-litewskie pokonały zakon krzyżacki."),
    ("drugi pokój toruński", 1466, "Kazimierz Jagiellończyk", "Zakończenie wojny trzynastoletniej."),
    ("konstytucja Nihil novi", 1505, "Aleksander Jagiellończyk", "Sejm w Radomiu ograniczył prawodawczą władzę króla."),
    ("hołd pruski", 1525, "Zygmunt Stary", "Albrecht Hohenzollern złożył hołd w Krakowie."),
    ("konfederacja warszawska", 1573, None, "Akt gwarantujący pokój między wyznaniami."),
    ("unia brzeska", 1596, None, "Część hierarchii prawosławnej uznała zwierzchnictwo papieża."),
    ("bitwa pod Kircholmem", 1605, "Jan Karol Chodkiewicz", "Husaria rozbiła armię szwedzką."),
    ("bitwa pod Kłuszynem", 1610, "Stanisław Żółkiewski", "Hetman pokonał wojska rosyjsko-szwedzkie."),
    ("bitwa pod Oliwą", 1627, None, "Flota Rzeczypospolitej pokonała eskadrę szwedzką."),
    ("wybuch powstania Chmielnickiego", 1648, "Bohdan Chmielnicki", "Kozacy zaporoscy wystąpili przeciw Rzeczypospolitej."),
    ("traktaty welawsko-bydgoskie", 1657, "Jan Kazimierz", "Elektor brandenburski uzyskał suwerenność w Prusach Książęcych."),
    ("pokój w Oliwie", 1660, "Jan Kazimierz", "Zakończenie wojny ze Szwecją."),
    ("sejm niemy", 1717, "August II Mocny", "Sejm obradował pod presją wojsk rosyjskich."),
    ("pierwszy rozbiór Polski", 1772, "Stanisław August Poniatowski", "Rosja, Prusy i Austria zajęły część ziem Rzeczypospolitej."),
    ("powstanie kościuszkowskie", 1794, "Tadeusz Kościuszko", "Akt powstania ogłoszono na krakowskim Rynku."),
    ("utworzenie Księstwa Warszawskiego", 1807, "Napoleon Bonaparte", "Państwo powstało na mocy pokoju w Tylży."),
    ("Wiosna Ludów", 1848, None, "Fala rewolucji w wielu państwach Europy."),
    ("uwłaszczenie chłopów w Królestwie Polskim", 1864, "Aleksander II", "Ukaz carski nadał chłopom ziemię na własność."),
    ("proklamowanie Cesarstwa Niemieckiego", 1871, "Otto von Bismarck", "Uroczystość odbyła się w Wersalu."),
    ("bitwa pod Verdun", 1916, None, "Jedna z najdłuższych bitew I wojny światowej."),
    ("podpisanie traktatu wersalskiego", 1919, None, "Traktat kończący I wojnę światową z Niemcami."),
    ("przewrót majowy", 1926, "Józef Piłsudski", "Zamach stanu w Warszawie."),
    ("wybuch powstania warszawskiego", 1944, "Tadeusz Bór-Komorowski", "Walki rozpoczęły się 1 sierpnia."),
    ("konferencja jałtańska", 1945, None, "Spotkanie przywódców wielkiej trójki na Krymie."),
    ("Poznański Czerwiec", 1956, None, "Protest robotników w Poznaniu."),
    ("wydarzenia marcowe", 1968, None, "Protesty studenckie i kampania antysemicka."),
    ("wprowadzenie stanu wojennego", 1981, "Wojciech Jaruzelski", "Wojskowa Rada Ocalenia Narodowego przejęła władzę."),
    ("obrady Okrągłego Stołu", 1989, None, "Rozmowy władzy z opozycją solidarnościową."),
    ("wstąpienie Polski do NATO", 1999, None, "Polska stała się członkiem Sojuszu Północnoatlantyckiego."),
    ("upadek cesarstwa zachodniorzymskiego", 476, "Odoaker", "Odoaker złożył z tronu Romulusa Augustulusa."),
    ("koronacja cesarska Karola Wielkiego", 800, "Karol Wielki", "Koronacji dokonał papież Leon III."),
    ("schizma wschodnia", 1054, None, "Rozłam między Kościołem zachodnim i wschodnim."),
    ("pierwsza wyprawa Kolumba do Ameryki", 1492, "Krzysztof Kolumb", "Wyprawa pod banderą hiszpańską."),
    ("ogłoszenie 95 tez", 1517, "Marcin Luter", "Początek reformacji w Wittenberdze."),
    ("uchwalenie Deklaracji niepodległości Stanów Zjednoczonych", 1776, "Thomas Jefferson", "Kongres Kontynentalny w Filadelfii."),
    ("zburzenie Bastylii", 1789, None, "Symboliczny początek rewolucji francuskiej."),
]
LET = "ABCDEFGH"


def distract_years(y, rnd, k=3):
    out = set()
    while len(out) < k:
        d = rnd.choice([-1, 1]) * rnd.choice([3, 7, 10, 12, 18, 25, 30, 40, 50, 64, 100])
        if y + d > 0 and y + d != y:
            out.add(y + d)
    return list(out)


def q_abcd(rnd):
    ev, y, _, ctx = rnd.choice(FACTS)
    opts = distract_years(y, rnd) + [y]
    rnd.shuffle(opts)
    stem = rnd.choice([f"W którym roku miało miejsce wydarzenie: {ev}?", f"Wskaż rok, w którym nastąpiło wydarzenie: {ev}."])
    q = stem + "\n" + "\n".join(f"{LET[i]}. {o}" for i, o in enumerate(opts))
    return "abcd", q, LET[opts.index(y)], [ctx]


def q_person(rnd):
    ev, y, p, ctx = rnd.choice([f for f in FACTS if f[2]])
    others = rnd.sample([f[2] for f in FACTS if f[2] and f[2] != p], 3)
    opts = others + [p]
    rnd.shuffle(opts)
    q = f"Która postać jest związana z wydarzeniem: {ev} ({y})?\n" + "\n".join(f"{LET[i]}. {o}" for i, o in enumerate(opts))
    return "abcd", q, LET[opts.index(p)], [ctx]


def q_chrono(rnd):
    n = rnd.choice([3, 4, 4, 5])
    fs = rnd.sample(FACTS, n)
    while len({f[1] for f in fs}) < n:
        fs = rnd.sample(FACTS, n)
    q = "Uporządkuj chronologicznie wydarzenia, od najwcześniejszego do najpóźniejszego.\n" + \
        "\n".join(f"{LET[i]}. {f[0]}" for i, f in enumerate(fs))
    order = sorted(range(n), key=lambda i: fs[i][1])
    return "chrono", q, ", ".join(LET[i] for i in order), [f[3] for f in fs[:2]]


def q_pf(rnd):
    n = rnd.choice([3, 3, 4])
    fs = rnd.sample(FACTS, n)
    lines, vals = [], []
    for f in fs:
        true = rnd.random() < 0.5
        y = f[1] if true else rnd.choice(distract_years(f[1], rnd))
        lines.append(f"{f[0][0].upper() + f[0][1:]} miało miejsce w {y} roku.")
        vals.append("P" if true else "F")
    q = ("Oceń prawdziwość podanych zdań. Zaznacz P, jeśli zdanie jest prawdziwe, albo F – jeśli jest fałszywe.\n"
         + "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines)))
    return "pf", q, ", ".join(vals), [f[3] for f in fs[:2]]


def q_match(rnd):
    n = 3
    fs = rnd.sample(FACTS, n + 1)
    while len({f[1] for f in fs}) < n + 1:
        fs = rnd.sample(FACTS, n + 1)
    years = [f[1] for f in fs]
    rnd.shuffle(years)
    q = ("Przyporządkuj każdemu wydarzeniu (1–3) właściwy rok (A–D). Jeden rok nie pasuje do żadnego wydarzenia.\n"
         + "\n".join(f"{i + 1}. {f[0]}" for i, f in enumerate(fs[:n])) + "\n"
         + "\n".join(f"{LET[i]}. {y}" for i, y in enumerate(years)))
    ans = ", ".join(f"{i + 1}-{LET[years.index(f[1])]}" for i, f in enumerate(fs[:n]))
    return "match", q, ans, [fs[0][3]]


def q_open(rnd):
    ev, y, p, ctx = rnd.choice(FACTS)
    if p and rnd.random() < 0.5:
        return "open", f"Podaj imię i nazwisko postaci związanej z wydarzeniem: {ev} ({y}).", p, [ctx]
    return "open", f"Podaj rok, w którym miało miejsce wydarzenie: {ev}.", str(y), [ctx]


GENS = [(q_abcd, 0.22), (q_person, 0.10), (q_chrono, 0.2), (q_pf, 0.2), (q_match, 0.14), (q_open, 0.14)]


def build(rnd, with_ctx_p=0.6, ctx_chars=0):
    g = rnd.choices([g for g, _ in GENS], weights=[w for _, w in GENS])[0]
    t, q, ans, ctx_lines = g(rnd)
    pq = detect(q, forced_type=t)
    ctxs = []
    if rnd.random() < with_ctx_p or ctx_chars:
        ctxs = [{"title": "Notatka", "text": c} for c in ctx_lines]
    while ctx_chars and sum(len(c["text"]) for c in ctxs) < ctx_chars:  # filler for throughput benchmarks
        f = rnd.sample(FACTS, 6)
        ctxs.append({"title": f[0][0], "text": " ".join(f"{x[0][0].upper() + x[0][1:]} ({x[1]}). {x[3]}" for x in f)})
    user = prompts.build_user(pq.text, ctxs, prompts.instruction(pq))
    return {"messages": [{"role": "system", "content": prompts.SYSTEM}, {"role": "user", "content": user},
                         {"role": "assistant", "content": ans}],
            "meta": {"type": t, "toy": True, "detected": detect(q).qtype, "question": q}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", required=True)
    ap.add_argument("--eval-n", type=int, default=24)
    ap.add_argument("--eval-out", default="")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--ctx-chars", type=int, default=0, help="pad every prompt with filler context (benchmarks)")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    seen, rows = set(), []
    while len(rows) < a.n + a.eval_n:
        r = build(rnd, ctx_chars=a.ctx_chars)
        key = r["meta"]["question"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows[: a.n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if a.eval_out and a.eval_n:
        with open(a.eval_out, "w", encoding="utf-8") as f:
            for r in rows[a.n:]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    bad = sum(1 for r in rows if r["meta"]["detected"] != r["meta"]["type"])
    print(f"wrote {a.n} train + {a.eval_n} eval; harness type detection mismatches: {bad}")


if __name__ == "__main__":
    main()
