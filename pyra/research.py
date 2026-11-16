"""Where the evidence is thin, and which new tests would help most.

Four things for the researcher view, all plain code (rule 8):

    weakness(corpus)          how much each investigation actually measured
    clusters(weaknesses)      investigations grouped by their main weakness
    opportunities(...)        gaps worth filling, ranked by a configurable score
    backtest(...)             would the gap engine have flagged what later work tested?

Every number here is DERIVED. The scenarios passed in are HYPOTHETICAL and
come from the caller, so no mission atmosphere is hardcoded in this file.
"""

from . import evidence, gaps

# Run values are rounded to this many decimals before two runs count as the
# same condition, so 21.0 and 21.04 % O2 are one condition, not two.
CONDITION_DECIMALS = 1

# Checked in this order; the first rule that matches is the dominant weakness.
CLUSTER_RULES = [
    ("no runs", lambda w, min_runs: w["tests"] == 0),
    ("few runs", lambda w, min_runs: w["tests"] < min_runs),
    ("mostly missing values", lambda w, min_runs: w["missing_share"] > 0.5),
    ("single condition", lambda w, min_runs: w["distinct_conditions"] == 1),
    ("no repeats", lambda w, min_runs: w["repeats_per_condition"] == 1),
]
NO_DOMINANT = "no dominant weakness"

# PLACEHOLDER weights until the team agrees on them (decisions.json key
# "opportunity_weights" overrides this). gap_size: how big a gap each class is.
# data_cost: per axis, higher means new data is cheaper to get, e.g. gravity
# needs a flight so it scores low. Axes not listed count as 1.0.
DEFAULT_WEIGHTS = {
    "gap_size": {
        "NO_INDEXED_DATA": 1.0, "INSUFFICIENT": 0.8, "ONE_SIDED": 0.6,
        "NOT_COMPARABLE": 0.5, "BOUNDED": 0.3, "DIRECTLY_TESTED": 0.0,
    },
    "data_cost": {
        "o2_percent": 1.0, "pressure": 1.0, "flow_speed": 0.8, "gravity": 0.3,
    },
    "default_relevance": 1.0,
}


def _runs_by_investigation(corpus):
    runs = {inv["id"]: [] for inv in corpus["investigations"]}
    for run in corpus["runs"]:
        runs.setdefault(run["investigation_id"], []).append(run)
    return runs


def _condition(run):
    return tuple(None if run["values"].get(q) is None else round(run["values"][q], CONDITION_DECIMALS)
                 for q in evidence.QUANTITIES)


def weakness(corpus):
    """Per investigation: runs, distinct conditions, repeats, missing share and stated limitations."""
    runs_of = _runs_by_investigation(corpus)
    report = []
    for inv in corpus["investigations"]:
        runs = runs_of[inv["id"]]
        conditions = {_condition(run) for run in runs}
        missing_values = sum(1 for run in runs for q in evidence.QUANTITIES if run["values"].get(q) is None)
        missing_ranges = sum(1 for q in evidence.QUANTITIES if q not in inv["ranges"])
        slots = (len(runs) + 1) * len(evidence.QUANTITIES)
        report.append({
            "acronym": inv["acronym"],
            "tests": len(runs),
            "distinct_conditions": len(conditions),
            "repeats_per_condition": len(runs) / len(conditions) if conditions else None,
            "missing_share": (missing_values + missing_ranges) / slots,
            "limitations": list(inv["notes"].get("limitation", [])),
            "label": "DERIVED",
        })
    return report


def dominant_weakness(entry, min_runs):
    for name, matches in CLUSTER_RULES:
        if matches(entry, min_runs):
            return name
    return NO_DOMINANT


def clusters(weaknesses, min_runs=None):
    """{weakness name: [acronyms]} using the fixed CLUSTER_RULES, first match wins."""
    if min_runs is None:
        min_runs = evidence.decisions()["min_runs_for_sufficient"]
    groups = {}
    for entry in weaknesses:
        groups.setdefault(dominant_weakness(entry, min_runs), []).append(entry["acronym"])
    return {name: sorted(acronyms) for name, acronyms in groups.items()}


def _weights(weights):
    if weights is not None:
        return weights
    return evidence.decisions().get("opportunity_weights", DEFAULT_WEIGHTS)


def opportunities(corpus, mission_atmospheres, weights=None):
    """Untested axes of each mission atmosphere, highest score first.

    Each mission atmosphere is {"name", "scenario": raw scenario, "relevance"?}.
    score = gap size of the axis x relevance of the atmosphere x data cost factor of the axis.
    """
    weights = _weights(weights)
    found = []
    for mission in mission_atmospheres:
        relevance = mission.get("relevance", weights["default_relevance"])
        analysis = gaps.analyze(corpus, evidence.scenario(mission["scenario"]))
        for axis, gap in analysis["axes"].items():
            if gap.get("state") == "NOT_EVALUATED":
                continue  # an unset axis is not a gap
            size = weights["gap_size"].get(gap["class"], 0.0)
            cost = weights["data_cost"].get(axis, 1.0)
            if size == 0:
                continue
            found.append({
                "mission": mission["name"], "axis": axis, "gap_class": gap["class"],
                "gap_size": size, "relevance": relevance, "data_cost": cost,
                "score": size * relevance * cost, "label": "DERIVED",
            })
    return sorted(found, key=lambda o: (-o["score"], o["mission"], o["axis"]))


def _year(years, publication_id, acronym):
    return years.get(publication_id, years.get(acronym))


def before(corpus, cutoff_year, years):
    """The corpus restricted to publications dated before cutoff_year, plus the undated acronyms."""
    def early(publication_id, acronym):
        year = _year(years, publication_id, acronym)
        return year is not None and year < cutoff_year

    kept, undated = [], []
    for inv in corpus["investigations"]:
        if all(_year(years, pub["id"], inv["acronym"]) is None for pub in inv["publications"]):
            undated.append(inv["acronym"])
        early_pubs = [pub for pub in inv["publications"] if early(pub["id"], inv["acronym"])]
        if early_pubs:
            kept.append(dict(inv, publications=early_pubs))
    kept_ids = {inv["id"] for inv in kept}
    runs = [run for run in corpus["runs"] if run["investigation_id"] in kept_ids
            and early(run["source"]["publication_id"], run["acronym"])]
    return {"investigations": kept, "runs": runs}, sorted(undated)


def backtest(corpus, cutoff_year, years, checks):
    """Run the gap engine on the pre-cutoff corpus and score each check as a hit or a miss.

    years is {publication id or acronym: year}. Each check is
    {"name", "scenario": raw scenario, "should_flag": bool}. A scenario counts as
    flagged when its combined gap class is anything other than DIRECTLY_TESTED.
    """
    early, undated = before(corpus, cutoff_year, years)
    outcomes = []
    for check in checks:
        combined = gaps.analyze(early, evidence.scenario(check["scenario"]))["combination"]["class"]
        flagged = combined != "DIRECTLY_TESTED"
        outcomes.append({
            "name": check["name"], "should_flag": check["should_flag"], "flagged": flagged,
            "gap_class": combined, "outcome": "hit" if flagged == check["should_flag"] else "miss",
        })
    return {
        "cutoff_year": cutoff_year,
        "investigations_kept": [inv["acronym"] for inv in early["investigations"]],
        "undated_dropped": undated,
        "checks": outcomes,
        "hits": sum(1 for r in outcomes if r["outcome"] == "hit"),
        "misses": sum(1 for r in outcomes if r["outcome"] == "miss"),
        "label": "DERIVED",
    }
