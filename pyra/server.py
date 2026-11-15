"""The PYRA web app: a small JSON API plus the static page in pyra/web/.

Standard library only (http.server), so there is nothing to install. The
corpus is loaded once at startup. The engines (ranking, gaps, compare, ...)
are imported inside each handler, so the server still starts while one of
them is missing; that endpoint then answers 503 and names the module.

    python -m pyra.server --dummy --port 8000
"""

import argparse
import importlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, evidence, paths

WEB = Path(__file__).resolve().parent / "web"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
# Our own example names for the SIMULATED mission-control panel, not a real vehicle layout.
DEFAULT_COMPARTMENTS = "habitat,lab,node"


class MissingModule(Exception):
    pass


class BadRequest(Exception):
    pass


def engine(name):
    """Import pyra.<name> now, or say clearly which module is not there yet."""
    try:
        return importlib.import_module(f"pyra.{name}")
    except ImportError as err:
        raise MissingModule(f"pyra.{name} is not available ({err})") from err


def load_corpus(dummy):
    if dummy:
        return evidence.load(evidence.dummy_conn())
    if not paths.DATABASE.exists():
        raise SystemExit(f"{paths.DATABASE} does not exist. Run 'python -m pyra build' first, or use --dummy.")
    return evidence.load(db.connect(paths.DATABASE))


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


def concern(corpus, body, query):
    if "sample" not in body or not body.get("material_class"):
        raise BadRequest("concern needs a 'sample' from /api/telemetry and a 'material_class' such as 'solid'")
    return engine("concern").evaluate(body["sample"], corpus, body.get("material_class"), body.get("history"))


def weakness(corpus, body, query):
    return engine("research").weakness(corpus)


def builder_match(corpus, body, query):
    """body: mission {name, environment}, layout {compartments, edges}, equipment, materials, maintenance."""
    try:
        return engine("builder").assess(body.get("mission") or {"name": None, "environment": {}},
                                        body.get("layout") or {"compartments": [], "edges": []},
                                        body.get("equipment") or [], body.get("materials") or [],
                                        body.get("maintenance") or [], corpus)
    except (KeyError, ValueError) as err:
        raise BadRequest(f"design is incomplete or inconsistent: {err}") from err


def ask(corpus, body, query):
    """Retrieved context and the assistant's checks. No model is called here."""
    retrieval, assistant = engine("retrieval"), engine("assistant")
    question = (body.get("question") or "").strip()
    if not question:
        raise BadRequest("ask needs a 'question'")
    index = retrieval.Index()
    index.index_corpus(corpus)
    chunks = index.search(question)
    reply = assistant.answer(question, chunks)
    return dict(reply, context=chunks)


GET_ROUTES = {
    "/api/investigations": lambda corpus, body, query: corpus["investigations"],
    "/api/runs": lambda corpus, body, query: corpus["runs"],
    "/api/telemetry": telemetry,
    "/api/research/weakness": weakness,
}
POST_ROUTES = {
    "/api/coverage": coverage,
    "/api/compare": compare,
    "/api/report": report,
    "/api/concern": concern,
    "/api/builder/match": builder_match,
    "/api/ask": ask,
}


class Handler(BaseHTTPRequestHandler):
    corpus = None

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

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/export":
            return self.export(parse_qs(url.query))
        if url.path.startswith("/api/"):
            return self.answer(GET_ROUTES, {})
        self.static(url.path)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as err:
            return self.send_json(400, {"error": f"request body is not valid JSON ({err})"})
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
        target = (WEB / (path.lstrip("/") or "index.html")).resolve()
        if WEB not in target.parents or not target.is_file():
            return self.send_json(404, {"error": f"no file {path}"})
        self.send(200, target.read_bytes(), CONTENT_TYPES.get(target.suffix, "application/octet-stream"))


def make_server(corpus, port=8000, host="127.0.0.1"):
    """A server bound to host:port that answers from this corpus. Port 0 picks a free one."""
    handler = type("PyraHandler", (Handler,), {"corpus": corpus})
    return ThreadingHTTPServer((host, port), handler)


def serve(dummy=False, port=8000):
    server = make_server(load_corpus(dummy), port)
    print(f"PYRA on http://127.0.0.1:{server.server_address[1]}  ({'DUMMY' if dummy else paths.DATABASE.name})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pyra.server", description="PYRA web app")
    parser.add_argument("--dummy", action="store_true", help="use the DUMMY sample data")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    serve(args.dummy, args.port)


if __name__ == "__main__":
    main()
