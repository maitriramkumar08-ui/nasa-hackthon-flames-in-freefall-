"""Early-design evidence check: what NASA combustion evidence covers for a candidate
cabin atmosphere and materials list, before a team commits to them.

    result = builder.check(form, corpus)

Every input is optional. A blank field is NOT_EVALUATED in the gap engine, never an
error and never a crash. Invalid values (O2 outside 0-100, pressure <= 0, flow min >
flow max, unknown unit or preset) come back as {"valid": False, "errors": {...}} and
the gap engine is not called at all.

What comes out (never safe/unsafe, rule 6; never a prediction, rule 9):

    hints         where each numeric input sits against the tested ranges (gap engine)
    table         materials x axis: gap class per axis, combination, nearest evidence with source
    proposals     suggested experiments for the gaps, labelled PROPOSAL
    design_notes  cited rules from config/design_rules.json, or exactly 'no sourced guidance'

Mission duration is a display label only: it does not change any result.
Presets come from config/environment_presets.json and carry their (unverified) sources.
"""

import json

from . import evidence, gaps, paths, ranking, report, units

DESIGN_RULES = paths.ROOT / "config" / "design_rules.json"
PRESETS = paths.ROOT / "config" / "environment_presets.json"
RULE_FIELDS = ("id", "text", "source", "page")
NO_GUIDANCE = "no sourced guidance"
PURPOSE = ("Check what NASA combustion evidence covers for a candidate cabin atmosphere and "
           "materials list before you commit to them.")

PRESSURE_UNITS = ("psi", "kPa")
FLOW_UNITS = ("cm/s", "mm/s", "m/s")
PILLARS = ("all", "prevention", "detection", "suppression")
MAX_LABEL = 80
ANY_MATERIAL = "(no material chosen)"


def load_rules(path=DESIGN_RULES):
    """The rules list from design_rules.json, refusing any rule without a full citation."""
    rules = json.loads(path.read_text(encoding="utf-8"))["rules"]
    for number, rule in enumerate(rules):
        missing = [field for field in RULE_FIELDS if not rule.get(field)]
        if missing:
            raise ValueError(f"design rule #{number} ({rule.get('id', 'no id')}) is missing {', '.join(missing)}")
    return rules


def presets(path=PRESETS):
    """{preset id: preset dict} in file order."""
    return {p["id"]: p for p in json.loads(path.read_text(encoding="utf-8"))["presets"]}


def indexed_materials(corpus):
    """The material categories in the index, with investigation and run counts, most runs first."""
    counts = {}
    for run in corpus["runs"]:
        for key in {gaps.category_key(m) for m in run.get("materials") or []} - {None}:
            entry = counts.setdefault(key, {"category": key, "investigations": set(), "runs": 0})
            entry["runs"] += 1
            entry["investigations"].add(run.get("investigation_id"))
    for inv in corpus["investigations"]:
        for key in {gaps.category_key(f.get("material")) for f in inv.get("fuels") or []} - {None}:
            counts.setdefault(key, {"category": key, "investigations": set(), "runs": 0})["investigations"].add(inv["id"])
    return sorted(({"category": c["category"], "investigations": len(c["investigations"]), "runs": c["runs"]}
                   for c in counts.values()), key=lambda c: (-c["runs"], c["category"]))


def options(corpus):
    """What the Builder form offers: presets, indexed material classes, pillars, units."""
    return {"purpose": PURPOSE, "presets": list(presets().values()), "materials": indexed_materials(corpus),
            "pillars": list(PILLARS), "pressure_units": list(PRESSURE_UNITS), "flow_units": list(FLOW_UNITS)}


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _number(form, key, errors, message):
    value = form.get(key)
    if _blank(value):
        return None
    number = units.to_number(value)
    if number is None:
        errors[key] = message
    return number


