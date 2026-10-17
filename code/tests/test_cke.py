"""CKE_MODE (harness v3) tests: detection / parsing helpers (harness/cke.py, harness/cke_essay.py) and the
answer flows with a fake LLM (harness/cke_flow.py; skipped when httpx is not installed).

All item texts below are our own wording in the CKE layout (no CKE text is embedded).
Run:  python -m unittest tests.test_cke -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import cke, cke_essay  # noqa: E402
from harness.config import Settings  # noqa: E402
from harness.qtype import ParsedQuestion, detect_v2  # noqa: E402

try:
    import httpx  # noqa: F401
    HAVE_HTTPX = True
except ImportError:  # the flows import harness.llm (httpx); pure helpers do not
    HAVE_HTTPX = False

DECIDE = """Źródło 1. Fragment kroniki
W roku tym książę zwołał wiec do Gniezna i ogłosił nowe prawa dla rycerstwa.
Na podstawie: Kronika, Warszawa 1990, s. 10.
Źródło 2. Fragment opracowania
Reforma sądów przeprowadzona przez radę miejską przeniosła sprawy karne do nowego trybunału,
co ograniczyło dawne kompetencje wiecu.
Na podstawie: A. Autor, Dzieje, Kraków 2001, s. 5.
Rozstrzygnij, czy wydarzenia opisane w źródle 1. miały miejsce przed reformą opisaną
w źródle 2. czy po niej. Odpowiedź uzasadnij, odwołując się do treści obu źródeł.
Rozstrzygnięcie:
Uzasadnienie:"""

NAMES = """Źródło 1. Lista władców
Mieszko II, Kazimierz Odnowiciel, Bolesław Śmiały.
Źródło 2. Fragmenty opracowań
Fragment A:
Władca odbudował państwo po najeździe i przeniósł główny ośrodek władzy do Krakowa, co umocniło kraj.
Fragment B:
Władca koronował się w Gnieźnie, a potem popadł w konflikt z biskupem krakowskim i musiał uchodzić z kraju.
Każdemu wydarzeniu opisanemu we fragmentach A–B (źródło 2.) przyporządkuj
władcę ze źródła 1., który był związany z tym wydarzeniem. Odpowiedzi zapisz poniżej.
Fragment A –
Fragment B –"""


def pq_of(text: str) -> ParsedQuestion:
    return detect_v2(text)


class Labels(unittest.TestCase):
    def test_colon_and_dash_labels(self):
        self.assertEqual(cke.sheet_labels("Podaj imiona.\nWystawca:\nZasadźca:"),
                         [("Wystawca", ": "), ("Zasadźca", ": ")])
        self.assertEqual([l for l, _ in cke.sheet_labels("Podaj nazwy stylów.\nNazwa stylu 1.:\nCecha:\n"
                                                         "Nazwa stylu 2.:\nCecha:")],
                         ["Nazwa stylu 1.", "Cecha", "Nazwa stylu 2.", "Cecha"])
        self.assertEqual(cke.sheet_labels("Podaj nazwy dynastii.\nFragment A –\nFragment B –"),
                         [("Fragment A", " – "), ("Fragment B", " – ")])
        self.assertEqual(cke.sheet_labels("Wyjaśnij, dlaczego upadło powstanie."), [])

    def test_names_task(self):
        pq = pq_of(NAMES)
        self.assertEqual([l for l, _ in cke.names_task(pq)], ["Fragment A", "Fragment B"])
        code = pq_of("Tekst 1: a\nTekst 2: b\nObok opisu wpisz numer fragmentu.\nA. opis jeden\nB. opis dwa")
        self.assertEqual(cke.names_task(code), [])
        rows = pq_of("Uzupełnij tabelę – wpisz obok każdego z opisów nazwę zakonu.\n"
                     "Opis zakonu A: zakon żebrzący założony we Włoszech.\nOpis zakonu B: zakon założony w Paryżu.")
        self.assertEqual([l for l, _ in cke.names_task(rows)], ["Opis zakonu A", "Opis zakonu B"])
        dec = pq_of(DECIDE)
        self.assertEqual(cke.names_task(dec), [])

    def test_parse_and_render_labeled_one_line(self):
        labs = [("Fragment A", " – "), ("Fragment B", " – ")]
        out = "Fragment A dotyczy odbudowy.\nOdpowiedź: Fragment A – Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały"
        tr = cke.parse_labeled(cke.final_region(out), labs)
        self.assertEqual(cke.render_labeled(tr), "Fragment A – Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały")
        tr = cke.parse_labeled("A – Kazimierz Odnowiciel\nB – Bolesław Śmiały", labs)
        self.assertEqual([v for _, _, v in tr], ["Kazimierz Odnowiciel", "Bolesław Śmiały"])
        rep = [("Nazwa stylu 1.", ": "), ("Cecha", ": "), ("Nazwa stylu 2.", ": "), ("Cecha", ": ")]
        tr = cke.parse_labeled("Nazwa stylu 1.: gotyk\nCecha: ostrołuk\nNazwa stylu 2.: barok\nCecha: hełm wieży", rep)
        self.assertEqual([v for _, _, v in tr], ["gotyk", "ostrołuk", "barok", "hełm wieży"])
        # inflected label ('Nazwę'), no period, bold values, an appended section after the last label
        tr = cke.parse_labeled("Nazwę stylu 1: **gotyk**\nCecha: ostrołuk\n\nNazwę stylu 2.: barok\nCecha: hełm\n\n"
                               "Fakty historyczne:\n- gotyk od XIII w.", rep)
        self.assertEqual([v for _, _, v in tr], ["gotyk", "ostrołuk", "barok", "hełm"])

    def test_render_explain_labels_and_prose(self):
        labs = [("Podobieństwo", ": "), ("Różnica", ": ")]
        out = "**Podobieństwo:** oba źródła chwalą króla.\n\nRóżnica:\n1. źródło 1 mówi o wojnie,\n2. źródło 2 o prawie."
        r = cke.render_explain_cke(out, labs)
        self.assertTrue(r.startswith("Podobieństwo: oba źródła chwalą króla."))
        self.assertIn("\nRóżnica: źródło 1 mówi o wojnie, źródło 2 o prawie.", r)
        self.assertEqual(cke.flatten_prose("Powody:\n- pierwszy\n- drugi."), "Powody: pierwszy drugi.")


class FinalAnswer(unittest.TestCase):
    def test_last_explicit_answer(self):
        t = "Odpowiedź A odpada, bo... Odpowiedź: B jest zła.\nZatem:\n**Odpowiedź:** C"
        self.assertEqual(cke.final_region(t), "C")
        self.assertEqual(cke.final_region("Rozumowanie.\nOstatecznie wybieram D"), "Ostatecznie wybieram D")
        self.assertEqual(cke.reasoning_part("Myślę.\nOdpowiedź: A"), "Myślę.")

    def test_closed_instruction_asks_reasoning_then_final_line(self):
        pq = pq_of("Dokończ zdanie. Zaznacz właściwą odpowiedź spośród podanych.\nPokój zawarto w\n"
                   "A. Toruniu.\nB. Kaliszu.\nC. Krakowie.\nD. Gnieźnie.")
        self.assertEqual(pq.qtype, "abcd")
        ins = cke.closed_instruction(pq)
        self.assertIn("rozumuj", ins)
        self.assertTrue(ins.rstrip().splitlines()[-1].startswith("Odpowiedź:"))


class Decisions(unittest.TestCase):
    def dv(self, cmd):
        d = cke.decision_variants(cmd)
        return d["kind"], [x for _, x in d["variants"]]

    def test_variants(self):
        self.assertEqual(self.dv(DECIDE.split("Rozstrzygnij", 1)[1].join(["Rozstrzygnij", ""])),
                         ("choice", ["przed reformą", "po reformie"]))
        self.assertEqual(self.dv("Rozstrzygnij, na którym z planów ukazanych w źródle 1. (A czy B) przedstawiono "
                                 "bitwę. Odpowiedź uzasadnij."), ("choice", ["Plan A", "Plan B"]))
        self.assertEqual(self.dv("Rozstrzygnij, w którym źródle – 1. czy 2. – opisano reformę. Odpowiedź uzasadnij."),
                         ("choice", ["Źródło 1", "Źródło 2"]))
        self.assertEqual(self.dv("Rozstrzygnij, który z fragmentów 1–3 zawiera opis Sparty. Odpowiedź uzasadnij."),
                         ("choice", ["Fragment 1", "Fragment 2", "Fragment 3"]))
        self.assertEqual(self.dv("Rozstrzygnij, o którym władcy – Mieszku czy Bolesławie – jest mowa w tekście."),
                         ("choice", ["Mieszku", "Bolesławie"]))
        self.assertEqual(self.dv("Rozstrzygnij, czy rzeźba ukazana w źródle 2. jest przykładem baroku czy "
                                 "klasycyzmu. Odpowiedź uzasadnij."), ("choice", ["baroku", "klasycyzmu"]))
        self.assertEqual(self.dv("Rozstrzygnij, czy decyzję podjęła strona zwolenników czy strona przeciwników "
                                 "reformy. Odpowiedź uzasadnij."),
                         ("choice", ["strona zwolenników", "strona przeciwników reformy"]))
        self.assertEqual(self.dv("Rozstrzygnij, czy źródła 1. i 2. dotyczą tego samego zaboru. Odpowiedź uzasadnij."),
                         ("yesno", ["Tak", "Nie"]))

    def test_match_variant(self):
        d = cke.decision_variants("Rozstrzygnij, w którym fragmencie – A czy B – opisano bitwę.")
        self.assertEqual(cke.match_variant("Fragment B, ponieważ...", d), 1)
        d = cke.decision_variants("Rozstrzygnij, czy decyzję podjęła strona zwolenników czy strona przeciwników reformy.")
        self.assertEqual(cke.match_variant("przeciwników reformy", d), 1)
        self.assertEqual(cke.match_variant("Strona zwolenników reformy", d), 0)
        d = cke.decision_variants("Rozstrzygnij, czy rekonstrukcja dotyczy epoki paleolitu czy neolitu.")
        self.assertEqual(cke.match_variant("Neolit", d), 1)
        d = cke.decision_variants("Rozstrzygnij, czy źródła dotyczą tego samego zaboru.")
        self.assertEqual(cke.match_variant("Nie, ponieważ", d), 1)
        self.assertIsNone(cke.match_variant("To zależy", d))

    def test_sources_and_citations(self):
        pq = pq_of(DECIDE)
        units = cke.split_sources(pq.sources)
        self.assertEqual([u for u, _ in units], ["Źródło 1", "Źródło 2"])
        self.assertEqual([c for c, _ in cke.cited_sources(pq.command, units)], ["Źródło 1", "Źródło 2"])
        pq = pq_of(NAMES)
        units = cke.split_sources(pq.sources)
        self.assertEqual([u for u, _ in units], ["Źródło 1", "Fragment A", "Fragment B"])
        cited = cke.cited_sources("Rozstrzygnij, o kim jest mowa we fragmencie B ze źródła 2.", units)
        self.assertEqual([c for c, _ in cited], ["Fragment B"])

    def test_fix_wrapped_command(self):
        text = ("Fragment 1.: tekst o Atenach i ich flocie wojennej oraz o murach długich w Pireusie.\n"
                "Fragment 2.: tekst o Sparcie i jej wychowaniu młodzieży oraz o surowych obyczajach.\n"
                "Rozstrzygnij, który z fragmentów 1–2 zawiera opis Sparty. Odpowiedź\n"
                "uzasadnij, odwołując się do informacji z tego fragmentu.\nRozstrzygnięcie:\nUzasadnienie:")
        pq = pq_of(text)
        src, cmd = cke.fix_command(pq)
        self.assertTrue(cmd.startswith("Rozstrzygnij"))
        self.assertEqual([x for _, x in cke.decision_variants(cmd)["variants"]], ["Fragment 1", "Fragment 2"])

    def test_granularity(self):
        self.assertIn("państwa", cke.granularity_hint("Podaj nazwę państwa, w którego stolicy..."))
        self.assertIn("przydomek", cke.granularity_hint("Podaj imię i przydomek polityka."))


class Essay(unittest.TestCase):
    def test_time_frame(self):
        self.assertEqual(cke_essay.time_frame("Zimna wojna osiągnęła apogeum w latach 50. XX wieku."), (1950, 1959))
        self.assertEqual(cke_essay.time_frame("W okresie XI–XII wieku dominowały tendencje..."), (1001, 1200))
        self.assertEqual(cke_essay.time_frame("Lata 1871–1914 są niesłusznie nazywane..."), (1871, 1914))
        self.assertEqual(cke_essay.time_frame("Rok 1956 był przełomem."), (1956, 1956))
        self.assertEqual(cke_essay.time_frame("Rewolucje z końca XVIII wieku miały podobne przyczyny."), (1770, 1800))
        self.assertIsNone(cke_essay.time_frame("Władysław Jagiełło był najwybitniejszym władcą."))

    def test_superlative_and_kind(self):
        self.assertTrue(cke_essay.superlative("Jagiełło był najwybitniejszym władcą Polski"))
        self.assertFalse(cke_essay.superlative("Rok 1956 był przełomem"))
        self.assertEqual(cke_essay.element_kind("... uwzględniając w swojej argumentacji panowanie trzech wybranych "
                                                "władców z tego okresu."), ("władca", "władców", 3))
        self.assertEqual(cke_essay.element_kind("... charakteryzując trzy wybrane wydarzenia z tego okresu.")[0],
                         "wydarzenie")

    def test_parse_plan_respects_frame(self):
        els, alt = cke_essay.parse_plan("1. Wojna koreańska (1950–1953)\n2. Kryzys kubański (1962)\n"
                                        "3. Powstanie węgierskie (1956)\n4. Kryzys berliński (1948)\nAlternatywa: brak",
                                        3, (1950, 1959))
        self.assertEqual([e for e, _ in els], ["Wojna koreańska (1950–1953)", "Powstanie węgierskie (1956)"])
        self.assertEqual(alt, "brak")

    def test_verify_removes_unsupported_dates_keeps_coherence(self):
        blob = "Bitwa pod Grunwaldem 1410. Pokój toruński 1411. Unia w Krewie 1385."
        par = ("Jagiełło umocnił państwo w 1385 roku. Zwyciężył pod Grunwaldem w 1410 roku. W 1411 roku zawarto pokój. "
               "W 1432 roku wydał wymyślony przywilej. To potwierdza tezę.")
        out, log = cke_essay.verify_paragraph(par, blob)
        self.assertNotIn("1432", out)
        self.assertIn("1410", out)
        self.assertEqual(len(log), 1)
        # the first sentence is never dropped - only its unsupported date goes
        out, log = cke_essay.verify_paragraph("Król w 1399 roku zreformował skarb. Zwyciężył w 1410 roku. "
                                              "To wzmocniło państwo.", blob)
        self.assertTrue(out.startswith("Król zreformował skarb."))

    def test_out_of_frame_sentence(self):
        blob = "1962 kryzys kubański 1956 powstanie"
        iss = cke_essay.sentence_issues("W 1962 roku wybuchł kryzys kubański.", blob, cke.norm(blob), (1950, 1959))
        self.assertTrue(iss["flag"])

    def test_stance_alt_prefill(self):
        intro, added = cke_essay.ensure_stance("Temat wymaga rozważenia.", "Rok 1956 był przełomem w systemie.")
        self.assertTrue(added)
        self.assertTrue(intro.endswith("Zgadzam się z tezą, że rok 1956 był przełomem w systemie."))
        intro, added = cke_essay.ensure_stance("Wstęp. Nie zgadzam się z tezą, że X.", "X")
        self.assertFalse(added)
        self.assertEqual(cke_essay.stance_sentence(intro), "Nie zgadzam się z tezą, że X.")
        self.assertEqual(cke_essay.parse_alt("Alternatywa: Kazimierz Jagiellończyk\ncoś", "Jagiełło był..."),
                         "Kazimierz Jagiellończyk")
        self.assertEqual(cke_essay.parse_alt("Alternatywa: Władysław Jagiełło", "Władysław Jagiełło był..."), "")
        self.assertEqual(cke_essay.aspect_prefill("społeczno-gospodarczy"), "W aspekcie społeczno-gospodarczym")

    def test_header_and_prompt_copy(self):
        topic = ("Władysław Jagiełło był najwybitniejszym władcą Polski z dynastii Jagiellonów. Zajmij stanowisko "
                 "wobec powyższej tezy i je uzasadnij, uwzględniając w swojej argumentacji aspekty: militarny i ustrojowy.")
        txt = ("WYPRACOWANIE na temat nr 1\n\nWYPROCOWANIE na temat nr 1\n\nWładca Jagiełło był najwybitniejszym "
               "władcą Polski z dynastii Jagiellonów. Zajmij stanowisko wobec powyższej tezy i je uzasadnij.\n\n"
               "Zgadzam się z tezą, że Jagiełło był wybitnym władcą.")
        lines = cke_essay.clean_header_lines(txt)
        self.assertNotIn("WYPROCOWANIE", lines)
        body = [cke_essay.strip_prompt_copy(p, topic) for p in lines.split("\n\n") if p.strip()]
        final = cke_essay.assemble("1", body)
        self.assertEqual(final.count("na temat nr"), 1)
        self.assertNotIn("Zajmij stanowisko", final)
        self.assertTrue(final.endswith("Zgadzam się z tezą, że Jagiełło był wybitnym władcą."))


class Defaults(unittest.TestCase):
    def test_cke_mode_off_by_default(self):
        old = os.environ.pop("CKE_MODE", None)
        try:
            self.assertFalse(Settings().cke_mode)
        finally:
            if old is not None:
                os.environ["CKE_MODE"] = old


# ------------------------------------------------------------------ flows with a fake LLM
class FakeLLM:
    def __init__(self, replies):
        self.replies = replies  # list of (predicate(messages, body) -> bool, reply dict or str)
        self.calls = []
        self._lora_ids = [0]

    async def lora_zero(self):
        return {"lora": [{"id": 0, "scale": 0.0}]}

    async def chat(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")  # skip an assistant prefill
        for pred, rep in self.replies:
            if pred(user, kw):
                if callable(rep):
                    rep = rep(user, kw)
                if isinstance(rep, str):
                    rep = {"choices": [{"message": {"content": rep}, "finish_reason": "stop"}]}
                return rep
        return {"choices": [{"message": {"content": "Odpowiedź: A"}, "finish_reason": "stop"}]}


class NoKB:
    available = False
    reranker = None


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (flows import harness.llm)")
class Flows(unittest.TestCase):
    def run_q(self, text, replies, **over):
        from harness.pipeline import Pipeline
        s = Settings()
        s.cke_mode = True
        s.qtype_v2 = True
        for k, v in over.items():
            setattr(s, k, v)
        fake = FakeLLM(replies)
        pipe = Pipeline(s, fake, NoKB())
        res = asyncio.run(pipe.answer(text))
        return res, fake

    def test_closed_reasoning_then_last_answer(self):
        q = ("Dokończ zdanie. Zaznacz właściwą odpowiedź spośród podanych.\nPokój zawarto w\n"
             "A. Toruniu.\nB. Kaliszu.\nC. Krakowie.\nD. Gnieźnie.")
        res, fake = self.run_q(q, [(lambda u, kw: True, "Źródło mówi o 1466 r., więc A? Nie, B.\nOdpowiedź: B")])
        self.assertEqual(res.answer, "B")
        self.assertIsNone(fake.calls[0].get("grammar"))
        self.assertEqual(fake.calls[0]["lora"], [{"id": 0, "scale": 0.0}])
        self.assertIsNone(fake.calls[0].get("stop"))

    def test_pf_multi_part_one_line(self):
        q = ("Oceń prawdziwość poniższych stwierdzeń. Zaznacz P, jeśli stwierdzenie jest prawdziwe, albo F – jeśli "
             "jest fałszywe.\n1. Pokój zawarto w Toruniu.\n2. Wojna trwała trzynaście lat.")
        res, _ = self.run_q(q, [(lambda u, kw: True, "1. Tak, w Toruniu.\n2. Wojna trwała 13 lat.\nOdpowiedź: P, P")])
        self.assertEqual(res.answer, "P, P")

    def test_names_flow(self):
        res, fake = self.run_q(NAMES, [(lambda u, kw: True,
                                        "Fragment A to odbudowa państwa, fragment B – konflikt z biskupem.\n"
                                        "Odpowiedź: Fragment A – Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały")])
        self.assertEqual(res.answer, "Fragment A – Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały")
        self.assertEqual(res.mode, "cke-names")

    def test_names_flow_completes_cut_answer(self):
        replies = [(lambda u, kw: "tylko ostateczną odpowiedź" in u, " Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały"),
                   (lambda u, kw: True, "Fragment A: odbudowa...\nOdpowiedź:\n- Fragment A – Kazimierz Odnowiciel\n"
                                        "Fragment B: konflikt z biskupem, bo")]
        res, fake = self.run_q(NAMES, replies)
        self.assertEqual(res.answer, "Fragment A – Kazimierz Odnowiciel; Fragment B – Bolesław Śmiały")
        self.assertEqual(fake.calls[-1]["messages"][-1],
                         {"role": "assistant", "content": "Odpowiedź: Fragment A –"})

    def test_decision_flow_debias_and_variant(self):
        def decide(u, kw):
            return {"choices": [{"message": {"content": "po reformie"}, "finish_reason": "stop"}]}
        replies = [
            (lambda u, kw: "czterech krótkich liniach" in u, "Kto: książę\nCo: wiec\nKiedy: XII w.\nGdzie: Gniezno"),
            (lambda u, kw: "porównania" in u and "Odpowiedź:" in u, "Źródło 1 jest późniejsze.\nOdpowiedź: po reformie"),
            (lambda u, kw: kw.get("grammar"), decide),
            (lambda u, kw: "Rozstrzygnięcie jest już ustalone" in u,
             "Uzasadnienie: Źródło 1 wspomina „nowe prawa”, a źródło 2 opisuje reformę sądów."),
        ]
        res, fake = self.run_q(DECIDE, replies, cke_decide_mode="compare")
        self.assertTrue(res.answer.startswith("Rozstrzygnięcie: po reformie\nUzasadnienie: Źródło 1 wspomina"),
                        res.answer)
        self.assertNotIn("Tak", res.answer.split("\n")[0])
        who = [c for c in fake.calls if "czterech krótkich" in c["messages"][1]["content"]]
        self.assertEqual(len(who), 2)
        self.assertEqual(who[0]["messages"][-1], {"role": "assistant", "content": "Kto:"})  # format prefilled

    def test_yesno_threshold(self):
        q = ("Źródło 1. Tekst\nOpis wydarzeń w zaborze pruskim, w tym strajk dzieci we Wrześni w roku 1901.\n"
             "Źródło 2. Tekst\nOpis wydarzeń w zaborze rosyjskim, w tym rewolucja w Łodzi w roku 1905 i jej skutki.\n"
             "Rozstrzygnij, czy źródła 1. i 2. dotyczą tego samego zaboru. Odpowiedź uzasadnij, odwołując się do obu "
             "źródeł.\nRozstrzygnięcie:\nUzasadnienie:")

        def decide(u, kw):  # the model leans 'Tak' (0.6) - below the 0.7 threshold -> 'Nie'
            return {"choices": [{"message": {"content": "Tak"}, "finish_reason": "stop",
                                 "logprobs": {"content": [{"token": "Tak", "logprob": -0.51,
                                                           "top_logprobs": [{"token": "Tak", "logprob": -0.51},
                                                                            {"token": "Nie", "logprob": -0.92}]}]}}]}
        replies = [(lambda u, kw: "czterech krótkich liniach" in u, "Kto: -\nCo: -\nKiedy: -\nGdzie: -"),
                   (lambda u, kw: kw.get("grammar"), decide),
                   (lambda u, kw: "porównania" in u, "Oba o zaborach.\nOdpowiedź: Tak"),
                   (lambda u, kw: "ustalone" in u, "Źródło 1 dotyczy Wrześni (zabór pruski), źródło 2 Łodzi.")]
        res, _ = self.run_q(q, replies, cke_decide_mode="compare")
        self.assertTrue(res.answer.startswith("Rozstrzygnięcie: Nie"), res.answer)
        self.assertAlmostEqual(res.parsed["cke"]["decision"]["p_tak"], 0.601, places=2)

    def test_decision_summaries_one_call(self):
        replies = [(lambda u, kw: "czterech krótkich liniach" in u, "Kto: książę\nCo: wiec\nKiedy: XII w.\nGdzie: Gniezno"),
                   (lambda u, kw: "Format odpowiedzi" in u,
                    " po reformie\nUzasadnienie: Źródło 1 wspomina „nowe prawa”, źródło 2 reformę sądów.")]
        res, fake = self.run_q(DECIDE, replies)  # default CKE_DECIDE_MODE=summaries
        self.assertEqual(res.answer, "Rozstrzygnięcie: po reformie\nUzasadnienie: Źródło 1 wspomina „nowe prawa”, "
                                     "źródło 2 reformę sądów.")
        self.assertEqual(fake.calls[-1]["messages"][-1], {"role": "assistant", "content": "Rozstrzygnięcie:"})

    def test_decision_summaries_yesno_flip_rewrites(self):
        q = ("Źródło 1. Tekst\nOpis wydarzeń w zaborze pruskim, w tym strajk dzieci we Wrześni w roku 1901.\n"
             "Źródło 2. Tekst\nOpis wydarzeń w zaborze rosyjskim, w tym rewolucja w Łodzi w roku 1905 i jej skutki.\n"
             "Rozstrzygnij, czy źródła 1. i 2. dotyczą tego samego zaboru. Odpowiedź uzasadnij, odwołując się do obu "
             "źródeł.\nRozstrzygnięcie:\nUzasadnienie:")

        def first(u, kw):
            if kw.get("logprobs"):
                return {"choices": [{"message": {"content": " Tak\nUzasadnienie: oba o zaborach."}, "finish_reason": "stop",
                                     "logprobs": {"content": [{"token": " Tak", "logprob": -0.51,
                                                               "top_logprobs": [{"token": " Tak", "logprob": -0.51},
                                                                                {"token": " Nie", "logprob": -0.92}]}]}}]}
            return " Września to zabór pruski, Łódź – rosyjski."
        replies = [(lambda u, kw: "czterech krótkich liniach" in u, "Kto: -\nCo: -\nKiedy: -\nGdzie: -"),
                   (lambda u, kw: "Format odpowiedzi" in u, first)]
        res, fake = self.run_q(q, replies)
        self.assertEqual(res.answer, "Rozstrzygnięcie: Nie\nUzasadnienie: Września to zabór pruski, Łódź – rosyjski.")
        self.assertEqual(fake.calls[-1]["messages"][-1]["content"], "Rozstrzygnięcie: Nie\nUzasadnienie:")

    def test_default_path_untouched_when_off(self):
        from harness.pipeline import Pipeline
        s = Settings()
        s.cke_mode = False
        fake = FakeLLM([(lambda u, kw: True, "C")])
        pipe = Pipeline(s, fake, NoKB())
        res = asyncio.run(pipe.answer("Który król?\nA. x\nB. y\nC. z\nD. w"))
        self.assertEqual(res.answer, "C")
        self.assertIsNotNone(fake.calls[0].get("grammar"))
        self.assertNotIn("lora", fake.calls[0])


if __name__ == "__main__":
    unittest.main()
