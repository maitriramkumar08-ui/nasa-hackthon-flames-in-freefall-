import helpers  # noqa: F401

import json
import re
import threading
import time
import unittest
from urllib.request import Request, urlopen

from pyra import evidence, server
from pyra.agents import llm, runs, team, tools
from pyra.agents.ctx import OfflineLLM

LUNAR = {"preset": "lunar_surface", "materials": ["PMMA", "cotton"], "flow_speed": 10, "pilot_mode": "shadow"}


def corpus():
    return helpers.sample_corpus()


def approve_all(agent, payload):
    return {"decision": "approve", "ids": []}


class FakeModel:
    """A ChatLLM transport that always answers with the same text."""

    def __init__(self, text):
        self.text, self.bodies = text, []

    def __call__(self, body):
        self.bodies.append(body)
        return {"choices": [{"message": {"content": self.text}}]}


class TeamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus()
        cls.events = []
        cls.state = team.run_team({"mode": "full", "scenario": LUNAR}, cls.corpus, sink=cls.events.append)

    def test_every_agent_in_the_full_route_ran_and_the_reporter_wrote_a_briefing(self):
        for agent in team.MODE_ROUTES["full"] + ["skeptic"]:
            self.assertIn(agent, self.state["done"])
        self.assertIn("headline", self.state["report"])
        self.assertTrue(self.state["report"]["markdown"].startswith("# "))

    def test_skeptic_rejects_the_first_draft_at_partial_gravity_and_approves_the_second(self):
        history = self.state["ranking"]["history"]
        self.assertGreaterEqual(len(history), 2)
        self.assertGreater(history[0]["measured"], 0)
        self.assertTrue(self.state["review"]["approved"])
        self.assertEqual(self.state["done"].count("skeptic"), len(history))

    def test_final_claims_are_labelled_cited_and_never_overclaim(self):
        for claim in self.state["ranking"]["claims"]:
            self.assertIn(claim["label"], tools.LABELS)
            if claim["label"] == "MEASURED":
                self.assertTrue(claim["citations"])
            if claim["kind"] == "material":
                self.assertIn("not directly measured", claim["text"])

    def test_no_output_calls_anything_safe_or_unsafe(self):
        text = json.dumps(self.state, default=str)
        self.assertIsNone(re.search(r"\b(un)?safe\b", text, re.I))

    def test_events_bracket_every_node(self):
        starts = [e["agent"] for e in self.events if e["type"] == "node_start"]
        ends = [e["agent"] for e in self.events if e["type"] == "node_end"]
        self.assertEqual(starts, ends)
        self.assertEqual(starts[0], "supervisor")
        self.assertEqual(starts[-1], "reporter")

    def test_shadow_mode_leaves_recommendations_unreviewed(self):
        recs = self.state["actions"]["recommendations"]
        self.assertTrue(recs)
        self.assertTrue(all(r["status"] == "unreviewed" for r in recs))

    def test_not_real_corpus_is_flagged(self):
        self.assertTrue(self.state["corpus"]["not_real"])
        codes = {i["code"] for i in self.state["review"]["issues"]}
        self.assertIn("NOT_REAL_DATA", codes)


class RoutingTest(unittest.TestCase):
    def test_gaps_mode_runs_only_its_route(self):
        state = team.run_team({"mode": "gaps", "scenario": LUNAR}, corpus())
        self.assertEqual(state["done"], ["librarian", "mission_profiler", "gap_hunter"])
        self.assertIsNotNone(state["gaps"]["combination"])

    def test_custom_route_adds_what_it_depends_on(self):
        self.assertEqual(team.normalise(["skeptic"]), ["librarian", "mission_profiler", "evidence_ranker"])
        self.assertEqual(team.normalise(["nobody"]), [])

    def test_broken_agent_does_not_end_the_run(self):
        original = team.FUNCTIONS["physicist"]
        team.FUNCTIONS["physicist"] = lambda state, ctx: 1 / 0
        try:
            state = team.run_team({"mode": "evidence", "scenario": LUNAR}, corpus())
        finally:
            team.FUNCTIONS["physicist"] = original
        self.assertIn("report", state)
        self.assertTrue(any(m["kind"] == "warning" and "physicist failed" in m["text"] for m in state["messages"]))

    def test_approval_marks_only_the_chosen_recommendations(self):
        scen = dict(LUNAR, pilot_mode="approve")
        state = team.run_team({"mode": "full", "scenario": scen}, corpus(),
                              approver=lambda a, p: {"decision": "approve", "ids": [p["actions"][0]["id"]]})
        statuses = [r["status"] for r in state["actions"]["recommendations"]]
        self.assertEqual(statuses[0], "approved")
        self.assertTrue(all(s == "rejected" for s in statuses[1:]))

    def test_without_a_reviewer_nothing_is_approved(self):
        state = team.run_team({"mode": "full", "scenario": dict(LUNAR, pilot_mode="approve")}, corpus())
        self.assertEqual(state["actions"]["approved_ids"], [])


