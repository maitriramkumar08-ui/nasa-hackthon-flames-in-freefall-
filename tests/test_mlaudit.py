import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence, mlaudit


def dummy_rows():
    """DUMMY rows: y = 2 * o2 + 0.5 * flow + 3, three campaigns, all at 0 g."""
    rows = []
    for index in range(66):
        o2 = 15 + index % 11
        flow = 2 + (index * 7) % 13
        rows.append({"group": f"DUMMY-{index % 3}",
                     "x": {"o2_percent": o2, "flow_speed": flow, "gravity": 0.0},
                     "y": 2 * o2 + 0.5 * flow + 3})
    return rows


class TestMlAudit(unittest.TestCase):

    def test_real_dummy_corpus_does_not_train(self):
        corpus = helpers.sample_corpus()
        found = mlaudit.audit(corpus, "flame_spread_rate")
        self.assertFalse(found["train"])
        self.assertEqual(found["rows"], 0)
        self.assertIn("as text", found["conclusion"])

    def test_under_min_rows_stops(self):
        found = mlaudit.audit_rows(dummy_rows()[:40], "y")
        self.assertFalse(found["train"])
        self.assertIn("fewer than the 50", found["reason"])
        self.assertNotIn("metrics", found)

    def test_one_investigation_stops(self):
        rows = [dict(row, group="DUMMY-0") for row in dummy_rows()]
        self.assertFalse(mlaudit.audit_rows(rows, "y")["train"])

    def test_recovers_linear_relationship(self):
        found = mlaudit.audit_rows(dummy_rows(), "y", alpha=0.0)
        self.assertTrue(found["train"])
        self.assertEqual(found["per_investigation"], {"DUMMY-0": 22, "DUMMY-1": 22, "DUMMY-2": 22})
        self.assertLess(found["metrics"]["ols"]["rmse"]["mean"], 1e-6)
        answer = mlaudit.predict(found["model"], {"o2_percent": 20, "flow_speed": 10, "gravity": 0.0})
        self.assertFalse(answer["refused"])
        self.assertAlmostEqual(answer["prediction"], 48.0)

    def test_refuses_outside_range(self):
        model = mlaudit.audit_rows(dummy_rows(), "y")["model"]
        answer = mlaudit.predict(model, {"o2_percent": 40, "flow_speed": 10, "gravity": 0.0})
        self.assertTrue(answer["refused"])
        self.assertIsNone(answer["prediction"])

    def test_microgravity_model_refuses_moon(self):
        model = mlaudit.audit_rows(dummy_rows(), "y")["model"]
        answer = mlaudit.predict(model, {"o2_percent": 20, "flow_speed": 10, "gravity": 0.16})
        self.assertTrue(answer["refused"])
        self.assertIn("gravity", answer["reasons"][0])

    def test_missing_feature_refuses(self):
        model = mlaudit.audit_rows(dummy_rows(), "y")["model"]
        self.assertTrue(mlaudit.predict(model, {"o2_percent": 20, "flow_speed": 10})["refused"])


if __name__ == "__main__":
    unittest.main()
