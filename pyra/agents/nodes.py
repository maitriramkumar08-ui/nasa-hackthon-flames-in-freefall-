"""The agents. Each one is run(state, ctx) -> dict and returns only its own key.

Numbers come from pyra.agents.tools and the PYRA engines; ctx.llm may reword
a summary, and that wording is checked against the rules before it is kept.
Every node tolerates a missing upstream result and builds what it needs.
"""

from .. import builder, ranking
from . import tools


def _corpus(state, ctx):
    return ctx.corpus


def _profile(state, ctx):
    return state.get("mission") or tools.mission_profile(state.get("scenario") or {}, ctx.corpus)


def _analyses(state, ctx, profile):
    return tools.analyse_materials(ctx.corpus, profile["raw"], profile["materials"])


# --------------------------------------------------------------------------- librarian
def librarian(state, ctx):
    ctx.emit("thought", "Reading the PYRA evidence database: investigations, test runs, publications and findings.")
    summary = ctx.tool("corpus_summary", tools.corpus_summary, corpus=_corpus(state, ctx))
    if summary["not_real"]:
        ctx.emit("warning", "This corpus holds sheets marked NOT REAL DATA. Their numbers are not NASA results.")
    g = summary["runs_by_gravity"]
    fallback = (f"{summary['investigations']} investigation(s) with {summary['runs']} test run(s) and "
                f"{summary['measured_findings']} MEASURED finding(s). Runs by gravity: {g['microgravity']} microgravity, "
                f"{g['normal gravity']} normal gravity, {g['partial']} partial gravity.")
    ctx.emit("llm", ctx.llm.think("librarian", "Summarise what the evidence corpus covers.", summary, fallback))
    ctx.handoff("mission_profiler", "the evidence is loaded; next we need the scenario")
    return {"corpus": summary}


# --------------------------------------------------------------------------- mission profiler
def mission_profiler(state, ctx):
    request = state.get("scenario") or {}
    ctx.emit("thought", f"Building the scenario from preset '{request.get('preset') or 'custom'}' and the values you typed.")
    profile = ctx.tool("mission_profile", tools.mission_profile, request=request, corpus=ctx.corpus)
    s = profile["scenario"]
    parts = [f"{v['field']} {v['value']} {v['unit']}" for v in profile["values"] if v["value"] is not None]
    fallback = f"{profile['name']}: " + (", ".join(parts) if parts else "no values set") + " (HYPOTHETICAL)."
    if profile["o2_partial_kpa"] is not None:
        fallback += f" O2 partial pressure {profile['o2_partial_kpa']} kPa (DERIVED)."
    ctx.emit("llm", ctx.llm.think("mission_profiler", "Describe the scenario for a fire-safety evidence check.",
                                  {k: profile[k] for k in ("name", "values", "o2_partial_kpa")}, fallback))
    if profile["unverified_sources"]:
        ctx.emit("warning", f"The {profile['name']} preset has not been verified by the team yet.")
    if profile["gravity_regime"] == tools.PARTIAL:
        ctx.emit("thought", f"{s['gravity']} g is partial gravity: microgravity and 1 g runs can only bound it.")
    if not profile["materials"]:
        ctx.emit("thought", "No materials named, so the evidence check covers the scenario as a whole.")
    return {"mission": profile}


# --------------------------------------------------------------------------- physicist
def physicist(state, ctx):
    profile = _profile(state, ctx)
    s = profile["scenario"]
    ctx.emit("thought", "Comparing the buoyant flow a flame would make at this gravity with the ventilation flow. "
                        "Order-of-magnitude scaling with ILLUSTRATIVE constants, not a flow solution.")
    found = ctx.tool("flame_regime", tools.flame_regime, gravity_g=s["gravity"], flow_cm_s=s["flow_speed"])
    if found["state"] != "EVALUATED":
        fallback = f"Flame regime not evaluated: {found['reason']}."
    else:
        fallback = (f"Buoyant flow scale {found['buoyant_velocity_m_s']} m/s against {found['earth_buoyant_velocity_m_s']} m/s "
                    f"in normal gravity. {found['regime_text']} Similarity to a normal-gravity screening test: "
                    f"{found['normal_gravity_test_similarity'] or 'not evaluated'}.")
    found["summary"] = ctx.llm.think("physicist", "Explain the flow regime to an engineer in plain words.", found, fallback)
    ctx.emit("llm", found["summary"])
    ctx.handoff("evidence_ranker", "the regime is known; now rank the evidence for this scenario")
    return {"physics": found}


