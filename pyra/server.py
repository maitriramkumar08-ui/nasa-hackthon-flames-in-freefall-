"""The PYRA web app: a small JSON API plus the static page in pyra/web/.

Standard library only (http.server), so there is nothing to install. The
corpus is loaded once at startup. The engines (ranking, gaps, compare, ...)
are imported inside each handler, so the server still starts while one of
them is missing; that endpoint then answers 503 and names the module.

    python -m pyra.server --port 8000
"""

import argparse
import importlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, evidence, paths

WEB = Path(__file__).resolve().parent / "web"
# The standalone 3D flame demo, served at /demo/ so one server runs everything.
DEMO = paths.ROOT / "demo"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
# Our own example names for the SIMULATED mission-control panel, not a real vehicle layout.
DEFAULT_COMPARTMENTS = "habitat,lab,node"


class MissingModule(Exception):
    pass


class BadRequest(Exception):
    pass


class PlannerFailed(Exception):
    pass


class NotFound(Exception):
    pass


def engine(name):
    """Import pyra.<name> now, or say clearly which module is not there yet."""
    try:
        return importlib.import_module(f"pyra.{name}")
    except ImportError as err:
        raise MissingModule(f"pyra.{name} is not available ({err})") from err


def load_corpus():
    """The verified evidence in data/pyra.db. There is no fallback data: an empty database serves empty."""
    if not paths.DATABASE.exists():
        raise SystemExit(f"{paths.DATABASE} does not exist. Run 'python -m pyra build' first.")
    corpus = evidence.load(db.connect(paths.DATABASE))
    if not corpus["investigations"]:
        print(f"{paths.DATABASE.name} holds no investigations yet. Add verified fact sheets to "
              f"{paths.VERIFIED} and run 'python -m pyra build'.")
    return corpus


def runs_for(corpus, scen):
    """Runs shown on the map: all of them, or one pillar if the scenario asks."""
    if not scen.get("pillar"):
        return corpus["runs"]
    return [run for run in corpus["runs"] if run["pillar"] == scen["pillar"]]


def comma_list(text):
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def coverage(corpus, body, query):
    scen = evidence.scenario(body)
    ranked = engine("ranking").rank(corpus, scen)
    return {"scenario": scen, "runs": runs_for(corpus, scen),
            "ranked": ranked[:5], "gaps": engine("gaps").analyze(corpus, scen)}


def compare(corpus, body, query):
    acronyms = body.get("acronyms") or []
    if len(acronyms) < 2:
        raise BadRequest("compare needs at least two acronyms")
    return engine("compare").compare(corpus, acronyms)


def report(corpus, body, query):
    scen = evidence.scenario(body.get("scenario") or {})
    ranked = engine("ranking").rank(corpus, scen)
    gap_result = engine("gaps").analyze(corpus, scen)
    acronyms = body.get("acronyms") or []
    comparison = engine("compare").compare(corpus, acronyms) if len(acronyms) >= 2 else None
    builder = engine("report")
    markdown = builder.build(scen, ranked, gap_result, comparison)
    return {"markdown": markdown, "html": builder.to_html(markdown)}


def telemetry(corpus, body, query):
    """The chosen scenario plays in the first compartment; the others run nominal for contrast."""
    sim = engine("telemetry")
    name = query.get("scenario", [""])[0] or "nominal"
    if name not in sim.SCENARIOS:
        raise BadRequest(f"unknown telemetry scenario '{name}', pick one of {sorted(sim.SCENARIOS)}")
    compartments = comma_list(query.get("compartments", [DEFAULT_COMPARTMENTS])[0])
    try:
        seed = int(query.get("seed", ["1"])[0])
        steps = int(query.get("steps", ["60"])[0])
        dt = float(query.get("dt", ["1"])[0])
    except ValueError as err:
        raise BadRequest(f"seed and steps must be whole numbers, dt a number ({err})") from err
    samples = []
    for number, compartment in enumerate(compartments):
        played = name if number == 0 else "nominal"
        samples.extend(sim.record(played, seed + number, steps, dt, compartment))
    samples.sort(key=lambda sample: sample["t"])
    return {"label": "SIMULATED", "scenarios": sorted(sim.SCENARIOS), "samples": samples}


