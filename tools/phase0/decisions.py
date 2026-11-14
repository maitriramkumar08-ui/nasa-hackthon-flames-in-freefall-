import json


def load(json_path):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def unconfirmed(decisions):
    problems = []
    for name, decision in decisions.items():
        if name.startswith("_"):  # "_note" and friends aren't decisions
            continue
        if not decision.get("confirmed_by", "").strip():
            problems.append(f"{name}: nobody has confirmed it yet")
    return problems


def weights_total(decisions):
    weights = decisions.get("ranking_weights", {}).get("value", {})
    # rounding because 0.1 + 0.2 != 0.3 in floating point
    return round(sum(weights.values()), 6)


def check_decisions(json_path):
    decisions = load(json_path)
    problems = unconfirmed(decisions)

    total = weights_total(decisions)
    if total != 1:
        problems.append(f"ranking_weights add up to {total}, should be 1")
    return problems
