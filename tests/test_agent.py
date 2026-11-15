import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  (puts the project on sys.path)
from pyra import agent, evidence, server

SCENARIO = {"o2_percent": 30, "pressure": 70, "gravity_g": 0.16, "flow_speed": 10}
GOOD = ("MEASURED:\nDUMMY-A reports flame spread went up with flow [S1].\n\nINTERPRETATION:\nFlow matters here.\n\n"
        "Limits and gaps:\nOnly DUMMY data.\n\nConfidence: low, one passage.")


class Scripted:
    """Plays back fixed replies: first the tool calls, then one answer per begin/revise."""

    name = "scripted"

    def __init__(self, answers, calls=None):
        self.answers = list(answers)
        self.calls = calls or [{"id": "1", "name": "search_evidence", "input": {"query": "flame spread flow"}}]
        self.notes, self.results = [], []

    def begin(self, system, user, task):
        self.system = system
        return {"calls": self.calls, "text": ""}

    def reply(self, results):
        self.results.append(results)
        return {"calls": [], "text": self.answers.pop(0)}

    def revise(self, note):
        self.notes.append(note)
        return {"calls": [], "text": self.answers.pop(0)}


class Looping(Scripted):
    def reply(self, results):
        return {"calls": self.calls, "text": ""}


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = evidence.load(evidence.dummy_conn())

    def test_offline_answer_passes_its_own_checks(self):
        found = agent.run("How does flow change flame spread?", self.corpus, SCENARIO)
        self.assertTrue(found["passed"], found["problems"])
        self.assertEqual(found["planner"], "offline")
        tools = [step["tool"] for step in found["steps"]]
        self.assertEqual(tools, ["list_investigations", "search_evidence", "rank_investigations", "analyze_gaps"])
        self.assertIn("[S1]", found["answer"])
        self.assertIn("0.16 g scenario is not directly measured", found["answer"])

    def test_offline_compares_named_investigations(self):
        found = agent.run("Compare DUMMY-A and DUMMY-B flame", self.corpus, {}, "engineer")
        self.assertTrue(found["passed"], found["problems"])
        compare_step = [s for s in found["steps"] if s["tool"] == "compare_investigations"][0]
        self.assertEqual(compare_step["input"], {"acronyms": ["DUMMY-A", "DUMMY-B"]})
        self.assertIn("not directly comparable", found["answer"])

    def test_no_passage_means_no_data_whatever_the_planner_says(self):
        planner = Scripted([GOOD], calls=[{"id": "1", "name": "search_evidence", "input": {"query": "zebra"}}])
        found = agent.run("zebra", self.corpus, planner=planner)
        self.assertTrue(found["answer"].startswith("No data found"))
        self.assertEqual(found["context"], [])

    def test_bad_answer_gets_one_rewrite(self):
        bad = GOOD.replace("[S1]", "[S9]")
        planner = Scripted([bad, GOOD])
        found = agent.run("flame spread and flow", self.corpus, planner=planner)
        self.assertTrue(found["passed"])
        self.assertTrue(found["revised"])
        self.assertIn("[S9]", planner.notes[0])

    def test_answer_that_keeps_failing_is_withheld(self):
        invented = GOOD.replace("flow [S1]", "flow by 42 percent [S1]")
        found = agent.run("flame spread and flow", self.corpus, planner=Scripted([invented, invented]))
        self.assertFalse(found["passed"])
        self.assertIsNone(found["answer"])
        self.assertEqual(found["draft"], invented)
        self.assertTrue(any("42" in problem for problem in found["problems"]))

    def test_tool_errors_go_back_to_the_planner(self):
        calls = [{"id": "1", "name": "search_evidence", "input": {"query": "flame spread flow"}},
                 {"id": "2", "name": "compare_investigations", "input": {"acronyms": ["DUMMY-A"]}},
                 {"id": "3", "name": "launch_rocket", "input": {}}]
        planner = Scripted([GOOD], calls=calls)
        found = agent.run("flame spread and flow", self.corpus, planner=planner)
        errors = {result["id"]: result["error"] for result in planner.results[0]}
        self.assertEqual(errors, {"1": False, "2": True, "3": True})
        self.assertIn("at least two", found["steps"][1]["output"]["error"])

    def test_step_limit_stops_a_looping_planner(self):
        found = agent.run("flame spread and flow", self.corpus, planner=Looping([]), max_steps=3)
        self.assertEqual(found["stopped"], "stopped after 3 tool calls")
        self.assertFalse(found["passed"])

    def test_system_prompt_keeps_the_assistant_rules(self):
        planner = Scripted([GOOD])
        agent.run("flame spread and flow", self.corpus, planner=planner)
        self.assertIn("Never state or compute numbers", planner.system)
        self.assertIn("AGENT MODE", planner.system)

    def test_unknown_planner_and_audience_are_refused(self):
        with self.assertRaises(ValueError):
            agent.make_planner("gpt")
        with self.assertRaises(ValueError):
            agent.run("flame", self.corpus, audience="child")


