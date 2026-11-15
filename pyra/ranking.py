"""Rank investigations by how close they are to a user's scenario.

Every investigation gets seven sub-scores between 0 and 1 and a weighted total.
All of it is plain arithmetic (DERIVED), so anyone can redo a score by hand:

    entries = ranking.rank(corpus, evidence.scenario(raw))

Numeric dimensions score 1 inside the tested range and fall off in a straight
line outside it, reaching 0 at one SCALES step away. A dimension the scenario
or the investigation does not give scores 0 and is listed as unmatched with
the reason. Missing is never treated as a match.
"""

from . import evidence

DIMENSIONS = ["atmosphere", "flow", "gravity", "material", "objective", "scale", "measurement"]

# How far outside the tested range a value can be before its score reaches 0.
# Our own starting choices (DERIVED), not NASA data.
SCALES = {
    "o2_percent": 10.0,       # O2 percentage points
    "o2_partial_kpa": 10.0,   # kPa of oxygen partial pressure
    "flow_speed": 20.0,       # cm/s
    "gravity": 0.5,           # g
}

# Our own keyword grouping for "same class" material matches. Not a NASA taxonomy.
MATERIAL_CLASSES = {
    "fabric": ["fabric", "cotton", "nomex", "cloth", "textile"],
    "plastic": ["plastic", "pmma", "acrylic", "polyethylene", "delrin", "polymer", "silicone"],
    "paper": ["paper", "kimwipe", "cellulose"],
    "liquid fuel": ["heptane", "decane", "ethanol", "methanol", "dodecane", "fuel"],
    "gas fuel": ["methane", "ethylene", "propane", "hydrogen"],
}

MATCH_LEVELS = {"exact": 1.0, "class": 0.6, "phase": 0.3}


def material_class(material):
    """The MATERIAL_CLASSES group a material name falls in, or None."""
    if not material:
        return None
    text = material.lower()
    for group, keywords in MATERIAL_CLASSES.items():
        if any(word in text for word in keywords):
            return group
    return None


def closeness(value, low, high, scale):
    """1 inside [low, high], then a straight-line drop to 0 one scale step outside."""
    if value is None or low is None or high is None:
        return None
    outside = max(low - value, value - high, 0.0)
    return max(0.0, 1.0 - outside / scale)


def _span(inv, runs, quantity):
    """(low, high) over the investigation's reported range and its runs' values."""
    values = [r["values"][quantity] for r in runs if r["values"][quantity] is not None]
    reported = inv["ranges"].get(quantity)
    if reported:
        values += [v for v in (reported["min"], reported["max"]) if v is not None]
    return (min(values), max(values), values) if values else (None, None, [])


def _atmosphere(inv, runs, scen):
    o2_low, o2_high, _ = _span(inv, runs, "o2_percent")
    p_low, p_high, _ = _span(inv, runs, "pressure")
    parts = [closeness(scen["o2_percent"], o2_low, o2_high, SCALES["o2_percent"])]
    if None not in (scen["o2_percent"], scen["pressure"], o2_low, p_low):
        parts.append(closeness(scen["o2_percent"] * scen["pressure"] / 100,
                               o2_low * p_low / 100, o2_high * p_high / 100,
                               SCALES["o2_partial_kpa"]))
    known = [p for p in parts if p is not None]
    if not known:
        return 0.0, "no O2 value to compare (scenario or investigation)"
    return sum(known) / len(known), None


def _flow(inv, runs, scen):
    low, high, _ = _span(inv, runs, "flow_speed")
    score = closeness(scen["flow_speed"], low, high, SCALES["flow_speed"])
    return (0.0, "no flow speed to compare") if score is None else (score, None)


def _gravity(inv, runs, scen):
    # Distance to the nearest tested gravity, not to a range: 0 g and 1 g
    # results say nothing direct about the 0.16 g in between.
    _, _, tested = _span(inv, runs, "gravity")
    if scen["gravity"] is None or not tested:
        return 0.0, "no gravity value to compare"
    nearest = min(abs(g - scen["gravity"]) for g in tested)
    return max(0.0, 1.0 - nearest / SCALES["gravity"]), None


