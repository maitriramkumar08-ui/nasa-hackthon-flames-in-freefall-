import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence, ranking


def dummy_investigation(**changes):
    """DUMMY - NOT REAL DATA. One investigation with ranges and no runs."""
    inv = {
        "id": 1, "acronym": "DUMMY-X", "name": "DUMMY - NOT REAL DATA", "pillar": "prevention",
        "scale": "bench", "fuels": [{"phase": "solid", "material": "PMMA"}],
        "sensors": ["camera for flame spread"], "findings": [],
        "ranges": {"o2_percent": {"min": 15, "max": 21}, "pressure": {"min": 70, "max": 101},
                   "flow_speed": {"min": 1, "max": 25}, "gravity": {"min": 0.0, "max": 0.0}},
    }
    inv.update(changes)
    return inv


def ranked(raw, *investigations):
    corpus = {"investigations": list(investigations) or [dummy_investigation()], "runs": []}
    return ranking.rank(corpus, evidence.scenario(raw))


class TestRanking(unittest.TestCase):

    def test_everything_inside_scores_one(self):
        entry = ranked({"o2_percent": 21, "pressure": 101, "flow_speed": 10, "gravity_g": 0,
                        "material": "PMMA", "fuel_phase": "solid", "pillar": "prevention",
                        "scale": "bench", "outputs": ["flame spread"]})[0]
        self.assertEqual(entry["total"], 1.0)
        self.assertEqual(entry["evidence_class"], "direct")
        self.assertEqual(entry["unmatched"], [])

    def test_hand_calculated_partial_match(self):
        # atmosphere (0 + 1) / 2 = 0.5: O2 is 13 points past 21, partial pressure 19.21 kPa is inside
        # flow 1 - 5/20 = 0.75, gravity 1 - 0.16/0.5 = 0.68, material same phase only = 0.3
        # total .25*.5 + .1*.75 + .2*.68 + .2*.3 + .1*0 + .1*1 + .05*.5 = 0.521
        entry = ranked({"o2_percent": 34, "pressure": 56.5, "flow_speed": 30, "gravity_g": 0.16,
                        "material": "cotton", "fuel_phase": "solid", "pillar": "suppression",
                        "scale": "bench", "outputs": ["flame spread", "extinction"]})[0]
        self.assertEqual(entry["scores"], {"atmosphere": 0.5, "flow": 0.75, "gravity": 0.68,
                                           "material": 0.3, "objective": 0.0, "scale": 1.0,
                                           "measurement": 0.5})
        self.assertEqual(entry["total"], 0.521)
        self.assertEqual(entry["evidence_class"], "supporting")
        self.assertEqual(entry["unmatched"], ["material", "objective"])

    def test_hand_calculated_missing_values(self):
        # atmosphere 1 (O2 only, no pressure), gravity 1 - 0.38/0.5 = 0.24, acrylic is the same class as PMMA
        # total .25*1 + .2*.24 + .2*.6 = 0.418
        entry = ranked({"o2_percent": 21, "gravity_g": 0.38, "material": "acrylic sheet"})[0]
        self.assertEqual(entry["scores"]["material"], 0.6)
        self.assertEqual(entry["total"], 0.418)
        self.assertEqual(entry["evidence_class"], "supporting")
        self.assertIn("flow", entry["unmatched"])
        self.assertEqual(entry["reasons"]["flow"], "no flow speed to compare")

    def test_sorted_best_first(self):
        far = dummy_investigation(id=2, acronym="DUMMY-Y", pillar="detection")
        entries = ranked({"o2_percent": 21, "pillar": "prevention"}, far, dummy_investigation())
        self.assertEqual([e["acronym"] for e in entries], ["DUMMY-X", "DUMMY-Y"])

    def test_weights_must_add_to_one(self):
        weights = dict(evidence.decisions()["ranking_weights"], atmosphere=0.5)
        with self.assertRaises(ValueError):
            ranking.rank({"investigations": [], "runs": []}, evidence.scenario({}), weights)

    def test_dummy_database(self):
        corpus = helpers.sample_corpus()
        entries = ranking.rank(corpus, evidence.scenario({"o2_percent": 21, "gravity_g": 0}))
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(e["label"] == "DERIVED" and e["explanation"] for e in entries))


if __name__ == "__main__":
    unittest.main()
