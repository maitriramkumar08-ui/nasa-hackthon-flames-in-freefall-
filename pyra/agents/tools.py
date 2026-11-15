"""Deterministic tools for the agents. Every number an agent reports comes from here
or from the PYRA engines it calls (ranking, gaps, builder, research).

Nothing here predicts a fire (rule 9) or calls a material safe or unsafe (rule 6).
The flame-regime scaling is order of magnitude, its constants are ILLUSTRATIVE
and they come back with every result.
"""

import json
import math

from .. import builder, evidence, gaps, paths, ranking, research

INCIDENTS = paths.ROOT / "config" / "incidents.json"
G0 = 9.80665

# ILLUSTRATIVE constants for the buoyant velocity scale u_b ~ sqrt(g L (T_f/T_a - 1)).
# Our choice, not NASA data. Replace them with values from a cited paper before relying on them.
REGIME_ASSUMPTIONS = {"flame_length_m": 0.05, "flame_temp_k": 1500.0, "ambient_temp_k": 295.0,
                      "forced_above_ratio": 3.0, "mixed_above_ratio": 0.3, "label": "ILLUSTRATIVE"}
PARTIAL = "partial"
LABELS = ("MEASURED", "DERIVED", "HYPOTHETICAL", "INTERPRETATION", "PROPOSAL")
STRICT_PHRASE = "not directly measured"


NOT_REAL = "NOT REAL DATA"


def has_unreal_data(corpus):
    """True when any loaded sheet carries the NOT REAL DATA marker, so it can never pass as a NASA result."""
    return any(NOT_REAL in (inv.get("name") or "") for inv in corpus["investigations"])


def gravity_regime(gravity):
    if gravity is None:
        return None
    if gravity == 0.0:
        return "microgravity"
    if gravity == 1.0:
        return "normal gravity"
    return PARTIAL


# --------------------------------------------------------------------------- librarian
def corpus_summary(corpus):
    invs, runs = corpus["investigations"], corpus["runs"]
    pillars, gravities = {}, {"microgravity": 0, "normal gravity": 0, PARTIAL: 0, "not given": 0}
    for inv in invs:
        pillars[inv["pillar"] or "not given"] = pillars.get(inv["pillar"] or "not given", 0) + 1
    for run in runs:
        gravities[gravity_regime(run["values"].get("gravity")) or "not given"] += 1
    return {
        "investigations": len(invs), "runs": len(runs),
        "publications": sum(len(inv["publications"]) for inv in invs),
        "findings": sum(len(inv["findings"]) for inv in invs),
        "measured_findings": sum(f["type"] == "MEASURED" for inv in invs for f in inv["findings"]),
        "by_pillar": pillars, "runs_by_gravity": gravities,
        "materials": builder.indexed_materials(corpus),
        "acronyms": [inv["acronym"] for inv in invs],
        "not_real": has_unreal_data(corpus), "label": "DERIVED",
    }


# --------------------------------------------------------------------------- mission
def mission_profile(request, corpus):
    """Preset + typed values -> one scenario. Every value is HYPOTHETICAL, and each one names
    where it came from. A typed value wins over the preset."""
    request = request if isinstance(request, dict) else {}
    presets = builder.presets()
    preset_id = request.get("preset") if request.get("preset") in presets else "custom"
    preset = presets[preset_id]

    def pick(key, preset_key=None):
        typed = request.get(key)
        if typed not in (None, ""):
            return typed, "typed by you"
        value = preset.get(preset_key or key)
        source = preset.get("gravity_source" if key == "gravity_g" else "atmosphere_source") or "not provided"
        return value, (source if value is not None else "not set")

    o2, o2_source = pick("o2_percent")
    pressure, pressure_source = pick("pressure")
    gravity, gravity_source = pick("gravity_g")
    pressure_unit = request.get("pressure_unit") if request.get("pressure") not in (None, "") else None
    pressure_unit = pressure_unit or preset.get("pressure_unit") or "kPa"
    materials = request.get("materials") or []
    if isinstance(materials, str):
        materials = materials.split(",")
    materials = [m.strip() for m in materials if isinstance(m, str) and m.strip()][:6]
    raw = {"o2_percent": o2, "pressure": pressure, "pressure_unit": pressure_unit,
           "flow_speed": request.get("flow_speed"), "flow_unit": request.get("flow_unit") or "cm/s",
           "gravity_g": gravity, "pillar": request.get("pillar") or None,
           "material": materials[0] if materials else None, "fuel_phase": request.get("fuel_phase") or None}
    scen = evidence.scenario(raw)
    o2_partial = None
    if scen["o2_percent"] is not None and scen["pressure"] is not None:
        o2_partial = round(scen["pressure"] * scen["o2_percent"] / 100, 3)
    values = [
        {"field": "O2", "value": scen["o2_percent"], "unit": "%", "source": o2_source},
        {"field": "pressure", "value": None if scen["pressure"] is None else round(scen["pressure"], 2),
         "unit": "kPa", "source": pressure_source},
        {"field": "flow", "value": scen["flow_speed"], "unit": "cm/s",
         "source": "typed by you" if scen["flow_speed"] is not None else "not set"},
        {"field": "gravity", "value": scen["gravity"], "unit": "g", "source": gravity_source},
    ]
    for value in values:
        value["label"] = "HYPOTHETICAL" if value["value"] is not None else "not set"
    return {"preset": preset_id, "name": preset.get("name") or preset_id, "raw": raw, "scenario": scen,
            "materials": materials, "values": values,
            "o2_partial_kpa": o2_partial, "o2_partial_label": "DERIVED",
            "gravity_regime": gravity_regime(scen["gravity"]),
            "preset_verified": bool(preset.get("verified_by")),
            "unverified_sources": [] if preset.get("verified_by") or preset_id == "custom" else
            sorted({s for s in (o2_source, pressure_source, gravity_source) if s not in ("typed by you", "not set")}),
            "label": "HYPOTHETICAL"}


