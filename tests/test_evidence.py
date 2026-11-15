import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence


class TestEvidence(unittest.TestCase):

    def setUp(self):
        self.corpus = helpers.sample_corpus()

    def test_shapes(self):
        acronyms = [i["acronym"] for i in self.corpus["investigations"]]
        self.assertEqual(acronyms, ["DUMMY-A", "DUMMY-B"])
        self.assertEqual(len(self.corpus["runs"]), 2)

    def test_microgravity_word_becomes_zero_and_is_marked(self):
        run = self.corpus["runs"][0]
        self.assertEqual(run["values"]["gravity"], 0.0)
        self.assertIn("gravity", run["from_words"])

    def test_run_flow_is_converted(self):
        second = self.corpus["runs"][1]
        self.assertEqual(second["values"]["flow_speed"], 20.0)   # 0.2 m/s
        self.assertIsNone(second["values"]["pressure"])          # missing stays missing

    def test_ranges_merge_across_papers(self):
        alpha = self.corpus["investigations"][0]
        self.assertEqual(alpha["ranges"]["o2_percent"]["max"], 21)
        self.assertEqual(len(alpha["publications"]), 2)

    def test_scenario_converts_units(self):
        s = evidence.scenario({"o2_percent": 34, "pressure": 8.2, "pressure_unit": "psi", "gravity_g": 0.16})
        self.assertAlmostEqual(s["pressure"], 56.537, places=2)
        self.assertEqual(s["label"], "HYPOTHETICAL")
