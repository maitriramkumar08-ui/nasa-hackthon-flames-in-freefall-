"""Safety Officer: recommendations + human approval. Output key: actions.
In pilot_mode 'approve' the node calls interrupt(); the server resumes it with
{"decision": "approve"|"reject", "ids": [...]}."""
from __future__ import annotations

from langgraph.types import interrupt

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    ph = state.get("physics") or ft.flame_regime(m["gravity_g"], m["fan_m_s"])
    items = (state.get("risk") or {}).get("items") or []
    cases = (state.get("incidents") or {}).get("cases") or ft.match_incidents(m, items)
    records = (state.get("corpus") or ft.load_psi())["records"]
    recs = ctx.tool("recommendations", ft.recommendations, mission=m, physics=ph, risk_items=items,
                    incidents=cases, records=records)
    mode = (state.get("scenario") or {}).get("pilot_mode") or "approve"
    approved, rejected = [r["id"] for r in recs], []
    if mode == "approve":
        ctx.emit("thought", f"{len(recs)} recommendations ready. Waiting for a human to approve them before they go in the report.")
        decision = interrupt({"actions": recs, "question": "Approve these fire-safety recommendations?"})
        decision = decision if isinstance(decision, dict) else {}
        ids = set(decision.get("ids") or [])
        if decision.get("decision") == "approve":
            approved = [r["id"] for r in recs if not ids or r["id"] in ids]
        else:
            approved = [r["id"] for r in recs if ids and r["id"] not in ids] if ids else []
        rejected = [r["id"] for r in recs if r["id"] not in approved]
        ctx.emit("result", f"Human decision: {len(approved)} approved, {len(rejected)} rejected.")
    else:
        ctx.emit("thought", "Shadow mode: recommendations are listed but marked as not yet reviewed.")
    for r in recs:
        r["status"] = "approved" if r["id"] in approved and mode == "approve" else \
                      "rejected" if r["id"] in rejected else "unreviewed"
    return {"actions": {"recommendations": recs, "pilot_mode": mode, "approved_ids": approved, "rejected_ids": rejected}}