# --------------------------------------------------------------------------- physicist
def buoyant_velocity(gravity_g, a=REGIME_ASSUMPTIONS):
    return math.sqrt(max(gravity_g, 0.0) * G0 * a["flame_length_m"] * (a["flame_temp_k"] / a["ambient_temp_k"] - 1))


def flame_regime(gravity_g, flow_cm_s):
    """Which flow sets the flow at a flame, in a one-number scaling. DERIVED with ILLUSTRATIVE constants."""
    if gravity_g is None:
        return {"state": "NOT_EVALUATED", "reason": "gravity is not set", "label": "DERIVED",
                "assumptions": REGIME_ASSUMPTIONS}
    a = REGIME_ASSUMPTIONS
    ub = buoyant_velocity(gravity_g)
    ub_earth = buoyant_velocity(1.0)
    flow = None if flow_cm_s is None else flow_cm_s / 100.0
    if flow is None:
        ratio, regime = None, "buoyant" if gravity_g > 0 else "not evaluated (flow not set)"
    else:
        ratio = flow / ub if ub > 0 else math.inf
        regime = ("quiescent" if flow < 0.01 and ub < 0.01 else
                  "forced" if ratio > a["forced_above_ratio"] else
                  "mixed" if ratio > a["mixed_above_ratio"] else "buoyant")
    text = {
        "quiescent": "Almost no flow from either buoyancy or ventilation in this scaling.",
        "forced": "Ventilation flow is larger than the buoyant flow, so the ventilation sets the flow at a flame.",
        "mixed": "Ventilation and buoyant flow are of the same size.",
        "buoyant": "Buoyant flow is larger than the ventilation flow, as in normal gravity, but weaker than on Earth.",
    }.get(regime, "Set a flow speed to compare ventilation with buoyancy.")
    relevance = {"buoyant": "closest", "mixed": "partial", "forced": "distant", "quiescent": "distant"}.get(regime)
    return {"state": "EVALUATED", "gravity_g": gravity_g, "flow_m_s": flow,
            "buoyant_velocity_m_s": round(ub, 4), "earth_buoyant_velocity_m_s": round(ub_earth, 3),
            "buoyant_fraction_of_earth": round(ub / ub_earth, 3),
            "flow_to_buoyancy_ratio": None if ratio is None else (round(ratio, 2) if math.isfinite(ratio) else "infinite"),
            "regime": regime, "regime_text": text, "normal_gravity_test_similarity": relevance,
            "assumptions": a, "label": "DERIVED",
            "limits": "One velocity scale for the whole flame. Not a flow solution and not a prediction of "
                      "ignition, spread or extinction (rule 9)."}


# --------------------------------------------------------------------------- evidence ranker
def _citation(run_or_nearest):
    src = run_or_nearest.get("source") or {}
    return {"acronym": run_or_nearest.get("acronym"), "run_id": run_or_nearest.get("run_id"),
            "title": src.get("title") if isinstance(src, dict) else src,
            "url": src.get("url") if isinstance(src, dict) else run_or_nearest.get("url")}


def analyse_materials(corpus, raw, materials):
    """{material or '(no material)': gaps.analyze(...)} for the scenario with that material."""
    out = {}
    for material in materials or [None]:
        scen = evidence.scenario(dict(raw, material=material))
        out[material or builder.ANY_MATERIAL] = gaps.analyze(corpus, scen)
    return out


