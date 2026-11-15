"""Deterministic tools for the EMBER agents. Every number the agents report comes from here.

Physics is deliberately simple, order-of-magnitude scaling, so it runs instantly
and can be explained on stage. Every assumption is listed in ASSUMPTIONS and
returned with the results; replace the constants with values fitted to PSI data
(BASS-II, Saffire, ACME BRE) when you have them.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
G0 = 9.81

ASSUMPTIONS = {
    "flame_length_m": 0.05,       # characteristic flame/fuel length scale for buoyant velocity
    "flame_temp_k": 1500.0,
    "ambient_temp_k": 295.0,
    "ug_shift_low_flow": -2.0,    # O2 points: microgravity low-flow window can burn below the 1 g limit (calibrate with BASS-II)
    "ug_shift_mixed": -1.0,
    "quiescent_shift": 2.0,       # near-quiescent microgravity: oxygen starvation and radiative loss make sustained flame harder
    "pressure_coeff": 3.0,        # O2 points added to the limit per (14.7 - P)/14.7
    "low_flow_window_m_s": [0.02, 0.25],
}

# --------------------------------------------------------------------------- missions
MISSIONS = {
    "iss": {"name": "International Space Station", "gravity_g": 1e-6, "pressure_psia": 14.7, "o2_pct": 21.0,
            "fan_m_s": 0.10, "comm_delay_min": 0.0,
            "o2_sources": ["water electrolysis", "high-pressure O2 tanks", "solid-fuel oxygen generator (backup)"],
            "atmosphere_note": "Sea-level air."},
    "gateway": {"name": "Lunar Gateway", "gravity_g": 1e-6, "pressure_psia": 10.2, "o2_pct": 26.5,
                "fan_m_s": 0.10, "comm_delay_min": 0.02,
                "o2_sources": ["high-pressure O2 tanks"],
                "atmosphere_note": "Scenario assumption: 10.2 psia / 26.5% O2, one of the NASA-considered atmospheres listed in ACME BRE (PSI-20)."},
    "lunar": {"name": "Lunar surface habitat", "gravity_g": 0.165, "pressure_psia": 8.2, "o2_pct": 34.0,
              "fan_m_s": 0.10, "comm_delay_min": 0.02,
              "o2_sources": ["high-pressure O2 tanks", "solid-fuel oxygen generator (backup)"],
              "atmosphere_note": "Scenario assumption: 8.2 psia / 34% O2, a NASA-considered exploration atmosphere (PSI-20)."},
    "mars_transit": {"name": "Mars transit vehicle", "gravity_g": 1e-6, "pressure_psia": 10.2, "o2_pct": 26.5,
                     "fan_m_s": 0.10, "comm_delay_min": 22.0,
                     "o2_sources": ["water electrolysis", "high-pressure O2 tanks", "solid-fuel oxygen generator (backup)"],
                     "atmosphere_note": "Scenario assumption: 10.2 psia / 26.5% O2. One-way delay up to about 22 minutes."},
    "mars_surface": {"name": "Mars surface habitat", "gravity_g": 0.38, "pressure_psia": 8.2, "o2_pct": 34.0,
                     "fan_m_s": 0.10, "comm_delay_min": 22.0,
                     "o2_sources": ["high-pressure O2 tanks", "in-situ O2 production"],
                     "atmosphere_note": "Scenario assumption: 8.2 psia / 34% O2."},
}

# Approximate normal-gravity limiting oxygen index (LOI, % O2 at 1 atm, ASTM D2863-type),
# typical literature values. Verify for the exact product before using.
MATERIALS = {
    "cotton":      {"name": "Cotton fabric", "loi_1g": 18.5, "use": "clothing, towels"},
    "paper":       {"name": "Paper / cellulose", "loi_1g": 18.0, "use": "checklists, packaging"},
    "pmma":        {"name": "PMMA (acrylic)", "loi_1g": 17.5, "use": "windows, covers"},
    "polyethylene": {"name": "Polyethylene film", "loi_1g": 17.5, "use": "bags, stowage"},
    "polyester":   {"name": "Polyester fabric", "loi_1g": 21.0, "use": "straps, clothing"},
    "nylon":       {"name": "Nylon (hook-and-loop)", "loi_1g": 24.0, "use": "fasteners, netting"},
    "silicone":    {"name": "Silicone rubber", "loi_1g": 28.0, "use": "seals, tubing"},
    "nomex":       {"name": "Nomex (aramid)", "loi_1g": 29.0, "use": "bags, covers"},
    "kapton":      {"name": "Kapton (polyimide)", "loi_1g": 37.0, "use": "wire insulation"},
    "ptfe":        {"name": "PTFE (Teflon)", "loi_1g": 95.0, "use": "wire insulation, liners"},
}

ATMOSPHERES = ["14.7/21", "10.2/26.5", "8.2/34"]
GRAVITY_CELLS = [("micro", 1e-6), ("lunar", 0.165), ("mars", 0.38), ("earth", 1.0)]
TOPICS = {"ignition": 1.0, "spread": 1.0, "flammability": 1.0, "suppression": 0.9,
          "extinction": 0.8, "smoke": 0.8, "detection": 0.8, "cool_flame": 0.7}


def gravity_class(g: float) -> str:
    if g < 1e-3:
        return "micro"
    if g < 0.25:
        return "lunar"
    if g < 0.9:
        return "mars"
    return "earth"


def atmosphere_key(p: float, o2: float) -> str:
    return f"{p:g}/{o2:g}"


# --------------------------------------------------------------------------- librarian
def load_psi() -> dict:
    raw = json.loads((DATA / "psi_combustion.json").read_text(encoding="utf-8"))
    pattern = raw["url_pattern"]
    keep, dropped = [], []
    for r in raw["records"]:
        r = dict(r, url=pattern.format(id=r["id"]))
        if r["area"] != "Combustion Science" or not r["topics"]:
            dropped.append({"id": r["id"], "title": r["title"], "reason": f"{r['area']}, not combustion"})
            continue
        r.setdefault("atmospheres", [])
        r["atmosphere_assumed"] = not r["atmospheres"]
        if not r["atmospheres"] and r["type"] == "microgravity":
            r["atmospheres"] = ["14.7/21"]
        r.setdefault("materials", [])
        r["gravity"] = "micro" if r["type"] == "microgravity" else "earth"
        keep.append(r)
    counts = {"total": len(raw["records"]), "kept": len(keep), "dropped": len(dropped),
              "microgravity": sum(r["type"] == "microgravity" for r in keep),
              "ground": sum(r["type"] == "ground" for r in keep),
              "partial_gravity": 0,
              "verified": sum(bool(r.get("verified")) for r in keep)}
    by_topic: dict[str, int] = {}
    for r in keep:
        for t in r["topics"]:
            by_topic[t] = by_topic.get(t, 0) + 1
    return {"records": keep, "dropped": dropped, "counts": counts, "by_topic": by_topic,
            "sources": [raw["_about"].split(" from ")[1].split(" (")[0]]}


# --------------------------------------------------------------------------- mission
def mission_profile(mission_id: str, fan_m_s: float | None = None) -> dict:
    m = dict(MISSIONS.get(mission_id) or MISSIONS["iss"])
    m["id"] = mission_id if mission_id in MISSIONS else "iss"
    if fan_m_s is not None:
        m["fan_m_s"] = float(fan_m_s)
    m["ppo2_psia"] = round(m["pressure_psia"] * m["o2_pct"] / 100, 2)
    m["gravity_class"] = gravity_class(m["gravity_g"])
    m["atmosphere_key"] = atmosphere_key(m["pressure_psia"], m["o2_pct"])
    return m


# --------------------------------------------------------------------------- physics
def buoyant_velocity(g: float, a: dict = ASSUMPTIONS) -> float:
    return math.sqrt(max(g, 0) * G0 * a["flame_length_m"] * (a["flame_temp_k"] / a["ambient_temp_k"] - 1))


def flame_regime(gravity_g: float, fan_m_s: float) -> dict:
    ub = buoyant_velocity(gravity_g)
    ub_earth = buoyant_velocity(1.0)
    ratio = fan_m_s / ub if ub > 0 else float("inf")
    if fan_m_s < 0.01 and gravity_g < 1e-3:
        regime = "quiescent"
        text = "Almost no flow: the flame starves itself of oxygen and may shrink or go out, but smoldering and cool flames remain possible."
    elif ratio > 3:
        regime = "forced"
        text = "Fan flow dominates: the fire goes where the ventilation pushes it, and shutting the fans off removes most of its oxygen supply."
    elif ratio > 0.3:
        regime = "mixed"
        text = "Fan flow and buoyancy are comparable: flames lean with the ventilation but still rise."
    else:
        regime = "buoyant"
        text = "Buoyancy dominates, as on Earth, but the induced flow is weaker, so flames are taller and slower than in 1 g."
    relevance = {"buoyant": "high", "mixed": "medium", "forced": "low", "quiescent": "low"}[regime]
    fan_off = ("large: buoyancy is negligible, so fan shutdown leaves the flame little fresh oxygen"
               if gravity_g < 1e-3 else
               f"limited: buoyancy alone still drives about {ub:.2f} m/s of flow toward the flame")
    return {"buoyant_velocity_m_s": round(ub, 4), "earth_buoyant_velocity_m_s": round(ub_earth, 3),
            "fan_m_s": fan_m_s, "mixing_ratio": round(ratio, 2) if math.isfinite(ratio) else 1e9,
            "regime": regime, "regime_text": text, "earth_test_relevance": relevance,
            "fan_shutdown_effect": fan_off,
            "assumptions": {k: ASSUMPTIONS[k] for k in ("flame_length_m", "flame_temp_k", "ambient_temp_k")}}


# --------------------------------------------------------------------------- risk
def _shift(regime: str, fan: float) -> float:
    lo, hi = ASSUMPTIONS["low_flow_window_m_s"]
    if regime == "quiescent":
        return ASSUMPTIONS["quiescent_shift"]
    if regime == "forced" and lo <= fan <= hi:
        return ASSUMPTIONS["ug_shift_low_flow"]
    if regime in ("forced", "mixed"):
        return ASSUMPTIONS["ug_shift_mixed"]
    return 0.0


def evidence_for(material: str, records: list[dict], gcls: str | None = None, atm: str | None = None) -> list[str]:
    out = []
    for r in records:
        if material not in r.get("materials", []):
            continue
        if gcls and r["gravity"] != gcls:
            continue
        if atm and atm not in r.get("atmospheres", []):
            continue
        out.append(r["id"])
    return out


def rank_materials(materials: list[str], mission: dict, physics: dict, records: list[dict],
                   strict: bool = False, fixes: dict | None = None) -> list[dict]:
    """strict=False is the optimistic first pass: any microgravity test of the material counts
    as 'measured'. strict=True (after the Skeptic) requires a test at the mission's gravity
    class AND atmosphere; otherwise the claim is labelled extrapolated / no data and the band widens."""
    fixes = fixes or {}
    o2, p = mission["o2_pct"], mission["pressure_psia"]
    shift = _shift(physics["regime"], mission["fan_m_s"])
    p_corr = ASSUMPTIONS["pressure_coeff"] * (14.7 - p) / 14.7
    items = []
    for mid in materials:
        mat = MATERIALS.get(mid)
        if not mat:
            continue
        eff = mat["loi_1g"] + shift + p_corr
        margin = o2 - eff
        any_ev = evidence_for(mid, records, "micro")
        exact = evidence_for(mid, records, mission["gravity_class"], mission["atmosphere_key"])
        if not strict:
            conf = "measured" if any_ev else "extrapolated"
            band = 1.0 if any_ev else 2.5
            ev = any_ev
        elif exact:
            conf, band, ev = "measured", 1.0, exact
        elif mission["gravity_class"] == "micro" and any_ev:
            conf, band, ev = "extrapolated", 2.5, any_ev
        elif mission["gravity_class"] == "micro":
            conf, band, ev = "extrapolated", 3.0, []
        else:
            conf, band, ev = "no data", 4.0, any_ev
        band = fixes.get(mid, {}).get("band", band)
        if margin >= 0:
            verdict = "burns"
        elif margin + band >= 0:
            verdict = "could burn"
        elif margin > -3 - band:
            verdict = "near limit"
        else:
            verdict = "unlikely"
        score = max(0.0, min(100.0, 50 + 8 * (margin + band)))
        items.append({"material": mid, "name": mat["name"], "use": mat["use"], "loi_1g": mat["loi_1g"],
                      "eff_limit": round(eff, 1), "margin": round(margin, 1), "band": band,
                      "verdict": verdict, "score": round(score), "confidence": conf, "evidence": ev,
                      "why": (f"Cabin O2 {o2:g}% vs estimated limit {eff:.1f}% "
                              f"(1 g LOI {mat['loi_1g']:g}, regime shift {shift:+g}, pressure {p_corr:+.1f})")})
    items.sort(key=lambda x: (-x["score"], x["material"]))
    return items


def skeptic_review(items: list[dict], mission: dict, records: list[dict]) -> list[dict]:
    issues = []
    g, atm = mission["gravity_class"], mission["atmosphere_key"]
    for it in items:
        exact = evidence_for(it["material"], records, g, atm)
        if it["confidence"] == "measured" and not exact:
            where = "partial gravity" if g in ("lunar", "mars") else f"{atm} psia/% O2"
            issues.append({"code": "EXTRAPOLATION", "severity": "block", "material": it["material"],
                           "text": f"{it['name']} is labelled measured, but no PSI investigation tested it at {where}.",
                           "fix": "Relabel as extrapolated or no data and widen the uncertainty band."})
        if not it["evidence"]:
            issues.append({"code": "NO_EVIDENCE", "severity": "warn", "material": it["material"],
                           "text": f"{it['name']} has no microgravity record in PSI; its limit comes from a 1 g index only.",
                           "fix": "Keep, but mark for screening at mission conditions."})
    if g in ("lunar", "mars"):
        issues.append({"code": "PARTIAL_GRAVITY", "severity": "warn", "material": None,
                       "text": "No PSI combustion investigation ran in partial gravity; every number here interpolates between orbit and Earth.",
                       "fix": "State this on every slide and hand the gap to the Gap Hunter."})
    return issues


# --------------------------------------------------------------------------- incidents
INCIDENTS = [
    {"id": "apollo1", "name": "Apollo 1", "year": 1967, "outcome": "Three crew members lost during a ground test.",
     "source": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1",
     "chain": {"oxidizer": "100% oxygen cabin above sea-level pressure", "fuel": "Nylon netting, hook-and-loop, foam pads",
               "ignition": "Probable electrical arc from damaged wiring", "detection": "Crew voice call",
               "suppression": "None effective", "escape": "Inward-opening hatch could not be opened against cabin pressure"}},
    {"id": "apollo13", "name": "Apollo 13", "year": 1970, "outcome": "Oxygen tank failure; crew survived using the lunar module.",
     "source": "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
     "chain": {"oxidizer": "High-pressure oxygen tank", "fuel": "Teflon wire insulation inside the tank",
               "ignition": "Heater switches damaged before launch; insulation burned when the tank fans ran",
               "detection": "Bang and pressure drop", "suppression": "Not possible", "escape": "Lunar module used as lifeboat"}},
    {"id": "mir", "name": "Mir", "year": 1997, "outcome": "Fire put out; no lasting harm to the crew.",
     "source": "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/",
     "chain": {"oxidizer": "Solid-fuel oxygen generator canister", "fuel": "Canister contents; latex glove material was the likely contaminant",
               "ignition": "Canister failed on activation; flame about three feet long", "detection": "Crew saw it; smoke filled the station",
               "suppression": "Foam extinguishers; the flame went out on its own", "escape": "Flame blocked the route to the docked Soyuz"}},
]


def match_incidents(mission: dict, risk_items: list[dict]) -> list[dict]:
    burns = [i["name"] for i in risk_items if i["verdict"] in ("burns", "could burn")]
    out = []
    for inc in INCIDENTS:
        reasons = []
        if inc["id"] == "apollo1":
            if mission["o2_pct"] > 21:
                reasons.append(f"Oxygen-enriched cabin ({mission['o2_pct']:g}% O2)")
            if burns:
                reasons.append(f"Soft goods that can burn at mission conditions: {', '.join(burns[:3])}")
        if inc["id"] == "apollo13" and "high-pressure O2 tanks" in mission["o2_sources"]:
            reasons.append("High-pressure oxygen tanks with internal heaters/fans or valves")
        if inc["id"] == "mir":
            if any("solid-fuel" in s for s in mission["o2_sources"]):
                reasons.append("Solid-fuel oxygen generators carried as backup")
            if mission["comm_delay_min"] > 5:
                reasons.append(f"Crew must act without real-time ground support ({mission['comm_delay_min']:g} min delay)")
        level = "high" if len(reasons) >= 2 else "medium" if reasons else "low"
        out.append({**inc, "match": level, "match_reasons": reasons})
    return out


# --------------------------------------------------------------------------- gaps
def coverage_matrix(records: list[dict]) -> dict:
    cells: dict[str, dict] = {}
    for gname, _ in GRAVITY_CELLS:
        for atm in ATMOSPHERES:
            for topic in TOPICS:
                cells[f"{gname}|{atm}|{topic}"] = {"gravity": gname, "atmosphere": atm, "topic": topic, "records": []}
    for r in records:
        if r["type"] != "microgravity":
            continue
        for atm in r.get("atmospheres", []):
            for topic in r["topics"]:
                k = f"micro|{atm}|{topic}"
                if k in cells:
                    cells[k]["records"].append(r["id"])
    return cells


def rank_gaps(cells: dict, mission: dict, top: int = 6) -> list[dict]:
    gaps = []
    for c in cells.values():
        if c["records"]:
            continue
        g_rel = 1.0 if c["gravity"] == mission["gravity_class"] else 0.3
        a_rel = 1.0 if c["atmosphere"] == mission["atmosphere_key"] else 0.4
        if c["gravity"] == "earth":
            g_rel *= 0.2   # ground facilities can test these cheaply
        score = round(100 * g_rel * a_rel * TOPICS[c["topic"]])
        gaps.append({**c, "score": score})
    gaps.sort(key=lambda x: (-x["score"], x["gravity"], x["topic"]))
    return gaps[:top]


def design_experiment(gap: dict, mission: dict, risk_items: list[dict]) -> dict:
    mats = [i["material"] for i in risk_items if i["verdict"] in ("burns", "could burn", "near limit")][:3] or ["cotton", "pmma"]
    if gap["gravity"] in ("lunar", "mars"):
        platform = ("Parabolic flight at the target gravity (about 20 s per parabola) for ignition and early spread; "
                    "sustained spread needs a rotating rig or surface tests.")
    else:
        platform = "ISS combustion facility (a SoFIE-class solid-fuel rig) or a free-flying Saffire-style test."
    p, o2 = gap["atmosphere"].split("/")
    tightened = sum(1 for i in risk_items if i["material"] in mats)
    return {"title": f"{gap['topic'].replace('_', ' ').title()} of cabin materials at {gap['gravity']} gravity, {p} psia / {o2}% O2",
            "platform": platform, "materials": mats, "atmosphere": gap["atmosphere"], "gravity": gap["gravity"],
            "flows_m_s": [0.0, 0.05, 0.1, 0.2],
            "measurements": ["visible and IR video (flame front position)", "radiometer", "CO and CO2", "smoke particle counter"],
            "answers": f"Replaces interpolated limits for {tightened} ranked material(s) with measured ones.",
            "gap_score": gap["score"]}


# --------------------------------------------------------------------------- recommendations
def recommendations(mission: dict, physics: dict, risk_items: list[dict], incidents: list[dict], records: list[dict]) -> list[dict]:
    recs = []
    hot = [i for i in risk_items if i["verdict"] in ("burns", "could burn")]
    if hot:
        recs.append({"id": "R1", "priority": "P1", "title": "Re-screen soft goods at the mission atmosphere",
                     "text": f"Test {', '.join(i['name'] for i in hot[:4])} at {mission['atmosphere_key']} psia/% O2 before flight, or replace them.",
                     "evidence": sorted({e for i in hot for e in i["evidence"]}) or ["PSI-20"]})
    if mission["gravity_class"] == "micro":
        recs.append({"id": "R2", "priority": "P1", "title": "Shut ventilation first on a fire alarm",
                     "text": f"In the {physics['regime']} regime the fans feed the flame; fan shutdown effect is {physics['fan_shutdown_effect'].split(':')[0]}.",
                     "evidence": ["PSI-25", "PSI-26"]})
    else:
        recs.append({"id": "R2", "priority": "P2", "title": "Do not rely on fan shutdown alone",
                     "text": f"At {mission['gravity_g']:g} g buoyancy still supplies about {physics['buoyant_velocity_m_s']:.2f} m/s of flow; pair shutdown with isolation and suppression.",
                     "evidence": ["PSI-25"]})
    recs.append({"id": "R3", "priority": "P1", "title": "Detect smoke where the air goes, and sense gases too",
                 "text": "Smoke does not rise without gravity; put detectors in the ventilation path and add CO/CO2 sensing, because cool flames and smoldering give little light.",
                 "evidence": ["PSI-102", "PSI-101", "PSI-69", "PSI-68"]})
    for inc in incidents:
        if inc["id"] == "mir" and inc["match"] != "low":
            recs.append({"id": "R4", "priority": "P1", "title": "Treat oxygen generators as ignition hazards",
                         "text": "Inspect canisters for contamination, activate them away from escape routes, and keep the path to the return vehicle clear.",
                         "evidence": ["Mir 1997"]})
        if inc["id"] == "apollo13" and inc["match"] != "low":
            recs.append({"id": "R5", "priority": "P2", "title": "Audit electrical parts inside oxygen tanks",
                         "text": "Check heater, fan and switch ratings against every power source used on the ground and in flight.",
                         "evidence": ["Apollo 13 1970"]})
    if mission["comm_delay_min"] > 5:
        recs.append({"id": "R6", "priority": "P1", "title": "Give the crew an onboard fire playbook",
                     "text": f"With up to {mission['comm_delay_min']:g} min one-way delay, the first response must not wait for Earth.",
                     "evidence": ["Mir 1997"]})
    return recs
