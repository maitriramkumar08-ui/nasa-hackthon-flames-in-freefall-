"""Physicist: buoyancy vs fan flow -> flame regime. Output key: physics."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    m = state.get("mission") or ft.mission_profile("iss")
    ctx.emit("thought", "Comparing the buoyancy-driven flow a flame would make at this gravity with the cabin fan flow.")
    ph = ctx.tool("flame_regime", ft.flame_regime, gravity_g=m["gravity_g"], fan_m_s=m["fan_m_s"])
    fb = (f"Buoyant flow is about {ph['buoyant_velocity_m_s']:g} m/s against {ph['earth_buoyant_velocity_m_s']:g} m/s on Earth, "
          f"so fan-to-buoyancy ratio is {ph['mixing_ratio']:g}: {ph['regime']} regime. {ph['regime_text']} "
          f"Relevance of the normal-gravity upward-burning screening test: {ph['earth_test_relevance']}.")
    ph["summary"] = ctx.llm.think("physicist", system="Explain the flame regime to an engineer in plain words.",
                                  payload=ph, fallback=fb)
    ctx.emit("llm", ph["summary"])
    ctx.handoff("risk_ranker", "regime known; rank materials at these conditions")
    return {"physics": ph}
