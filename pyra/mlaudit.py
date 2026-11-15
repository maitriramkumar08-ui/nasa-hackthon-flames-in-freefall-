"""Decide whether a predictive model is justified before anyone trains one (Prompt 11).

audit() counts the rows that have a number for the target. Below the minimum
(decisions.json key ml_min_rows, default 50) it stops and says why. Above it,
it fits ordinary least squares and ridge regression in pure Python and scores
them with leave-one-investigation-out cross-validation, so a model is never
judged on the campaign it learned from.

No tree model: with the row counts we have, a tree would only memorise a few
campaigns, and the linear baselines already answer "is there signal at all".

predict() refuses any input outside the training range, and always refuses a
gravity outside the trained gravity values, so a model fitted on microgravity
runs is never shown as valid for the Moon (0.16 g).
"""

import math
import statistics

from . import evidence, units

DEFAULT_MIN_ROWS = 50
RIDGE_ALPHA = 1.0


def _target_value(run, target):
    """A number for the target in one run, or None. Outcome text is never parsed."""
    if target in evidence.QUANTITIES:
        return run["values"].get(target)
    outcome = run.get("outcome")
    if isinstance(outcome, dict):
        return units.to_number(outcome.get(target))
    return None


def rows_for(corpus, target):
    """Runs that have a number for the target, as {"group", "x", "y"} rows."""
    rows = []
    for run in corpus["runs"]:
        y = _target_value(run, target)
        if y is None:
            continue
        x = {q: v for q, v in run["values"].items() if q != target and v is not None}
        rows.append({"group": run["acronym"], "x": x, "y": y})
    return rows