def validate(form, known_presets=None):
    """(clean inputs, errors). errors is {field: message}; empty means valid."""
    known_presets = presets() if known_presets is None else known_presets
    form = form if isinstance(form, dict) else {}
    errors = {}

    preset_id = form.get("preset") or "custom"
    if preset_id not in known_presets:
        errors["preset"] = f"Unknown environment preset '{preset_id}'."
        preset_id = "custom"
    preset = known_presets.get(preset_id, {})

    o2 = _number(form, "o2_percent", errors, "O2 must be a number.")
    if o2 is not None and "o2_percent" not in errors and not 0 <= o2 <= 100:
        errors["o2_percent"] = "O2 must be between 0 and 100 %."

    pressure_unit = form.get("pressure_unit") or "kPa"
    if pressure_unit not in PRESSURE_UNITS:
        errors["pressure_unit"] = f"Pressure unit must be one of {', '.join(PRESSURE_UNITS)}."
    pressure = _number(form, "pressure", errors, "Pressure must be a number.")
    if pressure is not None and "pressure" not in errors and pressure <= 0:
        errors["pressure"] = "Pressure must be greater than 0."

    flow_unit = form.get("flow_unit") or "cm/s"
    if flow_unit not in FLOW_UNITS:
        errors["flow_unit"] = f"Flow unit must be one of {', '.join(FLOW_UNITS)}."
    flow_min = _number(form, "flow_min", errors, "Flow min must be a number.")
    flow_max = _number(form, "flow_max", errors, "Flow max must be a number.")
    for key, value in (("flow_min", flow_min), ("flow_max", flow_max)):
        if value is not None and key not in errors and value < 0:
            errors[key] = "Flow cannot be negative."
    if None not in (flow_min, flow_max) and not {"flow_min", "flow_max"} & set(errors) and flow_min > flow_max:
        errors["flow_max"] = "Flow max must be at least flow min."

    if preset_id == "custom":
        gravity = _number(form, "gravity_g", errors, "Gravity must be a number.")
        if gravity is not None and "gravity_g" not in errors and gravity < 0:
            errors["gravity_g"] = "Gravity cannot be negative."
    else:
        gravity = preset.get("gravity_g")

    materials = form.get("materials") or []
    if isinstance(materials, str):
        materials = materials.split(",")
    if not isinstance(materials, list) or not all(isinstance(m, str) for m in materials):
        errors["materials"] = "Materials must be a list of names."
        materials = []
    materials = list(dict.fromkeys(m.strip() for m in materials if m.strip()))

    pillar = form.get("pillar") or "all"
    if pillar not in PILLARS:
        errors["pillar"] = f"Pillar must be one of {', '.join(PILLARS)}."

    duration = form.get("mission_duration") or ""
    if not isinstance(duration, str) or len(duration) > MAX_LABEL:
        errors["mission_duration"] = f"Mission duration is a short label (at most {MAX_LABEL} characters)."
        duration = ""

    clean = {"preset": preset_id, "o2_percent": o2, "pressure": pressure, "pressure_unit": pressure_unit,
             "flow_min": flow_min, "flow_max": flow_max, "flow_unit": flow_unit, "gravity_g": gravity,
             "materials": materials, "pillar": pillar, "mission_duration": duration.strip(),
             "label": "HYPOTHETICAL"}
    return clean, errors


def o2_partial_kpa(clean):
    """O2 partial pressure in kPa (DERIVED), or None if O2 or pressure is not set."""
    if clean["o2_percent"] is None or clean["pressure"] is None:
        return None
    return round(clean["o2_percent"] / 100 * units.convert(clean["pressure"], clean["pressure_unit"], "kPa"), 3)


def _raw(clean, material=None, flow=None):
    return {"o2_percent": clean["o2_percent"], "pressure": clean["pressure"],
            "pressure_unit": clean["pressure_unit"], "flow_speed": flow, "flow_unit": clean["flow_unit"],
            "gravity_g": clean["gravity_g"], "material": material,
            "pillar": None if clean["pillar"] == "all" else clean["pillar"]}


def _flows(clean):
    """The flow values to check: min and max, or just the one given, or none."""
    return [(name, clean[name]) for name in ("flow_min", "flow_max") if clean[name] is not None] or [(None, None)]


def _cell(found):
    if found["state"] == gaps.NOT_EVALUATED:
        return {"class": None, "state": gaps.NOT_EVALUATED, "summary": found["summary"]}
    return {"class": found["class"], "state": gaps.EVALUATED, "summary": found["summary"]}


def _nearest(analysis, corpus, scen):
    """Nearest run with its source, else the best-ranked investigation, else none."""
    if analysis["nearest_runs"]:
        run = analysis["nearest_runs"][0]
        source = run.get("source") or {}
        return {"acronym": run["acronym"], "run_id": run["run_id"], "distance": run["distance"],
                "source": source.get("title"), "url": source.get("url"), "label": "MEASURED source, DERIVED distance"}
    ranked = [r for r in ranking.rank(corpus, scen) if r["total"] > 0]
    if ranked:
        inv = next(i for i in corpus["investigations"] if i["id"] == ranked[0]["investigation_id"])
        pub = (inv.get("publications") or [{}])[0]
        return {"acronym": inv["acronym"], "run_id": None, "distance": None,
                "source": pub.get("title"), "url": pub.get("url"), "label": "MEASURED source, DERIVED match"}
    return None


def hints(clean, corpus):
    """Where each numeric input sits against the tested values, ignoring material."""
    out = {}
    for name, flow in _flows(clean):
        analysis = gaps.analyze(corpus, evidence.scenario(_raw(clean, flow=flow)))
        if not out:
            for field, axis in (("o2_percent", "o2_percent"), ("pressure", "pressure"), ("gravity_g", "gravity")):
                out[field] = _cell(analysis["axes"][axis])
        if name:
            out[name] = _cell(analysis["axes"]["flow_speed"])
    return out


