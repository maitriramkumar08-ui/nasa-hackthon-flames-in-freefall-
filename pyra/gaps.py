"""Say where the indexed evidence stops for a scenario, axis by axis.

For each axis the scenario sets we look at the tested values and say whether
the scenario value was directly tested, sits between tested conditions, lies
beyond the tested conditions on one side, or has too little or no data. Then
we ask the stricter question: did any single run match every set axis at once?
All of it is plain code (DERIVED).

    report = gaps.analyze(corpus, evidence.scenario(raw))

Axis state vs coverage class
----------------------------
An axis the user left blank is NOT_EVALUATED. That is an axis *state*, not a
coverage class: it is never in COVERAGE_CLASSES, it never feeds the
combination class, and analyze() lists such axes in ``skipped_axes``.

Two kinds of axis
-----------------
- numeric (o2_percent, pressure, flow_speed, gravity): tested min/max with
  unit, the scenario value, which side of the tested values the scenario is
  on, the distance to the nearest tested value (absolute and in tolerances)
  and the runs within tolerance.
- categorical (material_class, pillar): the tested categories with
  investigation and run counts each, and whether the scenario's category is
  among them. There is no range and no distance on a categorical axis.

Coverage classes and their precedence (numeric axis)
----------------------------------------------------
The first rule that applies wins:

1. nothing usable at all           -> NO_INDEXED_DATA, or NOT_COMPARABLE when
                                       values exist but all come from another scale
2. >= min_runs runs within tol      -> DIRECTLY_TESTED
3. 1 .. min_runs-1 runs within tol  -> INSUFFICIENT  (e.g. 2 runs, min_runs 3:
                                       INSUFFICIENT, never DIRECTLY_TESTED)
4. only an investigation-level range endpoint within tol
                                    -> INSUFFICIENT  (a range is not a run, so it
                                       can never make an axis DIRECTLY_TESTED)
5. only word values within tol      -> NOT_COMPARABLE ("microgravity" is a word,
                                       see evidence.GRAVITY_WORDS)
6. tested values on both sides      -> BOUNDED
7. otherwise (all on one side)      -> ONE_SIDED

BOUNDED means the scenario value lies *between tested conditions*. It says
nothing about outcomes between them: flammability can be non-monotonic in
gravity and flow (for example a flame can be weaker at partial gravity than
at both 0 g and 1 g), so a BOUNDED value is not interpolated evidence.

ONE_SIDED means every tested value is on the same side of the scenario value
and none is within tolerance: the scenario is extrapolation.

Categorical axes use the same order: >= min_runs matching runs is
DIRECTLY_TESTED, fewer (or only range-level investigations) is INSUFFICIENT.

Where the values come from
--------------------------
- Test runs give one point each.
- An investigation with no runs gives its reported range endpoints (min and
  max) as tested values. They count for side, distance and BOUNDED, but never
  for DIRECTLY_TESTED, the combination or the nearest runs (rule 4 above).
- If the scenario names a scale, points from a known different scale are left
  out. If that leaves nothing, the axis is NOT_COMPARABLE.
"""

import math

from . import evidence, ranking

# The coverage enum. NOT_EVALUATED is deliberately not in it.
DIRECTLY_TESTED = "DIRECTLY_TESTED"
BOUNDED = "BOUNDED"
ONE_SIDED = "ONE_SIDED"
INSUFFICIENT = "INSUFFICIENT"
NOT_COMPARABLE = "NOT_COMPARABLE"
NO_INDEXED_DATA = "NO_INDEXED_DATA"
COVERAGE_CLASSES = (DIRECTLY_TESTED, BOUNDED, ONE_SIDED, INSUFFICIENT, NOT_COMPARABLE, NO_INDEXED_DATA)

# Axis states.
EVALUATED = "EVALUATED"
NOT_EVALUATED = "NOT_EVALUATED"

NUMERIC = "numeric"
CATEGORICAL = "categorical"

# Which side of the tested values the scenario value is on.
SIDE_WITHIN = "within"   # at least one tested value within tolerance
SIDE_BOTH = "both"       # tested values below and above, none within tolerance
SIDE_ABOVE = "above"     # scenario is above every tested value
SIDE_BELOW = "below"     # scenario is below every tested value