def ops_view(corpus, body, query):
    """body: {scenario, seed, steps, dt, step, compartments: [..], material_class or
    material_classes: {compartment: class}, gravity_g}. Rebuilds the SIMULATED streams
    from the seed, so the same body always gives the same answer."""
    sim, ops = engine("telemetry"), engine("ops")
    name = body.get("scenario") or "nominal"
    if not isinstance(name, str) or name not in sim.SCENARIOS:
        raise BadRequest(f"unknown telemetry scenario '{name}', pick one of {sorted(sim.SCENARIOS)}")
    compartments = body.get("compartments") or comma_list(DEFAULT_COMPARTMENTS)
    if isinstance(compartments, str):
        compartments = comma_list(compartments)
    try:
        seed, steps, step = int(body.get("seed", 1)), int(body.get("steps", 60)), int(body.get("step", 0))
        dt = float(body.get("dt", 1))
        gravity = body.get("gravity_g")
        gravity = None if gravity in (None, "") else float(gravity)
    except (TypeError, ValueError) as err:
        raise BadRequest(f"seed, steps and step must be whole numbers, dt and gravity_g numbers ({err})") from err
    if not 1 <= steps <= 3600:
        raise BadRequest("steps must be between 1 and 3600")
    default = body.get("material_class")
    classes = {c: (body.get("material_classes") or {}).get(c) or default for c in compartments}
    streams = ops.record_compartments(name, seed, steps, dt, compartments)
    view = ops.snapshot(streams, step, corpus, classes, gravity)
    view.update(scenario=name, scenarios=sorted(sim.SCENARIOS), steps=steps)
    return view


def concern(corpus, body, query):
    if "sample" not in body or not body.get("material_class"):
        raise BadRequest("concern needs a 'sample' from /api/telemetry and a 'material_class' such as 'solid'")
    return engine("concern").evaluate(body["sample"], corpus, body.get("material_class"), body.get("history"))


def weakness(corpus, body, query):
    research = engine("research")
    rows = research.weakness(corpus)
    min_runs = evidence.decisions()["min_runs_for_sufficient"]
    for row in rows:
        row["dominant_weakness"] = research.dominant_weakness(row, min_runs)
    return rows


def opportunities(corpus, body, query):
    """body: {"missions": [{"name", "scenario", "relevance"?}]} or {"scenario": raw} for just one."""
    missions = body.get("missions") or [{"name": "your scenario", "scenario": body.get("scenario") or {}}]
    for mission in missions:
        if not isinstance(mission, dict) or not isinstance(mission.get("scenario"), dict):
            raise BadRequest("each mission needs a 'name' and a 'scenario' object")
        mission.setdefault("name", "unnamed")
    return engine("research").opportunities(corpus, missions)


def backtest(corpus, body, query):
    """body: {"cutoff_year": 2015, "years": {acronym or publication id: year}, "checks": [...]}"""
    try:
        cutoff = int(body.get("cutoff_year"))
        years = {(int(k) if str(k).isdigit() else k): int(v) for k, v in (body.get("years") or {}).items()}
    except (TypeError, ValueError) as err:
        raise BadRequest(f"cutoff_year and every year must be whole numbers ({err})") from err
    checks = body.get("checks") or []
    if not checks:
        raise BadRequest("backtest needs at least one check {name, scenario, should_flag}")
    return engine("research").backtest(corpus, cutoff, years, checks)


def builder_options(corpus, body, query):
    return engine("builder").options(corpus)


def builder_check(corpus, body, query):
    """body: the Builder form. Invalid values come back as {"valid": false, "errors": {...}}."""
    return engine("builder").check(body, corpus)


