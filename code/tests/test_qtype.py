"""Question-type detection tests (harness/qtype.py), v1 regression + v2 fixes.

Real item texts are loaded at runtime from devset/*.jsonl by id. CKE items live only in the git-ignored
devset/cke-*.jsonl (copyrighted) and those tests are skipped when the files are absent; no CKE text is
embedded here. Synthetic cases below are our own wording that mimics the CKE layout.

Run:  python -m unittest tests.test_qtype -v      (or: python -m pytest tests/test_qtype.py)
"""
from __future__ import annotations

import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness import formats, prompts  # noqa: E402
from harness.config import Settings  # noqa: E402
from harness.pipeline import _max_tokens, needs_rewrite, parse_rewrite  # noqa: E402
from harness.postprocess import parse_pairs  # noqa: E402
from harness.qtype import detect, split_command  # noqa: E402

DEV = os.path.join(ROOT, "devset")


def _load(pattern: str) -> dict:
    out = {}
    for f in sorted(glob.glob(os.path.join(DEV, pattern))):
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    d = json.loads(ln)
                    out[d["id"]] = d
    return out


DEV_ITEMS = _load("dev-[a-h].jsonl")
CKE = {**_load("cke-2023.jsonl"), **_load("cke-more.jsonl")}


def cke(test, item_id):
    if item_id not in CKE:
        test.skipTest(f"{item_id}: devset/cke-*.jsonl not present (git-ignored CKE material)")
    return CKE[item_id]["question"]


class TestV1Unchanged(unittest.TestCase):
    def test_dev_sets_gold_types_v1(self):
        if not DEV_ITEMS:
            self.skipTest("no dev sets")
        bad = [(i, d["type"], detect(d["question"]).qtype) for i, d in DEV_ITEMS.items()
               if detect(d["question"]).qtype != d["type"]]
        self.assertEqual(bad, [])

    def test_v2_identical_to_v1_on_dev_sets(self):
        """v2 must not change the parse of the Wikipedia-style dev questions (no sources, command-only)."""
        diffs = []
        for i, d in DEV_ITEMS.items():
            a, b = detect(d["question"]), detect(d["question"], v2=True)
            if (a.qtype, a.options, a.statements, a.items, a.left, a.right, a.n_select, a.open_kind) != \
                    (b.qtype, b.options, b.statements, b.items, b.left, b.right, b.n_select, b.open_kind):
                diffs.append(i)
        self.assertEqual(diffs, [])


class TestCkeTypesV2(unittest.TestCase):
    def test_all_cke_items_typed(self):
        if not CKE:
            self.skipTest("no CKE dev sets")
        special = {"cke23-21": "abcd_parts", "cke23-2.2": "match"}
        bad = []
        for i, d in CKE.items():
            got = detect(d["question"], v2=True).qtype
            if i in special:
                exp = special[i]
            elif d.get("rubric"):
                exp = "explain"
            else:
                exp = d["type"]
            if got != exp:
                bad.append((i, exp, got))
        self.assertEqual(bad, [])


class TestTwoSentenceChoice(unittest.TestCase):  # (a)
    def test_cke21(self):
        pq = detect(cke(self, "cke23-21"), v2=True)
        self.assertEqual(pq.qtype, "abcd_parts")
        self.assertEqual([p[0] for p in pq.parts], ["1", "2"])
        self.assertTrue(all([l for l, _ in p[2]] == list("ABCD") for p in pq.parts))
        self.assertIn('"1-"', prompts.grammar_for(pq))
        self.assertEqual(_max_tokens(pq, Settings()), 16)
        left = [p[0] for p in pq.parts]
        self.assertEqual(formats.render_match(parse_pairs("1-B, 2-C", left, list("ABCD"))), "1-B, 2-C")

    def test_v1_still_single_abcd(self):
        self.assertEqual(detect(cke(self, "cke23-21")).qtype, "abcd")

    def test_synthetic(self):
        q = ("Dokończ zdania 1. i 2. Zaznacz właściwą odpowiedź spośród podanych.\n"
             "1. Pierwszym królem Polski był\nA. Mieszko I.\nB. Bolesław Chrobry.\nC. Kazimierz Wielki.\n"
             "2. Unię w Krewie zawarto w roku\nA. 1385.\nB. 1410.\nC. 1569.")
        pq = detect(q, v2=True)
        self.assertEqual(pq.qtype, "abcd_parts")
        self.assertEqual([len(p[2]) for p in pq.parts], [3, 3])