# axis: (tolerance key in decisions.json, unit shown in the report)
NUMERIC_AXES = {
    "o2_percent": ("o2_percent_points", "%"),
    "pressure": ("pressure_kpa", "kPa"),
    "flow_speed": ("flow_cm_s", "cm/s"),
    "gravity": ("gravity_g", "g"),
}
CATEGORY_AXES = ["material_class", "pillar"]
AXES = list(NUMERIC_AXES) + CATEGORY_AXES

AXIS_NAMES = {"o2_percent": "O2", "pressure": "Pressure", "flow_speed": "Flow",
              "gravity": "Gravity", "material_class": "Material", "pillar": "Pillar"}

# Most serious first: the combination can never look better than its worst axis.
SEVERITY = [NO_INDEXED_DATA, NOT_COMPARABLE, ONE_SIDED, BOUNDED, INSUFFICIENT, DIRECTLY_TESTED]


def classify_axis(tested_values, target, tolerance, min_runs):
    """(gap class, distance in tolerances) for plain run values on one numeric axis.

    Same precedence as the module docstring, for the simple case where every
    value is a run: >= min_runs within tolerance is DIRECTLY_TESTED, fewer is
    INSUFFICIENT, values on both sides is BOUNDED (between tested conditions,
    not a statement about outcomes), else ONE_SIDED.
    """
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


def category_key(material):
    """The category a material name is counted under: its MATERIAL_CLASSES group, else its own name."""
    if not material or not str(material).strip():
        return None
    text = str(material).strip().lower()
    if text in ranking.MATERIAL_CLASSES:  # a class name picked as-is ("gas fuel" must not become "liquid fuel")
        return text
    return ranking.material_class(material) or text


def _points(corpus):
    """Runs, plus one range point for each investigation that has no runs."""
    points = [{"run": r, "investigation_id": r.get("investigation_id"),
               "values": {q: [r["values"].get(q)] for q in NUMERIC_AXES},
               "words": set(r.get("from_words") or []), "scale": r.get("scale"), "pillar": r.get("pillar"),
               "classes": {category_key(m) for m in r.get("materials") or []} - {None}}
              for r in corpus["runs"]]
    with_runs = {r.get("investigation_id") for r in corpus["runs"]}
    for inv in corpus["investigations"]:
        if inv["id"] in with_runs:
            continue
        ranges = inv.get("ranges") or {}
        points.append({
            "run": None, "investigation_id": inv["id"],
            "values": {q: [ranges[q]["min"], ranges[q]["max"]] if q in ranges else [None]
                       for q in NUMERIC_AXES},
            "words": {q for q in ranges if ranges[q]["from_words"]},
            "scale": inv.get("scale"), "pillar": inv.get("pillar"),
            "classes": {category_key(f["material"]) for f in inv.get("fuels") or []} - {None},
        })
    return points


def _comparable(point, scen):
    return not scen.get("scale") or point["scale"] in (scen["scale"], None, "unknown")


def _side(values, target, any_within):
    if any_within:
        return SIDE_WITHIN
    below = any(v < target for v in values)
    above = any(v > target for v in values)
    if below and above:
        return SIDE_BOTH
    return SIDE_ABOVE if below else SIDE_BELOW


