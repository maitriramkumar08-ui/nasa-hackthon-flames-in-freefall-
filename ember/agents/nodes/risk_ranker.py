"""Risk Ranker: ranks cabin materials; revised after each Skeptic review. Output keys: risk, risk_iterations."""
from __future__ import annotations

from ..tools import fire_tools as ft

DEFAULT_MATERIALS = ["cotton", "paper", "pmma", "polyethylene", "polyester", "nylon", "silicone", "nomex", "kapton", "ptfe"]


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    ph = state.get("physics") or ft.flame_regime(m["gravity_g"], m["fan_m_s"])
    records = (state.get("corpus") or ft.load_psi())["records"]
    mats = (state.get("scenario") or {}).get("materials") or DEFAULT_MATERIALS
    it = int(state.get("risk_iterations") or 0) + 1
    review = state.get("review") or {}
    strict = it > 1 and not review.get("approved", True)
    prev = state.get("risk") or {}
    if strict:
        ctx.emit("thought", f"Pass {it}: applying the Skeptic's {len(review.get('issues', []))} issue(s). "
                            "A claim is 'measured' only if PSI tested that material at this gravity and atmosphere.")
    else:
        ctx.emit("thought", f"Pass {it}: ranking {len(mats)} materials by oxygen margin to their flammability limit.")
    items = ctx.tool("rank_materials", ft.rank_materials, materials=mats, mission=m, physics=ph,
                     records=records, strict=strict)
    hot = [i for i in items if i["verdict"] in ("burns", "could burn")]
    history = list(prev.get("history") or [])
    history.append({"iteration": it, "strict": strict, "burns_or_could": len(hot),
                    "measured": sum(i["confidence"] == "measured" for i in items)})
    fb = (f"{len(hot)} of {len(items)} materials burn or could burn at {m['o2_pct']:g}% O2 in this regime; "
          f"highest risk: {items[0]['name']} (margin {items[0]['margin']:+g} points).")
    ctx.emit("llm", ctx.llm.think("risk_ranker", system="Summarise the material ranking and its biggest risk.",
                                  payload={"top": items[:4], "count": len(items)}, fallback=fb))
    ctx.handoff("skeptic", "review this ranking before anyone relies on it")
    return {"risk": {"iteration": it, "items": items, "history": history, "strict": strict},
            "risk_iterations": it}