def draft_claims(corpus, profile, analyses, ranked, strict, review=None):
    """The claims the Evidence Ranker puts forward, one per material plus the closest investigations.

    strict=False is the quick first draft: a material counts as MEASURED when any indexed run
    uses its class. strict=True, after the Skeptic, keeps MEASURED only for a combination that
    is DIRECTLY_TESTED and words everything else as DERIVED distance to the nearest run."""
    scen = profile["scenario"]
    partial = profile["gravity_regime"] == PARTIAL
    runs_by_id = {r["run_id"]: r for r in corpus["runs"]}
    claims = []
    for number, (material, analysis) in enumerate(analyses.items(), 1):
        combo = analysis["combination"]
        mat_axis = analysis["axes"]["material_class"]
        nearest = analysis["nearest_runs"][:2]
        if material == builder.ANY_MATERIAL:
            class_runs = [runs_by_id[n["run_id"]] for n in nearest if n["run_id"] in runs_by_id]
        else:
            wanted = ranking.material_class(material)
            class_runs = [r for r in corpus["runs"]
                          if wanted and any(ranking.material_class(m) == wanted for m in r["materials"])]
        if not strict:
            measured = bool(class_runs)
            cites = [_citation(r) for r in class_runs[:2]] if measured else [_citation(n) for n in nearest]
            text = (f"{material}: tested in {', '.join(sorted({r['acronym'] for r in class_runs}))}."
                    if measured else f"{material}: no indexed run uses its class.")
            label = "MEASURED" if measured else "DERIVED"
        elif combo.get("class") == gaps.DIRECTLY_TESTED:
            cites = [_citation(runs_by_id[r]) for r in combo["runs_matching"] if r in runs_by_id][:3]
            text = (f"{material}: {len(combo['runs_matching'])} indexed run(s) match every set axis at once "
                    "(DIRECTLY_TESTED).")
            label = "MEASURED"
        else:
            near = nearest[0] if nearest else None
            where = (f"; the nearest run is {near['acronym']} {near['run_id']}, distance {near['distance']} "
                     "tolerances (DERIVED)") if near else "; no indexed run to compare with"
            text = (f"{material}: {STRICT_PHRASE} at this scenario. All set axes together are "
                    f"{combo.get('class') or 'not evaluated'}{where}.")
            if partial:
                text += (f" At {scen['gravity']} g it is only bounded by microgravity and normal-gravity runs.")
            cites = [_citation(n) for n in nearest]
            label = "DERIVED"
        claims.append({"id": f"C{number}", "subject": material, "kind": "material", "label": label,
                       "text": text, "citations": cites, "gap_class": combo.get("class"),
                       "material_class": mat_axis.get("class")})

    top = ranked[:3]
    for entry in top:
        inv = next(i for i in corpus["investigations"] if i["id"] == entry["investigation_id"])
        pub = (inv["publications"] or [{}])[0]
        claims.append({"id": f"C{len(claims) + 1}", "subject": entry["acronym"], "kind": "ranking", "label": "DERIVED",
                       "text": entry["explanation"],
                       "citations": [{"acronym": inv["acronym"], "run_id": None, "title": pub.get("title"),
                                      "url": pub.get("url")}],
                       "gap_class": None, "material_class": None})
    if strict and len(top) >= 2:
        problems = comparability(corpus, [e["investigation_id"] for e in top])
        if problems:
            claims.append({"id": f"C{len(claims) + 1}", "subject": "comparison", "kind": "comparability",
                           "label": "INTERPRETATION",
                           "text": "Do not compare numbers across these investigations directly: " + "; ".join(problems) + ".",
                           "citations": [], "gap_class": None, "material_class": None})
    return claims


def comparability(corpus, investigation_ids):
    """Reasons two or more investigations cannot be compared number for number (rule 7)."""
    invs = [i for i in corpus["investigations"] if i["id"] in investigation_ids]
    problems = []
    for name, get in (("hardware", lambda i: i["hardware"] or "not provided"),
                      ("scale", lambda i: i["scale"] or "not provided"),
                      ("fuel phase", lambda i: "/".join(sorted({f["phase"] for f in i["fuels"]})) or "not provided")):
        found = {get(i) for i in invs}
        if len(found) > 1:
            problems.append(f"different {name} ({', '.join(sorted(found))})")
    return problems