def ask(corpus, body, query):
    """The research assistant. Retrieves passages, then asks the language model (Groq by default)
    when a key is set; every answer is checked against PYRA's rules and retried once on a break.
    Without a key, or when the model cannot be reached, the passages come back on their own."""
    retrieval, assistant = engine("retrieval"), engine("assistant")
    question = (body.get("question") or "").strip()
    if not question:
        raise BadRequest("ask needs a 'question'")
    audience = body.get("audience") if body.get("audience") in assistant.AUDIENCES else "student"
    scenario = body.get("scenario") if isinstance(body.get("scenario"), dict) else None
    index = retrieval.Index()
    index.index_corpus(corpus)
    chunks = index.search(question)
    llm = engine("agents.llm").get_llm()
    live = bool(getattr(llm, "live", False))
    meta = {"model": getattr(llm, "model", None) if live else None, "live": live, "context": chunks}
    if not live or not chunks:
        reply = assistant.answer(question, chunks, scenario, audience)
        reply.pop("messages", None)
        return dict(reply, **meta)
    try:
        reply = assistant.answer(question, chunks, scenario, audience, ask_model=llm.chat)
        if reply["problems"]:
            first = reply["problems"]

            def retry(system, user):
                fixes = "\n- ".join(first)
                return llm.chat(system, f"{user}\n\nYOUR LAST ANSWER BROKE THESE RULES, FIX THEM:\n- {fixes}")
            again = assistant.answer(question, chunks, scenario, audience, ask_model=retry)
            if len(again["problems"]) <= len(first):
                reply = again
            reply["retried"] = True
    except Exception as err:  # noqa: BLE001  the passages still answer
        reply = dict(assistant.answer(question, chunks, scenario, audience),
                     model_error=f"{type(err).__name__}: {err}"[:300])
    reply.pop("messages", None)
    return dict(reply, **meta)


def _agent_run(path_tail):
    run = engine("agents.runs").get(path_tail)
    if run is None:
        raise NotFound(f"no agent run '{path_tail}'")
    return run


def agents_info(corpus, body, query):
    team, llm = engine("agents.team"), engine("agents.llm").get_llm()
    return dict(team.describe(), llm=llm.name, live=llm.live,
                agents=[{"id": a, "label": label, "role": role} for a, label, role in team.AGENTS])


def agents_start(corpus, body, query):
    """body: {goal, mode: full|evidence|gaps|lessons|custom, agents: [...],
    scenario: {preset, o2_percent, pressure, pressure_unit, flow_speed, gravity_g, materials, pillar, pilot_mode}}"""
    team = engine("agents.team")
    if body.get("mode") and body["mode"] not in team.MODES:
        raise BadRequest(f"mode must be one of {', '.join(team.MODES)}")
    if body.get("scenario") is not None and not isinstance(body["scenario"], dict):
        raise BadRequest("scenario must be an object")
    run = engine("agents.runs").start(body, corpus)
    return {"run_id": run.id}


def agents_ask(corpus, body, query):
    runs, team = engine("agents.runs"), engine("agents.team")
    agent = str(body.get("agent") or "supervisor")
    if agent not in team.LABELS:
        raise BadRequest(f"unknown agent '{agent}'")
    run = runs.get(str(body.get("run_id") or ""))
    state = run.state if run and run.state else runs.latest_state()
    return runs.ask(agent, str(body.get("question") or "").strip(), state, engine("agents.llm").get_llm())


def agent_reply(corpus, body, query):
    """The research agent: plans tool calls, writes an answer and checks it. See pyra/agent.py."""
    agent = engine("agent")
    question = (body.get("question") or "").strip()
    if not question:
        raise BadRequest("agent needs a 'question'")
    try:
        planner = agent.make_planner(body.get("planner") or Handler.planner_kind)
        return agent.run(question, corpus, body.get("scenario") or {}, body.get("audience") or "student", planner)
    except ValueError as err:
        raise BadRequest(str(err)) from err
    except agent.PlannerError as err:
        raise PlannerFailed(str(err)) from err


