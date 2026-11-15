import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence, gaps


def dummy_run(run_id, gravity, words=(), scale="bench", **values):
    """DUMMY - NOT REAL DATA. One test run with the given values."""
    numbers = {"o2_percent": 21.0, "pressure": 101.0, "flow_speed": 10.0, "temperature": None}
    numbers.update(values, gravity=gravity)
    return {"run_id": run_id, "investigation_id": 1, "acronym": "DUMMY-X", "scale": scale,
            "pillar": "prevention", "materials": ["PMMA"], "values": numbers,
            "from_words": list(words), "source": {"title": "DUMMY - NOT REAL DATA"}}


def corpus(*runs):
    return {"investigations": [{"id": 1}], "runs": list(runs)}


def scenario(**raw):
    base = {"o2_percent": 21, "pressure": 101, "flow_speed": 10, "material": "PMMA", "pillar": "prevention"}
    return evidence.scenario(dict(base, **raw))


class TestClassifyAxis(unittest.TestCase):

    def test_moon_between_zero_and_one_g_is_bounded(self):
        gap, distance = gaps.classify_axis([0.0, 0.0, 1.0, 1.0], 0.16, 0.05, 3)
        self.assertEqual(gap, "BOUNDED")
        self.assertAlmostEqual(distance, 3.2)

    def test_classes(self):
        self.assertEqual(gaps.classify_axis([20, 21, 22], 21, 2, 3), ("DIRECTLY_TESTED", 0.0))
        self.assertEqual(gaps.classify_axis([21, 30], 21, 2, 3), ("INSUFFICIENT", 0.0))
        self.assertEqual(gaps.classify_axis([15, 17], 30, 2, 3), ("ONE_SIDED", 6.5))
        self.assertEqual(gaps.classify_axis([None], 30, 2, 3), ("NO_INDEXED_DATA", None))


class TestAnalyze(unittest.TestCase):

    def test_moon_with_only_zero_and_one_g_data(self):
        runs = [dummy_run(f"R{n}", g) for n, g in enumerate([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))
        self.assertEqual(found["axes"]["gravity"]["class"], "BOUNDED")
        self.assertNotEqual(found["combination"]["class"], "DIRECTLY_TESTED")
        self.assertEqual(found["combination"]["runs_matching"], [])
        text = " ".join(found["report"])
        self.assertIn("bounded by", text)
        self.assertIn("not directly measured", text)
        self.assertNotIn("safe", text.lower())

    def test_combination_needs_one_run_matching_every_axis(self):
        runs = [dummy_run(f"R{n}", 0.16) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))
        self.assertEqual(found["combination"]["class"], "DIRECTLY_TESTED")
        self.assertEqual(found["combination"]["runs_matching"], ["R0", "R1", "R2"])

    def test_axes_covered_separately_are_not_a_combination(self):
        runs = [dummy_run(f"G{n}", 0.16, o2_percent=40.0) for n in range(3)]
        runs += [dummy_run(f"O{n}", 1.0) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))
        self.assertEqual(found["axes"]["gravity"]["class"], "DIRECTLY_TESTED")
        self.assertEqual(found["axes"]["o2_percent"]["class"], "DIRECTLY_TESTED")
        self.assertEqual(found["combination"]["class"], "INSUFFICIENT")

    def test_word_gravity_is_not_comparable(self):
        runs = [dummy_run(f"R{n}", 0.0, words=["gravity"]) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0))
        self.assertEqual(found["axes"]["gravity"]["class"], "NOT_COMPARABLE")

    def test_other_scale_is_not_comparable(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, scale="spacecraft-scale"))
        self.assertEqual(found["axes"]["o2_percent"]["class"], "NOT_COMPARABLE")

    def test_nearest_runs_carry_source(self):
        runs = [dummy_run(f"R{n}", 0.0, o2_percent=21.0 + n) for n in range(5)]
        nearest = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0))["nearest_runs"]
        self.assertEqual([r["run_id"] for r in nearest], ["R0", "R1", "R2"])
        self.assertEqual(nearest[0]["source"]["title"], "DUMMY - NOT REAL DATA")

    def test_dummy_database(self):
        found = gaps.analyze(helpers.sample_corpus(), scenario(gravity_g=0.16))
        self.assertEqual(found["label"], "DERIVED")
        self.assertEqual(set(found["axes"]), {"o2_percent", "pressure", "flow_speed", "gravity",
                                              "material_class", "pillar"})


def range_investigation(number, material="PMMA", **ranges):
    """DUMMY - NOT REAL DATA. An investigation with reported ranges and no test runs."""
    return {"id": number, "acronym": f"DUMMY-R{number}", "scale": "bench", "pillar": "prevention",
            "fuels": [{"phase": "solid", "material": material}],
            "ranges": {q: {"min": lo, "max": hi, "from_words": False} for q, (lo, hi) in ranges.items()}}


