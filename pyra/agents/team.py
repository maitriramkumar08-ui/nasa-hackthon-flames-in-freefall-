"""The team: who is in it, how the supervisor routes, and the small graph runner.

    START -> supervisor -> {agent} -> supervisor -> ... -> reporter -> END
    review loop: evidence_ranker -> skeptic -> (not approved and passes < 3) ? evidence_ranker : supervisor

Same shape as the EMBER prototype (ember/agents, LangGraph), rebuilt on the
standard library so PYRA still installs nothing. Rules for every node: return
only its own state key, never touch "messages" or "done", and survive a
missing upstream result. One broken agent logs a warning and the run goes on.
"""

import time
import traceback

from . import nodes
from .ctx import AgentCtx, Cancelled, OfflineLLM

AGENTS = [
    ("librarian", "Librarian", "Reads the PYRA evidence database and says what it covers and whether any sheet is marked NOT REAL DATA."),
    ("mission_profiler", "Mission Profiler", "Turns a preset and your typed values into one HYPOTHETICAL scenario, with the source of every value."),
    ("physicist", "Physicist", "Compares buoyant flow with ventilation flow (ILLUSTRATIVE scaling) to say how close a normal-gravity test is."),
    ("evidence_ranker", "Evidence Ranker", "Ranks investigations and drafts one labelled, cited claim per material."),
    ("skeptic", "Skeptic", "Checks every claim against PYRA's rules and sends the draft back until it is honest."),
    ("incident_analyst", "Incident Analyst", "Breaks Apollo 1, Apollo 13 and Mir into a fire chain and finds the same links in the scenario."),
    ("gap_hunter", "Gap Hunter", "Classifies every axis, scores data opportunities and proposes the experiment that closes the biggest gap."),
    ("safety_officer", "Safety Officer", "Turns the findings into evidence actions and waits for a person to approve them."),
]
AGENT_IDS = [a for a, _, _ in AGENTS]
LABELS = {a: label for a, label, _ in AGENTS} | {"supervisor": "Supervisor", "reporter": "Reporter"}
ROLES = {a: role for a, _, role in AGENTS} | {
    "supervisor": "Plans the route from the goal and mode, then hands over to one agent at a time.",
    "reporter": "Writes the briefing with KPIs, labels and a markdown copy."}
STATE_KEY = {"librarian": "corpus", "mission_profiler": "mission", "physicist": "physics",
             "evidence_ranker": "ranking", "skeptic": "review", "incident_analyst": "incidents",
             "gap_hunter": "gaps", "safety_officer": "actions", "reporter": "report"}

MAX_REVIEW_PASSES = 3
MODES = ("full", "evidence", "gaps", "lessons", "custom")
MODE_ROUTES = {
    "full": ["librarian", "mission_profiler", "physicist", "evidence_ranker", "incident_analyst", "gap_hunter", "safety_officer"],
    "evidence": ["librarian", "mission_profiler", "physicist", "evidence_ranker"],
    "gaps": ["librarian", "mission_profiler", "gap_hunter"],
    "lessons": ["librarian", "mission_profiler", "evidence_ranker", "incident_analyst"],
}
WHY = {
    "librarian": "load the evidence first so every agent cites the same records",
    "mission_profiler": "set the scenario and say where each value came from",
    "physicist": "work out whether buoyancy or ventilation sets the flow",
    "evidence_ranker": "draft the claims; the Skeptic reviews every pass",
    "incident_analyst": "compare the scenario with Apollo 1, Apollo 13 and Mir",
    "gap_hunter": "find what has not been tested and propose the next experiment",
    "safety_officer": "turn the findings into actions for human approval",
}


def normalise(ids):
    """A custom agent list in run order, with the agents it depends on added."""
    seen = {str(x).strip() for x in (ids or [])} & set(AGENT_IDS)
    if "skeptic" in seen:
        seen.add("evidence_ranker")
    if seen:
        seen |= {"librarian", "mission_profiler"}
    return [a for a in AGENT_IDS if a in seen and a != "skeptic"]


def default_route(state):
    mode = state.get("mode") or "full"
    if mode == "custom":
        return normalise(state.get("agents")) or list(MODE_ROUTES["full"])
    return list(MODE_ROUTES.get(mode, MODE_ROUTES["full"]))


def plan_route(state, ctx):
    """The mode's route. With a model and a goal, the model may add agents, never remove them."""
    route = default_route(state)
    if (state.get("mode") or "full") == "custom" or not getattr(ctx.llm, "live", False) or not state.get("goal"):
        return route
    picked = ctx.llm.json("supervisor",
                          "You route a team of spacecraft fire-safety evidence agents. Valid ids: "
                          f"{[a for a in AGENT_IDS if a != 'skeptic']}. The skeptic runs after evidence_ranker "
                          'automatically. Return {"route": [ids], "why": "..."}.',
                          {"goal": state["goal"], "default_route": route}, {"route": route, "why": ""})
    extra = normalise(picked.get("route") if isinstance(picked.get("route"), list) else [])
    return [a for a in AGENT_IDS if a in set(route) | set(extra)]