class TestWrappedStatements(unittest.TestCase):  # (b)
    def test_cke3_full_statement(self):
        pq = detect(cke(self, "cke23-3"), v2=True)
        self.assertEqual(pq.qtype, "pf")
        self.assertEqual(len(pq.statements), 3)
        self.assertTrue(pq.statements[0][1].endswith("w wyniku II wojny punickiej."))

    def test_cke19_uppercase_wrap(self):
        pq = detect(cke(self, "cke23-19"), v2=True)
        s2 = pq.statements[1][1]
        self.assertIn("II Rzeczypospolitej", s2)
        self.assertTrue(s2.endswith("w źródle 1."))

    def test_v1_truncates(self):
        pq = detect(cke(self, "cke23-3"))
        self.assertFalse(pq.statements[0][1].endswith("punickiej."))

    def test_synthetic(self):
        q = ("Oceń prawdziwość poniższych stwierdzeń. Zaznacz P, jeśli stwierdzenie jest\n"
             "prawdziwe, albo F – jeśli jest fałszywe.\n"
             "1. Bitwa pod Grunwaldem została stoczona\nw 1410 roku.\n"
             "2. Unia lubelska połączyła Koronę\nKrólestwa Polskiego z Wielkim Księstwem Litewskim.\n"
             "3. Konstytucję 3 maja uchwalono w 1791 roku.\nOdpowiedz w formacie: P/F, P/F, P/F.")
        pq = detect(q, v2=True)
        self.assertEqual([s for _, s in pq.statements], [
            "Bitwa pod Grunwaldem została stoczona w 1410 roku.",
            "Unia lubelska połączyła Koronę Królestwa Polskiego z Wielkim Księstwem Litewskim.",
            "Konstytucję 3 maja uchwalono w 1791 roku."])


class TestLetterNumberMatch(unittest.TestCase):  # (c)
    def test_cke22_letters_to_fragment_numbers(self):
        pq = detect(cke(self, "cke23-2.2"), v2=True)
        self.assertEqual(pq.qtype, "match")
        self.assertEqual([l for l, _ in pq.left], ["A", "B"])
        self.assertEqual([l for l, _ in pq.right], ["1", "2", "3"])
        g = prompts.grammar_for(pq)
        self.assertIn('"A-', g)
        self.assertEqual(formats.render_match(parse_pairs("A-3, B-2", ["A", "B"], ["1", "2", "3"])), "A-3, B-2")
        self.assertIn("literą", prompts.instruction(pq))

    def test_v1_misread_as_abcd(self):
        self.assertEqual(detect(cke(self, "cke23-2.2")).qtype, "abcd")

    def test_fragment_blocks_to_letters(self):
        pq = detect(cke(self, "cke2505-5.1"), v2=True)  # 'Fragment 1:' blocks -> genealogical list A-F
        self.assertEqual(pq.qtype, "match")
        self.assertEqual([l for l, _ in pq.left], ["1", "2"])
        self.assertEqual([l for l, _ in pq.right], list("ABCDEF"))

    def test_letter_labelled_fragments(self):
        pq = detect(cke(self, "cke2305-2.2"), v2=True)  # right side = 'Fragment A:' .. 'Fragment C:'
        self.assertEqual([l for l, _ in pq.right], list("ABC"))


