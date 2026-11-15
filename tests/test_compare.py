import copy
import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import compare, evidence


class TestCompare(unittest.TestCase):

    def setUp(self):
        self.corpus = helpers.sample_corpus()   # DUMMY samples
        self.table = compare.compare(self.corpus, ["DUMMY-A", "DUMMY-B"])

    def row(self, field):
        return next(r for r in self.table["rows"] if r["field"] == field)

    def test_needs_two_or_three(self):
        with self.assertRaises(ValueError):
            compare.compare(self.corpus, ["DUMMY-A"])
        with self.assertRaises(ValueError):
            compare.compare(self.corpus, ["DUMMY-A", "DUMMY-B", "X", "Y"])
        with self.assertRaises(ValueError):
            compare.compare(self.corpus, ["DUMMY-A", "NOPE"])

    def test_rows_show_original_units_and_same_flags(self):
        self.assertIn("psi", self.row("pressure range")["values"][1])
        self.assertTrue(self.row("scale")["same"])
        self.assertFalse(self.row("hardware")["same"])
        self.assertIn("DERIVED", self.row("gravity")["values"][0])

    def test_findings_are_measured_only_with_page(self):
        cell = self.row("key measured findings")["values"][0]
        self.assertIn("Figure 3", cell)
        self.assertNotIn("authors think", cell)

    def test_verdict_reasons(self):
        verdict = self.table["verdict"]
        self.assertFalse(verdict["comparable"])
        text = " ".join(verdict["reasons"])
        self.assertIn("hardware", text)
        self.assertIn("phases", text)
        self.assertIn("sensors", text)
        self.assertNotIn("scales", text)
        self.assertEqual(self.table["label"], "DERIVED")

    def test_matching_investigations_are_comparable(self):
        twin = copy.deepcopy(self.corpus["investigations"][0])
        twin["acronym"] = "DUMMY-A2"
        corpus = {"investigations": self.corpus["investigations"] + [twin], "runs": []}
        table = compare.compare(corpus, ["DUMMY-A", "DUMMY-A2"])
        self.assertTrue(table["verdict"]["comparable"])
        self.assertTrue(all(r["same"] for r in table["rows"]))

    def test_summary_context_has_ids_for_displayed_rows(self):
        blocks = compare.summary_context(self.table)
        self.assertEqual(len(blocks), len(self.table["rows"]) + 1)
        self.assertEqual(blocks[0]["id"], "C1")
        self.assertTrue(blocks[0]["text"].startswith("objective"))


if __name__ == "__main__":
    unittest.main()
