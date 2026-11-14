import json
import unittest

from helpers import TempFiles, dummy_sheet

from pyra import db, paths
from pyra.loader import load_folder, load_sheet


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


class TestLoader(TempFiles, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.conn = db.create(":memory:")

    def test_samples_load_and_share_investigations(self):
        results = load_folder(self.conn, paths.SAMPLES)
        self.assertTrue(all(not errors for errors, _ in results.values()))
        self.assertEqual(count(self.conn, "investigations"), 2)  # two of the sheets are DUMMY-A
        self.assertEqual(count(self.conn, "publications"), 3)
        self.assertEqual(count(self.conn, "test_runs"), 2)

    def test_original_and_converted_values_are_both_kept(self):
        load_sheet(self.conn, dummy_sheet("dummy_b.json"), "b.json")
        row = self.conn.execute("""SELECT * FROM measurements
                                   WHERE quantity = 'pressure' AND bound = 'max'""").fetchone()
        self.assertEqual((row["original_value"], row["original_unit"]), (14.7, "psi"))
        self.assertEqual((row["normalized_value"], row["normalized_unit"]), (101.352932, "kPa"))

    def test_missing_is_null_never_zero(self):
        load_sheet(self.conn, dummy_sheet("dummy_a2.json"), "a2.json")
        row = self.conn.execute("""SELECT * FROM measurements
                                   WHERE quantity = 'o2_percent' AND bound = 'min'""").fetchone()
        self.assertIsNone(row["original_value"])
        self.assertIsNone(row["normalized_value"])
        self.assertEqual(row["is_missing"], 1)

    def test_rejected_sheet_stores_nothing(self):
        sheet = dummy_sheet()
        sheet["source"] = {"title": "no link", "url": None, "ntrs_id": None}
        errors, _ = load_sheet(self.conn, sheet, "bad.json")
        self.assertTrue(errors)
        self.assertEqual(count(self.conn, "investigations"), 0)

    def test_broken_file_is_reported_not_crashed(self):
        self.write("broken.json", "{ not json")
        self.write("wrong_shape.json", json.dumps({**dummy_sheet(), "conditions": "oops"}))
        results = load_folder(self.conn, self.folder)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(errors for errors, _ in results.values()))
        self.assertEqual(count(self.conn, "investigations"), 0)


if __name__ == "__main__":
    unittest.main()
