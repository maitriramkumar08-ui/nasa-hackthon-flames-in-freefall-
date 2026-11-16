"""Mission Profiler: mission -> gravity, atmosphere, ventilation, delay. Output key: mission."""
from __future__ import annotations

from ..tools import fire_tools as ft


def run(state, ctx) -> dict:
    sc = state.get("scenario") or {}
    mid = sc.get("mission") or "iss"
    ctx.emit("thought", f"Building the environment profile for mission '{mid}'.")
    m = ctx.tool("mission_profile", ft.mission_profile, mission_id=mid, fan_m_s=sc.get("fan_m_s"))
    fb = (f"{m['name']}: {m['gravity_g']:g} g, {m['pressure_psia']:g} psia at {m['o2_pct']:g}% oxygen "
          f"(O2 partial pressure {m['ppo2_psia']:g} psia), cabin flow {m['fan_m_s']:g} m/s. {m['atmosphere_note']}")
    ctx.emit("llm", ctx.llm.think("mission_profiler", system="Describe the mission environment for fire safety.",
                                  payload=m, fallback=fb))
    if m["o2_pct"] > 21:
        ctx.emit("thought", f"Oxygen fraction is {m['o2_pct']:g}%, above sea-level air. Materials that are safe on the ISS may burn here.")
    return {"mission": m}