def agent_status(corpus, body, query):
    agent = engine("agent")
    return {"default": Handler.planner_kind, "claude_ready": agent.claude_ready(),
            "model": agent.claude_model(), "groq_ready": agent.groq_ready(),
            "groq_model": agent.groq_model(), "tools": agent.TOOL_SPECS}


GET_ROUTES = {
    "/api/agents": agents_info,
    "/api/investigations": lambda corpus, body, query: corpus["investigations"],
    "/api/runs": lambda corpus, body, query: corpus["runs"],
    "/api/telemetry": telemetry,
    "/api/research/weakness": weakness,
    "/api/agent/status": agent_status,
    "/api/builder/options": builder_options,
}
POST_ROUTES = {
    "/api/coverage": coverage,
    "/api/compare": compare,
    "/api/report": report,
    "/api/concern": concern,
    "/api/ops": ops_view,
    "/api/builder/check": builder_check,
    "/api/research/opportunities": opportunities,
    "/api/research/backtest": backtest,
    "/api/ask": ask,
    "/api/agent": agent_reply,
    "/api/agents/run": agents_start,
    "/api/agents/ask": agents_ask,
}
# /api/agents/<action>/<run_id>
AGENT_RUN_GET = {"state": lambda run, body: run.snapshot()}
AGENT_RUN_POST = {
    "resume": lambda run, body: _resume(run, body),
    "stop": lambda run, body: (run.stop(), {"ok": True})[1],
}