class ToolsTest(unittest.TestCase):
    def test_typed_values_win_over_the_preset_and_are_hypothetical(self):
        profile = tools.mission_profile({"preset": "lunar_surface", "o2_percent": 30}, corpus())
        self.assertEqual(profile["scenario"]["o2_percent"], 30)
        self.assertEqual(profile["scenario"]["gravity"], 0.165)
        o2 = next(v for v in profile["values"] if v["field"] == "O2")
        self.assertEqual((o2["source"], o2["label"]), ("typed by you", "HYPOTHETICAL"))
        self.assertTrue(profile["unverified_sources"])

    def test_flame_regime_needs_gravity_and_names_its_assumptions(self):
        self.assertEqual(tools.flame_regime(None, 10)["state"], "NOT_EVALUATED")
        found = tools.flame_regime(0.0, 10)
        self.assertEqual(found["regime"], "forced")
        self.assertEqual(found["assumptions"]["label"], "ILLUSTRATIVE")

    def test_incidents_are_interpretation_and_say_what_was_not_evaluated(self):
        profile = tools.mission_profile({"preset": "lunar_surface", "materials": ["cotton"]}, corpus())
        cases = tools.match_incidents(profile, {})
        self.assertEqual({c["id"] for c in cases}, {"apollo1", "apollo13", "mir"})
        self.assertTrue(all(c["label"] == "INTERPRETATION" and c["not_evaluated"] for c in cases))


class RuleCheckTest(unittest.TestCase):
    def test_rule_problems(self):
        self.assertEqual(llm.rule_problems("PMMA was tested at 21 % O2.", {"o2": 21}), [])
        self.assertTrue(llm.rule_problems("PMMA was tested at 37 % O2.", {"o2": 21}))
        self.assertTrue(llm.rule_problems("Nomex is safe here.", {}))
        self.assertTrue(llm.rule_problems("These results apply to the Moon.", {}))
        self.assertEqual(llm.rule_problems("These results do not apply to the Moon.", {}), [])
        self.assertTrue(llm.rule_problems("The cotton would ignite.", {}))

    def test_model_text_that_breaks_a_rule_is_replaced_by_the_fallback(self):
        model = llm.ChatLLM("key", post=FakeModel("Cotton is unsafe at 99.5 % oxygen."))
        self.assertEqual(model.think("x", "sys", {"o2": 34}, "scripted"), "scripted")
        self.assertTrue(model.rejected)

    def test_model_text_that_passes_is_kept(self):
        model = llm.ChatLLM("key", post=FakeModel("The scenario sits at 34 % oxygen, not directly measured."))
        self.assertIn("not directly measured", model.think("x", "sys", {"o2": 34}, "scripted"))

    def test_a_failing_model_falls_back_and_then_stops_being_called(self):
        def boom(body):
            raise OSError("offline")
        model = llm.ChatLLM("key", post=boom)
        for _ in range(5):
            self.assertEqual(model.think("x", "sys", {}, "scripted"), "scripted")
        self.assertEqual(model.calls, 0)

    def test_get_llm_is_offline_without_a_key(self):
        self.assertIsInstance(llm.get_llm(force_offline=True), OfflineLLM)

    def test_a_live_model_can_add_agents_but_not_remove_them(self):
        model = llm.ChatLLM("key", post=FakeModel('{"route": ["incident_analyst"], "why": "goal"}'))
        state = team.run_team({"mode": "gaps", "goal": "past fires?", "scenario": LUNAR}, corpus(), llm=model)
        self.assertIn("gap_hunter", state["done"])
        self.assertIn("incident_analyst", state["done"])


class ServerAgentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(corpus(), port=0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, path, body):
        request = Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def get(self, path):
        with urlopen(self.base + path, timeout=30) as response:
            return response.read().decode("utf-8")

    def test_info_lists_the_team(self):
        info = json.loads(self.get("/api/agents"))
        self.assertEqual([a["id"] for a in info["agents"]], team.AGENT_IDS)

    def test_run_stream_approve_and_ask(self):
        run_id = self.post("/api/agents/run", {"mode": "full", "scenario": dict(LUNAR, pilot_mode="approve")})["run_id"]
        for _ in range(100):
            snap = json.loads(self.get(f"/api/agents/state/{run_id}"))
            if snap["waiting"]:
                break
            time.sleep(0.05)
        self.assertEqual(snap["waiting"]["agent"], "safety_officer")
        self.assertEqual(self.post(f"/api/agents/resume/{run_id}", {"decision": "approve", "ids": []}), {"ok": True})
        events = [json.loads(line[6:]) for line in self.get(f"/api/agents/stream/{run_id}").splitlines()
                  if line.startswith("data: ")]
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "run_start")
        self.assertIn("interrupt", types)
        self.assertEqual(types[-1], "done")
        final = events[-1]["state"]
        self.assertTrue(all(r["status"] == "approved" for r in final["actions"]["recommendations"]))
        answer = self.post("/api/agents/ask", {"agent": "skeptic", "run_id": run_id})
        self.assertIn("Skeptic", answer["answer"])

    def test_unknown_run_and_bad_mode(self):
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as caught:
            self.get("/api/agents/state/nope")
        self.assertEqual(caught.exception.code, 404)
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/agents/run", {"mode": "everything"})
        self.assertEqual(caught.exception.code, 400)

    def test_stop_ends_a_waiting_run(self):
        run = runs.start({"mode": "full", "scenario": dict(LUNAR, pilot_mode="approve")}, corpus(), OfflineLLM())
        for _ in range(100):
            if run.waiting:
                break
            time.sleep(0.05)
        self.post(f"/api/agents/stop/{run.id}", {})
        for _ in range(100):
            if run.finished:
                break
            time.sleep(0.05)
        self.assertEqual(run.events[-1]["type"], "error")


if __name__ == "__main__":
    unittest.main()
