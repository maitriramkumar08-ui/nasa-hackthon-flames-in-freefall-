"""Reporter: headline, one section per agent, KPIs. Output key: report."""
from __future__ import annotations


def build_report(state) -> dict:
    s, k = [], {}
    c, m, ph = state.get("corpus"), state.get("mission"), state.get("physics")
    risk, rev, inc, gaps, act = (state.get(x) for x in ("risk", "review", "incidents", "gaps", "actions"))
    if c:
        n = c["counts"]
        k["psi_records"] = n["kept"]
        s.append({"agent": "librarian", "title": "Evidence base", "bullets": [
            f"{n['kept']} combustion investigations from NASA PSI ({n['microgravity']} flight, {n['ground']} ground).",
            f"{n['dropped']} non-combustion record(s) removed; {n['partial_gravity']} partial-gravity investigations exist."]})
    if m:
        k["mission"] = m["name"]
        s.append({"agent": "mission_profiler", "title": "Mission", "bullets": [
            f"{m['name']}: {m['gravity_g']:g} g, {m['pressure_psia']:g} psia, {m['o2_pct']:g}% O2, fan {m['fan_m_s']:g} m/s.",
            m["atmosphere_note"]]})
    if ph:
        k["regime"] = ph["regime"]
        s.append({"agent": "physicist", "title": "Flame regime", "bullets": [ph.get("summary") or ph["regime_text"],
                  f"Fan shutdown effect: {ph['fan_shutdown_effect']}."]})
    if risk:
        items = risk["items"]
        hot = [i for i in items if i["verdict"] in ("burns", "could burn")]
        k["materials_at_risk"] = len(hot)
        k["materials_ranked"] = len(items)
        k["measured_claims"] = sum(i["confidence"] == "measured" for i in items)
        k["hot_measured"] = sum(i["confidence"] == "measured" for i in hot)
        k["review_passes"] = risk["iteration"]
        b = [f"{i['name']}: {i['verdict']} (margin {i['margin']:+g} +/- {i['band']:g} pts, {i['confidence']})" for i in items[:5]]
        if rev:
            b.append("Skeptic approved the final ranking." if rev["approved"] else "Skeptic still has open issues.")
        s.append({"agent": "risk_ranker", "title": "Material risk", "bullets": b})
    if inc:
        s.append({"agent": "incident_analyst", "title": "Lessons from past fires", "bullets": [
            f"{x['name']} ({x['year']}): {x['match']} match. " + "; ".join(x["match_reasons"]) for x in inc["cases"]]})
    if gaps:
        p = gaps["proposal"]
        k["coverage_pct"] = round(100 * gaps["covered"] / gaps["cells"])
        s.append({"agent": "gap_hunter", "title": "What has not been tested", "bullets": [
            f"{gaps['covered']} of {gaps['cells']} condition cells have flight data.",
            f"Next experiment: {p['title']}.", p["platform"], p["answers"]]})
    if act:
        recs = act["recommendations"]
        k["recommendations"] = len(recs)
        k["approved"] = len([r for r in recs if r.get("status") == "approved"])
        s.append({"agent": "safety_officer", "title": "Recommendations", "bullets": [
            f"[{r['priority']}] {r['title']} ({r.get('status', 'unreviewed')})" for r in recs]})
    if m and risk:
        hm = k.get("hot_measured", 0)
        tail = ("none of those claims rests on a NASA test at these conditions" if hm == 0 else
                f"only {hm} of those claims rest on a NASA test at these conditions")
        headline = (f"{m['name']}: {k.get('materials_at_risk', 0)} of {k.get('materials_ranked', 0)} cabin materials burn or could burn "
                    f"at {m['o2_pct']:g}% O2; {tail}.")
    elif m:
        headline = f"{m['name']}: assessment complete."
    else:
        headline = "EMBER run complete."
    return {"headline": headline, "sections": s, "kpis": k}


def run(state, ctx) -> dict:
    rep = build_report(state)
    rep["headline"] = ctx.llm.think("reporter", system="Rewrite this headline for a mission manager. Keep every number.",
                                    payload={"headline": rep["headline"], "kpis": rep["kpis"]}, fallback=rep["headline"])
    ctx.emit("result", rep["headline"])
    return {"report": rep}
