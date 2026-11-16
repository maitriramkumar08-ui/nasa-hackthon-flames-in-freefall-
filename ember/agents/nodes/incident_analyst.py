"""Incident Analyst: Apollo 1, Apollo 13, Mir -> fire chain -> match. Output key: incidents."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    items = (state.get("risk") or {}).get("items") or []
    ctx.emit("thought", "Breaking each historical fire into oxidizer, fuel, ignition, detection, suppression and escape, then looking for the same links in this mission.")
    cases = ctx.tool("match_incidents", ft.match_incidents, mission=m, risk_items=items)
    for c in cases:
        if c["match_reasons"]:
            ctx.emit("thought", f"{c['name']} ({c['year']}) match {c['match']}: {'; '.join(c['match_reasons'])}.")
    worst = max(cases, key=lambda c: len(c["match_reasons"]))
    fb = f"The closest historical pattern is {worst['name']} ({worst['year']}), with {len(worst['match_reasons'])} matching link(s)."
    ctx.emit("llm", ctx.llm.think("incident_analyst", system="Say which past spaceflight fire this mission most resembles and why.",
                                  payload={"cases": [{k: c[k] for k in ('name', 'year', 'match', 'match_reasons')} for c in cases]},
                                  fallback=fb))
    return {"incidents": {"cases": cases, "closest": worst["id"]}}
