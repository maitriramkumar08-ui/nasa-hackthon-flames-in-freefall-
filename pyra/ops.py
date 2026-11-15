"""The Ops view: one SIMULATED telemetry stream seen by the crew and by a controller.

Nothing here predicts a fire (rule 9) and nothing adds concerns up into a
score: every entry stands on its own, with its own label. Three things are
built on top of concern.evaluate():

    tiles            the six crew tiles, each with a status chip (nominal/watch/alert)
                     and the reasons behind it, for the tile's expanded view
    banner           the single highest-priority active concern for a compartment,
                     picked by the fixed BANNER_PRIORITY order below
    combined view    for the controller: (a) the gap engine's combination check on
                     the live O2 / pressure / flow / gravity for each compartment's
                     material class, and (b) co-occurring channels grouped by the
                     explicit ILLUSTRATIVE rules in config/alerts.json

    streams = ops.record_compartments("overheating_wire", seed=1, steps=120, dt=1,
                                      compartments=["habitat", "lab"])
    view = ops.snapshot(streams, step=90, corpus=corpus, material_classes={"habitat": "solid"})

The same streams and step always give the same snapshot.
"""

from . import concern, evidence, gaps, telemetry

NOMINAL, WATCH, ALERT = "nominal", "watch", "alert"

# channel, tile title, unit. Temperature is not a crew tile, but it feeds the co-occurrence rules.
CREW_TILES = [
    ("o2_percent", "O2", "%"),
    ("total_pressure_kpa", "Total pressure", "kPa"),
    ("co_ppm", "CO", "ppm"),
    ("co2_ppm", "CO2", "ppm"),
    ("smoke_level", "Smoke", "index"),
    ("flow_cm_s", "Airflow", "cm/s"),
]

# Live channel -> gap-engine axis, for the evidence-envelope check.
ENVELOPE_AXES = {"o2_percent": "o2_percent", "total_pressure_kpa": "pressure", "flow_cm_s": "flow_speed"}

# An axis is "outside the tested conditions" when the live value is beyond every tested
# value (ONE_SIDED) or nothing is indexed for it. BOUNDED (between tested conditions) and
# INSUFFICIENT (thin but nearby) are shown in the status, but do not raise an entry.
OUTSIDE = {gaps.ONE_SIDED, gaps.NO_INDEXED_DATA}

FIRE_SIGNATURE = {"smoke_level", "co_ppm"}
ATMOSPHERE = {"o2_percent", "total_pressure_kpa"}

# Crew banner priority, most urgent first. The banner shows only the first active concern.
# This order is OUR choice (INTERPRETATION) and needs review by someone with crew-ops
# experience before it is shown as anything but a demo:
#   1. CO_OCCURRENCE      several channels moving together under an explicit rule
#   2. THRESHOLD on smoke or CO
#   3. THRESHOLD on O2 or total pressure
#   4. THRESHOLD on any other channel (CO2, temperature, airflow)
#   5. ENVELOPE           live conditions outside what has been tested for the material
#   6. TREND on smoke, CO or temperature
#   7. TREND on any other channel
# Ties keep CREW_TILES channel order, then compartment order.
BANNER_PRIORITY = [
    ("CO_OCCURRENCE", None),
    ("THRESHOLD", FIRE_SIGNATURE),
    ("THRESHOLD", ATMOSPHERE),
    ("THRESHOLD", None),
    ("ENVELOPE", None),
    ("TREND", FIRE_SIGNATURE | {"temperature_c"}),
    ("TREND", None),
]

NOT_COMPARED = {"co_ppm", "co2_ppm", "smoke_level"}


def record_compartments(scenario, seed=1, steps=60, dt=1.0, compartments=("habitat",)):
    """{compartment: [samples]}. The scenario plays in the first compartment, the rest run nominal."""
    return {name: telemetry.record(scenario if number == 0 else "nominal", seed + number, steps, dt, name)
            for number, name in enumerate(compartments)}


def priority(item):
    """Position of a concern in BANNER_PRIORITY (lower is more urgent)."""
    for rank, (kind, channels) in enumerate(BANNER_PRIORITY):
        if item["type"] == kind and (channels is None or item.get("channel") in channels):
            return rank
    return len(BANNER_PRIORITY)


def _window(sample, history, window):
    return [h for h in history if sample["t"] - window <= h["t"] < sample["t"]]