def _material(inv, scen):
    materials = [f["material"].lower() for f in inv["fuels"] if f["material"]]
    phases = {f["phase"] for f in inv["fuels"]}
    wanted = (scen["material"] or "").lower()
    if not wanted and not scen["fuel_phase"]:
        return 0.0, "scenario gives no material or fuel phase"
    if wanted and wanted in materials:
        return MATCH_LEVELS["exact"], None
    group = material_class(wanted)
    if group and group in {material_class(m) for m in materials}:
        return MATCH_LEVELS["class"], None
    if scen["fuel_phase"] and scen["fuel_phase"] in phases:
        return MATCH_LEVELS["phase"], None
    return 0.0, "no matching material, class or phase"


def _same(scen_value, inv_value, what):
    if not scen_value:
        return 0.0, f"scenario gives no {what}"
    if scen_value == inv_value:
        return 1.0, None
    return 0.0, f"{what} is {inv_value or 'unknown'}, scenario wants {scen_value}"


def _measurement(inv, scen):
    if not scen["outputs"]:
        return 0.0, "scenario names no outputs"
    recorded = " ".join(inv["sensors"] + [f["text"] for f in inv["findings"]]).lower()
    found = [o for o in scen["outputs"] if o.lower() in recorded]
    if not found:
        return 0.0, "none of the wanted outputs appear in sensors or findings"
    return len(found) / len(scen["outputs"]), None


def score(inv, runs, scen):
    """{dimension: (score, reason or None)} for one investigation."""
    return {
        "atmosphere": _atmosphere(inv, runs, scen),
        "flow": _flow(inv, runs, scen),
        "gravity": _gravity(inv, runs, scen),
        "material": _material(inv, scen),
        "objective": _same(scen["pillar"], inv["pillar"], "pillar"),
        "scale": _same(scen["scale"], inv["scale"], "scale"),
        "measurement": _measurement(inv, scen),
    }


def evidence_class(scores, total):
    if all(scores[d] >= 0.7 for d in ("atmosphere", "gravity", "material")):
        return "direct"
    return "supporting" if total >= 0.4 else "background"


def explain(entry):
    """One fixed-template sentence pair describing a ranked entry."""
    best = max(DIMENSIONS, key=lambda d: entry["scores"][d])
    text = (f"{entry['acronym']} scores {entry['total']:.3f} ({entry['evidence_class']} evidence). "
            f"Its closest match is {best} ({entry['scores'][best]:.2f}).")
    if entry["unmatched"]:
        text += " Unmatched: " + ", ".join(entry["unmatched"]) + "."
    return text


def rank(corpus, scen, weights=None):
    """Every investigation scored against the scenario, best first."""
    weights = weights or evidence.decisions()["ranking_weights"]
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"ranking weights add up to {sum(weights.values())}, they must add up to 1")
    missing = [d for d in DIMENSIONS if d not in weights]
    if missing:
        raise ValueError(f"ranking weights have no value for: {', '.join(missing)}")

    entries = []
    for inv in corpus["investigations"]:
        runs = [r for r in corpus["runs"] if r["investigation_id"] == inv["id"]]
        found = score(inv, runs, scen)
        scores = {d: round(found[d][0], 3) for d in DIMENSIONS}
        total = round(sum(weights[d] * found[d][0] for d in DIMENSIONS), 3)
        unmatched = [d for d in DIMENSIONS if found[d][0] < 0.5]
        entry = {
            "investigation_id": inv["id"], "acronym": inv["acronym"], "name": inv["name"],
            "total": total, "scores": scores,
            "evidence_class": evidence_class(scores, total),
            "unmatched": unmatched,
            "reasons": {d: found[d][1] or f"scored {scores[d]:.2f}, below 0.5" for d in unmatched},
            "label": "DERIVED",
        }
        entry["explanation"] = explain(entry)
        entries.append(entry)
    return sorted(entries, key=lambda e: e["total"], reverse=True)