def _numeric_axis(points, axis, target, tolerance, min_runs, scen):
    usable = [p for p in points if _comparable(p, scen)]

    def values_of(chosen, runs, words):
        return [v for p in chosen if (p["run"] is not None) == runs and (axis in p["words"]) == words
                for v in p["values"][axis] if v is not None]

    run_values = values_of(usable, True, False)
    range_values = values_of(usable, False, False)
    word_values = values_of(usable, True, True) + values_of(usable, False, True)
    values = run_values + range_values + word_values

    def near(found):
        return [v for v in found if abs(v - target) <= tolerance]

    runs_within = len(near(run_values))
    if not values:
        every = [v for p in points for v in p["values"][axis] if v is not None]
        gap, values = (NOT_COMPARABLE, every) if every else (NO_INDEXED_DATA, [])
    elif runs_within >= min_runs:
        gap = DIRECTLY_TESTED
    elif runs_within or near(range_values):
        gap = INSUFFICIENT
    elif near(word_values):
        gap = NOT_COMPARABLE
    elif min(values) < target < max(values):
        gap = BOUNDED
    else:
        gap = ONE_SIDED

    unit = NUMERIC_AXES[axis][1]
    found = {
        "state": EVALUATED, "kind": NUMERIC, "class": gap, "unit": unit, "scenario_value": target,
        "tested_min": min(values) if values else None, "tested_max": max(values) if values else None,
        "side": None, "distance": None, "gap_to_nearest": None, "nearest_value": None,
        "nearest_below": None, "nearest_above": None,
        "runs_within": runs_within, "runs_tested": sum(1 for p in usable if p["run"] is not None
                                                       and p["values"][axis][0] is not None),
        "range_investigations": sum(1 for p in usable if p["run"] is None
                                    and any(v is not None for v in p["values"][axis])),
        "tolerance": tolerance,
    }
    if values:
        nearest = min(values, key=lambda v: abs(v - target))
        below = [v for v in values if v < target]
        above = [v for v in values if v > target]
        any_within = bool(near(values))
        found.update({
            "side": _side(values, target, any_within),
            "distance": 0.0 if any_within else round(abs(nearest - target) / tolerance, 3),
            "gap_to_nearest": 0.0 if any_within else round(abs(nearest - target), 6),
            "nearest_value": nearest,
            "nearest_below": max(below) if below else None,
            "nearest_above": min(above) if above else None,
        })
    return found


def _category_axis(points, axis, target, min_runs, scen):
    usable = [p for p in points if _comparable(p, scen)]
    counts = {}
    for point in usable:
        for category in _categories(point, axis):
            entry = counts.setdefault(category, {"category": category, "investigations": set(), "runs": 0})
            entry["investigations"].add(point["investigation_id"])
            if point["run"] is not None:
                entry["runs"] += 1
    categories = sorted(({"category": c["category"], "investigations": len(c["investigations"]),
                          "runs": c["runs"]} for c in counts.values()),
                        key=lambda c: (-c["runs"], -c["investigations"], c["category"]))

    matching = [p for p in usable if target in _categories(p, axis)]
    matching_runs = sum(1 for p in matching if p["run"] is not None)
    if matching_runs >= min_runs:
        gap = DIRECTLY_TESTED
    elif matching:
        gap = INSUFFICIENT
    elif points and not usable:
        gap = NOT_COMPARABLE
    else:
        gap = NO_INDEXED_DATA
    return {"state": EVALUATED, "kind": CATEGORICAL, "class": gap, "scenario_value": target,
            "categories": categories, "in_tested": target in counts, "runs_within": matching_runs}


def _categories(point, axis):
    if axis == "pillar":
        return {point["pillar"]} if point["pillar"] else set()
    return point["classes"]


