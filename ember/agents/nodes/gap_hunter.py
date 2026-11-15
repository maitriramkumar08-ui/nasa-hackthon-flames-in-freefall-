"""Gap Hunter: coverage matrix -> ranked gaps -> experiment proposal. Output key: gaps."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    records = (state.get("corpus") or ft.load_psi())["records"]
    items = (state.get("risk") or {}).get("items") or []
    ctx.emit("thought", "Building the gravity x atmosphere x topic coverage matrix from the flight investigations.")
    cells = ctx.tool("coverage_matrix", ft.coverage_matrix, records=records)
    covered = sum(1 for c in cells.values() if c["records"])
    gaps = ctx.tool("rank_gaps", ft.rank_gaps, cells=cells, mission=m)
    proposal = ctx.tool("design_experiment", ft.design_experiment, gap=gaps[0], mission=m, risk_items=items)
    mission_cells = {t: cells[f"{m['gravity_class']}|{m['atmosphere_key']}|{t}"]["records"]
                     for t in ft.TOPICS if f"{m['gravity_class']}|{m['atmosphere_key']}|{t}" in cells}
    fb = (f"Only {covered} of {len(cells)} condition cells have a flight investigation. "
          f"Top gap for this mission: {gaps[0]['topic'].replace('_', ' ')} at {gaps[0]['gravity']} gravity and "
          f"{gaps[0]['atmosphere']} psia/% O2. Proposed: {proposal['title']}.")
    ctx.emit("llm", ctx.llm.think("gap_hunter", system="Explain the most important untested condition and the experiment that fills it.",
                                  payload={"covered": covered, "cells": len(cells), "top_gap": gaps[0], "proposal": proposal},
                                  fallback=fb))
    compact = {k: len(v["records"]) for k, v in cells.items()}
    return {"gaps": {"matrix": compact, "covered": covered, "cells": len(cells), "mission_cell": mission_cells,
                     "gaps": gaps, "proposal": proposal}}
