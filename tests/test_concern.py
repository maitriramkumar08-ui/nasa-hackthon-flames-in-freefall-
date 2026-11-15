import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import concern, telemetry


def dummy_run(number, o2, phase="solid", material="DUMMY cotton"):
    return {
        "id": number, "run_id": f"DUMMY-R{number}", "experiment": "DUMMY", "outcome": None,
        "page_or_table": "p. 1", "investigation_id": 1, "acronym": "DUMMY-X",
        "hardware": None, "scale": "bench", "pillar": "prevention",
        "fuel_phases": [phase], "materials": [material],
        "source": {"publication_id": 1, "title": "DUMMY paper", "url": None, "ntrs_id": None},
        "values": {"o2_percent": o2, "pressure": 56.5, "flow_speed": 10.0, "gravity": 0.0,
                   "temperature": 295.0},
        "original": {}, "from_words": [], "flow_direction": None,
    }


# Hand-built DUMMY corpus: three solid-fuel runs tested up to 30% O2.
DUMMY_CORPUS = {
    "investigations": [{
        "id": 1, "acronym": "DUMMY-X", "name": "DUMMY investigation", "psi_id": None,
        "pillar": "prevention", "evidence_class": None, "scale": "bench", "platform": None,
        "objective": "DUMMY flame spread", "hardware": None,
        "publications": [{"id": 1, "title": "DUMMY paper", "url": None, "ntrs_id": None}],
        "fuels": [{"phase": "solid", "material": "DUMMY cotton", "geometry": None, "dimensions": None}],
        "sensors": [], "notes": {},
        "findings": [{"text": "DUMMY finding", "page_or_table": "p. 2", "type": "MEASURED", "source_id": 1}],
        "ranges": {"o2_percent": {"min": 21.0, "max": 30.0, "from_words": False, "original": []}},
    }],
    "runs": [dummy_run(1, 21.0), dummy_run(2, 26.0), dummy_run(3, 30.0)],
}

NO_ALERT_LIMITS = {"threshold": {}, "trend": {}}


def sample(**changes):
    reading = {"source": "SIMULATED", "compartment": "habitat", "t": 0.0, "o2_percent": 29.0,
               "total_pressure_kpa": 56.5, "co_ppm": 1.0, "co2_ppm": 2000.0, "smoke_level": 0.0,
               "temperature_c": 22.0, "flow_cm_s": 10.0, "gravity_g": 0.0}
    reading.update(changes)
    return reading


class TestConcern(unittest.TestCase):

    def evaluate(self, reading, history=None, config=NO_ALERT_LIMITS, material="solid"):
        return concern.evaluate(reading, DUMMY_CORPUS, material, history, config)

    def test_o2_above_tested_max_fires_envelope_alert(self):
        report = self.evaluate(sample(o2_percent=34.0))
        envelope = [a for a in report["alerts"] if a["type"] == "ENVELOPE"]
        self.assertEqual(len(envelope), 1)
        self.assertIn("outside the tested range", envelope[0]["message"])

    def test_no_envelope_alert_inside_tested_range(self):
        report = self.evaluate(sample(o2_percent=29.0))
        self.assertEqual(report["alerts"], [])

    def test_material_name_also_matches(self):
        report = self.evaluate(sample(o2_percent=34.0), material="cotton")
        self.assertEqual([a["type"] for a in report["alerts"]], ["ENVELOPE"])

    def test_no_material_class_does_not_crash(self):
        report = concern.evaluate(sample(o2_percent=34.0), DUMMY_CORPUS, None, None, NO_ALERT_LIMITS)
        self.assertFalse([a for a in report["alerts"] if a["type"] == "ENVELOPE"])

    def test_threshold_alert_is_placeholder(self):
        config = {"threshold": {"co_ppm": {"max": 25.0}}, "trend": {}}
        report = self.evaluate(sample(co_ppm=40.0), config=config)
        self.assertEqual(report["alerts"][0]["type"], "THRESHOLD")
        self.assertEqual(report["alerts"][0]["label"], "PLACEHOLDER")

    def test_trend_alert_from_history(self):
        config = {"threshold": {}, "trend": {"window_s": 60, "o2_percent": {"rise_per_min": 0.3}}}
        history = [sample(t=0.0, o2_percent=27.0), sample(t=30.0, o2_percent=27.5)]
        report = self.evaluate(sample(t=60.0, o2_percent=28.0), history, config)
        self.assertEqual([a["type"] for a in report["alerts"]], ["TREND"])

    def test_wording_never_predicts_fire(self):
        report = self.evaluate(sample(o2_percent=40.0, co_ppm=99.0), config=concern.load_alerts())
        for alert in report["alerts"]:
            self.assertNotIn("will", alert["message"].lower())
            self.assertNotIn("safe", alert["message"].lower())

    def test_reasoning_chain_has_sources(self):
        report = self.evaluate(sample(o2_percent=34.0))
        chain = report["reasoning"]
        self.assertEqual(report["source"], "SIMULATED")
        self.assertIn("o2_percent", report["envelope"])
        self.assertEqual(chain["matched_experiments"][0]["id"], 1)
        for finding in chain["measured_findings"]:
            self.assertIsNotNone(finding["source"])
        self.assertIn(chain["confidence"], {"HIGH", "MEDIUM", "LOW"})

    def test_drifting_stream_eventually_leaves_the_envelope(self):
        messages = telemetry.record("o2_drift_fan_slowing", seed=1, steps=600, noise=0)
        last = concern.evaluate(messages[-1], DUMMY_CORPUS, "solid", messages[:-1], NO_ALERT_LIMITS)
        self.assertIn("ENVELOPE", [a["type"] for a in last["alerts"]])


if __name__ == "__main__":
    unittest.main()
