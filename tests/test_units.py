import unittest

import helpers  # noqa: F401  (sets up the import path)

from pyra.units import convert, normalize


class TestConvert(unittest.TestCase):

    def test_pressure(self):
        self.assertEqual(convert(1, "atm", "kPa"), 101.325)
        self.assertEqual(convert(10.2, "psi", "kPa"), 70.326524)
        self.assertEqual(convert(1000, "Pa", "kPa"), 1)

    def test_speed_length_time(self):
        self.assertEqual(convert(0.2, "m/s", "cm/s"), 20)
        self.assertEqual(convert(25, "cm/s", "m/s"), 0.25)
        self.assertEqual(convert(3, "cm", "mm"), 30)
        self.assertEqual(convert(250, "ms", "s"), 0.25)

    def test_temperature_both_ways(self):
        self.assertEqual(convert(25, "C", "K"), 298.15)
        self.assertEqual(convert(273.15, "K", "°C"), 0)

    def test_refuses_nonsense(self):
        with self.assertRaises(ValueError):
            convert(1, "psi", "cm/s")
        with self.assertRaises(ValueError):
            convert(1, "furlong", "m")


class TestNormalize(unittest.TestCase):

    def test_missing_stays_missing_not_zero(self):
        self.assertEqual(normalize(None, "kPa", "pressure"), (None, None, "missing"))

    def test_text_is_not_guessed(self):
        value, _, method = normalize("microgravity", None, "gravity")
        self.assertIsNone(value)
        self.assertIn("text", method)

    def test_wrong_kind_of_unit(self):
        value, _, method = normalize(30, "kPa", "o2")
        self.assertIsNone(value)
        self.assertIn("expected o2", method)

    def test_converts_and_says_how(self):
        self.assertEqual(normalize(14.7, "psi", "pressure"), (101.352932, "kPa", "psi -> kPa"))
        self.assertEqual(normalize(21, "%", "o2"), (21.0, "%", "unchanged"))


if __name__ == "__main__":
    unittest.main()