def supervisor(state, ctx):
    route = state.get("route")
    if route is None:
        route = plan_route(state, ctx)
        ctx.emit("thought", f"Goal: {state.get('goal') or 'full evidence check'}. "
                            f"Route: {' -> '.join(route)} -> reporter.")
    route = [a for a in route if a not in (state.get("done") or [])]
    if not route:
        ctx.handoff("reporter", "every agent has reported; write the briefing")
        return {"route": [], "next": "reporter"}
    ctx.handoff(route[0], WHY.get(route[0], "next step"))
    return {"route": route[1:], "next": route[0]}


def reporter(state, ctx):
    return nodes.reporter(state, ctx)


def next_node(node, state):
    if node == "supervisor":
        nxt = state.get("next")
        return nxt if nxt in AGENT_IDS or nxt == "reporter" else "reporter"
    if node == "evidence_ranker":
        return "skeptic"
    if node == "skeptic":
        review = state.get("review")
        approved = review.get("approved", True) if isinstance(review, dict) else True
        if not approved and int(state.get("review_passes") or 0) < MAX_REVIEW_PASSES:
            return "evidence_ranker"
        return "supervisor"
    if node == "reporter":
        return None
    return "supervisor"


FUNCTIONS = dict(nodes.REGISTRY, supervisor=supervisor, reporter=reporter)


def initial_state(request):
    request = request if isinstance(request, dict) else {}
    mode = request.get("mode") if request.get("mode") in MODES else "full"
    return {"goal": str(request.get("goal") or "")[:500], "mode": mode,
            "agents": [a for a in (request.get("agents") or []) if a in AGENT_IDS],
            "scenario": dict(request.get("scenario") or {}) if isinstance(request.get("scenario"), dict) else {},
            "done": [], "review_passes": 0, "messages": []}


def run_team(request, corpus, llm=None, sink=None, approver=None, cancelled=None, max_steps=60):
    """Run the whole team once and return the final state. sink(event) gets every event."""
    llm = llm or OfflineLLM()
    sink = sink or (lambda event: None)
    cancelled = cancelled or (lambda: False)
    state = initial_state(request)
    node, steps = "supervisor", 0
    try:  # demo pacing: a pause before each agent so people can follow the graph
        pace = min(max(float((request or {}).get("pace") or 0), 0.0), 3.0)
    except (TypeError, ValueError, AttributeError):
        pace = 0.0
    while node is not None:
        if pace and steps:
            time.sleep(pace)
        if cancelled():
            raise Cancelled("run stopped")
        steps += 1
        if steps > max_steps:
            sink({"type": "message", "agent": "supervisor",
                  "data": {"agent": "supervisor", "kind": "warning", "text": "step limit reached; writing the briefing"}})
            node = "reporter"
        ctx = AgentCtx(node, llm, sink, approver, corpus)
        sink({"type": "node_start", "agent": node, "t": time.time()})
        try:
            update = FUNCTIONS[node](state, ctx) or {}
        except Cancelled:
            raise
        except Exception as err:  # noqa: BLE001  one broken agent must not end the run
            ctx.emit("warning", f"{node} failed: {type(err).__name__}: {err}",
                     {"traceback": traceback.format_exc(limit=4)[-600:]})
            update = {}
        update = {k: v for k, v in update.items() if k not in ("messages", "done")} if isinstance(update, dict) else {}
        state.update(update)
        state["messages"] = state["messages"] + ctx.messages
        if node in AGENT_IDS:
            state["done"] = state["done"] + [node]
        sink({"type": "node_end", "agent": node, "update": update, "t": time.time()})
        node = "reporter" if steps > max_steps and node != "reporter" else next_node(node, state)
    return state


def describe():
    """The graph for GET /api/agents/graph."""
    nodes_ = ([{"id": "supervisor", "label": "Supervisor", "role": ROLES["supervisor"], "kind": "router"}]
              + [{"id": a, "label": l, "role": r, "kind": "agent"} for a, l, r in AGENTS]
              + [{"id": "reporter", "label": "Reporter", "role": ROLES["reporter"], "kind": "terminal"}])
    edges = [{"from": "supervisor", "to": a, "kind": "conditional"} for a in AGENT_IDS if a != "skeptic"]
    edges += [{"from": "supervisor", "to": "reporter", "kind": "conditional"},
              {"from": "evidence_ranker", "to": "skeptic", "kind": "normal"},
              {"from": "skeptic", "to": "evidence_ranker", "kind": "loop"},
              {"from": "skeptic", "to": "supervisor", "kind": "conditional"}]
    edges += [{"from": a, "to": "supervisor", "kind": "normal"} for a in AGENT_IDS if a not in ("evidence_ranker", "skeptic")]
    return {"nodes": nodes_, "edges": edges, "modes": {m: MODE_ROUTES.get(m) for m in MODES},
            "max_review_passes": MAX_REVIEW_PASSES}