def _targets(scen):
    pillar = scen.get("pillar")
    return {
        "o2_percent": scen.get("o2_percent"), "pressure": scen.get("pressure"),
        "flow_speed": scen.get("flow_speed"), "gravity": scen.get("gravity"),
        "material_class": category_key(scen.get("material")),
        "pillar": None if not pillar or pillar == "all" else pillar,
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
        elif target not in _categories(point, axis):
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


def _sentence(axis, found, min_runs):
    """One plain sentence for the text report. Never says safe/unsafe or predicts an outcome."""
    name = axis.replace("_", " ")
    if found["state"] == NOT_EVALUATED:
        return f"{name}: not set in the scenario, so it is not evaluated."
    gap = found["class"]
    if found["kind"] == CATEGORICAL:
        target = found["scenario_value"]
        if gap == DIRECTLY_TESTED:
            return f"{name}: {found['runs_within']} tested runs use {target}."
        if gap == INSUFFICIENT:
            return (f"{name}: only {found['runs_within']} tested run(s) use {target}; "
                    f"at least {min_runs} are needed.")
        if gap == NOT_COMPARABLE:
            return f"{name}: the data for {target} come from a different scale, so they are not comparable."
        return f"{name}: no indexed data for {target}."
    unit = found["unit"]
    shown = f"{found['scenario_value']} {unit}"
    if gap == DIRECTLY_TESTED:
        return f"{name}: {found['runs_within']} tested runs match the scenario value {shown}."
    if gap == INSUFFICIENT:
        return (f"{name}: only {found['runs_within']} tested run(s) match the scenario value {shown}; "
                f"at least {min_runs} are needed.")
    if gap == BOUNDED:
        return (f"{name}: {shown} is not directly measured; it is bounded by tested conditions "
                f"{found['nearest_below']} and {found['nearest_above']} {unit}. This says nothing "
                f"about outcomes in between.")
    if gap == ONE_SIDED:
        tested_side = "below" if found["side"] == SIDE_ABOVE else "above"
        return (f"{name}: {shown} is not directly measured; every tested value is {tested_side} it, "
                f"on one side only. The nearest is {found['nearest_value']} {unit}, "
                f"{found['distance']} tolerances away.")
    if gap == NOT_COMPARABLE:
        return (f"{name}: {shown} is not directly measured; the data that exist come from a different "
                f"scale or from words, so they are not comparable.")
    return f"{name}: no indexed data for {shown}."


def _num(value):
    """Short display of a number: 21.0 -> '21', 101.325 -> '101.3', 0.16 -> '0.16'."""
    return f"{value:.4g}"


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _amount(value, unit):
    """A distance on the axis in words: '13 points' for %, '6.2 kPa' otherwise."""
    shown = _num(value)
    return f"{shown} point{'' if shown == '1' else 's'}" if unit == "%" else f"{shown} {unit}"


def _tested_numeric(found):
    unit = found["unit"]
    low, high = found["tested_min"], found["tested_max"]
    span = f"{_num(low)} {unit}" if low == high else f"{_num(low)}–{_num(high)} {unit}"
    runs, ranges = found["runs_tested"], found["range_investigations"]
    if not runs and not ranges:
        return f"Tested {span} at other scales only."
    counts = [_plural(runs, "run")] if runs else ["no runs"]
    if ranges:
        counts.append(_plural(ranges, "investigation range"))
    return f"Tested {span} ({', '.join(counts)})."


def _yours_numeric(found, min_runs):
    unit, gap = found["unit"], found["class"]
    yours = f"Yours {_num(found['scenario_value'])} {unit}"
    tolerance = f"±{_num(found['tolerance'])} {unit}"
    if gap == DIRECTLY_TESTED:
        return f"{yours} → {_plural(found['runs_within'], 'run')} within {tolerance} (directly tested)."
    if gap == INSUFFICIENT and found["runs_within"]:
        return (f"{yours} → {_plural(found['runs_within'], 'run')} within {tolerance}, "
                f"{min_runs} needed (insufficient).")
    if gap == INSUFFICIENT:
        return f"{yours} → only investigation ranges reach it, no runs within {tolerance} (insufficient)."
    if gap == BOUNDED:
        return (f"{yours} → between tested {_num(found['nearest_below'])} and {_num(found['nearest_above'])} {unit}, "
                f"{_amount(found['gap_to_nearest'], unit)} from the nearest (bounded by tested conditions, "
                f"not by outcomes).")
    if gap == ONE_SIDED:
        return f"{yours} → {_amount(found['gap_to_nearest'], unit)} {found['side']} (one-sided)."
    return f"{yours} → nearby values come from words or another scale (not comparable)."


def _tested_categories(found):
    categories = found["categories"]
    if not categories:
        return "Tested: none indexed."
    first, rest = categories[0], categories[1:]
    parts = [f"{first['category']} ({first['investigations']} inv, {_plural(first['runs'], 'run')})"]
    parts += [f"{c['category']} ({c['investigations']}, {c['runs']})" for c in rest]
    return f"Tested: {', '.join(parts)}."


def _yours_category(found, min_runs):
    target, typed = found["scenario_value"], found.get("scenario_input")
    shown = f"{typed} ({target})" if typed and typed.strip().lower() != target else target
    gap, runs = found["class"], found["runs_within"]
    if gap == DIRECTLY_TESTED:
        result = f"{_plural(runs, 'run')} (directly tested)"
    elif gap == INSUFFICIENT and runs:
        result = f"{_plural(runs, 'run')}, {min_runs} needed (insufficient)"
    elif gap == INSUFFICIENT:
        result = "investigation-level data only, no runs (insufficient)"
    elif gap == NOT_COMPARABLE:
        result = "data from another scale only (not comparable)"
    else:
        result = "no indexed data"
    return f"Yours: {shown} → {result}."


def panel_line(axis, found, min_runs):
    """The one line the gap panel shows for an axis. Never contains 'not provided'."""
    if found["state"] == NOT_EVALUATED:
        return f"{AXIS_NAMES[axis]}: not set. Choose one to check coverage."
    if found["kind"] == CATEGORICAL:
        return f"{_tested_categories(found)} {_yours_category(found, min_runs)}"
    if found["class"] == NO_INDEXED_DATA:
        return f"No indexed tests. Yours {_num(found['scenario_value'])} {found['unit']}."
    return f"{_tested_numeric(found)} {_yours_numeric(found, min_runs)}"


def combination_line(combination):
    if combination["state"] == NOT_EVALUATED:
        return "All axes together: nothing set yet. Choose at least one axis to check coverage."
    runs = len(combination["runs_matching"])
    line = (f"All set axes together: {combination['class']}. "
            f"{runs} run{' matches' if runs == 1 else 's match'} every set axis at once.")
    if combination["skipped_axes"]:
        line += " Not set: " + ", ".join(AXIS_NAMES[a] for a in combination["skipped_axes"]) + "."
    return line


def _skipped(axis):
    return {"state": NOT_EVALUATED, "kind": NUMERIC if axis in NUMERIC_AXES else CATEGORICAL,
            "class": None, "unit": NUMERIC_AXES.get(axis, (None, None))[1]}


def analyze(corpus, scen, tolerances=None, min_runs=None):
    """Per-axis results, the combination class, the nearest runs and a short report.

    axes[axis]["state"] is EVALUATED or NOT_EVALUATED; only EVALUATED axes carry a
    coverage "class". combination["skipped_axes"] names the NOT_EVALUATED ones.
    When no axis is set at all, the combination is NOT_EVALUATED with class None.
    """
    chosen = evidence.decisions()
    tolerances = tolerances or chosen["gap_tolerances"]
    min_runs = min_runs or chosen["min_runs_for_sufficient"]
    by_axis = {axis: tolerances[key] for axis, (key, _) in NUMERIC_AXES.items()}

    points = _points(corpus)
    targets = _targets(scen)
    axes = {}
    for axis, target in targets.items():
        if target is None:
            axes[axis] = _skipped(axis)
        elif axis in NUMERIC_AXES:
            axes[axis] = _numeric_axis(points, axis, target, by_axis[axis], min_runs, scen)
        else:
            axes[axis] = _category_axis(points, axis, target, min_runs, scen)
            if axis == "material_class":
                axes[axis]["scenario_input"] = scen.get("material")
        axes[axis]["summary"] = panel_line(axis, axes[axis], min_runs)

    skipped = [a for a in AXES if axes[a]["state"] == NOT_EVALUATED]
    evaluated = [a for a in AXES if axes[a]["state"] == EVALUATED]
    if not evaluated:
        combination = {"state": NOT_EVALUATED, "class": None, "runs_matching": [],
                       "skipped_axes": skipped, "evaluated_axes": []}
    else:
        fits = [p["run"]["run_id"] for p in points if _run_fits(p, targets, by_axis, scen)]
        if len(fits) >= min_runs:
            combined = DIRECTLY_TESTED
        elif fits:
            combined = INSUFFICIENT
        else:
            worst = min((axes[a]["class"] for a in evaluated), key=SEVERITY.index)
            # Axes covered one at a time are not a combination, so the best this can be is INSUFFICIENT.
            combined = INSUFFICIENT if worst == DIRECTLY_TESTED else worst
        combination = {"state": EVALUATED, "class": combined, "runs_matching": fits,
                       "skipped_axes": skipped, "evaluated_axes": evaluated}
    combination["summary"] = combination_line(combination)

    report = [_sentence(a, axes[a], min_runs) for a in AXES]
    if combination["state"] == EVALUATED:
        report.append(f"Combination: {combination['class']}. {len(combination['runs_matching'])} run(s) "
                      f"match every set axis at the same time.")
    else:
        report.append("Combination: not evaluated, because no axis is set.")
    if skipped:
        report.append(f"Not evaluated (left unset): {', '.join(skipped)}.")
    gravity = targets["gravity"]
    if gravity is not None and gravity not in (0.0, 1.0) and axes["gravity"]["class"] != DIRECTLY_TESTED:
        report.append(f"Microgravity and 1 g results are not results at {gravity} g; "
                      "the scenario gravity is not directly measured.")

    return {"axes": axes, "combination": combination, "skipped_axes": skipped,
            "nearest_runs": _nearest(points, targets, by_axis), "report": report, "label": "DERIVED"}