def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting. None when the system is singular."""
    size = len(rhs)
    grid = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(grid[r][col]))
        if abs(grid[pivot][col]) < 1e-12:
            return None
        grid[col], grid[pivot] = grid[pivot], grid[col]
        for r in range(size):
            if r != col:
                factor = grid[r][col] / grid[col][col]
                grid[r] = [a - factor * b for a, b in zip(grid[r], grid[col])]
    return [grid[i][size] / grid[i][i] for i in range(size)]


def fit(rows, features, alpha=0.0):
    """Linear model y = b0 + sum(b * standardized x). alpha > 0 makes it ridge.

    Features that do not vary in these rows are dropped, since they carry no
    information and would make the system singular.
    """
    scale = {}
    for name in features:
        values = [row["x"][name] for row in rows]
        spread = statistics.pstdev(values)
        if spread > 0:
            scale[name] = (statistics.fmean(values), spread)
    used = list(scale)
    design = [[1.0] + [(row["x"][n] - scale[n][0]) / scale[n][1] for n in used] for row in rows]
    targets = [row["y"] for row in rows]
    width = len(used) + 1
    normal = [[sum(r[i] * r[j] for r in design) + (alpha if i == j and i > 0 else 0.0)
               for j in range(width)] for i in range(width)]
    rhs = [sum(r[i] * y for r, y in zip(design, targets)) for i in range(width)]
    coefficients = _solve(normal, rhs)
    if coefficients is None:
        return None
    return {"intercept": coefficients[0], "weights": dict(zip(used, coefficients[1:])), "scale": scale}


def _raw_predict(model, x):
    return model["intercept"] + sum(
        weight * (x[name] - model["scale"][name][0]) / model["scale"][name][1]
        for name, weight in model["weights"].items())


def cross_validate(rows, features, alpha=0.0):
    """Leave-one-investigation-out RMSE and MAE: mean, standard deviation, min and max over folds."""
    rmse, mae = [], []
    for group in sorted({row["group"] for row in rows}):
        train = [row for row in rows if row["group"] != group]
        held = [row for row in rows if row["group"] == group]
        model = fit(train, features, alpha)
        if model is None:
            continue
        errors = [_raw_predict(model, row["x"]) - row["y"] for row in held]
        rmse.append(math.sqrt(sum(e * e for e in errors) / len(errors)))
        mae.append(sum(abs(e) for e in errors) / len(errors))
    if not rmse:
        return None

    def summary(values):
        return {"mean": statistics.fmean(values), "sd": statistics.pstdev(values),
                "min": min(values), "max": max(values)}
    return {"folds": len(rmse), "rmse": summary(rmse), "mae": summary(mae), "label": "DERIVED"}


def training_ranges(rows):
    """{feature: (min, max)} over every row, including features that did not vary."""
    ranges = {}
    for row in rows:
        for name, value in row["x"].items():
            low, high = ranges.get(name, (value, value))
            ranges[name] = (min(low, value), max(high, value))
    return ranges


def in_training_range(model, x):
    """(ok, reasons). Any feature outside its trained range is a refusal."""
    reasons = []
    for name in model["features"]:
        if x.get(name) is None:
            reasons.append(f"{name} is not provided")
    for name, value in x.items():
        if value is None:
            continue
        if name not in model["ranges"]:
            if name == "gravity":
                reasons.append("the model was trained without any gravity value")
            continue
        low, high = model["ranges"][name]
        if not low <= value <= high:
            reasons.append(f"{name} = {value} is outside the trained range {low} to {high}")
    return not reasons, reasons


def predict(model, x):
    """A DERIVED prediction, or a refusal with the reasons when x is outside the training data."""
    ok, reasons = in_training_range(model, x)
    if not ok:
        return {"prediction": None, "refused": True, "reasons": reasons}
    return {"prediction": _raw_predict(model["ridge"], x), "refused": False, "reasons": [],
            "label": "DERIVED"}


def _stop(base, reason):
    return dict(base, train=False, reason=reason, conclusion=f"Do not train a model: {reason}.")


def audit_rows(rows, target, min_rows=None, alpha=RIDGE_ALPHA):
    """The audit on rows already prepared as {"group", "x", "y"}."""
    min_rows = DEFAULT_MIN_ROWS if min_rows is None else min_rows
    per_investigation = {}
    for row in rows:
        per_investigation[row["group"]] = per_investigation.get(row["group"], 0) + 1
    base = {"target": target, "rows": len(rows), "per_investigation": per_investigation,
            "min_rows": min_rows, "label": "DERIVED"}
    if len(rows) < min_rows:
        return _stop(base, f"only {len(rows)} valid rows for {target}, fewer than the {min_rows} required")
    if len(per_investigation) < 2:
        return _stop(base, "all rows come from one investigation, so grouped cross-validation is impossible")

    # Only features every row has, so no missing value is ever filled in.
    features = sorted(set.intersection(*(set(row["x"]) for row in rows)))
    ols = cross_validate(rows, features)
    ridge = cross_validate(rows, features, alpha)
    final = fit(rows, features, alpha)
    if ridge is None or final is None:
        return _stop(base, "the features do not vary enough to fit a linear model")

    model = {"features": features, "ranges": training_ranges(rows), "ridge": final}
    conclusion = (f"{len(rows)} rows from {len(per_investigation)} investigations. Ridge regression "
                  f"has leave-one-investigation-out RMSE {ridge['rmse']['mean']:.3g} "
                  f"(sd {ridge['rmse']['sd']:.3g} over {ridge['folds']} folds). Predictions are "
                  "refused outside the trained range, including any untrained gravity. "
                  "This is a statistical baseline, not a fire prediction.")
    return dict(base, train=True, features=features, metrics={"ols": ols, "ridge": ridge},
                tree="not implemented, see module docstring", model=model, conclusion=conclusion)


def audit(corpus, target, min_rows=None):
    """The dataset audit for one target over the whole corpus."""
    if min_rows is None:
        min_rows = evidence.decisions().get("ml_min_rows", DEFAULT_MIN_ROWS)
    found = audit_rows(rows_for(corpus, target), target, min_rows)
    text_outcomes = sum(1 for run in corpus["runs"] if isinstance(run.get("outcome"), str))
    if not found["train"] and text_outcomes:
        found["conclusion"] += (f" {text_outcomes} of {len(corpus['runs'])} test runs record the "
                                "outcome as text, not as a number, so the current data cannot "
                                "support a predictive model.")
    return found