# --------------------------------------------------------------------------- evidence ranker
def evidence_ranker(state, ctx):
    profile = _profile(state, ctx)
    iteration = int(state.get("review_passes") or 0) + 1
    review = state.get("review") or {}
    strict = iteration > 1 and not review.get("approved", True)
    if strict:
        ctx.emit("thought", f"Pass {iteration}: applying the Skeptic's {len(review.get('issues', []))} issue(s). "
                            "MEASURED now needs a run that matches every set axis at once.")
    else:
        ctx.emit("thought", f"Pass {iteration}: quick draft. Ranking investigations and checking each material's coverage.")
    ranked = ctx.tool("rank", ranking.rank, corpus=ctx.corpus, scen=profile["scenario"])
    analyses = ctx.tool("analyse_materials", tools.analyse_materials, corpus=ctx.corpus, raw=profile["raw"],
                        materials=profile["materials"])
    claims = ctx.tool("draft_claims", tools.draft_claims, corpus=ctx.corpus, profile=profile, analyses=analyses,
                      ranked=ranked, strict=strict, review=review)
    measured = sum(c["label"] == "MEASURED" for c in claims)
    fallback = (f"{len(claims)} claim(s), {measured} labelled MEASURED. Closest investigation: "
                f"{ranked[0]['acronym']} (score {ranked[0]['total']})." if ranked else "No investigations to rank.")
    reworded = any(i["code"] == "WORDING" for i in review.get("issues", []))
    summary = fallback if reworded else ctx.llm.think(
        "evidence_ranker", "Summarise the claims and the closest investigation.",
        {"claims": [{k: c[k] for k in ("subject", "label", "text")} for c in claims]}, fallback)
    ctx.emit("llm", summary)
    history = list((state.get("ranking") or {}).get("history") or [])
    history.append({"pass": iteration, "strict": strict, "claims": len(claims), "measured": measured})
    ctx.handoff("skeptic", "check every label before anyone relies on it")
    return {"ranking": {"pass": iteration, "strict": strict, "ranked": ranked[:5], "claims": claims,
                        "summary": summary, "history": history,
                        "coverage": {m: {"class": a["combination"]["class"], "summary": a["combination"]["summary"]}
                                     for m, a in analyses.items()}},
            "review_passes": iteration}


# --------------------------------------------------------------------------- skeptic
def skeptic(state, ctx):
    profile = _profile(state, ctx)
    found = state.get("ranking") or {"claims": [], "ranked": [], "pass": 0}
    ctx.emit("thought", "Checking every claim against PYRA's rules: labels, citations, MEASURED only when the whole "
                        "combination was tested, partial gravity stated, no verdict on any material, no fire prediction.")
    analyses = _analyses(state, ctx, profile)
    issues = ctx.tool("review_claims", tools.review_claims, claims=found["claims"], analyses=analyses,
                      profile=profile, corpus=ctx.corpus, ranked=found["ranked"])
    summary = found.get("summary") or ""
    from .llm import rule_problems
    for problem in rule_problems(summary, found, profile):
        issues.append({"code": "WORDING", "severity": "block", "claim": "summary",
                       "text": f"The summary {problem}.", "fix": "Use the scripted wording."})
    blocks = [i for i in issues if i["severity"] == "block"]
    for issue in blocks[:5]:
        ctx.emit("warning", issue["text"])
    approved = not blocks
    fallback = ("Approved: every label matches what was tested." if approved else
                f"Rejected: {len(blocks)} problem(s). Sending the claims back.")
    ctx.emit("llm", ctx.llm.think("skeptic", "You are a strict reviewer. Give your verdict in one sentence.",
                                  {"blocks": len(blocks), "warnings": len(issues) - len(blocks)}, fallback))
    if not approved:
        ctx.handoff("evidence_ranker", "relabel the claims and state what was not directly measured")
    return {"review": {"pass": found.get("pass", 0), "approved": approved, "issues": issues}}