class TestAxisState(unittest.TestCase):

    def test_unset_axis_is_not_evaluated_and_listed_as_skipped(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, pressure=None, pillar=None))
        self.assertEqual(found["axes"]["pressure"]["state"], "NOT_EVALUATED")
        self.assertIsNone(found["axes"]["pressure"]["class"])
        self.assertEqual(found["combination"]["skipped_axes"], ["pressure", "pillar"])
        self.assertEqual(found["skipped_axes"], ["pressure", "pillar"])
        self.assertNotIn("pressure", found["combination"]["evaluated_axes"])

    def test_not_evaluated_is_not_a_coverage_class(self):
        self.assertNotIn("NOT_EVALUATED", gaps.COVERAGE_CLASSES)
        self.assertEqual(len(gaps.COVERAGE_CLASSES), 6)

    def test_unset_axis_does_not_change_the_combination(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, pressure=None))
        self.assertEqual(found["combination"]["class"], "DIRECTLY_TESTED")

    def test_nothing_set_is_not_evaluated_not_directly_tested(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        found = gaps.analyze(corpus(*runs), evidence.scenario({}))
        self.assertEqual(found["combination"]["state"], "NOT_EVALUATED")
        self.assertIsNone(found["combination"]["class"])
        self.assertEqual(found["combination"]["runs_matching"], [])
        self.assertEqual(len(found["skipped_axes"]), 6)


class TestNumericAxis(unittest.TestCase):

    def test_moon_with_only_microgravity_data_is_one_sided(self):
        runs = [dummy_run(f"R{n}", g) for n, g in enumerate([0.0, 0.0, 0.01, 0.0])]
        gravity = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))["axes"]["gravity"]
        self.assertEqual(gravity["class"], "ONE_SIDED")
        self.assertEqual(gravity["side"], "above")
        self.assertEqual(gravity["kind"], "numeric")
        self.assertEqual((gravity["tested_min"], gravity["tested_max"], gravity["unit"]), (0.0, 0.01, "g"))
        self.assertAlmostEqual(gravity["gap_to_nearest"], 0.15)
        self.assertAlmostEqual(gravity["distance"], 3.0)
        self.assertEqual(gravity["runs_within"], 0)
        self.assertEqual(gravity["runs_tested"], 4)

    def test_moon_between_zero_and_one_g_is_bounded_on_both_sides(self):
        runs = [dummy_run(f"R{n}", g) for n, g in enumerate([0.0, 0.0, 1.0])]
        gravity = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))["axes"]["gravity"]
        self.assertEqual(gravity["class"], "BOUNDED")
        self.assertEqual(gravity["side"], "both")
        self.assertEqual((gravity["nearest_below"], gravity["nearest_above"]), (0.0, 1.0))

    def test_scenario_below_every_tested_value(self):
        runs = [dummy_run(f"R{n}", 0.0, o2_percent=o2) for n, o2 in enumerate([30.0, 35.0])]
        o2 = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, o2_percent=21))["axes"]["o2_percent"]
        self.assertEqual((o2["class"], o2["side"]), ("ONE_SIDED", "below"))

    def test_bounded_docstring_says_it_is_about_conditions_not_outcomes(self):
        self.assertIn("non-monotonic", gaps.__doc__)
        self.assertIn("between tested conditions", gaps.classify_axis.__doc__)


class TestPrecedence(unittest.TestCase):

    def test_two_runs_within_tolerance_with_min_three_is_insufficient(self):
        runs = [dummy_run("A", 0.0, o2_percent=21.0), dummy_run("B", 0.0, o2_percent=21.5),
                dummy_run("C", 0.0, o2_percent=15.0), dummy_run("D", 0.0, o2_percent=30.0)]
        found = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0), min_runs=3)
        o2 = found["axes"]["o2_percent"]
        self.assertEqual(o2["class"], "INSUFFICIENT")
        self.assertEqual(o2["runs_within"], 2)
        self.assertEqual(o2["side"], "within")
        self.assertEqual(found["combination"]["class"], "INSUFFICIENT")

    def test_ranges_alone_never_make_directly_tested(self):
        invs = [range_investigation(n, o2_percent=(20.5, 21.5), pressure=(100.0, 102.0),
                                    flow_speed=(9.0, 11.0), gravity=(0.0, 0.0)) for n in range(1, 6)]
        found = gaps.analyze({"investigations": invs, "runs": []}, scenario(gravity_g=0.0))
        for axis in ("o2_percent", "pressure", "flow_speed", "gravity", "material_class", "pillar"):
            self.assertNotEqual(found["axes"][axis]["class"], "DIRECTLY_TESTED", axis)
        self.assertEqual(found["axes"]["o2_percent"]["class"], "INSUFFICIENT")
        self.assertNotEqual(found["combination"]["class"], "DIRECTLY_TESTED")
        self.assertEqual(found["combination"]["runs_matching"], [])
        self.assertEqual(found["nearest_runs"], [])

    def test_range_spanning_the_scenario_is_bounded(self):
        invs = [range_investigation(1, o2_percent=(15.0, 30.0))]
        o2 = gaps.analyze({"investigations": invs, "runs": []}, scenario(gravity_g=0.0))["axes"]["o2_percent"]
        self.assertEqual((o2["class"], o2["range_investigations"]), ("BOUNDED", 1))


