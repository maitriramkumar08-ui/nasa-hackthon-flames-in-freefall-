import json
import unittest

from helpers import TempFiles

from phase0.decisions import check_decisions, weights_total


class TestDecisions(TempFiles, unittest.TestCase):

    def check(self, decisions):
        return check_decisions(self.write("d.json", json.dumps(decisions)))

    def test_weights_must_add_to_one(self):
        problems = self.check({"ranking_weights": {"value": {"a": 0.5, "b": 0.4},
                                                   "confirmed_by": "Asha"}})
        self.assertTrue(any("add up to" in p for p in problems))

    def test_float_noise_is_ignored(self):
        decisions = {"ranking_weights": {"value": {"a": 0.1, "b": 0.2, "c": 0.7}}}
        self.assertEqual(weights_total(decisions), 1)

    def test_unconfirmed_flagged_and_notes_skipped(self):
        problems = self.check({"_note": "ignore me",
                               "database": {"value": "sqlite", "confirmed_by": ""}})
        self.assertEqual(problems, ["database: nobody has confirmed it yet",
                                    "ranking_weights add up to 0, should be 1"])


if __name__ == "__main__":
    unittest.main()