def co_occurrence(sample, history, rules, alerts=()):
    """One grouped concern per rule whose every channel moved far enough inside its window."""
    found = []
    for rule in rules:
        recent = _window(sample, history, rule.get("window_s", 60))
        changes, ok = {}, bool(recent)
        wanted = [(ch, limit, 1) for ch, limit in (rule.get("rise") or {}).items()]
        wanted += [(ch, limit, -1) for ch, limit in (rule.get("fall") or {}).items()]
        for channel, limit, sign in wanted:
            earlier = [h for h in recent if h.get(channel) is not None]
            if sample.get(channel) is None or not earlier:
                ok = False
                break
            change = sample[channel] - min(earlier, key=lambda h: h["t"])[channel]
            changes[channel] = round(change, 4)
            if sign * change < limit:
                ok = False
                break
        if not ok or not wanted:
            continue
        channels = [ch for ch, _, _ in wanted]
        found.append({
            "type": "CO_OCCURRENCE", "rule": rule["id"], "name": rule.get("name", rule["id"]),
            "compartment": sample.get("compartment"), "channels": channels, "changes": changes,
            "window_s": rule.get("window_s", 60), "label": "ILLUSTRATIVE", "thresholds": "PLACEHOLDER",
            "members": [a for a in alerts if a.get("channel") in channels],
            "message": (f"{rule.get('name', rule['id'])} within {rule.get('window_s', 60)} s "
                        f"(ILLUSTRATIVE rule, PLACEHOLDER thresholds)."),
        })
    return found


def envelope_check(sample, corpus, material_class, gravity_g=None):
    """The gap engine's combination check on the live atmosphere, for one material class.

    The corpus is first narrowed to the runs and investigations whose fuel phase or
    material matches the class (concern.matching_runs), so the material is a filter here,
    and the material axis itself is left unset.
    """
    compartment = sample.get("compartment")
    if not material_class or not str(material_class).strip():
        return {"compartment": compartment, "material_class": None, "state": gaps.NOT_EVALUATED,
                "combination": None, "axes": {}, "outside": [], "label": "DERIVED",
                "summary": f"{compartment}: material class not set, so the evidence envelope is not checked."}
    subset = {"runs": concern.matching_runs(corpus, material_class),
              "investigations": concern.matching_investigations(corpus, material_class)}
    scen = evidence.scenario({
        "o2_percent": sample.get("o2_percent"),
        "pressure": sample.get("total_pressure_kpa"), "pressure_unit": "kPa",
        "flow_speed": sample.get("flow_cm_s"), "flow_unit": "cm/s",
        "gravity_g": gravity_g,
    })
    result = gaps.analyze(subset, scen)
    axes = {axis: {"class": found.get("class"), "state": found["state"], "side": found.get("side"),
                   "summary": found["summary"]}
            for axis, found in result["axes"].items() if axis in gaps.NUMERIC_AXES}
    outside = [axis for axis, found in axes.items() if found["class"] in OUTSIDE]
    checked = [gaps.AXIS_NAMES[a] for a, found in axes.items() if found["state"] == gaps.EVALUATED]
    combined = result["combination"]["class"] or gaps.NOT_EVALUATED
    summary = (f"{compartment} ({material_class}, {len(subset['runs'])} runs in class): {combined} "
               f"on {', '.join(checked) or 'no axis'}"
               f"{'; outside tested conditions on ' + ', '.join(gaps.AXIS_NAMES[a] for a in outside) if outside else ''}.")
    return {"compartment": compartment, "material_class": material_class, "state": gaps.EVALUATED,
            "combination": result["combination"]["class"], "skipped_axes": result["skipped_axes"],
            "runs_in_class": len(subset["runs"]), "axes": axes, "outside": outside, "label": "DERIVED",
            "summary": summary}


def _envelope_entry(check):
    if not check["outside"]:
        return None
    parts = []
    for axis in check["outside"]:
        found = check["axes"][axis]
        where = f"{found['side']} every tested value" if found["side"] in (gaps.SIDE_ABOVE, gaps.SIDE_BELOW) \
            else "with no indexed data"
        parts.append(f"{gaps.AXIS_NAMES[axis]} is {where}")
    channel = next((ch for ch, axis in ENVELOPE_AXES.items() if axis == check["outside"][0]), None)
    return {"type": "ENVELOPE", "compartment": check["compartment"], "channel": channel,
            "axes": check["outside"], "combination": check["combination"], "label": "DERIVED",
            "message": (f"Live conditions are outside the tested conditions for {check['material_class']}: "
                        f"{'; '.join(parts)}. This is about evidence coverage, not a fire prediction.")}


