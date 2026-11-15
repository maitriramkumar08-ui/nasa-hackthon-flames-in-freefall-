"""Say where the indexed evidence stops for a scenario, axis by axis.

For each axis (O2, pressure, flow, gravity, material class, pillar) we look at
the tested values and say whether the scenario value was directly tested, is
bounded by tests on both sides, lies beyond the tests on one side, or has too
little or no data. Then we ask the stricter question: did any single run match
every axis at once? All of it is plain code (DERIVED).

    report = gaps.analyze(corpus, evidence.scenario(raw))

Where the values come from:
- Test runs give one point each.
- An investigation with no runs gives its reported range endpoints (min and
  max) as tested values. They count per axis but never for the combination
  or the nearest runs, because a range is not a run.

When data are NOT_COMPARABLE:
- If the scenario names a scale, points from a known different scale are left
  out. If that leaves nothing, the axis is NOT_COMPARABLE.
- Values that came from words ("microgravity", see evidence.GRAVITY_WORDS) can
  show which side of the scenario the tests lie on, but cannot make an axis
  DIRECTLY_TESTED. If only word values are within tolerance, the axis is
  NOT_COMPARABLE.
"""

import math

from . import evidence, ranking

DIRECTLY_TESTED = "DIRECTLY_TESTED"
BOUNDED = "BOUNDED"
ONE_SIDED = "ONE_SIDED"
INSUFFICIENT = "INSUFFICIENT"
NOT_COMPARABLE = "NOT_COMPARABLE"
NO_INDEXED_DATA = "NO_INDEXED_DATA"
NOT_SPECIFIED = "NOT_SPECIFIED"

# axis: (tolerance key in decisions.json, unit shown in the report)
NUMERIC_AXES = {
    "o2_percent": ("o2_percent_points", "%"),
    "pressure": ("pressure_kpa", "kPa"),
    "flow_speed": ("flow_cm_s", "cm/s"),
    "gravity": ("gravity_g", "g"),
}
CATEGORY_AXES = ["material_class", "pillar"]

# Most serious first: the combination can never look better than its worst axis.
SEVERITY = [NO_INDEXED_DATA, NOT_COMPARABLE, ONE_SIDED, BOUNDED, INSUFFICIENT, DIRECTLY_TESTED]


def classify_axis(tested_values, target, tolerance, min_runs):
    """(gap class, distance in tolerances) for one numeric axis."""
    values = [v for v in tested_values if v is not None]
    if not values:
        return NO_INDEXED_DATA, None
    within = sum(1 for v in values if abs(v - target) <= tolerance)
    if within >= min_runs:
        return DIRECTLY_TESTED, 0.0
    if within:
        return INSUFFICIENT, 0.0
    distance = min(abs(v - target) for v in values) / tolerance
    if min(values) < target < max(values):
        return BOUNDED, distance
    return ONE_SIDED, distance


def _points(corpus):
    """Runs, plus one range point for each investigation that has no runs."""
    points = [{"run": r, "values": {q: [r["values"][q]] for q in NUMERIC_AXES},
               "words": set(r["from_words"]), "scale": r["scale"], "pillar": r["pillar"],
               "classes": {ranking.material_class(m) for m in r["materials"]}}
              for r in corpus["runs"]]
    with_runs = {r["investigation_id"] for r in corpus["runs"]}
    for inv in corpus["investigations"]:
        if inv["id"] in with_runs:
            continue
        ranges = inv["ranges"]
        points.append({
            "run": None,
            "values": {q: [ranges[q]["min"], ranges[q]["max"]] if q in ranges else [None]
                       for q in NUMERIC_AXES},
            "words": {q for q in ranges if ranges[q]["from_words"]},
            "scale": inv["scale"], "pillar": inv["pillar"],
            "classes": {ranking.material_class(f["material"]) for f in inv["fuels"]},
        })
    return points


def _comparable(point, scen):
    return not scen["scale"] or point["scale"] in (scen["scale"], None, "unknown")


def _numeric_axis(points, axis, target, tolerance, min_runs, scen):
    usable = [p for p in points if _comparable(p, scen)]
    every = [v for p in points for v in p["values"][axis] if v is not None]
    values = [v for p in usable for v in p["values"][axis] if v is not None]
    measured = [v for p in usable if axis not in p["words"] for v in p["values"][axis] if v is not None]

    gap, distance = classify_axis(values, target, tolerance, min_runs)
    if gap in (DIRECTLY_TESTED, INSUFFICIENT):
        gap, _ = classify_axis(measured, target, tolerance, min_runs)
        if gap not in (DIRECTLY_TESTED, INSUFFICIENT):
            gap = NOT_COMPARABLE
    if gap == NO_INDEXED_DATA and every:
        gap, values = NOT_COMPARABLE, every
        distance = min(abs(v - target) for v in values) / tolerance

    below = [v for v in values if v < target]
    above = [v for v in values if v > target]
    return {
        "class": gap,
        "distance": None if distance is None else round(distance, 3),
        "nearest_value": min(values, key=lambda v: abs(v - target)) if values else None,
        "nearest_below": max(below) if below else None,
        "nearest_above": min(above) if above else None,
        "tested_min": min(values) if values else None,
        "tested_max": max(values) if values else None,
        "runs_within": sum(1 for v in measured if abs(v - target) <= tolerance),
        "tolerance": tolerance,
    }


