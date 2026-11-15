import helpers
import unittest

from helpers import dummy_sheet

from pyra import db, paths
from pyra.loader import load_folder, load_sheet
from pyra.quality import run_checks


class TestQuality(unittest.TestCase):

    def setUp(self):
        self.conn = db.create(":memory:")

    def test_dummy_samples_are_clean(self):
        load_folder(self.conn, helpers.SAMPLES)
        problems = {name: rows for name, rows in run_checks(self.conn).items() if rows}
        self.assertEqual(problems, {})

    def test_impossible_values_are_flagged(self):
        sheet = dummy_sheet()
        sheet["conditions"]["o2_percent"].update(min=15, max=120)
        sheet["conditions"]["pressure"].update(min=-5, max=101)
        load_sheet(self.conn, sheet, "a.json")
        results = run_checks(self.conn)
        self.assertEqual(len(results["O2 outside 0-100 %"]), 1)
        self.assertEqual(len(results["Negative pressure"]), 1)

    def test_same_paper_twice_is_flagged(self):
        load_sheet(self.conn, dummy_sheet(), "a.json")
        load_sheet(self.conn, dummy_sheet(), "a_copy.json")
        results = run_checks(self.conn)
        self.assertEqual(len(results["Same paper loaded twice"]), 1)
        self.assertEqual(len(results["Same finding twice"]), 1)


if __name__ == "__main__":
    unittest.main()