def _resume(run, body):
    decision = body.get("decision") if body.get("decision") in ("approve", "reject") else "reject"
    ids = [str(x) for x in body.get("ids")] if isinstance(body.get("ids"), list) else []
    if not run.resume({"decision": decision, "ids": ids}):
        raise BadRequest("this run is not waiting for approval")
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    corpus = None
    planner_kind = "auto"

    def log_message(self, format, *args):
        pass

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status, value):
        self.send(status, json.dumps(value, default=str))

    def answer(self, routes, body):
        url = urlparse(self.path)
        route = routes.get(url.path)
        if route is None:
            return self.send_json(404, {"error": f"no endpoint {url.path}"})
        try:
            self.send_json(200, route(self.corpus, body, parse_qs(url.query)))
        except MissingModule as err:
            self.send_json(503, {"error": str(err)})
        except BadRequest as err:
            self.send_json(400, {"error": str(err)})
        except PlannerFailed as err:
            self.send_json(502, {"error": str(err)})

    def stream_events(self, events):
        """Server-sent events: one JSON object per 'data:' line, flushed as it is made."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for event in events:
                self.wfile.write(b"data: " + json.dumps(event, default=str).encode("utf-8") + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except ValueError as err:
            self.wfile.write(b"data: " + json.dumps({"type": "error", "error": str(err)}).encode("utf-8") + b"\n\n")

    def crew_stream(self, query):
        crew = engine("crew")
        first = lambda key, default: query.get(key, [default])[0]
        try:
            gravity = float(first("gravity", "0"))
        except ValueError:
            return self.send_json(400, {"error": "gravity must be a number of g"})
        if first("scenario", "overheating_wire") not in engine("telemetry").SCENARIOS:
            return self.send_json(400, {"error": "unknown telemetry scenario"})
        self.stream_events(crew.mission(self.corpus, first("scenario", "overheating_wire"),
                                        gravity_g=gravity, llm=first("planner", "auto")))

    def chat_stream(self, query):
        crew = engine("crew")
        try:
            history = json.loads(query.get("history", ["[]"])[0])
        except json.JSONDecodeError:
            history = []
        self.stream_events(crew.chat_stream(query.get("q", [""])[0], self.corpus, history,
                                            query.get("planner", ["auto"])[0]))

    def agent_run(self, routes, body):
        """/api/agents/<action>/<run_id>. True when the path was one of these."""
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["api", "agents"] or parts[2] not in routes:
            return False
        try:
            run = _agent_run(parts[3])
            self.send_json(200, routes[parts[2]](run, body))
        except MissingModule as err:
            self.send_json(503, {"error": str(err)})
        except NotFound as err:
            self.send_json(404, {"error": str(err)})
        except BadRequest as err:
            self.send_json(400, {"error": str(err)})
        return True

    def stream(self, run_id):
        """Server-Sent Events: every event of an agent run, then the connection closes."""
        try:
            run = _agent_run(run_id)
        except (MissingModule, NotFound) as err:
            return self.send_json(404, {"error": str(err)})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        index = 0
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                batch, finished = run.events_since(index, timeout=15)
                if not batch:
                    if finished:
                        return
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                for event in batch:
                    index += 1
                    self.wfile.write(f"id: {event['seq']}\ndata: {json.dumps(event, default=str)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if batch[-1].get("type") in ("done", "error"):
                    return
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/api/crew/stream", "/api/chat/stream"):
            try:
                handler = self.crew_stream if url.path == "/api/crew/stream" else self.chat_stream
                return handler(parse_qs(url.query))
            except MissingModule as err:
                return self.send_json(503, {"error": str(err)})
        if url.path == "/api/export":
            return self.export(parse_qs(url.query))
        if url.path.startswith("/api/agents/stream/"):
            return self.stream(url.path.rsplit("/", 1)[1])
        if self.agent_run(AGENT_RUN_GET, {}):
            return
        if url.path.startswith("/api/"):
            return self.answer(GET_ROUTES, {})
        self.static(url.path)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as err:
            return self.send_json(400, {"error": f"request body is not valid JSON ({err})"})
        if not isinstance(body, dict):
            return self.send_json(400, {"error": "request body must be a JSON object"})
        if self.agent_run(AGENT_RUN_POST, body):
            return
        self.answer(POST_ROUTES, body)

    def export(self, query):
        fmt = query.get("format", ["json"])[0]
        try:
            exporter = engine("export")
        except MissingModule as err:
            return self.send_json(503, {"error": str(err)})
        rows = exporter.rows(self.corpus, comma_list(query.get("acronyms", [""])[0]) or None)
        if fmt == "csv":
            return self.send(200, exporter.to_csv(rows), "text/csv; charset=utf-8")
        if fmt == "json":
            return self.send(200, exporter.to_json(rows))
        self.send_json(400, {"error": f"format must be csv or json, not '{fmt}'"})

    def static(self, path):
        if path == "/demo" or path.startswith("/demo/"):
            folder, rel = DEMO, path[len("/demo"):].lstrip("/") or "pyra-3d.html"
        else:
            folder, rel = WEB, path.lstrip("/") or "index.html"
        target = (folder / rel).resolve()
        if folder.resolve() not in target.parents or not target.is_file():
            return self.send_json(404, {"error": f"no file {path}"})
        self.send(200, target.read_bytes(), CONTENT_TYPES.get(target.suffix, "application/octet-stream"))


def make_server(corpus, port=8000, host="127.0.0.1"):
    """A server bound to host:port that answers from this corpus. Port 0 picks a free one."""
    handler = type("PyraHandler", (Handler,), {"corpus": corpus})
    return ThreadingHTTPServer((host, port), handler)


def serve(port=8000, planner="auto"):
    Handler.planner_kind = planner
    server = make_server(load_corpus(), port)
    print(f"PYRA on http://127.0.0.1:{server.server_address[1]}  ({paths.DATABASE.name})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pyra.server", description="PYRA web app")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--planner", default="auto", choices=("auto", "offline", "claude", "groq"),
                        help="who drives the research agent (auto picks Claude, then Groq, when a key is set)")
    args = parser.parse_args(argv)
    serve(args.port, args.planner)


if __name__ == "__main__":
    main()
