import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import assistant

CONTEXT = [{"id": "S1", "text": "DUMMY - NOT REAL DATA. Flame spread rose from 5 to 20 cm/s flow.",
            "investigation": "DUMMY-A", "source_id": "dummy_a.txt", "page": 3, "section": "Results",
            "score": 0.9}]

GOOD = """(a) What the sources report (MEASURED)
Flame spread rose as flow went from 5 to 20 cm/s [S1].
(b) What this means for the scenario (INTERPRETATION)
Your flow is bounded by the tested range.
(c) Limits and gaps
Lunar gravity was not directly measured.
Confidence: low. Only one DUMMY source."""


def fake(reply):
    calls = []

    def ask(system, user):
        calls.append((system, user))
        return reply
    return ask, calls


class TestAssistant(unittest.TestCase):

    def test_prompt_uses_word_limit_from_decisions(self):
        self.assertIn(f"under {assistant.word_limit()} words", assistant.system_prompt())

    def test_messages_follow_input_format(self):
        messages = assistant.build_messages({"o2_percent": 30}, "engineer", {"ranking": []}, CONTEXT, "Why?")
        for part in ("SCENARIO:", "AUDIENCE: engineer", "TOOL_RESULTS:", "CONTEXT:\n[S1]", "QUESTION:\nWhy?"):
            self.assertIn(part, messages["user"])
        with self.assertRaises(ValueError):
            assistant.build_messages({}, "child", {}, CONTEXT, "Why?")

    def test_no_context_never_asks_the_model(self):
        ask, calls = fake(GOOD)
        reply = assistant.answer("anything about comets?", [], ask_model=ask)
        self.assertTrue(reply["text"].startswith("No data found in the indexed sources."))
        self.assertEqual(calls, [])

    def test_good_answer_passes(self):
        ask, calls = fake(GOOD)
        reply = assistant.answer("How does flow matter?", CONTEXT, ask_model=ask)
        self.assertEqual(reply["problems"], [])
        self.assertEqual(reply["label"], "INTERPRETATION")
        self.assertEqual(len(calls), 1)

    def test_bad_answer_is_flagged(self):
        bad = """(a) What the sources report (MEASURED)
Flame spread doubled at 40 cm/s [S7].
Paper burns fast.
(b) INTERPRETATION
The material is safe and these results apply to the Moon."""
        ask, _ = fake(bad)
        problems = " | ".join(assistant.answer("Q?", CONTEXT, ask_model=ask)["problems"])
        for expected in ("without a citation", "[S7]", "Number 40", "'safe'", "Moon or Mars", "Confidence"):
            self.assertIn(expected, problems)

    def test_word_limit(self):
        problems = assistant.check_answer(GOOD + " word" * 300, ["S1"], CONTEXT[0]["text"])
        self.assertTrue(any("word limit" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