def review_claims(claims, analyses, profile, corpus, ranked):
    """The Skeptic's checklist. 'block' sends the claims back; 'warn' is shown but lets them through."""
    from .llm import rule_problems
    issues = []
    partial = profile["gravity_regime"] == PARTIAL
    for claim in claims:
        if claim["label"] not in LABELS:
            issues.append({"code": "NO_LABEL", "severity": "block", "claim": claim["id"],
                           "text": f"{claim['id']} has no PYRA label.", "fix": "Label it (rule 2)."})
        if claim["label"] == "MEASURED" and not claim["citations"]:
            issues.append({"code": "NO_CITATION", "severity": "block", "claim": claim["id"],
                           "text": f"{claim['id']} is MEASURED but cites nothing.", "fix": "Cite the run (rule 3)."})
        if claim["kind"] == "material" and claim["label"] == "MEASURED":
            combo = analyses.get(claim["subject"], {}).get("combination", {})
            if combo.get("class") != gaps.DIRECTLY_TESTED:
                issues.append({"code": "OVERCLAIM", "severity": "block", "claim": claim["id"],
                               "text": f"{claim['subject']} is called MEASURED, but no run matches the whole scenario "
                                       f"at once (combination {combo.get('class') or 'not evaluated'}).",
                               "fix": "Relabel as DERIVED and give the distance to the nearest run."})
        if partial and claim["kind"] == "material" and claim["gap_class"] != gaps.DIRECTLY_TESTED \
                and STRICT_PHRASE not in claim["text"] \
                and "bounded by" not in claim["text"]:
            issues.append({"code": "PARTIAL_GRAVITY", "severity": "block", "claim": claim["id"],
                           "text": f"{claim['id']} does not say that {profile['scenario']['gravity']} g is "
                                   "not directly measured.",
                           "fix": "Say 'bounded by' or 'not directly measured' (rule 5)."})
        for problem in rule_problems(claim["text"], claim, profile):
            if "number" in problem:
                continue  # numbers in claims come from the tools; the checks below are about wording
            issues.append({"code": "WORDING", "severity": "block", "claim": claim["id"],
                           "text": f"{claim['id']} {problem}.", "fix": "Use the scripted wording."})
    if len(ranked) >= 2 and not any(c["kind"] == "comparability" for c in claims):
        problems = comparability(corpus, [e["investigation_id"] for e in ranked[:3]])
        if problems:
            issues.append({"code": "NOT_COMPARABLE", "severity": "warn", "claim": None,
                           "text": "The top investigations differ: " + "; ".join(problems) + ".",
                           "fix": "Add a comparability warning (rule 7)."})
    if has_unreal_data(corpus):
        issues.append({"code": "NOT_REAL_DATA", "severity": "warn", "claim": None,
                       "text": "The corpus holds sheets marked NOT REAL DATA. Nothing from them is a NASA result.",
                       "fix": "Rebuild from verified factsheets before presenting."})
    if profile["unverified_sources"]:
        issues.append({"code": "UNVERIFIED_PRESET", "severity": "warn", "claim": None,
                       "text": f"The {profile['name']} preset values have not been checked by the team yet.",
                       "fix": "Verify the preset source in config/environment_presets.json."})
    return issues


# --------------------------------------------------------------------------- incidents
def load_incidents(path=INCIDENTS):
    return json.loads(path.read_text(encoding="utf-8"))["incidents"]


def match_incidents(profile, analyses):
    """Which links of each past fire also show up in the scenario. INTERPRETATION, never a prediction."""
    scen = profile["scenario"]
    classes = {ranking.material_class(m) for m in profile["materials"]} - {None}
    out = []
    for inc in load_incidents():
        f = inc["features"]
        links, unknown = [], []
        if scen["o2_percent"] is None:
            unknown.append("oxygen fraction not set")
        elif scen["o2_percent"] > 21 and f.get("oxygen_enriched"):
            links.append(f"oxygen-enriched cabin in the scenario ({scen['o2_percent']} % O2, HYPOTHETICAL); "
                         f"the {inc['name']} oxidizer was: {inc['chain']['oxidizer'].lower()}")
        shared = sorted(classes & set(f.get("material_classes") or []))
        if shared:
            links.append(f"scenario materials of the same class as the {inc['name']} fuel ({', '.join(shared)})")
        regime = profile["gravity_regime"]
        if regime is None:
            unknown.append("gravity not set")
        elif regime == f.get("gravity"):
            links.append(f"same gravity regime ({regime})")
        unknown.append("oxygen storage and generation are not part of a PYRA scenario")
        out.append({**{k: inc[k] for k in ("id", "name", "year", "setting", "outcome", "chain", "source")},
                    "verified": bool(inc.get("verified_by")), "links": links, "not_evaluated": unknown,
                    "shared_links": len(links), "label": "INTERPRETATION"})
    return out


