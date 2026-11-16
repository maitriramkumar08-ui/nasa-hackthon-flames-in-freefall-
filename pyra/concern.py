"""Turn one SIMULATED telemetry sample into envelope status, alerts and a reasoning chain.

This never predicts a fire (rule 9). It says where the cabin sits compared
with what has been tested for the compartment's material class, using the gap
engine, and raises three kinds of alert:

    THRESHOLD  a channel crossed a PLACEHOLDER limit from config/alerts.json
    TREND      a channel changed faster than a PLACEHOLDER rate over a window
    ENVELOPE   O2 is above the highest O2 tested for this material class

The material class is matched against a run's fuel phases or materials, so
"solid" and "Nomex" both work. Everything is plain code (rule 8).
"""

import json

from . import evidence, gaps, paths, ranking

ALERTS = paths.ROOT / "config" / "alerts.json"

# envelope axis: (sample channel, gap_tolerances key)
AXES = {
    "o2_percent": ("o2_percent", "o2_percent_points"),
    "pressure": ("total_pressure_kpa", "pressure_kpa"),
    "flow_speed": ("flow_cm_s", "flow_cm_s"),
    "gravity": ("gravity_g", "gravity_g"),
}

UNCOMPARED = ["co_ppm", "co2_ppm", "smoke_level", "temperature_c"]

LEVELS = {"DIRECTLY_TESTED": 2, "BOUNDED": 1}


def load_alerts():
    """config/alerts.json as a dict."""
    return json.loads(ALERTS.read_text(encoding="utf-8"))


def _matches(phases, materials, material_class):
    if not material_class or not material_class.strip():
        return False  # no material class given: nothing counts as a match
    wanted = material_class.strip().lower()
    return (wanted in {p.lower() for p in phases if p}
            or any(wanted in m.lower() for m in materials if m))


def matching_runs(corpus, material_class):
    return [r for r in corpus["runs"] if _matches(r["fuel_phases"], r["materials"], material_class)]


def matching_investigations(corpus, material_class):
    return [i for i in corpus["investigations"]
            if _matches([f["phase"] for f in i["fuels"]], [f["material"] for f in i["fuels"]], material_class)]


def tested_o2_max(corpus, material_class):
    """Highest O2 tested for the material class, from runs and reported ranges. None if nothing."""
    values = [r["values"]["o2_percent"] for r in matching_runs(corpus, material_class)]
    values += [i["ranges"].get("o2_percent", {}).get("max")
               for i in matching_investigations(corpus, material_class)]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def envelope(sample, runs, decisions):
    """{axis: gap_class} for every axis the sample reports."""
    status = {}
    for axis, (channel, tolerance_key) in AXES.items():
        if sample.get(channel) is None:
            continue
        tested = [r["values"][axis] for r in runs if r["values"].get(axis) is not None]
        status[axis], _ = gaps.classify_axis(tested, sample[channel],
                                             decisions["gap_tolerances"][tolerance_key],
                                             decisions["min_runs_for_sufficient"])
    return status


def threshold_alerts(sample, limits):
    alerts = []
    for channel, limit in limits.items():
        value = sample.get(channel)
        if value is None:
            continue
        for side, crossed in (("max", lambda v, x: v > x), ("min", lambda v, x: v < x)):
            if side in limit and crossed(value, limit[side]):
                word = "above" if side == "max" else "below"
                alerts.append({"type": "THRESHOLD", "channel": channel, "label": "PLACEHOLDER",
                               "message": f"{channel} is {value}, {word} the PLACEHOLDER limit "
                                          f"{limit[side]} (limit not sourced)."})
    return alerts


def trend_alerts(sample, history, rules):
    """Rate of change from the oldest sample inside the window to this one, per minute."""
    window = rules.get("window_s", 60)
    recent = [h for h in history if sample["t"] - window <= h["t"] < sample["t"]]
    alerts = []
    for channel, rule in rules.items():
        if channel == "window_s" or sample.get(channel) is None:
            continue
        earlier = [h for h in recent if h.get(channel) is not None]
        if not earlier:
            continue
        first = min(earlier, key=lambda h: h["t"])
        per_min = (sample[channel] - first[channel]) / (sample["t"] - first["t"]) * 60
        if "rise_per_min" in rule and per_min > rule["rise_per_min"]:
            word, limit = "rising", rule["rise_per_min"]
        elif "fall_per_min" in rule and -per_min > rule["fall_per_min"]:
            word, limit = "falling", rule["fall_per_min"]
        else:
            continue
        alerts.append({"type": "TREND", "channel": channel, "label": "PLACEHOLDER",
                       "message": f"{channel} is {word} at {abs(per_min):.3g} per minute, faster than "
                                  f"the PLACEHOLDER rate {limit} (rate not sourced)."})
    return alerts


def envelope_alert(sample, corpus, material_class):
    o2 = sample.get("o2_percent")
    highest = tested_o2_max(corpus, material_class)
    if o2 is None or highest is None or o2 <= highest:
        return []
    return [{"type": "ENVELOPE", "channel": "o2_percent",
             "message": f"O2 is {o2}%, above the highest O2 tested for {material_class} "
                        f"({highest}%). Conditions are outside the tested range."}]


def _scenario(sample, material_class):
    return evidence.scenario({
        "o2_percent": sample.get("o2_percent"),
        "pressure": sample.get("total_pressure_kpa"), "pressure_unit": "kPa",
        "flow_speed": sample.get("flow_cm_s"), "flow_unit": "cm/s",
        "gravity_g": sample.get("gravity_g"),
        "temperature": sample.get("temperature_c"), "temperature_unit": "C",
        "material": material_class,
        "fuel_phase": material_class if (material_class or "").lower() in {"solid", "liquid", "gas"} else None,
    })


def _confidence(status):
    if not status:
        return "LOW"
    lowest = min(LEVELS.get(c, 0) for c in status.values())
    return {2: "HIGH", 1: "MEDIUM", 0: "LOW"}[lowest]


def reasoning(sample, corpus, material_class, status, top=3):
    by_id = {i["id"]: i for i in corpus["investigations"]}
    ranked = [r for r in ranking.rank(corpus, _scenario(sample, material_class)) if r["total"] > 0][:top]
    findings = [{"text": f["text"], "source": f["source_id"], "page": f["page_or_table"]}
                for r in ranked for f in by_id[r["investigation_id"]]["findings"] if f["source_id"]]
    not_covered = [f"{channel} is not in the sample" for channel, _ in AXES.values()
                   if sample.get(channel) is None]
    not_covered += [f"{axis}: {gap_class}" for axis, gap_class in status.items()
                    if gap_class not in LEVELS]
    not_covered.append(", ".join(UNCOMPARED) + " are shown but not compared with experiments")
    return {
        "observed": dict(sample),
        "matched_experiments": [{"id": r["investigation_id"], "why": r["explanation"], "score": r["total"]}
                                for r in ranked],
        "measured_findings": findings,
        "not_covered": not_covered,
        "confidence": _confidence(status),
    }


def evaluate(sample, corpus, material_class, history=None, alerts_config=None):
    """Envelope status, alerts and reasoning chain for one sample. Output is SIMULATED."""
    config = alerts_config if alerts_config is not None else load_alerts()
    status = envelope(sample, matching_runs(corpus, material_class), evidence.decisions())
    alerts = (threshold_alerts(sample, config.get("threshold", {}))
              + trend_alerts(sample, history or [], config.get("trend", {}))
              + envelope_alert(sample, corpus, material_class))
    return {"envelope": status, "alerts": alerts,
            "reasoning": reasoning(sample, corpus, material_class, status),
            "source": "SIMULATED"}