# --------------------------------------------------------------------------- incident analyst
def incident_analyst(state, ctx):
    profile = _profile(state, ctx)
    ctx.emit("thought", "Breaking Apollo 1, Apollo 13 and Mir into oxidizer, fuel, ignition, detection, suppression "
                        "and escape, and looking for the same links in the scenario.")
    cases = ctx.tool("match_incidents", tools.match_incidents, profile=profile, analyses={})
    for case in cases:
        if case["links"]:
            ctx.emit("thought", f"{case['name']} ({case['year']}): " + "; ".join(case["links"]) + ".")
    if any(not c["verified"] for c in cases):
        ctx.emit("warning", "The incident summaries in config/incidents.json have not been verified by the team yet.")
    closest = max(cases, key=lambda c: c["shared_links"])
    fallback = (f"Closest historical pattern: {closest['name']} ({closest['year']}), {closest['shared_links']} shared link(s). "
                "This is a pattern match (INTERPRETATION), not a prediction.")
    ctx.emit("llm", ctx.llm.think("incident_analyst", "Say which past spaceflight fire the scenario resembles and why.",
                                  {"cases": [{k: c[k] for k in ("name", "year", "links")} for c in cases]}, fallback))
    return {"incidents": {"cases": cases, "closest": closest["id"], "label": "INTERPRETATION"}}


# --------------------------------------------------------------------------- gap hunter
def gap_hunter(state, ctx):
    profile = _profile(state, ctx)
    ctx.emit("thought", "Classifying every axis of the scenario, scoring the data opportunities and picking the "
                        "experiment that closes the biggest gap.")
    plan = ctx.tool("gap_plan", tools.gap_plan, corpus=ctx.corpus, profile=profile)
    combo = plan["combination"]
    nxt = plan["next_experiment"]
    fallback = (f"All set axes together: {combo.get('class') or 'not evaluated'}. "
                + (f"Next experiment: {nxt['text']}" if nxt else "No experiment proposed: nothing is missing or nothing is set."))
    ctx.emit("llm", ctx.llm.think("gap_hunter", "Explain the most important untested condition and the experiment that fills it.",
                                  {"combination": combo.get("class"), "next": nxt, "opportunities": plan["opportunities"][:3]},
                                  fallback))
    return {"gaps": plan}


# --------------------------------------------------------------------------- safety officer
def safety_officer(state, ctx):
    profile = _profile(state, ctx)
    physics = state.get("physics") or tools.flame_regime(profile["scenario"]["gravity"], profile["scenario"]["flow_speed"])
    claims = (state.get("ranking") or {}).get("claims")
    if claims is None:
        analyses = _analyses(state, ctx, profile)
        claims = tools.draft_claims(ctx.corpus, profile, analyses, ranking.rank(ctx.corpus, profile["scenario"]), True)
    incidents = (state.get("incidents") or {}).get("cases") or tools.match_incidents(profile, {})
    plan = state.get("gaps") or tools.gap_plan(ctx.corpus, profile)
    recs = ctx.tool("recommendations", tools.recommendations, profile=profile, physics=physics, claims=claims,
                    review=state.get("review"), incidents=incidents, plan=plan, corpus=ctx.corpus)
    mode = (state.get("scenario") or {}).get("pilot_mode") or "approve"
    approved, rejected = [], []
    if mode == "approve" and recs:
        ctx.emit("thought", f"{len(recs)} recommendation(s) ready. Waiting for a person to approve them.")
        decision = ctx.ask_human({"question": "Approve these recommendations for the briefing?", "actions": recs})
        ids = set(decision.get("ids") or [])
        if decision.get("decision") == "approve":
            approved = [r["id"] for r in recs if not ids or r["id"] in ids]
        rejected = [r["id"] for r in recs if r["id"] not in approved]
        ctx.emit("result", f"Human decision: {len(approved)} approved, {len(rejected)} rejected"
                           + (f" ({decision['reason']})" if decision.get("reason") else "") + ".")
    else:
        ctx.emit("thought", "Shadow mode: recommendations are listed and marked as not reviewed.")
    for rec in recs:
        rec["status"] = ("approved" if rec["id"] in approved else
                         "rejected" if rec["id"] in rejected else "unreviewed")
    return {"actions": {"recommendations": recs, "pilot_mode": mode, "approved_ids": approved, "rejected_ids": rejected}}