def tile_status(channel, alerts, groups, envelope_entry):
    """alert: a PLACEHOLDER limit is crossed on this channel.
    watch: the channel is trending, is in a co-occurring group, or is outside tested conditions.
    nominal: none of those."""
    if any(a["type"] == "THRESHOLD" and a["channel"] == channel for a in alerts):
        return ALERT
    if any(a["type"] in ("TREND", "ENVELOPE") and a["channel"] == channel for a in alerts):
        return WATCH
    if any(channel in g["channels"] for g in groups):
        return WATCH
    if envelope_entry and ENVELOPE_AXES.get(channel) in envelope_entry["axes"]:
        return WATCH
    return NOMINAL


def tiles(sample, alerts, groups, check, entry):
    """The crew tiles, each with status and the reasons shown when the tile is tapped."""
    out = []
    for channel, title, unit in CREW_TILES:
        reasons = [f"{a['type']}: {a['message']}" for a in alerts if a.get("channel") == channel]
        reasons += [f"CO_OCCURRENCE: {g['message']}" for g in groups if channel in g["channels"]]
        axis = ENVELOPE_AXES.get(channel)
        if axis and axis in check.get("axes", {}):
            reasons.append(f"Evidence (DERIVED): {check['axes'][axis]['summary']}")
        if channel in NOT_COMPARED:
            reasons.append("Shown, but not compared with experiments.")
        out.append({"channel": channel, "title": title, "unit": unit, "value": sample.get(channel),
                    "status": tile_status(channel, alerts, groups, entry), "reasons": reasons,
                    "label": "SIMULATED"})
    return out


def banner(compartment, concerns):
    """The single highest-priority concern with a one-sentence reason, or a quiet line."""
    active = sorted(concerns, key=priority)
    if not active:
        return {"compartment": compartment, "type": None, "status": NOMINAL,
                "text": f"No active concern in {compartment}. Values are SIMULATED, limits PLACEHOLDER."}
    top = active[0]
    label = top.get("label") or "PLACEHOLDER"
    return {"compartment": compartment, "type": top["type"], "channel": top.get("channel"),
            "status": ALERT if top["type"] in ("CO_OCCURRENCE", "THRESHOLD") else WATCH,
            "text": f"{compartment}: {top['message']} [{label}]", "others": len(active) - 1}


def _channel_order(item):
    order = [ch for ch, _, _ in CREW_TILES]
    channel = item.get("channel")
    return order.index(channel) if channel in order else len(order)


def snapshot(streams, step, corpus, material_classes=None, gravity_g=None, alerts_config=None):
    """Everything Ops shows at one step. streams is {compartment: [samples]} from record_compartments."""
    config = alerts_config if alerts_config is not None else concern.load_alerts()
    rules = (config.get("co_occurrence") or {}).get("rules", [])
    material_classes = material_classes or {}
    compartments, envelope, grouped, entries = {}, [], [], []
    for name, samples in streams.items():
        if not samples:
            continue
        upto = samples[:max(0, min(step, len(samples) - 1)) + 1]
        sample, history = upto[-1], upto[:-1]
        material = material_classes.get(name)
        verdict = concern.evaluate(sample, corpus, material, history, config)
        alerts = [dict(a, compartment=name) for a in verdict["alerts"]]
        groups = co_occurrence(sample, history, rules, alerts)
        check = envelope_check(sample, corpus, material, gravity_g)
        entry = _envelope_entry(check)
        concerns = groups + ([entry] if entry else []) + alerts
        concerns.sort(key=_channel_order)
        compartments[name] = {
            "sample": sample, "material_class": material, "alerts": alerts,
            "reasoning": verdict["reasoning"], "tiles": tiles(sample, alerts, groups, check, entry),
            "banner": banner(name, concerns),
        }
        envelope.append(check)
        grouped += groups
        if entry:
            entries.append(entry)
    times = [c["sample"]["t"] for c in compartments.values()]
    return {
        "label": "SIMULATED", "step": step, "t": max(times) if times else None,
        "compartments": compartments,
        "combined": {
            "envelope": envelope,
            "co_occurring": grouped,
            "entries": entries + grouped,
            "note": "No aggregate score: each entry stands on its own, with its own label.",
        },
    }