# --------------------------------------------------------------------------- gaps
def gap_plan(corpus, profile):
    """Combination class, the best data opportunities and the Builder's PROPOSAL experiments."""
    raw = profile["raw"]
    analysis = gaps.analyze(corpus, profile["scenario"])
    mission = {"name": profile["name"], "scenario": raw}
    opportunities = research.opportunities(corpus, [mission])
    form = {"preset": "custom", "o2_percent": raw["o2_percent"], "pressure": raw["pressure"],
            "pressure_unit": raw["pressure_unit"], "gravity_g": raw["gravity_g"],
            "materials": profile["materials"], "pillar": raw["pillar"] or "all"}
    if raw.get("flow_speed") not in (None, ""):
        form.update(flow_min=raw["flow_speed"], flow_max=raw["flow_speed"], flow_unit=raw["flow_unit"])
    check = builder.check(form, corpus)
    proposals = check.get("proposals", []) if check.get("valid") else []
    by_axis = {p["axis"]: p for p in proposals}
    next_experiment = None
    for opp in opportunities:
        if opp["axis"] in by_axis:
            next_experiment = dict(by_axis[opp["axis"]], opportunity_score=opp["score"])
            break
    if next_experiment is None and proposals:
        next_experiment = proposals[0]
    axes = [{"axis": axis, "class": found.get("class"), "summary": found.get("summary")}
            for axis, found in analysis["axes"].items()]
    return {"combination": analysis["combination"], "axes": axes, "report": analysis["report"],
            "opportunities": opportunities, "proposals": proposals, "next_experiment": next_experiment,
            "builder_errors": check.get("errors"), "label": "DERIVED"}


# --------------------------------------------------------------------------- recommendations
def recommendations(profile, physics, claims, review, incidents, plan, corpus):
    """What the team should do next, each with its evidence. All about evidence, none about safety."""
    recs = []

    def add(priority, title, text, label, evidence_list):
        recs.append({"id": f"R{len(recs) + 1}", "priority": priority, "title": title, "text": text,
                     "label": label, "evidence": evidence_list})

    if has_unreal_data(corpus):
        add("P1", "Rebuild with verified factsheets", "Some results in this run come from sheets marked NOT REAL DATA. "
            "Build data/pyra.db from data/factsheets/verified only before showing any number.", "INTERPRETATION",
            ["sheets marked NOT REAL DATA"])
    untested = [c for c in claims if c["kind"] == "material" and c["label"] != "MEASURED"]
    if untested:
        add("P1", "Do not present the materials as measured",
            f"{', '.join(c['subject'] for c in untested)}: {STRICT_PHRASE} at this scenario. Present them as "
            "distance to the nearest run, not as test results.", "DERIVED",
            sorted({f"{x['acronym']} {x['run_id']}" for c in untested for x in c["citations"] if x.get("run_id")}))
    if profile["gravity_regime"] == PARTIAL:
        add("P1", "Label partial gravity on every slide",
            f"At {profile['scenario']['gravity']} g PYRA has only microgravity and normal-gravity runs, so every "
            "number is bounded by them and not directly measured (rule 5).", "DERIVED", ["gap engine: gravity axis"])
    nxt = plan.get("next_experiment")
    if nxt:
        add("P2", "Run the proposed experiment", nxt["text"], "PROPOSAL",
            [f"gap class {nxt.get('gap_class')}", "research.opportunities"])
    if profile["unverified_sources"]:
        add("P2", "Verify the preset source", f"Check {profile['name']} against: "
            + "; ".join(profile["unverified_sources"]), "INTERPRETATION", ["config/environment_presets.json"])
    if physics.get("state") == "EVALUATED" and physics.get("normal_gravity_test_similarity") in ("partial", "distant"):
        add("P2", "Do not read normal-gravity screening results as mission results",
            f"In this scaling the flow at a flame is {physics['regime']} (ratio {physics['flow_to_buoyancy_ratio']}), "
            "so a normal-gravity test sees a different flow. ILLUSTRATIVE constants.", "DERIVED",
            ["flame_regime (ILLUSTRATIVE)"])
    linked = [i for i in incidents if i["shared_links"]]
    if linked:
        worst = max(linked, key=lambda i: i["shared_links"])
        add("P3", f"Review the {worst['name']} fire chain with the design team",
            f"{worst['shared_links']} link(s) also appear in this scenario: " + "; ".join(worst["links"]) + ".",
            "INTERPRETATION", [worst["source"] + (" (verified)" if worst["verified"] else " (not yet verified)")])
    return recs
