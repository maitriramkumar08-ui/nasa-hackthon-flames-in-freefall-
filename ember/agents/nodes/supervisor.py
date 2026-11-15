"""Supervisor: builds the route from the mode (or from the goal with a real LLM) and
hands control to one agent at a time. 'skeptic' is never routed directly: it is
reached through the risk loop (risk_ranker -> skeptic -> risk_ranker ...)."""
from __future__ import annotations

from ..ctx import OfflineLLM
from ..state import AGENT_IDS

ORDER = ["librarian", "mission_profiler", "physicist", "risk_ranker", "skeptic",
         "incident_analyst", "gap_hunter", "safety_officer"]
MODE_ROUTES = {
    "full": ["librarian", "mission_profiler", "physicist", "risk_ranker", "incident_analyst", "gap_hunter", "safety_officer"],
    "risk": ["librarian", "mission_profiler", "physicist", "risk_ranker"],
    "gaps": ["librarian", "mission_profiler", "gap_hunter"],
    "lessons": ["librarian", "mission_profiler", "physicist", "risk_ranker", "incident_analyst"],
}
WHY = {
    "librarian": "load the NASA evidence first so every agent cites the same records",
    "mission_profiler": "set gravity, atmosphere and ventilation for the chosen mission",
    "physicist": "work out whether buoyancy or the fans control the flame",
    "risk_ranker": "rank cabin materials; the Skeptic reviews each pass until it is honest",
    "incident_analyst": "check the mission against Apollo 1, Apollo 13 and Mir",
    "gap_hunter": "find what NASA has not tested yet and design the next experiment",
    "safety_officer": "turn findings into recommendations for human approval",
}


def normalise(ids) -> list[str]:
    seen = [a for a in dict.fromkeys(str(x).strip() for x in (ids or [])) if a in AGENT_IDS]
    if "skeptic" in seen and "risk_ranker" not in seen:
        seen.append("risk_ranker")
    if seen and "librarian" not in seen:
        seen.append("librarian")
    if seen and "mission_profiler" not in seen:
        seen.append("mission_profiler")
    return [a for a in ORDER if a in seen and a != "skeptic"]


def default_route(state) -> list[str]:
    mode = state.get("mode") or "full"
    if mode == "custom":
        return normalise(state.get("agents")) or list(MODE_ROUTES["full"])
    return list(MODE_ROUTES.get(mode, MODE_ROUTES["full"]))


def _plan(state, ctx) -> list[str]:
    fb = default_route(state)
    if (state.get("mode") or "full") == "custom" or isinstance(ctx.llm, OfflineLLM):
        return fb
    obj = ctx.llm.json("supervisor",
                       system=("You route a team of spacecraft fire-safety agents. Valid ids: "
                               f"{[a for a in ORDER if a != 'skeptic']}. The skeptic runs automatically after risk_ranker. "
                               'Return {"route": [ids], "why": str}.'),
                       payload={"goal": state.get("goal", ""), "default_route": fb}, fallback={"route": fb})
    picked = normalise(obj.get("route") if isinstance(obj.get("route"), list) else [])
    return [a for a in ORDER if a in set(fb) | set(picked)]


def run(state, ctx) -> dict:
    route = state.get("route")
    if route is None:
        route = _plan(state, ctx)
        ctx.emit("thought", f"Goal: {state.get('goal') or 'full fire-safety assessment'}. Route: {' -> '.join(route)} -> reporter.")
    route = [a for a in route if a not in (state.get("done") or [])]
    if not route:
        ctx.handoff("reporter", "every agent has reported; write the briefing")
        return {"route": [], "next": "reporter"}
    nxt, rest = route[0], route[1:]
    ctx.handoff(nxt, WHY.get(nxt, "next step"))
    return {"route": rest, "next": nxt}
