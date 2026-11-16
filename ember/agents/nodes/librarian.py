"""Librarian: loads the NASA PSI combustion investigations. Output key: corpus."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    ctx.emit("thought", "Loading the NASA PSI combustion investigations and filtering out anything that is not combustion science.")
    corpus = ctx.tool("load_psi", ft.load_psi)
    c = corpus["counts"]
    for d in corpus["dropped"]:
        ctx.emit("thought", f"Dropped {d['id']} ({d['title'][:60]}): {d['reason']}.")
    fb = (f"{c['kept']} of {c['total']} PSI records are combustion investigations: {c['microgravity']} flown in "
          f"microgravity, {c['ground']} ground studies that analyse flight data, and none in partial gravity.")
    ctx.emit("llm", ctx.llm.think("librarian", system="Summarise what the PSI combustion corpus covers.",
                                  payload={"counts": c, "by_topic": corpus["by_topic"]}, fallback=fb))
    ctx.handoff("mission_profiler", "the corpus is ready; next we need the mission conditions")
    return {"corpus": corpus}
