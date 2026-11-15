import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence, export


class TestExport(unittest.TestCase):

    def setUp(self):
        self.rows = export.rows(helpers.sample_corpus())   # DUMMY samples

    def test_columns_and_originals(self):
        self.assertEqual(len(self.rows), 2)
        self.assertEqual(list(self.rows[0]), export.COLUMNS)
        second = self.rows[1]
        self.assertEqual((second["flow_original"], second["flow_unit_original"], second["flow_cm_s"]),
                         (0.2, "m/s", 20.0))

    def test_missing_is_empty_not_zero(self):
        first, second = self.rows
        self.assertFalse(first["is_missing"])
        self.assertEqual(second["pressure_kpa"], "")
        self.assertTrue(second["is_missing"])
        self.assertEqual(second["uncertainty"], "")

    def test_filter_by_acronym(self):
        corpus = helpers.sample_corpus()
        self.assertEqual(export.rows(corpus, ["DUMMY-B"]), [])
        with self.assertRaises(ValueError):
            export.rows(corpus, ["NOPE"])

    def test_csv_and_json(self):
        parsed = list(csv.DictReader(io.StringIO(export.to_csv(self.rows))))
        self.assertEqual(parsed[1]["is_missing"], "true")
        self.assertEqual(parsed[1]["pressure_kpa"], "")
        self.assertEqual(json.loads(export.to_json(self.rows))[1]["is_missing"], True)

    def test_xlsx_parts_and_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = export.to_xlsx(self.rows, Path(tmp) / "runs.xlsx")
            with zipfile.ZipFile(path) as book:
                names = set(book.namelist())
                workbook = book.read("xl/workbook.xml").decode("utf-8")
                readme = book.read("xl/worksheets/sheet2.xml").decode("utf-8")
                data = book.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertTrue({"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                         "xl/_rels/workbook.xml.rels", "xl/worksheets/sheet1.xml",
                         "xl/worksheets/sheet2.xml"} <= names)
        self.assertIn('name="README"', workbook)
        self.assertIn("DERIVED", readme)
        self.assertIn("A-02", data)


if __name__ == "__main__":
    unittest.main()