class TestExplainMode(unittest.TestCase):  # (d)
    def test_wyjasnij(self):
        pq = detect(cke(self, "cke23-23"), v2=True)
        self.assertEqual(pq.qtype, "explain")
        self.assertEqual(_max_tokens(pq, Settings()), Settings().explain_max_tokens)
        self.assertIsNone(prompts.grammar_for(pq))
        self.assertEqual(detect(cke(self, "cke23-23")).qtype, "open")  # v1: short open, cut at first newline

    def test_decision_labels(self):
        pq = detect(cke(self, "cke23-12"), v2=True)
        self.assertEqual((pq.qtype, pq.open_kind), ("explain", "decision"))
        self.assertEqual(pq.labels, ["Rozstrzygnięcie", "Uzasadnienie"])
        out = formats.render_explain("Rozstrzygnięcie: Nie. Uzasadnienie: W tekście mowa o trzech stanach "
                                     "sejmujących, a nie o trzech władzach.", pq.labels)
        self.assertTrue(out.startswith("Rozstrzygnięcie: Nie.\nUzasadnienie: "))
        self.assertGreater(len(out), 60)

    def test_name_explain_and_compare(self):
        self.assertEqual(detect(cke(self, "cke23-25.1"), v2=True).labels, ["Nazwisko", "Wyjaśnienie"])
        self.assertEqual(detect(cke(self, "cke23-6"), v2=True).open_kind, "compare")

    def test_plan_a_or_b_is_decision_not_abcd(self):
        pq = detect(cke(self, "cke23-13.1"), v2=True)
        self.assertEqual((pq.qtype, pq.open_kind), ("explain", "decision"))

    def test_short_identification_stays_open(self):
        for i in ("cke23-4.1", "cke23-9.1", "cke23-16.2"):
            self.assertEqual(detect(cke(self, i), v2=True).qtype, "open", i)
        self.assertEqual(detect(cke(self, "cke23-9.1"), v2=True).open_kind, "person")


class TestCommandDetection(unittest.TestCase):  # (e)
    def test_sources_excluded(self):
        q = cke(self, "cke23-11.2")
        src, cmd = split_command(q)
        self.assertTrue(cmd.startswith("Dokończ zdanie."))
        self.assertIn("Dankowski", src)
        pq = detect(q, v2=True)
        self.assertEqual([l for l, _ in pq.options], list("ABCD"))
        self.assertEqual(pq.options[2][1], "Sejmu Wielkiego.")

    def test_bullets_in_sources_do_not_make_pf(self):
        pq = detect(cke(self, "cke23-5.1"), v2=True)  # genealogy bullets in the source, command = 'Podaj ...'
        self.assertEqual(pq.qtype, "open")
        self.assertEqual(detect(cke(self, "cke23-5.1")).qtype, "generic")

    def test_letter_hint_without_option_lines(self):
        pq = detect(cke(self, "cke2305-2.1"), v2=True)  # '... Podaj literę A, B albo C.'
        self.assertEqual((pq.qtype, [l for l, _ in pq.options]), ("abcd", ["A", "B", "C"]))

    def test_list_before_command(self):
        q = ("Poniżej wymieniono wydarzenia.\nA. chrzest Polski\nB. bitwa pod Grunwaldem\nC. hołd pruski\n"
             "Uporządkuj wydarzenia chronologicznie. Odpowiedz ciągiem liter, np. B, A, C.")
        pq = detect(q, v2=True)
        self.assertEqual((pq.qtype, [l for l, _ in pq.items]), ("chrono", ["A", "B", "C"]))

    def test_citation_line_is_not_a_command(self):
        src, cmd = split_command("Tekst źródła.\nNa podstawie: J. Kowalski, Historia, Warszawa 2000.\n\n"
                                 "Podaj nazwę dokumentu, o którym mowa w tekście.")
        self.assertTrue(cmd.startswith("Podaj nazwę"))
        self.assertIn("Na podstawie:", src)


class TestRewriteHelpers(unittest.TestCase):
    def test_parse_rewrite(self):
        qs = parse_rewrite("1. Bitwa pod Grunwaldem\n- „Wielka wojna z zakonem krzyżackim”\nTrzecie")
        self.assertEqual([q for _, q, _ in qs], ["Bitwa pod Grunwaldem", "Wielka wojna z zakonem krzyżackim"])

    def test_needs_rewrite(self):
        self.assertTrue(needs_rewrite(detect("W którym roku odbył się pierwszy rozbiór?", v2=True), 1))
        self.assertFalse(needs_rewrite(detect("W którym roku zmarł Kazimierz Wielki?", v2=True), 1))
        self.assertFalse(needs_rewrite(detect("W którym roku zmarł Kazimierz Wielki?", v2=True), 0))


if __name__ == "__main__":
    unittest.main()
