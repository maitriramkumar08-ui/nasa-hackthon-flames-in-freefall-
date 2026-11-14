import unittest

from helpers import dummy_sheet

from pyra.factsheet import check_factsheet


class TestFactsheet(unittest.TestCase):

    def test_good_sheet_has_no_errors(self):
        errors, _ = check_factsheet(dummy_sheet())
        self.assertEqual(errors, [])

    def test_no_source_is_rejected(self):
        sheet = dummy_sheet()
        sheet["source"] = {"title": "something", "url": None, "ntrs_id": None}
        errors, _ = check_factsheet(sheet)
        self.assertIn("source needs a url or an ntrs_id", errors)

    def test_unchecked_sheet_is_rejected(self):
        sheet = dummy_sheet()
        sheet["_review"]["checked_by"] = ""
        sheet["_review"]["prompt12_passed"] = False
        errors, _ = check_factsheet(sheet)
        self.assertEqual(len(errors), 2)

    def test_min_above_max_is_rejected(self):
        sheet = dummy_sheet()
        sheet["conditions"]["o2_percent"].update(min=30, max=21)
        errors, _ = check_factsheet(sheet)
        self.assertTrue(any("bigger than max" in e for e in errors))

    def test_unknown_unit_and_missing_page_are_warnings(self):
        sheet = dummy_sheet()
        sheet["conditions"]["pressure"].update(unit="bananas", page=None)
        errors, warnings = check_factsheet(sheet)
        self.assertEqual(errors, [])
        self.assertTrue(any("not recognised" in w for w in warnings))
        self.assertTrue(any("no page" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
