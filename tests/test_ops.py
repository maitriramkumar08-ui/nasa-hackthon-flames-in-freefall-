import json
import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import concern, ops
from test_concern import DUMMY_CORPUS, dummy_run


def tested_near_nominal():
    """DUMMY - NOT REAL DATA. Solid-fuel runs right at the simulated nominal cabin (34 % O2, 56.5 kPa, 10 cm/s)."""
    runs = [dummy_run(n, o2) for n, o2 in enumerate([33.0, 34.0, 35.0], start=1)]
    return dict(DUMMY_CORPUS, runs=runs)


class TestCombinedView(unittest.TestCase):

    def test_o2_drift_and_fan_slowdown_gives_an_envelope_entry(self):
        streams = ops.record_compartments("o2_drift_fan_slowing", seed=1, steps=600, compartments=["habitat"])
        view = ops.snapshot(streams, 599, tested_near_nominal(), {"habitat": "solid"})
        entries = [e for e in view["combined"]["entries"] if e["type"] == "ENVELOPE"]
        self.assertEqual(len(entries), 1)
        self.assertIn("o2_percent", entries[0]["axes"])
        self.assertIn("not a fire prediction", entries[0]["message"])
        check = view["combined"]["envelope"][0]
        self.assertEqual(check["axes"]["o2_percent"]["side"], "above")

    def test_nominal_cabin_inside_tested_conditions_has_no_envelope_entry(self):
        streams = ops.record_compartments("nominal", seed=1, steps=60, compartments=["habitat"])
        view = ops.snapshot(streams, 59, tested_near_nominal(), {"habitat": "solid"})
        self.assertEqual(view["combined"]["entries"], [])
        self.assertEqual(view["combined"]["envelope"][0]["axes"]["o2_percent"]["class"], "DIRECTLY_TESTED")

    def test_overheating_wire_groups_co_smoke_and_temperature(self):
        streams = ops.record_compartments("overheating_wire", seed=1, steps=120, compartments=["habitat", "lab"])
        view = ops.snapshot(streams, 90, DUMMY_CORPUS, {"habitat": "solid", "lab": "solid"})
        groups = view["combined"]["co_occurring"]
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["compartment"], "habitat")
        self.assertEqual(set(group["channels"]), {"co_ppm", "smoke_level", "temperature_c"})
        self.assertEqual(group["label"], "ILLUSTRATIVE")
        self.assertEqual(group["thresholds"], "PLACEHOLDER")
        self.assertTrue(group["members"])
        self.assertTrue(all(m["channel"] in group["channels"] for m in group["members"]))

    def test_same_seed_same_output(self):
        def run():
            streams = ops.record_compartments("overheating_wire", seed=4, steps=90, compartments=["habitat", "lab"])
            return json.dumps(ops.snapshot(streams, 80, DUMMY_CORPUS, {"habitat": "solid"}, 0.0), sort_keys=True)
        self.assertEqual(run(), run())

    def test_no_aggregate_score(self):
        streams = ops.record_compartments("overheating_wire", seed=1, steps=120, compartments=["habitat"])
        view = ops.snapshot(streams, 90, DUMMY_CORPUS, {"habitat": "solid"})
        habitat = view["compartments"]["habitat"]
        # The reasoning chain keeps ranking's per-investigation match score; that is similarity
        # to the scenario, not a fused concern score, so it is left out of this check.
        text = json.dumps([view["combined"], habitat["tiles"], habitat["banner"]]).lower()
        for word in ("risk", "probability", "score\""):
            self.assertNotIn(word, text)

    def test_no_material_class_is_not_evaluated(self):
        streams = ops.record_compartments("nominal", seed=1, steps=5, compartments=["habitat"])
        check = ops.snapshot(streams, 4, DUMMY_CORPUS, {})["combined"]["envelope"][0]
        self.assertEqual(check["state"], "NOT_EVALUATED")


class TestCrew(unittest.TestCase):

    def test_six_tiles_each_with_a_status(self):
        streams = ops.record_compartments("overheating_wire", seed=1, steps=120, compartments=["habitat"])
        tiles = ops.snapshot(streams, 90, DUMMY_CORPUS, {"habitat": "solid"})["compartments"]["habitat"]["tiles"]
        self.assertEqual([t["title"] for t in tiles], ["O2", "Total pressure", "CO", "CO2", "Smoke", "Airflow"])
        status = {t["channel"]: t["status"] for t in tiles}
        self.assertTrue(set(status.values()) <= {"nominal", "watch", "alert"})
        self.assertIn(status["co_ppm"], {"watch", "alert"})
        self.assertEqual(status["co2_ppm"], "nominal")
        self.assertTrue(all(t["reasons"] or t["status"] == "nominal" for t in tiles))

    def test_banner_shows_only_the_top_concern(self):
        streams = ops.record_compartments("overheating_wire", seed=1, steps=120, compartments=["habitat"])
        banner = ops.snapshot(streams, 90, DUMMY_CORPUS, {"habitat": "solid"})["compartments"]["habitat"]["banner"]
        self.assertEqual(banner["type"], "CO_OCCURRENCE")
        self.assertEqual(banner["text"].count(". ["), 1)  # one sentence, one label

    def test_priority_order(self):
        items = [{"type": "TREND", "channel": "o2_percent"}, {"type": "ENVELOPE", "channel": "o2_percent"},
                 {"type": "THRESHOLD", "channel": "co2_ppm"}, {"type": "THRESHOLD", "channel": "o2_percent"},
                 {"type": "THRESHOLD", "channel": "smoke_level"}, {"type": "CO_OCCURRENCE"},
                 {"type": "TREND", "channel": "co_ppm"}]
        ordered = [(i["type"], i.get("channel")) for i in sorted(items, key=ops.priority)]
        self.assertEqual(ordered, [("CO_OCCURRENCE", None), ("THRESHOLD", "smoke_level"),
                                   ("THRESHOLD", "o2_percent"), ("THRESHOLD", "co2_ppm"),
                                   ("ENVELOPE", "o2_percent"), ("TREND", "co_ppm"), ("TREND", "o2_percent")])

    def test_quiet_banner(self):
        self.assertEqual(ops.banner("lab", [])["status"], "nominal")


class TestRules(unittest.TestCase):

    def test_rule_needs_every_channel(self):
        rule = {"id": "r", "window_s": 60, "rise": {"co_ppm": 5.0, "smoke_level": 0.05}}
        history = [{"t": 0.0, "co_ppm": 1.0, "smoke_level": 0.0}]
        self.assertEqual(ops.co_occurrence({"t": 30.0, "co_ppm": 10.0, "smoke_level": 0.01}, history, [rule]), [])
        found = ops.co_occurrence({"t": 30.0, "co_ppm": 10.0, "smoke_level": 0.2}, history, [rule])
        self.assertEqual(found[0]["changes"], {"co_ppm": 9.0, "smoke_level": 0.2})

    def test_shipped_rules_are_labelled(self):
        rules = concern.load_alerts()["co_occurrence"]["rules"]
        self.assertTrue(rules)
        for rule in rules:
            self.assertEqual(rule["label"], "ILLUSTRATIVE")
            self.assertEqual(rule["thresholds_label"], "PLACEHOLDER")


if __name__ == "__main__":
    unittest.main()
