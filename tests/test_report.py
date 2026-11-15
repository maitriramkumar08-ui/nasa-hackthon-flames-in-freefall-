import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import report

SCEN = {"o2_percent": 34.0, "pressure": 56.5, "flow_speed": 10.0, "gravity": 0.16,
        "temperature": None, "material": "DUMMY cotton", "fuel_phase": "solid",
        "pillar": "prevention", "scale": "bench", "outputs": ["flame spread"], "label": "HYPOTHETICAL"}

CORPUS = {"investigations": [{
    "id": 1, "acronym": "DUMMY-A", "name": "Dummy Alpha",
    "publications": [{"id": 7, "title": "DUMMY paper", "url": None, "ntrs_id": None}],
    "findings": [
        {"text": "DUMMY flame spread rose with oxygen.", "page_or_table": "p. 4", "type": "MEASURED", "source_id": 7},
        {"text": "DUMMY authors think radiation matters.", "page_or_table": "p. 5",
         "type": "AUTHOR_INTERPRETATION", "source_id": 7}],
    "notes": {"limitation": ["DUMMY only one sample thickness."]},
}], "runs": []}

RANKED = [{"investigation_id": 1, "acronym": "DUMMY-A", "name": "Dummy Alpha", "total": 0.72,
           "scores": {"atmosphere": 0.9, "flow": 0.5, "gravity": 0.3, "material": 1.0,
                      "objective": 1.0, "scale": 1.0, "measurement": None},
           "evidence_class": "direct", "unmatched": ["temperature"],
           "explanation": "DUMMY-A matches on material and oxygen.", "label": "DERIVED"}]

GAPS = {"axes": {
    "o2_percent": {"class": "DIRECTLY_TESTED", "distance": 0.0, "nearest_value": 34.0,
                   "tested_min": 21.0, "tested_max": 40.0, "runs_within": 3},
    "gravity": {"class": "BOUNDED", "distance": 0.16, "nearest_value": 0.0,
                "tested_min": 0.0, "tested_max": 1.0, "runs_within": 0},
    "pressure": {"class": "ONE_SIDED", "distance": 0.3, "nearest_value": 101.3,
                 "tested_min": 101.3, "tested_max": 101.3, "runs_within": 0}},
    "combination": {"class": "BOUNDED", "runs_matching": 0},
    "nearest_runs": [{"run_id": "R1", "acronym": "DUMMY-A", "distance": 0.4,
                      "source": {"title": "DUMMY paper"}}],
    "report": ["Gravity 0.16 g is bounded by tests at 0 g and 1 g."], "label": "DERIVED"}

COMPARISON = {"rows": [{"field": "hardware", "values": {"DUMMY-A": "duct", "DUMMY-B": "chamber"}, "same": False}],
              "verdict": {"comparable": False, "reasons": ["hardware differs"]},
              "can_conclude": ["both report flame spread"], "cannot_conclude": ["which spreads faster"]}


class TestReport(unittest.TestCase):

    def setUp(self):
        self.markdown = report.build(SCEN, RANKED, GAPS, COMPARISON, corpus=CORPUS)

    def test_every_line_is_cited_or_labelled(self):
        self.assertEqual(report.check(self.markdown), [])

    def test_check_catches_bare_lines(self):
        self.assertEqual(report.check(self.markdown + "\nOxygen makes fires worse.\n"),
                         ["Oxygen makes fires worse."])

    def test_sections_and_footer(self):
        for number in range(1, 9):
            self.assertIn(f"## {number}. ", self.markdown)
        self.assertTrue(self.markdown.rstrip().endswith(report.FOOTER))

    def test_only_measured_findings_with_page(self):
        self.assertIn("DUMMY flame spread rose with oxygen. [DUMMY-A, p. 4]", self.markdown)
        self.assertNotIn("radiation", self.markdown)

    def test_experiments_only_for_untested_axes(self):
        section = self.markdown.split("## 7.")[1].split("## 8.")[0]
        self.assertIn("PROPOSAL: test gravity at 0.16 g", section)
        self.assertIn("PROPOSAL: test pressure", section)
        self.assertNotIn("o2_percent", section)

    def test_missing_is_not_zero(self):
        self.assertIn("Temperature: not provided (HYPOTHETICAL)", self.markdown)

    def test_works_without_comparison_or_corpus(self):
        markdown = report.build(SCEN, RANKED, GAPS)
        self.assertEqual(report.check(markdown), [])
        self.assertIn("No references were passed", markdown)

    def test_html(self):
        page = report.to_html(self.markdown)
        self.assertIn("<h2>1. Scenario</h2>", page)
        self.assertIn("<th>Axis</th>", page)
        self.assertIn("<li>", page)
        self.assertIn(report.FOOTER, page)


if __name__ == "__main__":
    unittest.main()