def _proposals(clean, rows):
    seen, found = set(), []
    for row in rows:
        for check in row["checks"]:
            for axis, gap in check["analysis"]["axes"].items():
                template = report.EXPERIMENTS.get(gap.get("class"))
                if template is None or gap["kind"] != gaps.NUMERIC:
                    continue
                unit = gap["unit"]
                text = template.format(
                    axis=axis, value=f"{gap['scenario_value']:.4g} {unit}",
                    low=f"{gap['tested_min']:.4g} {unit}" if gap["tested_min"] is not None else "no tested value",
                    high=f"{gap['tested_max']:.4g} {unit}" if gap["tested_max"] is not None else "no tested value",
                    nearest=f"{gap['nearest_value']:.4g} {unit}" if gap["nearest_value"] is not None else "none",
                    runs=gap["runs_within"])
                if text not in seen:
                    seen.add(text)
                    found.append({"text": text, "axis": axis, "gap_class": gap["class"], "label": "PROPOSAL"})
        material = row["material_cell"]
        if row["material"] != ANY_MATERIAL and material["class"] in ("NO_INDEXED_DATA", "INSUFFICIENT"):
            found_runs = row["checks"][0]["analysis"]["axes"]["material_class"]["runs_within"]
            if material["class"] == "NO_INDEXED_DATA":
                why = "nothing is indexed for its class"
            elif found_runs:
                why = f"only {found_runs} indexed run{'s' if found_runs != 1 else ''} use{'' if found_runs != 1 else 's'} its class"
            else:
                why = "its class appears only as an investigation-level range, with no indexed run"
            text = f"PROPOSAL: test {row['material']} at the candidate atmosphere; {why}."
            if text not in seen:
                seen.add(text)
                found.append({"text": text, "axis": "material_class", "gap_class": material["class"], "label": "PROPOSAL"})
    return found


def design_notes(clean, rules):
    """Cited rules that apply to the atmosphere or a chosen material, else 'no sourced guidance'."""
    subjects = [("atmosphere", {"atmosphere"})]
    subjects += [(f"material {m}", {"material", m, m.lower(), gaps.category_key(m)}) for m in clean["materials"]]
    notes = []
    for subject, tags in subjects:
        applying = [r for r in rules if "applies_to" not in r or tags & set(r["applies_to"])]
        notes.append({"subject": subject,
                      "guidance": [{f: r[f] for f in RULE_FIELDS} for r in applying] or NO_GUIDANCE})
    return notes


def check(form, corpus, rules=None, known_presets=None):
    """The whole early-design evidence check. Invalid input returns the errors and stops."""
    clean, errors = validate(form, known_presets)
    if errors:
        return {"valid": False, "errors": errors, "purpose": PURPOSE}
    rules = load_rules() if rules is None else rules

    rows = []
    for material in clean["materials"] or [None]:
        checks = []
        for name, flow in _flows(clean):
            scen = evidence.scenario(_raw(clean, material, flow))
            analysis = gaps.analyze(corpus, scen)
            checks.append({"flow_field": name, "flow": flow, "analysis": analysis, "scen": scen})
        first = checks[0]["analysis"]
        material_cell = _cell(first["axes"]["material_class"])
        rows.append({
            "material": material or ANY_MATERIAL,
            "in_index": material is None or first["axes"]["material_class"].get("in_tested", False),
            "material_cell": material_cell,
            "checks": checks,
        })

    table = []
    for row in rows:
        first = row["checks"][0]["analysis"]["axes"]
        table.append({
            "material": row["material"], "in_index": row["in_index"],
            "o2_percent": _cell(first["o2_percent"]), "pressure": _cell(first["pressure"]),
            "gravity": _cell(first["gravity"]), "material_class": row["material_cell"], "pillar": _cell(first["pillar"]),
            "flow": [dict(_cell(c["analysis"]["axes"]["flow_speed"]), at=c["flow_field"], value=c["flow"])
                     for c in row["checks"]],
            "combination": [{"at": c["flow_field"], "class": c["analysis"]["combination"]["class"],
                             "summary": c["analysis"]["combination"]["summary"]} for c in row["checks"]],
            "nearest": _nearest(row["checks"][0]["analysis"], corpus, row["checks"][0]["scen"]),
            "label": "DERIVED",
        })

    return {
        "valid": True, "purpose": PURPOSE, "inputs": clean,
        "derived": {"o2_partial_kpa": o2_partial_kpa(clean), "label": "DERIVED"},
        "hints": hints(clean, corpus), "table": table,
        "proposals": _proposals(clean, rows), "design_notes": design_notes(clean, rules),
        "mission_duration": clean["mission_duration"] or None, "label": "DERIVED",
    }
