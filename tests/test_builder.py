import json
import unittest
from unittest import mock

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import builder, evidence, gaps
from test_research import dummy_corpus

DUMMY_RULES = [
    {"id": "DUMMY-1", "text": "DUMMY rule for the atmosphere.", "source": "DUMMY standard", "page": "1",
     "applies_to": ["atmosphere"]},
    {"id": "DUMMY-2", "text": "DUMMY rule for fabric.", "source": "DUMMY standard", "page": "2",
     "applies_to": ["fabric"]},
]


def corpus():
    return helpers.sample_corpus()


class TestRules(helpers.TempFiles, unittest.TestCase):

    def test_shipped_rules_file_is_empty(self):
        self.assertEqual(builder.load_rules(), [])

    def test_rule_without_citation_is_refused(self):
        path = self.write("rules.json", json.dumps({"rules": [{"id": "DUMMY-X", "text": "DUMMY"}]}))
        with self.assertRaisesRegex(ValueError, "DUMMY-X.*source, page"):
            builder.load_rules(path)


class TestPresets(unittest.TestCase):

    def test_presets_set_gravity_and_name_a_source(self):
        found = builder.presets()
        self.assertEqual(list(found), ["leo_iss", "lunar_surface", "mars_transit", "mars_surface", "custom"])
        self.assertEqual(found["lunar_surface"]["gravity_g"], 0.165)
        for preset in found.values():
            self.assertIn("atmosphere_source", preset)
            self.assertIn("gravity_source", preset)

    def test_preset_gravity_is_used_and_custom_gravity_is_typed(self):
        clean, errors = builder.validate({"preset": "mars_surface", "gravity_g": 0.9})
        self.assertEqual((clean["gravity_g"], errors), (0.378, {}))
        clean, _ = builder.validate({"preset": "custom", "gravity_g": "0.5"})
        self.assertEqual(clean["gravity_g"], 0.5)


class TestValidation(unittest.TestCase):

    def test_empty_form_works_and_everything_is_not_evaluated(self):
        result = builder.check({}, corpus(), rules=[])
        self.assertTrue(result["valid"])
        row = result["table"][0]
        self.assertEqual(row["material"], builder.ANY_MATERIAL)
        for axis in ("o2_percent", "pressure", "gravity", "material_class", "pillar"):
            self.assertEqual(row[axis]["state"], "NOT_EVALUATED", axis)
        self.assertIsNone(result["derived"]["o2_partial_kpa"])
        self.assertIsNone(row["combination"][0]["class"])

    def test_none_and_junk_form_do_not_crash(self):
        self.assertTrue(builder.check(None, corpus(), rules=[])["valid"])
        self.assertFalse(builder.check({"materials": 5}, corpus(), rules=[])["valid"])

    def test_invalid_values_give_messages_and_skip_the_engine(self):
        form = {"o2_percent": "120", "pressure": "0", "flow_min": "9", "flow_max": "3",
                "pressure_unit": "bar", "preset": "jupiter"}
        with mock.patch.object(gaps, "analyze", side_effect=AssertionError("engine called")) as analyze:
            result = builder.check(form, corpus(), rules=[])
        analyze.assert_not_called()
        self.assertFalse(result["valid"])
        self.assertEqual(set(result["errors"]), {"o2_percent", "pressure", "flow_max", "pressure_unit", "preset"})
        self.assertIn("between 0 and 100", result["errors"]["o2_percent"])
        self.assertIn("greater than 0", result["errors"]["pressure"])
        self.assertIn("at least flow min", result["errors"]["flow_max"])

    def test_text_in_a_number_field(self):
        _, errors = builder.validate({"o2_percent": "lots"})
        self.assertEqual(errors, {"o2_percent": "O2 must be a number."})

    def test_o2_partial_pressure_is_derived(self):
        result = builder.check({"o2_percent": 34, "pressure": 8.2, "pressure_unit": "psi"}, corpus(), rules=[])
        self.assertAlmostEqual(result["derived"]["o2_partial_kpa"], 0.34 * 8.2 * 6.894757, places=2)
        self.assertEqual(result["derived"]["label"], "DERIVED")
        self.assertEqual(result["inputs"]["label"], "HYPOTHETICAL")


