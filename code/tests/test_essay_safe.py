"""ESSAY_SAFE=1 tests: the stricter date verification (harness/cke_essay.py, synthetic sentences and passages),
the best-of-two topic choice, and the proof that with ESSAY_SAFE off the essay output and every prompt are
byte-identical to the code before the safe mode (golden fixture tests/fixtures/essay_off_golden.json, recorded
from the pre-ESSAY_SAFE code by tests/essay_fakes.py).

All texts are our own wording (no CKE text).
Run:  python -m unittest tests.test_essay_safe -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import cke_essay  # noqa: E402
from harness.config import Settings  # noqa: E402

try:
    import httpx  # noqa: F401
    HAVE_HTTPX = True
except ImportError:  # the flows import harness.llm (httpx); the checker does not
    HAVE_HTTPX = False

PASSAGES = [
    "Kryzys berliński: 27 listopada 1958 Chruszczow wystosował ultimatum wobec mocarstw zachodnich w sprawie "
    "Berlina Zachodniego.",
    "Wojna koreańska rozpoczęła się 25 czerwca 1950 atakiem Korei Północnej na Koreę Południową.",
    "Józef Stalin zmarł w marcu 1953 roku w Moskwie.",
    "Rada Regencyjna 11 listopada 1918 przekazała Józefowi Piłsudskiemu naczelne dowództwo.",
    # the year and the entity in one passage, but far apart (> SAFE_WINDOW characters)
    "Traktat w Rydze podpisano w 1921 roku. " + "Kolejne lata przyniosły spokojny rozwój gospodarki i szkolnictwa. " * 6 +
    "Powstanie śląskie wybuchło później.",
]


def V(sent: str, passages=PASSAGES, fr=None):
    return cke_essay.verify_sentence_safe(sent, cke_essay.safe_index(passages), fr)


class SafeMonths(unittest.TestCase):
    def test_wrong_month_dropped_year_kept(self):
        out, issues, drop = V("W czerwcu 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual(out, "W 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual([i["kind"] for i in issues], ["month"])
        self.assertFalse(drop)

    def test_right_month_kept(self):
        s = "W listopadzie 1958 roku Chruszczow postawił ultimatum w sprawie Berlina."
        self.assertEqual(V(s), (s, [], False))

    def test_wrong_day_dropped_month_kept(self):
        out, issues, _ = V("25 listopada 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual(out, "W listopadzie 1958 roku Chruszczow postawił ultimatum w sprawie Berlina.")
        self.assertEqual([i["kind"] for i in issues], ["day"])
        out, _, _ = V("Wojsko ruszyło. 27 czerwca 1950 roku Korea Północna zaatakowała Koreę Południową.")
        self.assertIn("Wojsko ruszyło. W czerwcu 1950 roku Korea", out)  # capitalised after a sentence end

    def test_roman_months(self):
        s = "11 XI 1918 roku Piłsudski przejął dowództwo."
        self.assertEqual(V(s)[1], [])
        out, issues, _ = V("Dnia 11 XII 1918 roku Piłsudski przejął dowództwo.")
        self.assertEqual(out, "W 1918 roku Piłsudski przejął dowództwo.")
        self.assertEqual(issues[0]["kind"], "month")
        out, _, _ = V("Piłsudski w XII 1918 roku przejął dowództwo.")
        self.assertEqual(out, "Piłsudski w 1918 roku przejął dowództwo.")
        # a ruler's ordinal is not a month
        self.assertEqual(cke_essay._date_mentions("Władca Jan III 1683 roku ruszył pod Wiedeń."), [])

    def test_month_elsewhere_in_passage_does_not_count(self):
        far = ["W 1958 roku zaostrzył się spór o Berlin. " + "Rozmowy trwały bardzo długo i nie przyniosły wyniku. " * 6
               + "W czerwcu odbył się zjazd partii."]
        out, issues, _ = V("W czerwcu 1958 roku zaostrzył się spór o Berlin.", far)
        self.assertEqual(out, "W 1958 roku zaostrzył się spór o Berlin.")
        self.assertEqual(issues[0]["kind"], "month")

    def test_event_name_month_is_not_a_date(self):
        self.assertEqual(cke_essay._date_mentions("Marzec 1968 pokazał słabość władzy."), [])


class SafeYears(unittest.TestCase):
    def test_year_near_entity_supported(self):
        s = "W 1950 roku Korea Północna zaatakowała Koreę Południową."
        self.assertEqual(V(s), (s, [], False))

    def test_year_of_another_event_removed(self):
        # 1953 is in the passages, but only next to Stalin's death, not next to 'powstanie'
        out, issues, drop = V("W 1953 roku wybuchło powstanie węgierskie.")
        self.assertEqual(out, "Wybuchło powstanie węgierskie.")
        self.assertEqual(issues, [{"kind": "year", "year": "1953"}])
        self.assertFalse(drop)  # still concrete: an event noun is left

    def test_year_far_from_entity_unsupported(self):
        out, issues, _ = V("Powstanie śląskie wybuchło w 1921 roku.")
        self.assertEqual(out, "Powstanie śląskie wybuchło.")
        self.assertEqual(issues[0]["kind"], "year")
        self.assertTrue(cke_essay.year_supported("1921", [r"\btrakta"], cke_essay.safe_index(PASSAGES)))

    def test_nothing_concrete_left_is_dropped(self):
        out, issues, drop = V("W 1957 roku sytuacja się zmieniła.")
        self.assertTrue(drop)
        self.assertEqual(issues[0]["kind"], "year")

    def test_numbers_that_are_not_years(self):
        self.assertEqual(cke_essay._years_in("Armia liczyła 300 tysięcy żołnierzy w 1950 roku."), ["1950"])

    def test_sentence_initial_name_counts_only_when_proper(self):
        idx = cke_essay.safe_index(PASSAGES)
        self.assertTrue(any("chrusz" in k for k in cke_essay.content_keys("Chruszczow postawił ultimatum.", idx)))
        self.assertFalse(cke_essay.content_keys("Kolejnym krokiem była nauka.", idx))


class SafeParagraph(unittest.TestCase):
    PAR = ("Kryzys berliński potwierdza tezę. W czerwcu 1958 roku Chruszczow postawił ultimatum w sprawie Berlina. "
           "W 1957 roku sytuacja się zmieniła. W 1950 roku Korea Północna zaatakowała Koreę Południową. "
           "Mocarstwa zachodnie nie ustąpiły. To pokazuje, że zimna wojna była groźna.")

    def test_paragraph_rewrites_drops_and_counts(self):
        idx = cke_essay.safe_index(PASSAGES)
        out, log, n = cke_essay.verify_paragraph_safe(self.PAR, idx)
        self.assertIn("W 1958 roku Chruszczow postawił ultimatum", out)
        self.assertNotIn("1957", out)
        self.assertNotIn("sytuacja się zmieniła", out)
        self.assertIn("W 1950 roku Korea Północna", out)
        self.assertEqual(n, 2)  # one month + one year
        self.assertEqual(sum(1 for x in log if "removed" in x), 1)

    def test_no_drop_mode_and_first_sentence(self):
        idx = cke_essay.safe_index(PASSAGES)
        out, log, n = cke_essay.verify_paragraph_safe("W 1957 roku sytuacja się zmieniła. Zgadzam się z tezą.", idx,
                                                     allow_drop=False)
        self.assertEqual(out, "Sytuacja się zmieniła. Zgadzam się z tezą.")
        self.assertEqual(n, 1)
        # the first sentence is never dropped, only its unsupported year goes
        out, _, _ = cke_essay.verify_paragraph_safe("W 1957 roku sytuacja się zmieniła. A. B. C. D.", idx)
        self.assertTrue(out.startswith("Sytuacja się zmieniła."))

    def test_count_unsupported_offline(self):
        text = "WYPRACOWANIE na temat nr 1\n\n" + self.PAR + "\n\nZgadzam się z tezą."
        st = cke_essay.count_unsupported(text, PASSAGES)
        self.assertEqual(st["unsupported"], 2)
        self.assertEqual(st["kinds"], {"month": 1, "year": 1})
        self.assertEqual(st["words"], cke_essay.body_words(text))

    def test_pick_candidate(self):
        pick = cke_essay.pick_candidate
        self.assertEqual(pick([{"words": 500, "unsupported": 10}, {"words": 480, "unsupported": 4}]), 1)
        self.assertEqual(pick([{"words": 500, "unsupported": 4}, {"words": 500, "unsupported": 4}]), 0)  # tie -> 1st
        self.assertEqual(pick([{"words": 420, "unsupported": 0}, {"words": 600, "unsupported": 9}]), 1)  # < 450 out
        self.assertEqual(pick([{"words": 420, "unsupported": 0}, {"words": 380, "unsupported": 0}]), 0)  # longer
        self.assertEqual(pick([{"words": 500, "unsupported": 3}]), 0)

    def test_old_verifier_untouched(self):
        blob = "Bitwa pod Grunwaldem 1410. Pokój toruński 1411. Unia w Krewie 1385."
        out, log = cke_essay.verify_paragraph("Jagiełło umocnił państwo w 1385 roku. Zwyciężył pod Grunwaldem w 1410 "
                                              "roku. W 1411 roku zawarto pokój. W 1432 roku wydał wymyślony przywilej. "
                                              "To potwierdza tezę.", blob)
        self.assertNotIn("1432", out)
        self.assertEqual(len(log), 1)


class SafeDefaults(unittest.TestCase):
    def test_off_by_default(self):
        old = os.environ.pop("ESSAY_SAFE", None)
        try:
            self.assertFalse(Settings().essay_safe)
        finally:
            if old is not None:
                os.environ["ESSAY_SAFE"] = old


@unittest.skipUnless(HAVE_HTTPX, "httpx not installed (flows import harness.llm)")
class SafeFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import essay_fakes
        cls.ef = essay_fakes
        cls._env = dict(os.environ)
        essay_fakes.clean_env()

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._env)

    def test_off_is_byte_identical_to_pre_safe_code(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "essay_off_golden.json"), encoding="utf-8") as f:
            golden = json.load(f)
        for extra in ({}, {"essay_safe": False}):
            now = json.loads(json.dumps(self.ef.record(extra), ensure_ascii=False))
            for name in golden:
                for key in ("answer", "essay_meta", "calls", "retrieval"):
                    self.assertEqual(now[name][key], golden[name][key], f"{name}/{key} changed with ESSAY_SAFE off")

    def test_safe_best_of_two(self):
        res, llm, _ = self.ef.run_essay({"essay_safe": True})
        m = res.parsed["essay"]
        cands = m["safe"]["candidates"]
        self.assertEqual(len(cands), 2)
        self.assertNotEqual(cands[0]["topic"], cands[1]["topic"])
        self.assertEqual(m["safe"]["chosen"], cke_essay.pick_candidate(cands, Settings().essay_safe_min_words))
        self.assertEqual(m["topic"], m["safe"]["chosen_topic"])
        self.assertTrue(all(isinstance(c["unsupported"], int) for c in cands))
        self.assertEqual(res.llm_calls, sum(c["llm_calls"] for c in cands))
        bodies = [c for c in llm.calls if "Napisz akapit rozwinięcia" in c["messages"][-1]["content"] or
                  "Napisz akapit rozwinięcia" in c["messages"][1]["content"]]
        self.assertTrue(bodies)
        self.assertTrue(all("nigdy miesięcy ani dni" in c["messages"][1]["content"] for c in bodies))
        # the fake writes 'W listopadzie 1956 ... Gomułka' (passages: październik) and 'W 1957 roku ...' (no passage)
        self.assertNotIn("listopadzie 1956", res.answer)
        self.assertNotIn("1957", res.answer)

    def test_safe_forced_topic_single_candidate(self):
        res, _, _ = self.ef.run_essay({"essay_safe": True, "essay_topic": 3})
        m = res.parsed["essay"]
        self.assertEqual([c["topic"] for c in m["safe"]["candidates"]], ["3"])
        self.assertEqual(m["topic"], "3")


if __name__ == "__main__":
    unittest.main()
