"""Harness v4 tests: (1) with every V4 flag off the prompts are byte-identical to v3 (golden fixture recorded from
the pre-v4 code, tests/v3_golden.py); (2) v4 helpers (harness/v4.py); (3) v4 flows with a fake LLM
(harness/v4_flow.py); (4) the devset/eval.py lenient-grading fix.

All item texts are our own wording (no CKE text).  Run:  python -m unittest tests.test_v4 -v
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import v4  # noqa: E402
from harness.config import Settings  # noqa: E402
from harness.qtype import detect_v2  # noqa: E402

try:
    import httpx  # noqa: F401
    HAVE_HTTPX = True
except ImportError:
    HAVE_HTTPX = False

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "v3_prompts.json")


def _settings(**over) -> Settings:
    s = Settings()
    for k, v in over.items():
        setattr(s, k, v)
    return s


# ------------------------------------------------------------------ (1) v3 prompts unchanged
@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (the pipeline imports harness.llm)")
class V3PromptsUnchanged(unittest.TestCase):
    def setUp(self):
        from tests import v3_golden
        self.g = v3_golden
        self.saved = dict(os.environ)
        v3_golden._clean_env()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def _compare(self, extra=None):
        with open(FIXTURE, encoding="utf-8") as f:
            old = json.load(f)
        new = self.g.record(extra)
        for cfg in old:
            for item in old[cfg]:
                self.assertEqual(old[cfg][item], new[cfg][item], f"{cfg}/{item} differs from v3")

    def test_defaults_identical_to_v3(self):
        self._compare()

    def test_explicit_flags_off_identical_to_v3(self):
        off = {k: 0 for k in ("v4_abcd_parts", "v4_continue", "v4_source_first", "v4_title_rescore",
                              "v4_pf_evidence", "v4_pf_value", "v4_neutral_examples", "v4_chrono_bc",
                              "v4_chrono_ties")}
        self._compare({**off, "v4": True, "sc_k": 1})

    def test_v4_changes_prompts(self):
        with open(FIXTURE, encoding="utf-8") as f:
            old = json.load(f)
        new = self.g.record({"v4": True})
        self.assertNotEqual(old["v3_cke"]["abcd_parts"], new["v3_cke"]["abcd_parts"])
        self.assertNotEqual(old["v3_cke"]["match_example"], new["v3_cke"]["match_example"])


class Flags(unittest.TestCase):
    def test_defaults_off(self):
        saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith(("V4", "SC_"))}
        try:
            s = Settings()
            self.assertFalse(s.v4)
            for name in v4.V4_UMBRELLA | {"v4_pf_value", "v4_continue", "v4_source_first", "v4_pf_evidence",
                                          "v4_chrono_bc", "v4_chrono_ties", "v4_abcd_parts", "v4_title_rescore"}:
                self.assertFalse(v4.on(s, name), name)
            self.assertEqual(v4.sc_k(s), 1)
            self.assertEqual(v4.chrono_ties_mode(s), 0)
            self.assertFalse(v4.any_closed(s))
        finally:
            os.environ.update(saved)

    def test_umbrella_and_explicit(self):
        s = _settings(v4=True)
        for name in v4.V4_UMBRELLA:
            self.assertTrue(v4.on(s, name), name)
        s = _settings(v4=True, v4_pf_evidence=0)
        self.assertFalse(v4.on(s, "v4_pf_evidence"))
        s = _settings(v4=False, v4_pf_value=1, sc_k=5)
        self.assertTrue(v4.on(s, "v4_pf_value"))
        self.assertEqual(v4.sc_k(s), 5)

    def test_request_override(self):
        from harness.pipeline import apply_overrides  # noqa: F401 (needs httpx through harness.llm)

    test_request_override = unittest.skipUnless(HAVE_HTTPX, "httpx")(test_request_override)


# ------------------------------------------------------------------ (2) helpers
class Neutral(unittest.TestCase):
    def test_examples_replaced(self):
        n = v4.neutralize_examples
        self.assertEqual(n("Odpowiedz w formacie: 1-B, 2-A, 3-D, 4-C."), "Odpowiedz w formacie: 1-X, 2-X, 3-X, 4-X.")
        self.assertEqual(n("Odpowiedz ciągiem liter, np. B, A, D, C."), "Odpowiedz ciągiem liter, np. X, X, X, X.")
        self.assertEqual(n("Odpowiedz w formacie: P, F, P."), "Odpowiedz w formacie: P/F, P/F, P/F.")
        self.assertEqual(n("Wpisz w formacie: A-3, B-1."), "Wpisz w formacie: A-X, B-X.")

    def test_rest_untouched(self):
        t = "1. Austria\nA. ziemie na wschód od Niemna\nW latach 1618-1624 trwał okres C.\nOdpowiedz w formacie: P/F, P/F."
        self.assertEqual(v4.neutralize_examples(t), t)


class Titles(unittest.TestCase):
    REF = ("Poniżej wymieniono wydarzenia z okresu II wojny punickiej. Dopasuj okres wojny trzydziestoletniej "
           "do lat. Ziemie zajęte w III rozbiorze Polski (1795). Źródło dotyczy konstytucji marcowej.")

    def d(self, title):
        toks, caps = v4.ref_index(self.REF)
        return v4.title_delta(title, toks, caps, 3.0, 4.0)[1]

    def test_exact_and_numerals(self):
        self.assertEqual(self.d("II wojna punicka"), "exact")
        self.assertEqual(self.d("I wojna punicka"), "roman")
        self.assertEqual(self.d("III wojna punicka"), "roman")
        self.assertEqual(self.d("Wojna trzydziestoletnia"), "exact")
        self.assertEqual(self.d("II wojna trzydziestoletnia"), "roman")
        self.assertEqual(self.d("III rozbiór Polski"), "exact")
        self.assertEqual(self.d("Rozbiory Polski"), "roman")
        self.assertEqual(self.d("Konstytucja marcowa"), "exact")
        self.assertEqual(self.d("Konstytucja kwietniowa"), "")
        self.assertEqual(self.d("Polska"), "")  # one-word titles get no bonus

    def test_rescore_order(self):
        hits = {"a": {"title": "II wojna trzydziestoletnia"}, "b": {"title": "Pokój westfalski"},
                "c": {"title": "Wojna trzydziestoletnia"}}
        order, why = v4.title_rescore(["a", "b", "c"], hits, {"a": 2.0, "b": 1.0, "c": 0.5},
                                      "Dopasuj okres wojny trzydziestoletniej do lat.")
        self.assertEqual(order, ["c", "b", "a"])
        self.assertEqual(why, {"a": "roman", "c": "exact"})
        order, _ = v4.title_rescore(["a", "b", "c"], hits, None, "Dopasuj okres wojny trzydziestoletniej do lat.")
        self.assertEqual(order[0], "c")


class PFEvidence(unittest.TestCase):
    CTX = "Pokój w Karłowicach podpisano w 1699 roku, za panowania Augusta II Mocnego; Kamieniec wrócił do Polski."

    def test_parse_and_verify(self):
        q, v = v4.parse_pf_check(" 1699\nCytat: „Pokój w Karłowicach podpisano w 1699 roku, za panowania Augusta II "
                                 "Mocnego”\nOcena: F")
        self.assertTrue(q.startswith("Pokój w Karłowicach"))
        self.assertIs(v, False)
        self.assertTrue(v4.quote_supported(q, self.CTX))
        self.assertFalse(v4.quote_supported("Traktat podpisał Jan III Sobieski w Wiedniu", self.CTX))
        self.assertEqual(v4.parse_pf_check("Cytat: BRAK\nOcena: P"), ("", True))

    def test_decide(self):
        good = "Pokój w Karłowicach podpisano w 1699 roku, za panowania Augusta II"
        self.assertEqual(v4.pf_decide(False, good, False, self.CTX), (False, "F-kept"))
        self.assertEqual(v4.pf_decide(False, "", False, self.CTX)[0], True)            # no quote -> P
        self.assertEqual(v4.pf_decide(False, "zmyślone zdanie o czymś innym", False, self.CTX)[0], True)
        self.assertEqual(v4.pf_decide(True, good, False, self.CTX), (False, "P->F"))
        self.assertEqual(v4.pf_decide(True, "", False, self.CTX), (True, "P-kept"))

    def test_has_value(self):
        self.assertTrue(v4.has_value("Konstytucję uchwalono w 1921 roku."))
        self.assertTrue(v4.has_value("Wprowadzała ostatecznie ustrój prezydencki."))
        self.assertTrue(v4.has_value("Po raz pierwszy zwołano sejm."))
        self.assertFalse(v4.has_value("Parlament składał się z sejmu i senatu."))


class Chrono(unittest.TestCase):
    ITEMS = [("A", "bitwa pod Kannami"), ("B", "zdobycie Syrakuz"), ("C", "bitwa nad Metaurusem"),
             ("D", "kapitulacja Saguntu")]

    def test_bc_from_context(self):
        yrs = {"A": 216, "B": 212, "C": 207, "D": 219}
        ctx = "W 216 p.n.e. pod Kannami. Syrakuzy zdobyto w 212 p.n.e.; Metaurus 207 p.n.e.; Sagunt 219 p.n.e."
        out, log = v4.bc_fix(yrs, {}, self.ITEMS, "Wydarzenia drugiej wojny", ctx)
        self.assertEqual(out, {"A": -216, "B": -212, "C": -207, "D": -219})
        self.assertEqual(sorted(out, key=out.get), ["D", "A", "B", "C"])
        self.assertEqual(len(log), 4)

    def test_bc_signed_or_ad_untouched(self):
        out, _ = v4.bc_fix({"A": 1410, "B": 216}, {"B": True}, [("A", "Grunwald"), ("B", "Kanny")], "", "216 p.n.e.")
        self.assertEqual(out, {"A": 1410, "B": 216})

    def test_grammar_and_signed(self):
        g = v4.grammar_years_bc(self.ITEMS[:2])
        self.assertIn('" p.n.e."?', g)
        self.assertEqual(v4.signed_labels("A: 216 p.n.e.\nB: 212\nC: -207", ["A", "B", "C"]),
                         {"A": True, "B": False, "C": True})

    def test_ties(self):
        self.assertEqual(v4.tie_groups({"A": 1848, "B": 1848, "C": 1849, "D": 1848}, list("ABCD")), [["A", "B", "D"]])
        md = v4.parse_monthday("A: 03-15\nB: 02\nD: ?", ["A", "B", "D"])
        self.assertEqual(md, {"A": (3, 15), "B": (2, None), "D": (None, None)})
        self.assertEqual(v4.order_group(["A", "B"], {"A": (3, 15), "B": (2, None)}, None, ["A", "B"]),
                         (["B", "A"], "monthday"))
        self.assertEqual(v4.order_group(["A", "B", "D"], md, None, ["D", "A", "B"])[1], "direct")
        self.assertEqual(v4.order_group(["A", "B"], None, {"A": 0, "B": 1}, ["A", "B"]), (["B", "A"], "pairwise"))


PARTS = ("Źródło. Fragment rozkazu\nZnoszę nazwę dotychczasowej organizacji. Wszyscy żołnierze w kraju tworzą "
         "odtąd armię podległą Panu Generałowi.\nNACZELNY WÓDZ\nDokończ zdania 1. i 2. Zaznacz właściwą odpowiedź "
         "spośród podanych.\n1. Rozkaz był skierowany do generała\nA. Michała Tokarzewskiego.\nB. Stefana Roweckiego.\n"
         "C. Tadeusza Komorowskiego.\nD. Leopolda Okulickiego.\n2. Rozkaz podpisał generał\nA. Władysław Anders.\n"
         "B. Kazimierz Sosnkowski.\nC. Władysław Sikorski.\nD. Emil Fieldorf.")


class Parts(unittest.TestCase):
    def test_part_questions(self):
        pq = detect_v2(PARTS)
        self.assertEqual(pq.qtype, "abcd_parts")
        q2 = v4.part_question(pq, 1)
        self.assertIn("Dokończ zdanie.", q2)
        self.assertNotIn("zdania 1. i 2.", q2)
        self.assertIn("Rozkaz podpisał generał\nA. Władysław Anders.", q2)
        self.assertNotIn("Tokarzewskiego", q2)
        self.assertIn("NACZELNY WÓDZ", q2)
        sub = detect_v2(q2, "abcd")
        self.assertEqual([l for l, _ in sub.options], list("ABCD"))


# ------------------------------------------------------------------ (3) flows with a fake LLM
class FakeLLM:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    async def lora_zero(self):
        return {}

    async def chat(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        pre = messages[-1]["content"] if messages[-1]["role"] == "assistant" else ""
        rep = self.fn(user, pre, kw)
        if isinstance(rep, str):
            rep = {"choices": [{"message": {"content": rep}, "finish_reason": "stop"}]}
        return rep


class OneDocKB:
    """available KB returning one fixed passage for every query (no reranker)."""
    available = True
    reranker = None

    def __init__(self, text, title="Artykuł"):
        self.text, self.title = text, title
        self.queries = []

    def search(self, q, k):
        self.queries.append(q)
        return [{"title": self.title, "section": "", "text": self.text, "url": "", "score": 1.0}]

    def dense_search(self, q, s):
        return []


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (flows import harness.llm)")
class Flows(unittest.TestCase):
    def run_q(self, text, fn, kb=None, **over):
        from harness.pipeline import Pipeline

        class NoKB:
            available = False
            reranker = None
        s = _settings(cke_mode=True, qtype_v2=True, **over)
        fake = FakeLLM(fn)
        res = asyncio.run(Pipeline(s, fake, kb or NoKB()).answer(text))
        return res, fake

    def test_abcd_parts_split(self):
        def fn(u, pre, kw):
            if "Rozkaz podpisał" in u and "Tokarzewskiego" not in u:
                return " Podpisał Naczelny Wódz.\nOdpowiedź: C"
            if "skierowany do generała" in u and "Anders" not in u:
                return " Adresat to dowódca ZWZ.\nOdpowiedź: B"
            return " ?\nOdpowiedź: 1-D, 2-B"
        res, fake = self.run_q(PARTS, fn, v4_abcd_parts=1)
        self.assertEqual(res.answer, "1-B, 2-C")
        self.assertEqual(res.mode, "cke-parts-v4")
        self.assertEqual(len(fake.calls), 2)
        res3, _ = self.run_q(PARTS, fn)  # v3: one joint call
        self.assertEqual(res3.answer, "1-D, 2-B")

    def test_pf_evidence_flips_unsupported_f(self):
        q = ("Oceń prawdziwość zdań.\n1. Pokój podpisano w 1699 roku.\n2. Pokój podpisał Jan III Sobieski.\n"
             "3. Twierdza wróciła do Polski.")
        kb = OneDocKB("Pokój w Karłowicach podpisano w 1699 roku, za panowania Augusta II Mocnego; twierdza wróciła "
                      "do Polski.")

        def fn(u, pre, kw):
            if pre.startswith("Rozumowanie"):
                return " Sprawdzam.\nOdpowiedź: F, F, P"
            if "stwierdzenie 1:" in u:
                return " 1699\nCytat: BRAK\nOcena: P"
            if "stwierdzenie 2:" in u:
                return " „Pokój w Karłowicach podpisano w 1699 roku, za panowania Augusta II Mocnego”\nOcena: F"
            return "?"
        res, fake = self.run_q(q, fn, kb=kb, v4_pf_evidence=1)
        self.assertEqual(res.answer, "P, F, P")
        checks = [c for c in fake.calls if "Sprawdź stwierdzenie" in c["messages"][1]["content"]]
        self.assertEqual(len(checks), 2)
        self.assertEqual(checks[0]["messages"][-1]["content"], "Wartość w kontekście:")  # '1699' -> value first
        self.assertEqual(res.parsed["cke"]["v4"]["pf_check"][0]["why"], "F->P")

    def test_self_consistency_majority(self):
        q = "Który władca?\nA. Mieszko I\nB. Bolesław Chrobry\nC. Kazimierz Wielki\nD. Jan Olbracht"
        seq = iter(["A", "B", "B", "C", "B"])

        def fn(u, pre, kw):
            return f" rozważam\nOdpowiedź: {next(seq)}"
        res, fake = self.run_q(q, fn, sc_k=5)
        self.assertEqual(res.answer, "B")
        self.assertEqual(len(fake.calls), 5)
        self.assertEqual(fake.calls[0]["temperature"], 0.0)
        self.assertEqual(fake.calls[1]["temperature"], 0.7)

    def test_neutral_match_example(self):
        q = ("Dopasuj państwo do ziem.\n1. Austria\n2. Prusy\n3. Rosja\nA. wschód\nB. Kraków\nC. Warszawa\n"
             "Odpowiedz w formacie: 1-B, 2-A, 3-C.")

        def fn(u, pre, kw):
            return " x\nOdpowiedź: 1-B, 2-C, 3-A"
        res, fake = self.run_q(q, fn, v4_neutral_examples=1)
        user = fake.calls[0]["messages"][1]["content"]
        self.assertIn("Odpowiedz w formacie: 1-X, 2-X, 3-X.", user)
        self.assertIn("Odpowiedź: 1-X, 2-X, 3-X, …", user)
        self.assertNotIn("1-B, 2-A", user)
        self.assertEqual(res.answer, "1-B, 2-C, 3-A")

    def test_source_first_queries(self):
        q = ("Źródło. Napis na medalu\n„Odzyskana twierdza nad Dniestrem wraca do Rzeczypospolitej”.\n"
             "Oceń prawdziwość poniższych stwierdzeń. Napisz P, jeśli stwierdzenie jest prawdziwe, albo F – jeśli "
             "jest fałszywe.\n1. Traktat podpisano za panowania Jana III Sobieskiego.\n"
             "2. Traktat kończył wojny z Portą.")
        kb = OneDocKB("Pokój w Karłowicach 1699 zwrócił Kamieniec Podolski.")

        def fn(u, pre, kw):
            if pre == "Kto:":
                return " August II\nCo: pokój w Karłowicach\nKiedy: 1699\nGdzie: Kamieniec Podolski"
            return " x\nOdpowiedź: F, P"
        res, fake = self.run_q(q, fn, kb=kb, v4_source_first=1)
        self.assertEqual(res.answer, "F, P")
        self.assertIn("pokój w Karłowicach 1699", " | ".join(kb.queries).replace("August II ", ""))
        self.assertFalse(any("Sobieskiego" in x for x in kb.queries), kb.queries)
        self.assertIn("Karłowicach", res.parsed["cke"]["v4"]["ident"])

    def test_chrono_bc_and_ties(self):
        q = ("Uporządkuj chronologicznie wydarzenia.\nA. bitwa pod Kannami\nB. zdobycie Syrakuz\n"
             "C. bitwa nad Metaurusem\nD. kapitulacja Saguntu\nOdpowiedz ciągiem liter, np. B, A, D, C.")

        def fn(u, pre, kw):
            g = kw.get("grammar") or ""
            if "Y ::=" in g:
                self.assertIn("p.n.e.", g)
                return "A: 216 p.n.e.\nB: 212\nC: 212\nD: 219 p.n.e."
            if "MM-DD" in u:
                return "B: ?\nC: ?"
            if "nastąpiło wcześniej" in u:
                return "C"
            return "D, A, B, C"
        kb = OneDocKB("Syrakuzy zdobyto w 212 p.n.e.; Metaurus 207 p.n.e. (w tekście błąd: 212 p.n.e.).")
        res, fake = self.run_q(q, fn, kb=kb, v4_chrono_bc=1, v4_chrono_ties=1, v4_neutral_examples=1)
        self.assertEqual(res.answer, "D, A, C, B")
        self.assertIn("np. X, X, X, X", fake.calls[0]["messages"][1]["content"])
        self.assertEqual(res.parsed["v4_chrono"]["ties"][0]["how"], "pairwise")


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (flows import harness.llm)")
class ContinueFlow(unittest.TestCase):
    def test_cut_reasoning_is_continued(self):
        from harness.pipeline import Pipeline

        class NoKB:
            available = False
            reranker = None
        q = "Który władca?\nA. Mieszko I\nB. Bolesław Chrobry\nC. Kazimierz Wielki\nD. Jan Olbracht"

        def fn(u, pre, kw):
            if pre.endswith("Odpowiedź:"):
                return " C"
            if kw.get("grammar"):
                return "A"
            return " A odpada. B odpada. C – pasuje, bo **"
        fake = FakeLLM(fn)
        res = asyncio.run(Pipeline(_settings(cke_mode=True, qtype_v2=True, v4_continue=1), fake, NoKB()).answer(q))
        self.assertEqual(res.answer, "C")
        self.assertTrue(fake.calls[-1]["messages"][-1]["content"].endswith("C – pasuje, bo\n\nOdpowiedź:"))
        fake3 = FakeLLM(fn)  # v3: grammar retry
        res3 = asyncio.run(Pipeline(_settings(cke_mode=True, qtype_v2=True), fake3, NoKB()).answer(q))
        self.assertEqual(res3.answer, "A")


# ------------------------------------------------------------------ (4) devset/eval.py lenient fix
class EvalLenient(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "devset"))
        import importlib
        try:
            self.ev = importlib.import_module("eval")
        except ImportError as e:  # httpx missing
            self.skipTest(str(e))

    def test_nie_not_accepted_for_tak(self):
        item = {"type": "open", "answer": "Tak", "accept": ["Rozstrzygnięcie: Tak"]}
        for pred in ("Nie", "Rozstrzygnięcie: Nie\nUzasadnienie: tak jak w źródle 1.", "Nie, ponieważ tak nie było."):
            g = self.ev.grade(item, pred)
            self.assertFalse(g["lenient"], pred)
            self.assertFalse(g["strict"], pred)
        self.assertTrue(self.ev.grade(item, "Tak")["strict"])
        self.assertTrue(self.ev.grade(item, "Rozstrzygnięcie: Tak\nUzasadnienie: źródło 1.")["lenient"])

    def test_substring_needs_whole_word(self):
        item = {"type": "open", "answer": "Stefan Batory", "accept": []}
        self.assertTrue(self.ev.grade(item, "Batory")["lenient"])
        self.assertFalse(self.ev.grade(item, "fan")["lenient"])
        self.assertTrue(self.ev.grade(item, "Odpowiedź: król Stefan Batory")["lenient"])


if __name__ == "__main__":
    unittest.main()
