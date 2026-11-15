import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import research

QUANTITIES = ["o2_percent", "pressure", "flow_speed", "gravity", "temperature"]


def dummy_investigation(number, acronym, publications, ranges=None, limitations=()):
    return {
        "id": number, "acronym": acronym, "name": f"DUMMY investigation {acronym}",
        "psi_id": None, "pillar": "prevention", "evidence_class": "MEASURED", "scale": "bench",
        "platform": "DUMMY", "objective": "DUMMY", "hardware": "DUMMY rig",
        "publications": [{"id": pid, "title": f"DUMMY paper {pid}", "url": None, "ntrs_id": None}
                         for pid in publications],
        "fuels": [{"phase": "solid", "material": "DUMMY cotton", "geometry": None, "dimensions": None}],
        "sensors": [], "findings": [],
        "notes": {"limitation": list(limitations)} if limitations else {},
        "ranges": ranges or {},
    }


def dummy_run(number, inv, publication_id, **values):
    return {
        "id": number, "run_id": f"DUMMY-{number}", "experiment": None, "outcome": None,
        "page_or_table": "p1", "investigation_id": inv["id"], "acronym": inv["acronym"],
        "hardware": inv["hardware"], "scale": inv["scale"], "pillar": inv["pillar"],
        "fuel_phases": ["solid"], "materials": ["DUMMY cotton"],
        "source": {"publication_id": publication_id, "title": "DUMMY", "url": None, "ntrs_id": None},
        "values": {q: values.get(q) for q in QUANTITIES},
        "original": {q: None for q in QUANTITIES}, "from_words": [], "flow_direction": None,
    }


def dummy_corpus():
    """DUMMY: one well-run investigation, one with a single run, one with nothing measured."""
    full_ranges = {q: {"min": 1.0, "max": 2.0, "from_words": False, "original": []} for q in QUANTITIES}
    good = dummy_investigation(1, "DUMMY-GOOD", [10, 11], full_ranges, ["DUMMY: short burn only"])
    thin = dummy_investigation(2, "DUMMY-THIN", [20])
    empty = dummy_investigation(3, "DUMMY-EMPTY", [30])
    point = dict(o2_percent=21.0, pressure=101.3, flow_speed=10.0, gravity=0.0, temperature=298.0)
    runs = [
        dummy_run(1, good, 10, **point),
        dummy_run(2, good, 10, **dict(point, o2_percent=21.04)),   # same condition once rounded
        dummy_run(3, good, 11, **dict(point, o2_percent=30.0)),
        dummy_run(4, good, 11, **dict(point, o2_percent=30.0)),
        dummy_run(5, thin, 20, o2_percent=21.0),
    ]
    return {"investigations": [good, thin, empty], "runs": runs}


class TestWeakness(unittest.TestCase):

    def setUp(self):
        self.report = {w["acronym"]: w for w in research.weakness(dummy_corpus())}

    def test_counts_runs_and_conditions(self):
        good = self.report["DUMMY-GOOD"]
        self.assertEqual(good["tests"], 4)
        self.assertEqual(good["distinct_conditions"], 2)
        self.assertEqual(good["repeats_per_condition"], 2.0)
        self.assertEqual(good["limitations"], ["DUMMY: short burn only"])

    def test_missing_share_counts_runs_and_ranges(self):
        self.assertEqual(self.report["DUMMY-GOOD"]["missing_share"], 0.0)
        # 4 missing run values + 5 missing ranges out of 10 slots
        self.assertAlmostEqual(self.report["DUMMY-THIN"]["missing_share"], 0.9)
        self.assertEqual(self.report["DUMMY-EMPTY"]["missing_share"], 1.0)
        self.assertIsNone(self.report["DUMMY-EMPTY"]["repeats_per_condition"])

    def test_clusters_follow_fixed_rules(self):
        groups = research.clusters(research.weakness(dummy_corpus()), min_runs=3)
        self.assertEqual(groups, {"no dominant weakness": ["DUMMY-GOOD"],
                                  "few runs": ["DUMMY-THIN"], "no runs": ["DUMMY-EMPTY"]})


class TestGapUsers(unittest.TestCase):

    def test_opportunities_are_ranked_and_scored(self):
        missions = [{"name": "DUMMY atmosphere", "relevance": 0.5,
                     "scenario": {"o2_percent": 34, "pressure": 56.5, "gravity_g": 0.16}}]
        found = research.opportunities(dummy_corpus(), missions, research.DEFAULT_WEIGHTS)
        self.assertTrue(found)
        scores = [o["score"] for o in found]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for o in found:
            self.assertAlmostEqual(o["score"], o["gap_size"] * 0.5 * o["data_cost"])
            self.assertNotEqual(o["gap_class"], "DIRECTLY_TESTED")

    def test_before_drops_later_and_undated_sources(self):
        early, undated = research.before(dummy_corpus(), 2015, {10: 2010, 11: 2020, "DUMMY-THIN": 2018})
        self.assertEqual([i["acronym"] for i in early["investigations"]], ["DUMMY-GOOD"])
        self.assertEqual([r["id"] for r in early["runs"]], [1, 2])
        self.assertEqual(undated, ["DUMMY-EMPTY"])

    def test_backtest_reports_hits_and_misses(self):
        checks = [
            {"name": "DUMMY tested point", "should_flag": True,
             "scenario": {"o2_percent": 21, "pressure": 101.3, "flow_speed": 10, "gravity_g": 0, "temperature": 298}},
            {"name": "DUMMY far atmosphere", "should_flag": True,
             "scenario": {"o2_percent": 40, "pressure": 30, "gravity_g": 0.38}},
        ]
        report = research.backtest(dummy_corpus(), 2015, {10: 2010, 11: 2020}, checks)
        self.assertEqual(report["hits"] + report["misses"], 2)
        far = report["checks"][1]
        self.assertTrue(far["flagged"])
        self.assertEqual(far["outcome"], "hit")


if __name__ == "__main__":
    unittest.main()
