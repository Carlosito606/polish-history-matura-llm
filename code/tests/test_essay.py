"""Essay mode tests (QTYPE_V2=1 -> qtype 'essay'; harness/essay.py, Pipeline._essay).

Synthetic essay commands below are our own wording that mimics the CKE layout (no CKE text is embedded).
Real CKE essays are checked only when the git-ignored devset/cke-essays.jsonl is present.

Run:  python -m unittest tests.test_essay -v
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import essay  # noqa: E402
from harness.config import Settings  # noqa: E402
from harness.pipeline import Pipeline  # noqa: E402
from harness.qtype import detect, essay_aspects, essay_topics, is_essay  # noqa: E402

DEV = os.path.join(ROOT, "devset")

F2023 = """Zadanie 26. (0–15)
Zadanie zawiera trzy tematy. Wybierz jeden z nich do opracowania. Twoja wypowiedź
powinna liczyć minimum 300 wyrazów.

1. Hołd pruski był największym sukcesem dyplomacji ostatnich Jagiellonów. Zajmij stanowisko
wobec powyższej tezy i je uzasadnij, uwzględniając w swojej argumentacji aspekty: polityczny,
społeczno-
-gospodarczy i militarny.

2. Kongres wiedeński zapewnił Europie trwały pokój. Zajmij stanowisko wobec powyższej tezy
i je uzasadnij, uwzględniając w swojej argumentacji aspekt ustrojowy, międzynarodowy i społeczny.

3. Odwilż 1956 roku zmieniła PRL tylko pozornie. Zajmij stanowisko wobec powyższej tezy i je
uzasadnij, charakteryzując trzy wybrane wydarzenia z lat 1956–1970.

WYPRACOWANIE
na temat nr ……
"""

F2015 = """Zadanie 27. (0–12)
Zadanie zawiera pięć tematów. Wybierz jeden z nich do opracowania.

1. Scharakteryzuj rolę Aten w świecie greckim w V w. p.n.e.
2. Wyjaśnij przyczyny rozwoju miast w Polsce w XIII w. W pracy wykorzystaj materiały
źródłowe (s. 25–26).
3. Porównaj politykę wewnętrzną Stefana Batorego i Zygmunta III Wazy.
4. Oceń skutki kongresu wiedeńskiego dla ziem polskich.
5. Scharakteryzuj politykę gospodarczą II Rzeczypospolitej w latach 1926–1939.

