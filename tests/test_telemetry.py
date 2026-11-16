import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import telemetry


class TestTelemetry(unittest.TestCase, helpers.TempFiles):

    def setUp(self):
        helpers.TempFiles.setUp(self)

    def test_same_seed_same_stream(self):
        self.assertEqual(telemetry.record("nominal", seed=7, steps=30),
                         telemetry.record("nominal", seed=7, steps=30))

    def test_different_seed_differs(self):
        self.assertNotEqual(telemetry.record("nominal", seed=1, steps=30),
                            telemetry.record("nominal", seed=2, steps=30))

    def test_every_message_is_labelled(self):
        for message in telemetry.record("overheating_wire", steps=10, compartment="node2"):
            self.assertEqual(message["source"], "SIMULATED")
            self.assertEqual(message["compartment"], "node2")
            self.assertEqual(message["scenario"], "overheating_wire")
            for channel in telemetry.CHANNELS:
                self.assertIn(channel, message)

    def test_stuck_sensor_is_constant(self):
        readings = {m["o2_percent"] for m in telemetry.record("stuck_sensor", seed=3, steps=50)}
        self.assertEqual(len(readings), 1)

    def test_o2_drifts_up_and_fan_slows(self):
        messages = telemetry.record("o2_drift_fan_slowing", steps=300, noise=0)
        self.assertGreater(messages[-1]["o2_percent"], messages[0]["o2_percent"] + 2)
        self.assertLess(messages[-1]["flow_cm_s"], messages[0]["flow_cm_s"])

    def test_smoke_stays_between_zero_and_one(self):
        for message in telemetry.record("overheating_wire", steps=400, dt=2.0):
            self.assertTrue(0.0 <= message["smoke_level"] <= 1.0)

    def test_replay_gives_back_the_recording(self):
        recording = telemetry.record("o2_drift_fan_slowing", seed=5, steps=20)
        path = self.folder / "demo.jsonl"
        telemetry.save(recording, path)
        self.assertEqual(list(telemetry.replay(path)), recording)

    def test_unknown_scenario(self):
        with self.assertRaises(ValueError):
            telemetry.record("meteor_strike")


if __name__ == "__main__":
    unittest.main()