class TestCategoricalAxis(unittest.TestCase):

    def test_categories_with_counts_and_no_distance(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        runs.append(dict(dummy_run("C1", 0.0), materials=["cellulose"], investigation_id=2))
        invs = [{"id": 1}, {"id": 2}, range_investigation(3, material="Kimwipe paper")]
        found = gaps.analyze({"investigations": invs, "runs": runs}, scenario(gravity_g=0.0))
        material = found["axes"]["material_class"]
        self.assertEqual(material["kind"], "categorical")
        self.assertEqual(material["categories"], [
            {"category": "plastic", "investigations": 1, "runs": 3},
            {"category": "paper", "investigations": 2, "runs": 1}])
        self.assertTrue(material["in_tested"])
        for key in ("distance", "tested_min", "tested_max", "side", "gap_to_nearest"):
            self.assertNotIn(key, material)

    def test_unindexed_material_has_no_indexed_data(self):
        runs = [dummy_run(f"R{n}", 0.0) for n in range(3)]
        material = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, material="unobtainium"))["axes"]["material_class"]
        self.assertEqual(material["class"], "NO_INDEXED_DATA")
        self.assertFalse(material["in_tested"])
        self.assertEqual(material["scenario_value"], "unobtainium")


class TestPanelLines(unittest.TestCase):

    def test_numeric_line(self):
        runs = [dummy_run(f"R{n}", 0.0, o2_percent=v) for n, v in enumerate([15.0, 18.0, 21.0])]
        o2 = gaps.analyze(corpus(*runs), scenario(gravity_g=0.0, o2_percent=34))["axes"]["o2_percent"]
        self.assertEqual(o2["summary"], "Tested 15–21 % (3 runs). Yours 34 % → 13 points above (one-sided).")

    def test_categorical_line(self):
        runs = [dict(dummy_run(f"C{n}", 0.0), materials=["cellulose"], investigation_id=1 + n % 2)
                for n in range(14)]
        runs += [dict(dummy_run(f"P{n}", 0.0), investigation_id=3) for n in range(6)]
        invs = [{"id": 1}, {"id": 2}, {"id": 3}]
        found = gaps.analyze({"investigations": invs, "runs": runs}, scenario(gravity_g=0.0, material="silicone rubber"))
        self.assertEqual(found["axes"]["material_class"]["summary"],
                         "Tested: paper (2 inv, 14 runs), plastic (1, 6). "
                         "Yours: silicone rubber (plastic) → 6 runs (directly tested).")
        found = gaps.analyze({"investigations": invs, "runs": runs}, scenario(gravity_g=0.0, material="unobtainium"))
        self.assertTrue(found["axes"]["material_class"]["summary"].endswith(
            "Yours: unobtainium → no indexed data."))

    def test_unset_line(self):
        found = gaps.analyze(corpus(dummy_run("R0", 0.0)), scenario(gravity_g=0.0, flow_speed=None))
        self.assertEqual(found["axes"]["flow_speed"]["summary"], "Flow: not set. Choose one to check coverage.")

    def test_bounded_line_names_both_sides(self):
        runs = [dummy_run(f"R{n}", g) for n, g in enumerate([0.0, 1.0])]
        line = gaps.analyze(corpus(*runs), scenario(gravity_g=0.16))["axes"]["gravity"]["summary"]
        self.assertIn("between tested 0 and 1 g", line)
        self.assertIn("bounded by tested conditions", line)

    def test_never_says_not_provided(self):
        ranged = {"investigations": [range_investigation(1, o2_percent=(20.0, 22.0))], "runs": []}
        words = corpus(*[dummy_run(f"W{n}", 0.0, words=["gravity"]) for n in range(3)])
        plain = corpus(*[dummy_run(f"R{n}", 0.0) for n in range(2)])
        cases = [(plain, {}), (plain, {"gravity_g": 0.16}), (plain, {"gravity_g": 0.0, "scale": "spacecraft-scale"}),
                 (words, {"gravity_g": 0.0}), (ranged, {"gravity_g": 0.16}), (corpus(), {"gravity_g": 0.16}),
                 (plain, {"gravity_g": 0.0, "material": "unobtainium", "pillar": "detection"}),
                 (helpers.sample_corpus(), {"gravity_g": 0.38, "pressure": None})]
        for data, raw in cases:
            found = gaps.analyze(data, evidence.scenario(raw) if not raw or "o2_percent" in raw else scenario(**raw))
            lines = [a["summary"] for a in found["axes"].values()] + [found["combination"]["summary"]]
            for line in lines:
                self.assertNotIn("not provided", line, raw)
                self.assertNotIn("None", line, raw)


if __name__ == "__main__":
    unittest.main()
