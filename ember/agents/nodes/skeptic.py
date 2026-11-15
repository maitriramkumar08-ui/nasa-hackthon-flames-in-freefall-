"""Skeptic: blocks claims beyond the tested envelope. Output key: review.
Loop: risk_ranker -> skeptic -> (not approved and iterations < 3) ? risk_ranker : supervisor."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    risk = state.get("risk") or {"items": [], "iteration": 0}
    records = (state.get("corpus") or ft.load_psi())["records"]
    ctx.emit("thought", f"Checking every 'measured' label against the PSI records for {m['gravity_class']} gravity and {m['atmosphere_key']} psia/% O2.")
    issues = ctx.tool("skeptic_review", ft.skeptic_review, items=risk["items"], mission=m, records=records)
    blocks = [i for i in issues if i["severity"] == "block"]
    for i in blocks[:4]:
        ctx.emit("warning", i["text"])
    approved = not blocks
    fb = ("Approved: every claim matches what was actually tested." if approved else
          f"Rejected: {len(blocks)} claim(s) present extrapolations as measurements. Sending the ranking back.")
    ctx.emit("llm", ctx.llm.think("skeptic", system="You are a strict reviewer. State your verdict in one or two sentences.",
                                  payload={"blocks": len(blocks), "warns": len(issues) - len(blocks)}, fallback=fb))
    if not approved:
        ctx.handoff("risk_ranker", "relabel extrapolated claims and widen their bands")
    return {"review": {"iteration": risk.get("iteration", 0), "approved": approved, "issues": issues}}