# --------------------------------------------------------------------------- reporter
def build_report(state):
    sections, kpis = [], {}
    corpus, mission, physics = state.get("corpus"), state.get("mission"), state.get("physics")
    found, review, incidents, plan, actions = (state.get(k) for k in ("ranking", "review", "incidents", "gaps", "actions"))
    if corpus:
        kpis["investigations"] = corpus["investigations"]
        kpis["runs"] = corpus["runs"]
        sections.append({"agent": "librarian", "title": "Evidence base", "label": "DERIVED", "bullets": [
            f"{corpus['investigations']} investigation(s), {corpus['runs']} run(s), "
            f"{corpus['measured_findings']} MEASURED finding(s).",
            "Holds sheets marked NOT REAL DATA." if corpus["not_real"] else "From data/pyra.db (verified factsheets)."]})
    if mission:
        kpis["scenario"] = mission["name"]
        sections.append({"agent": "mission_profiler", "title": "Scenario", "label": "HYPOTHETICAL", "bullets": [
            ", ".join(f"{v['field']} {v['value']} {v['unit']}" for v in mission["values"] if v["value"] is not None)
            or "No values set.",
            f"Materials: {', '.join(mission['materials']) or 'none named'}."]})
    if physics:
        sections.append({"agent": "physicist", "title": "Flow regime (ILLUSTRATIVE scaling)", "label": "DERIVED",
                         "bullets": [physics.get("summary") or physics.get("reason") or "", physics.get("limits", "")]})
    if found:
        claims = found["claims"]
        kpis["claims"] = len(claims)
        kpis["measured_claims"] = sum(c["label"] == "MEASURED" for c in claims)
        kpis["review_passes"] = found["pass"]
        bullets = [f"[{c['label']}] {c['text']}" for c in claims]
        if review:
            bullets.append("Skeptic approved the final claims." if review["approved"] else
                           "Skeptic still has open issues; treat these claims as drafts.")
        sections.append({"agent": "evidence_ranker", "title": "What the evidence says", "label": "MIXED", "bullets": bullets})
    if plan:
        combo = plan["combination"]
        kpis["combination"] = combo.get("class") or "not evaluated"
        nxt = plan["next_experiment"]
        sections.append({"agent": "gap_hunter", "title": "Where the evidence stops", "label": "DERIVED", "bullets":
                         [combo.get("summary", "")] + ([nxt["text"] if nxt["text"].startswith("PROPOSAL") else f"PROPOSAL: {nxt['text']}"] if nxt else [])})
    if incidents:
        sections.append({"agent": "incident_analyst", "title": "Lessons from past fires", "label": "INTERPRETATION",
                         "bullets": [f"{c['name']} ({c['year']}): " + ("; ".join(c["links"]) or "no shared links")
                                     for c in incidents["cases"]]})
    if actions:
        recs = actions["recommendations"]
        kpis["recommendations"] = len(recs)
        kpis["approved"] = len(actions["approved_ids"])
        sections.append({"agent": "safety_officer", "title": "Recommendations", "label": "MIXED", "bullets": [
            f"[{r['priority']}] {r['title']} ({r['status']})" for r in recs]})
    if mission and found:
        untested = sum(c["label"] != "MEASURED" for c in found["claims"] if c["kind"] == "material")
        total = sum(c["kind"] == "material" for c in found["claims"])
        headline = (f"{mission['name']}: {untested} of {total} material check(s) are not directly measured; "
                    f"all set axes together are {kpis.get('combination', 'not evaluated')}.")
    elif mission:
        headline = f"{mission['name']}: evidence check complete."
    else:
        headline = "PYRA agent run complete."
    lines = [f"# {headline}", ""]
    for s in sections:
        lines += [f"## {s['title']} ({s['label']})", ""] + [f"- {b}" for b in s["bullets"] if b] + [""]
    lines.append("Labels follow docs/RULES.md. PYRA does not predict fires and gives no verdict on any material (rules 6 and 9).")
    return {"headline": headline, "sections": sections, "kpis": kpis, "markdown": "\n".join(lines)}


def reporter(state, ctx):
    report = build_report(state)
    report["headline"] = ctx.llm.think("reporter", "Rewrite this headline for a mission manager. Keep every number and label.",
                                       {"headline": report["headline"], "kpis": report["kpis"]}, report["headline"])
    report["markdown"] = f"# {report['headline']}\n" + report["markdown"].split("\n", 1)[1]
    ctx.emit("result", report["headline"])
    return {"report": report}


REGISTRY = {"librarian": librarian, "mission_profiler": mission_profiler, "physicist": physicist,
            "evidence_ranker": evidence_ranker, "skeptic": skeptic, "incident_analyst": incident_analyst,
            "gap_hunter": gap_hunter, "safety_officer": safety_officer}
ANY_MATERIAL = builder.ANY_MATERIAL