class TestOutputs(unittest.TestCase):

    FORM = {"preset": "lunar_surface", "o2_percent": 34, "pressure": 8.2, "pressure_unit": "psi",
            "flow_min": 5, "flow_max": 20, "materials": ["plastic", "unobtainium"], "pillar": "all",
            "mission_duration": "30 days"}

    def test_unindexed_material_returns_no_indexed_data(self):
        result = builder.check(self.FORM, corpus(), rules=[])
        rows = {row["material"]: row for row in result["table"]}
        self.assertEqual(rows["unobtainium"]["material_class"]["class"], "NO_INDEXED_DATA")
        self.assertFalse(rows["unobtainium"]["in_index"])
        self.assertTrue(rows["plastic"]["in_index"])

    def test_flow_range_is_checked_at_both_ends(self):
        row = builder.check(self.FORM, corpus(), rules=[])["table"][0]
        self.assertEqual([(f["at"], f["value"]) for f in row["flow"]], [("flow_min", 5.0), ("flow_max", 20.0)])
        self.assertEqual(len(row["combination"]), 2)

    def test_hints_for_each_numeric_field(self):
        hints = builder.check(self.FORM, corpus(), rules=[])["hints"]
        self.assertEqual(set(hints), {"o2_percent", "pressure", "gravity_g", "flow_min", "flow_max"})
        self.assertEqual(hints["gravity_g"]["class"], "ONE_SIDED")  # DUMMY data is all at 0 g

    def test_nearest_evidence_has_a_source(self):
        for row in builder.check(self.FORM, corpus(), rules=[])["table"]:
            self.assertTrue(row["nearest"]["source"])

    def test_proposals_are_labelled(self):
        proposals = builder.check(self.FORM, corpus(), rules=[])["proposals"]
        self.assertTrue(proposals)
        for proposal in proposals:
            self.assertEqual(proposal["label"], "PROPOSAL")
            self.assertTrue(proposal["text"].startswith("PROPOSAL: "))

    def test_material_proposal_never_says_zero_runs(self):
        for material in ("liquid fuel", "unobtainium", "plastic"):
            proposals = builder.check(dict(self.FORM, materials=[material]), corpus(), rules=[])["proposals"]
            for proposal in proposals:
                self.assertNotIn("only 0", proposal["text"])
                if proposal["axis"] == "material_class":
                    self.assertNotIn("run(s)", proposal["text"])

    def test_design_notes_only_with_a_source(self):
        result = builder.check(dict(self.FORM, materials=["Nomex fabric"]), corpus(), rules=DUMMY_RULES)
        notes = {n["subject"]: n["guidance"] for n in result["design_notes"]}
        self.assertEqual([g["id"] for g in notes["atmosphere"]], ["DUMMY-1"])
        self.assertEqual([g["id"] for g in notes["material Nomex fabric"]], ["DUMMY-2"])
        empty = builder.check(self.FORM, corpus(), rules=[])["design_notes"]
        self.assertTrue(all(n["guidance"] == "no sourced guidance" for n in empty))

    def test_mission_duration_does_not_change_results(self):
        short = builder.check(dict(self.FORM, mission_duration="3 days"), corpus(), rules=[])
        long = builder.check(dict(self.FORM, mission_duration="3 years"), corpus(), rules=[])
        self.assertEqual(short["table"], long["table"])
        self.assertEqual(long["mission_duration"], "3 years")

    def test_never_says_safe(self):
        text = json.dumps(builder.check(self.FORM, dummy_corpus(), rules=[])).lower()
        self.assertNotIn("safe", text)

    def test_options_list_indexed_material_classes(self):
        found = builder.options(corpus())
        categories = [m["category"] for m in found["materials"]]
        self.assertIn("plastic", categories)
        self.assertEqual(found["pillars"], ["all", "prevention", "detection", "suppression"])

    def test_class_names_are_kept_as_picked(self):
        self.assertEqual(gaps.category_key("gas fuel"), "gas fuel")
        self.assertEqual(gaps.category_key("liquid fuel"), "liquid fuel")
        self.assertEqual(gaps.category_key("PMMA sheet"), "plastic")


if __name__ == "__main__":
    unittest.main()
