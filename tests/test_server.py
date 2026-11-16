import helpers  # noqa: F401

import importlib.util
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pyra import evidence, server

ENGINES_READY = all(importlib.util.find_spec(f"pyra.{name}") for name in ("ranking", "gaps"))


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(helpers.sample_corpus(), port=0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path):
        with urlopen(self.base + path, timeout=10) as response:
            return response.headers.get("Content-Type"), response.read()

    def post(self, path, body):
        request = Request(self.base + path, data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def test_investigations_come_from_the_dummy_corpus(self):
        _, body = self.get("/api/investigations")
        acronyms = [inv["acronym"] for inv in json.loads(body)]
        self.assertTrue(acronyms)

    @unittest.skipUnless(ENGINES_READY, "pyra.ranking or pyra.gaps not written yet")
    def test_coverage_returns_runs_top_five_and_gaps(self):
        found = self.post("/api/coverage", {"o2_percent": 30, "pressure": 10, "pressure_unit": "psi",
                                            "flow_speed": 10, "gravity_g": 0.16})
        self.assertEqual(found["scenario"]["label"], "HYPOTHETICAL")
        self.assertAlmostEqual(found["scenario"]["pressure"], 68.95, places=1)
        self.assertLessEqual(len(found["ranked"]), 5)
        self.assertIn("axes", found["gaps"])
        self.assertTrue(found["runs"])

    def test_static_page_is_served(self):
        content_type, body = self.get("/")
        self.assertTrue(content_type.startswith("text/html"))
        self.assertIn(b"PYRA", body)
        content_type, _ = self.get("/app.js")
        self.assertIn("javascript", content_type)

    def test_page_has_six_tabs_and_no_compare_tab(self):
        _, body = self.get("/")
        page = body.decode()
        for tab in ("explore", "ops", "builder", "agents", "assistant", "demo"):
            self.assertIn(f'data-tab="{tab}"', page)
        self.assertEqual(page.count('data-tab="'), 6)
        self.assertIn('href="/roundtable.html"', page)
        self.assertIn('id="ask-panel"', page)
        self.assertIn('id="compare-panel"', page)       # compare is a side panel now
        self.assertNotIn("explore/compare", page)       # not a tab or sub-view
        self.assertNotIn('class="badge', page)          # no provenance tags in the UI
        self.assertIn("not real sensors", page)         # Ops still says its readings are a demo

    def test_weakness_names_the_dominant_weakness(self):
        _, body = self.get("/api/research/weakness")
        rows = json.loads(body)
        self.assertTrue(rows)
        self.assertTrue(all("dominant_weakness" in row for row in rows))

    def test_opportunities_for_one_scenario(self):
        found = self.post("/api/research/opportunities", {"scenario": {"o2_percent": 34, "gravity_g": 0.16}})
        self.assertTrue(found)
        self.assertTrue(all(row["label"] == "DERIVED" for row in found))
        self.assertNotIn("pressure", {row["axis"] for row in found})  # unset, so not a gap

    def test_backtest_needs_numbers(self):
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/research/backtest", {"cutoff_year": "soon", "checks": [{}]})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        found = self.post("/api/research/backtest", {
            "cutoff_year": 2015, "years": {},
            "checks": [{"name": "c", "scenario": {"o2_percent": 34}, "should_flag": True}]})
        self.assertEqual(found["hits"] + found["misses"], 1)

    def test_compare_verdict_still_comes_from_the_engine(self):
        _, body = self.get("/api/investigations")
        acronyms = [inv["acronym"] for inv in json.loads(body)][:2]
        found = self.post("/api/compare", {"acronyms": acronyms})
        self.assertIn("comparable", found["verdict"])
        self.assertEqual(found["investigations"], acronyms)

    def test_ops_view_is_deterministic_and_labelled(self):
        body = {"scenario": "overheating_wire", "seed": 1, "steps": 100, "step": 90,
                "compartments": ["habitat", "lab"], "material_class": "solid"}
        first, second = self.post("/api/ops", body), self.post("/api/ops", body)
        self.assertEqual(first, second)
        self.assertEqual(first["label"], "SIMULATED")
        self.assertEqual(set(first["compartments"]), {"habitat", "lab"})
        self.assertIn("co_occurring", first["combined"])
        self.assertEqual(len(first["compartments"]["habitat"]["tiles"]), 6)

    def test_ops_unknown_scenario_is_a_400(self):
        with self.assertRaises(HTTPError) as caught:
            self.post("/api/ops", {"scenario": "meteor_strike"})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_builder_options_and_empty_check(self):
        _, body = self.get("/api/builder/options")
        options = json.loads(body)
        self.assertIn("Check what NASA combustion evidence covers", options["purpose"])
        self.assertEqual(options["presets"][-1]["id"], "custom")
        found = self.post("/api/builder/check", {})
        self.assertTrue(found["valid"])

    def test_builder_invalid_values_are_messages_not_errors(self):
        found = self.post("/api/builder/check", {"o2_percent": 140, "flow_min": 5, "flow_max": 1})
        self.assertFalse(found["valid"])
        self.assertEqual(set(found["errors"]), {"o2_percent", "flow_max"})
        self.assertNotIn("table", found)

    def test_files_outside_the_web_folder_are_refused(self):
        with self.assertRaises(HTTPError) as caught:
            self.get("/../server.py")
        caught.exception.close()
        self.assertEqual(caught.exception.code, 404)

    def test_bad_json_is_a_400_with_a_reason(self):
        request = Request(self.base + "/api/coverage", data=b"{not json")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("not valid JSON", json.loads(caught.exception.read())["error"])
        caught.exception.close()

    def test_missing_engine_is_a_503_naming_it(self):
        with self.assertRaises(server.MissingModule) as caught:
            server.engine("no_such_engine")
        self.assertIn("pyra.no_such_engine", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