def _category_axis(points, axis, target, min_runs, scen):
    usable = [p for p in points if _comparable(p, scen)]
    matching = sum(1 for p in usable if _matches(p, axis, target))
    if matching >= min_runs:
        gap = DIRECTLY_TESTED
    elif matching:
        gap = INSUFFICIENT
    elif points and not usable:
        gap = NOT_COMPARABLE
    else:
        gap = NO_INDEXED_DATA
    return {"class": gap, "distance": 0.0 if matching else 1.0, "nearest_value": target if matching else None,
            "tested_min": None, "tested_max": None, "runs_within": matching}


def _matches(point, axis, target):
    if axis == "pillar":
        return point["pillar"] == target
    return target in point["classes"]


def _targets(scen):
    material = scen["material"]
    return {
        "o2_percent": scen["o2_percent"], "pressure": scen["pressure"],
        "flow_speed": scen["flow_speed"], "gravity": scen["gravity"],
        "material_class": ranking.material_class(material) or (material.lower() if material else None),
        "pillar": scen["pillar"],
    }


def _run_fits(point, targets, tolerances, scen):
    if point["run"] is None or not _comparable(point, scen):
        return False
    for axis, target in targets.items():
        if target is None:
            continue
        if axis in NUMERIC_AXES:
            value = point["values"][axis][0]
            if value is None or axis in point["words"] or abs(value - target) > tolerances[axis]:
                return False
        elif not _matches(point, axis, target):
            return False
    return True


def _nearest(points, targets, tolerances):
    """The three closest runs, by root-mean-square distance in tolerances over the axes both have."""
    ranked = []
    for point in points:
        if point["run"] is None:
            continue
        gaps = [(point["values"][a][0] - targets[a]) / tolerances[a] for a in NUMERIC_AXES
                if targets[a] is not None and point["values"][a][0] is not None]
        if not gaps:
            continue
        run = point["run"]
        ranked.append({"run_id": run["run_id"], "acronym": run["acronym"],
                       "distance": round(math.sqrt(sum(g * g for g in gaps) / len(gaps)), 3),
                       "axes_compared": len(gaps), "source": run["source"]})
    ranked.sort(key=lambda r: (r["distance"], -r["axes_compared"]))
    return ranked[:3]


def _sentence(axis, found, target, unit, min_runs):
    name = axis.replace("_", " ")
    if found["class"] == NOT_SPECIFIED:
        return f"{name}: not given in the scenario."
    shown = f"{target} {unit}".strip()
    if found["class"] == DIRECTLY_TESTED:
        return f"{name}: {found['runs_within']} tested runs match the scenario value {shown}."
    if found["class"] == INSUFFICIENT:
        return (f"{name}: only {found['runs_within']} tested run(s) match the scenario value {shown}; "
                f"at least {min_runs} are needed.")
    if found["class"] == BOUNDED:
        return (f"{name}: {shown} is not directly measured; it is bounded by tested values "
                f"{found['nearest_below']} and {found['nearest_above']} {unit}.")
    if found["class"] == ONE_SIDED:
        return (f"{name}: {shown} is not directly measured; the nearest tested value is "
                f"{found['nearest_value']} {unit}, {found['distance']} tolerances away, on one side only.")
    if found["class"] == NOT_COMPARABLE:
        return (f"{name}: {shown} is not directly measured; the data that exist come from a different "
                f"scale or from words, so they are not comparable.")
    return f"{name}: no indexed data for {shown}."


def analyze(corpus, scen, tolerances=None, min_runs=None):
    """Per-axis gap classes, the combination class, the nearest runs and a short report."""
    chosen = evidence.decisions()
    tolerances = tolerances or chosen["gap_tolerances"]
    min_runs = min_runs or chosen["min_runs_for_sufficient"]
    by_axis = {axis: tolerances[key] for axis, (key, _) in NUMERIC_AXES.items()}

    points = _points(corpus)
    targets = _targets(scen)
    axes = {}
    for axis, target in targets.items():
        if target is None:
            axes[axis] = {"class": NOT_SPECIFIED, "distance": None, "nearest_value": None,
                          "tested_min": None, "tested_max": None, "runs_within": 0}
        elif axis in NUMERIC_AXES:
            axes[axis] = _numeric_axis(points, axis, target, by_axis[axis], min_runs, scen)
        else:
            axes[axis] = _category_axis(points, axis, target, min_runs, scen)

    fits = [p["run"]["run_id"] for p in points if _run_fits(p, targets, by_axis, scen)]
    if len(fits) >= min_runs:
        combined = DIRECTLY_TESTED
    elif fits:
        combined = INSUFFICIENT
    else:
        classes = [axes[a]["class"] for a in axes if axes[a]["class"] != NOT_SPECIFIED]
        worst = min(classes, key=SEVERITY.index) if classes else NO_INDEXED_DATA
        combined = INSUFFICIENT if worst == DIRECTLY_TESTED else worst

    report = [_sentence(a, axes[a], targets[a], NUMERIC_AXES.get(a, (None, ""))[1], min_runs) for a in axes]
    report.append(f"Combination: {combined}. {len(fits)} run(s) match every given axis at the same time.")
    if targets["gravity"] and axes["gravity"]["class"] != DIRECTLY_TESTED:
        report.append(f"Microgravity and 1 g results are not results at {targets['gravity']} g; "
                      "the scenario gravity is not directly measured.")

    return {"axes": axes, "combination": {"class": combined, "runs_matching": fits},
            "nearest_runs": _nearest(points, targets, by_axis), "report": report, "label": "DERIVED"}