Materiały źródłowe do tematu 2.
Źródło A. Przywilej lokacyjny dla miasta (fragment)
Wójt ma prawo sądzić mieszczan według prawa niemieckiego.
"""


class TestDetect(unittest.TestCase):
    def test_formula_2023_three_topics(self):
        pq = detect(F2023, v2=True)
        self.assertEqual(pq.qtype, "essay")
        self.assertEqual([n for n, _ in pq.topics], ["1", "2", "3"])
        self.assertTrue(pq.topics[2][1].startswith("Odwilż 1956"))
        self.assertNotIn("WYPRACOWANIE", pq.topics[2][1])
        self.assertEqual(essay_aspects(pq.topics[0][1]), ["polityczny", "społeczno-gospodarczy", "militarny"])
        self.assertEqual(essay_aspects(pq.topics[1][1]), ["ustrojowy", "międzynarodowy", "społeczny"])
        self.assertEqual(essay_aspects(pq.topics[2][1]), [])

    def test_mentor_header_and_no_task_header(self):
        body = F2023.split("\n", 1)[1]  # without 'Zadanie 26. (0–15)'
        self.assertEqual(detect("Zadanie 26 (15 pkt)\n\n" + body, v2=True).qtype, "essay")
        self.assertEqual(detect(body, v2=True).qtype, "essay")

    def test_formula_2015_five_topics_materials_after(self):
        pq = detect(F2015, v2=True)
        self.assertEqual(pq.qtype, "essay")
        self.assertEqual(len(pq.topics), 5)
        self.assertTrue(pq.topics[1][1].endswith("(s. 25–26)."))
        self.assertNotIn("Materiały", pq.topics[4][1])

    def test_other_essay_commands(self):
        for q in ("Napisz wypracowanie na temat: Znaczenie unii lubelskiej dla Rzeczypospolitej.",
                  "Napisz rozprawkę, w której ocenisz reformy Sejmu Czteroletniego.",
                  "Oceń politykę Piłsudskiego w latach 1926–1935. Wypowiedź w formie eseju.",
                  "Oceń rolę Kościoła w PRL. Twoja wypowiedź argumentacyjna powinna liczyć co najmniej 300 słów."):
            pq = detect(q, v2=True)
            self.assertEqual(pq.qtype, "essay", q)
            self.assertEqual(len(pq.topics), 1)

    def test_not_essay(self):
        for q in ("Na podstawie fragmentu eseju wyjaśnij, dlaczego autor krytykuje politykę Sanacji.",
                  "Zajmij stanowisko wobec opinii historyka. Odpowiedź uzasadnij, odwołując się do źródła.",
                  "Który z tematów obrad Sejmu z 1791 r. dotyczył miast?\nA. podatki\nB. prawa miejskie",
                  "W którym roku zawarto unię w Krewie?"):
            self.assertFalse(is_essay(q), q)
            self.assertNotEqual(detect(q, v2=True).qtype, "essay", q)

    def test_v1_never_essay(self):
        self.assertNotEqual(detect(F2023).qtype, "essay")
        self.assertNotEqual(detect(F2023, forced_type=None, v2=False).qtype, "essay")

    def test_dev_sets_have_no_essays(self):
        n = 0
        for f in sorted(glob.glob(os.path.join(DEV, "dev-[a-h].jsonl"))) + \
                sorted(glob.glob(os.path.join(DEV, "cke-2023.jsonl"))) + sorted(glob.glob(os.path.join(DEV, "cke-more.jsonl"))):
            with open(f, encoding="utf-8") as fh:
                for ln in fh:
                    if ln.strip():
                        d = json.loads(ln)
                        n += 1
                        self.assertNotEqual(detect(d["question"], v2=True).qtype, "essay", d["id"])
        if not n:
            self.skipTest("no dev sets")

    def test_cke_essays_detected(self):
        p = os.path.join(DEV, "cke-essays.jsonl")
        if not os.path.exists(p):
            self.skipTest("devset/cke-essays.jsonl not present (git-ignored CKE material)")
        with open(p, encoding="utf-8") as fh:
            recs = [json.loads(ln) for ln in fh if ln.strip()]
        for d in recs:
            pq = detect(d["question"], v2=True)
            self.assertEqual(pq.qtype, "essay", d["id"])
            self.assertIn(len(pq.topics), (3, 4, 5), d["id"])


class TestEssayHelpers(unittest.TestCase):
    def test_thesis_and_terms(self):
        t = essay_topics(F2023)[0][1]
        self.assertTrue(essay.thesis_of(t).startswith("Hołd pruski był największym sukcesem"))
        terms = essay.key_terms(t)
        self.assertIn("hold", terms)
        self.assertNotIn("zajmij", terms)
        self.assertEqual(essay.thesis_of("Scharakteryzuj rolę Aten w V w. p.n.e."), "rolę Aten w V w")

    def test_plan_queries(self):
        n, t = essay_topics(F2023)[0]
        p = essay.plan(n, t, F2023)
        names = [q[0] for q in p.queries]
        self.assertEqual(names[:4], ["stem", "item:a1", "item:a2", "item:a3"])
        self.assertIn("ents", names)
        p2 = essay.plan("2", essay_topics(F2015)[1][1], F2015)
        self.assertFalse(p2.needs_materials)  # the materials for topic 2 are in the input
        p3 = essay.plan("2", essay_topics(F2015)[1][1], F2015.split("Materiały źródłowe")[0])
        self.assertTrue(p3.needs_materials)

    def test_coverage_and_choice(self):
        tops = essay_topics(F2023)
        plans = [essay.plan(n, t, F2023) for n, t in tops]
        ctx_good = [{"title": "Hołd pruski", "text": "Hołd pruski złożył Albrecht Hohenzollern w 1525 roku, "
                     "kończąc wojnę; sukces dyplomacji Zygmunta Starego ostatnich Jagiellonów.", "rerank": 3.0}]
        ctx_bad = [{"title": "Kaszanka", "text": "Kaszanka to wyrób wędliniarski.", "rerank": -6.0}]
        for p, c in zip(plans, (ctx_good, ctx_bad, ctx_bad)):
            p.contexts = c
            p.score, p.coverage = essay.coverage(p, c)
        self.assertGreater(plans[0].score, plans[1].score)
        self.assertEqual(essay.choose(plans).n, "1")
        self.assertEqual(essay.choose(plans, forced=3).n, "3")
        for p in plans:
            p.score = 0.5
        self.assertEqual(essay.choose(plans).n, "1")  # tie -> the earlier topic

    def test_clean(self):
        raw = ("**WYPRACOWANIE na temat nr 2**\n\n## Wstęp\nZgadzam się z tezą, że kongres dał pokój. "
               "Pokój w Europie trwał bardzo długo po 1815 roku.\n\nRozwinięcie:\nPokój w Europie trwał bardzo długo po 1815 roku. Święte Przymierze tłumiło rewolucje.\n\n"
               "- Zakończenie jest krótkie i urwane w pół")
        out = essay.clean(raw, "2", truncated=True)
        self.assertTrue(out.startswith("WYPRACOWANIE na temat nr 2\n\n"))
        self.assertEqual(out.count("WYPRACOWANIE"), 1)
        self.assertNotIn("**", out)
        self.assertNotIn("Wstęp", out)
        self.assertEqual(out.count("Pokój w Europie trwał bardzo długo po 1815 roku."), 1)
        self.assertTrue(out.endswith("rewolucje."))
        self.assertEqual(essay.body_words("WYPRACOWANIE na temat nr 2\n\nAla ma kota, a społeczno-gospodarczy"), 5)
        raw2 = ("WYPRACOWANIE na temat nr 1\n\nWYPROCOWAĆ NA TEMA T NR 1\n\nWyprawy krzyżowe zmieniły Europę.\n\n"
                "Zakończenie wynika z rozwinięcia.\n\nDodatkowe argumenty:\n\nPolityczny: coś jeszcze.")
        out2 = essay.clean(raw2, "1")
        # (one-line paragraphs are merged into the next one)
        self.assertEqual(out2, "WYPRACOWANIE na temat nr 1\n\nWyprawy krzyżowe zmieniły Europę. "
                               "Zakończenie wynika z rozwinięcia.")

    def test_near_duplicate_and_parts(self):
        intro = ("W drugiej połowie XIX wieku Polacy w Galicji mieli lepsze warunki niż w pozostałych zaborach. "
                 "Zgadzam się z tą tezą.")
        body = ("W drugiej połowie XIX wieku Polacy w Galicji mieli lepsze warunki niż w pozostałych zaborach, "
                "co wynikało z autonomii. Sejm Krajowy obradował we Lwowie od 1861 roku.")
        end = "Podsumowując, w drugiej połowie XIX wieku Polacy w Galicji mieli lepsze warunki niż w pozostałych zaborach."
        out = essay.clean("\n\n".join([intro, body, body.replace("Sejm", "Rada"), end]), "1")
        self.assertEqual(out.count("co wynikało z autonomii"), 0)  # near-verbatim restart of the intro dropped
        self.assertIn("Sejm Krajowy obradował", out)
        self.assertTrue(out.endswith(end))  # the conclusion may restate the stance
        para = " ".join(f"To jest zdanie {i} części a1 o hołdzie pruskim z 1525 roku." for i in range(8))
        self.assertEqual(essay.clean(para, "1").count("To jest zdanie"), 8)  # similar but distinct sentences stay
        cut = essay.clean_part("Wstęp:\n\nPierwsze zdanie wstępu. Drugie zdanie wstępu. Urwane w pół", "body1")
        self.assertEqual(cut, "Pierwsze zdanie wstępu. Drugie zdanie wstępu.")
        ex = essay.clean("Wstęp jest tutaj i ma dość dużo słów, żeby nie był łączony z kolejnym akapitem tekstu.\n\n"
                         "W Polsce rządzili komuniści przez wiele lat po wojnie.\n\nPrzykład: W 1956 roku była odwilż.", "1")
        self.assertTrue(ex.endswith("po wojnie. W 1956 roku była odwilż."), ex)
        long_intro = " ".join(f"Zdanie numer {i} wstępu." for i in range(9))
        self.assertEqual(len(essay.clean_part(long_intro, "intro").split(". ")), 5)

    def test_instruction(self):
        n, t = essay_topics(F2023)[0]
        ins = essay.instruction(essay.plan(n, t, F2023))
        self.assertIn("WYPRACOWANIE na temat nr 1", ins)
        self.assertIn("polityczny, społeczno-gospodarczy, militarny", ins)
        self.assertIn("450–700", ins)


class _FakeLLM:
    def __init__(self, outs):
        self.outs, self.calls = list(outs), []

    async def chat(self, messages, **kw):
        self.calls.append((messages, kw))
        txt = self.outs.pop(0) if self.outs else "B"
        return {"choices": [{"message": {"content": txt}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    async def lora_zero(self):
        return {"lora": [{"id": 0, "scale": 0.0}]}


class _NoKB:
    available = False


class TestPipelineEssay(unittest.TestCase):
    def _run(self, outs, qtype=None, **over):
        llm = _FakeLLM(outs)
        pipe = Pipeline(Settings(), llm, _NoKB())
        res = asyncio.run(pipe.answer(F2023, qtype=qtype, overrides=over))
        return res, llm

    def test_essay_flow_with_expansion_and_lora_off(self):
        short = "Zgadzam się z tezą. " * 5
        long_ = " ".join(f"Zdanie numer {i} o kongresie wiedeńskim i Świętym Przymierzu." for i in range(80))
        res, llm = self._run([short, long_], qtype_v2=True, use_kb=False, essay_fallback="rewrite")
        self.assertEqual(res.qtype, "essay")
        self.assertEqual(len(llm.calls), 2)  # first draft < ESSAY_MIN_WORDS -> one rewrite call
        msgs, kw = llm.calls[0]
        self.assertEqual(kw["max_tokens"], 1400)
        self.assertEqual(kw["lora"], [{"id": 0, "scale": 0.0}])
        self.assertIn("Temat nr 1:", msgs[1]["content"])  # no KB: first topic with aspects and no materials
        self.assertTrue(res.answer.startswith("WYPRACOWANIE na temat nr "))
        self.assertTrue(res.parsed["essay"]["expanded"])
        self.assertGreater(res.parsed["essay"]["words"], 350)

    def test_sections_fallback(self):
        short = "Zgadzam się z tezą. " * 5
        para = lambda k: " ".join(f"To jest zdanie {i} części {k} o hołdzie pruskim z 1525 roku." for i in range(8))
        outs = [short, "**Wstęp**\n" + para("wstęp"), para("a1"), para("a2"), para("a3"), para("koniec")]
        res, llm = self._run(outs, qtype_v2=True, use_kb=False)  # default ESSAY_FALLBACK=sections
        self.assertEqual(len(llm.calls), 6)  # draft + intro + 3 aspect paragraphs + conclusion
        self.assertEqual([c[1]["max_tokens"] for c in llm.calls], [1400, 400, 700, 700, 700, 400])
        self.assertIn("aspekcie: społeczno-gospodarczy", llm.calls[3][0][1]["content"])
        self.assertIn("Dotychczas napisany tekst wypracowania:", llm.calls[5][0][1]["content"])
        body = res.answer.split("\n\n")
        self.assertEqual(body[0], "WYPRACOWANIE na temat nr 1")
        self.assertEqual(len(body), 6)
        self.assertNotIn("Wstęp", res.answer)
        self.assertEqual(res.parsed["essay"]["expanded"], "sections")

    def test_open_hint_does_not_block_essay(self):
        long_ = " ".join(f"Zdanie numer {i} o hołdzie pruskim i dyplomacji Jagiellonów." for i in range(80))
        res, llm = self._run([long_], qtype="open", qtype_v2=True, use_kb=False)
        self.assertEqual(res.qtype, "essay")
        self.assertEqual(len(llm.calls), 1)

    def test_v2_off_is_not_essay(self):
        res, llm = self._run(["Krótka odpowiedź."], qtype_v2=False, use_kb=False, qtype="essay")
        self.assertNotEqual(res.qtype, "essay")


if __name__ == "__main__":
    unittest.main()