class FakeMessages:
    """Stands in for client.beta.messages: first a tool call, then a final answer."""

    def __init__(self):
        self.requests = []

    def create(self, **request):
        self.requests.append(dict(request, messages=list(request["messages"])))
        if len(self.requests) == 1:
            content = [SimpleNamespace(type="tool_use", id="tu1", name="search_evidence", input={"query": "flame spread flow"})]
            return SimpleNamespace(stop_reason="tool_use", content=content)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=GOOD)])


class ClaudePlannerTest(unittest.TestCase):
    def setUp(self):
        errors = {name: type(name, (Exception,), {}) for name in
                  ("AuthenticationError", "RateLimitError", "APIStatusError", "APIConnectionError")}
        patcher = mock.patch.dict(sys.modules, {"anthropic": SimpleNamespace(**errors)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.messages = FakeMessages()
        client = SimpleNamespace(beta=SimpleNamespace(messages=self.messages))
        self.planner = agent.ClaudePlanner(model="claude-opus-5-5", client=client)

    def test_tool_results_go_back_as_tool_result_blocks(self):
        found = agent.run("flame spread and flow", evidence.load(evidence.dummy_conn()), planner=self.planner)
        self.assertTrue(found["passed"], found["problems"])
        second = self.messages.requests[1]
        self.assertEqual(second["model"], "claude-opus-5-5")
        self.assertEqual(second["messages"][1]["role"], "assistant")
        result = second["messages"][2]["content"][0]
        self.assertEqual((result["type"], result["tool_use_id"], result["is_error"]), ("tool_result", "tu1", False))
        self.assertIn("S1", json.loads(result["content"])["passages"][0]["id"])

    def test_refusal_is_reported_not_shown(self):
        self.messages.create = lambda **request: SimpleNamespace(stop_reason="refusal", content=[])
        with self.assertRaises(agent.PlannerError):
            agent.run("flame", evidence.load(evidence.dummy_conn()), planner=self.planner)


class AgentEndpointTest(unittest.TestCase):
    def setUp(self):
        httpd = server.make_server(evidence.load(evidence.dummy_conn()), port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(self, path, body):
        request = urllib.request.Request(self.base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_agent_endpoint_answers_offline(self):
        status, found = self.post("/api/agent", {"question": "flame spread with flow", "scenario": SCENARIO,
                                                 "planner": "offline"})
        self.assertEqual(status, 200)
        self.assertTrue(found["passed"], found["problems"])
        self.assertEqual(found["context"][0]["id"], "S1")

    def test_agent_endpoint_rejects_an_empty_question(self):
        status, found = self.post("/api/agent", {"question": "  "})
        self.assertEqual(status, 400)
        self.assertIn("question", found["error"])

    def test_status_lists_the_tools(self):
        with urllib.request.urlopen(self.base + "/api/agent/status") as response:
            status = json.loads(response.read())
        self.assertEqual({tool["name"] for tool in status["tools"]},
                         {"search_evidence", "list_investigations", "rank_investigations",
                          "analyze_gaps", "compare_investigations"})


if __name__ == "__main__":
    unittest.main()
