"""Scenario-to-experiment mismatch vectors and tiering."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pyra.matching.policy import MatchPolicy
from pyra.schema import Conditions, ExperimentRecord, Scenario
from pyra.units import quantity

Tier = Literal["EXACT", "NEIGHBOR", "ANALOG", "NONE"]


@dataclass(frozen=True)
class MismatchVector:
    dimensions: dict[str, float]
    aggregate: float
    tier: Tier
    blocked_by: tuple[str, ...] = ()


def _number(measure, target: str) -> tuple[float, float | None]:
    value = quantity(measure.value, measure.unit).to(target)
    uncertainty = None if measure.u is None else quantity(measure.u, measure.unit).to(target)
    return float(value.magnitude), None if uncertainty is None else float(uncertainty.magnitude)


def _dimension_values(c: Conditions) -> dict[str, tuple[float, float | None]]:
    result = {
        "gravity_g": _number(c.gravity_g, "dimensionless"),
        "pressure": _number(c.pressure, "Pa"),
        "o2_mole_fraction": _number(c.o2_mole_fraction, "dimensionless"),
        "length_scale": _number(c.length_scale, "m"),
    }
    if c.flow_velocity is not None:
        result["flow_velocity"] = _number(c.flow_velocity, "m/s")
    return result


def match_conditions(
    scenario: Conditions, experiment: Conditions, policy: MatchPolicy
) -> MismatchVector:
    """Compare two condition records while retaining every dimension's distance."""
    blocked: list[str] = []
    if scenario.configuration != experiment.configuration:
        blocked.append("configuration")
    if scenario.flow_mode != experiment.flow_mode:
        blocked.append("flow_mode")
    if scenario.fuel.material.casefold() != experiment.fuel.material.casefold():
        blocked.append("fuel")
    if blocked:
        return MismatchVector({}, math.inf, "NONE", tuple(blocked))

    left, right = _dimension_values(scenario), _dimension_values(experiment)
    distances: dict[str, float] = {}
    for name, tolerance in policy.tolerances.items():
        if name not in left or name not in right:
            distances[name] = math.inf
            continue
        a, ua = left[name]
        b, ub = right[name]
        if name in {"gravity_g", "pressure"}:
            floor = policy.g_floor if name == "gravity_g" else 1e-12
            a, b = math.log(max(a, floor)), math.log(max(b, floor))
        sigma = math.sqrt((ua or 0.0) ** 2 + (ub or 0.0) ** 2 + tolerance**2)
        distances[name] = abs(a - b) / sigma
    total_weight = sum(policy.weights.values())
    aggregate = math.sqrt(
        sum(policy.weights[name] * distance**2 for name, distance in distances.items())
        / total_weight
    )
    if all(distance <= 1 for distance in distances.values()):
        tier: Tier = "EXACT"
    elif (
        all(distance <= policy.d_max for distance in distances.values())
        and aggregate <= policy.aggregate_max
    ):
        tier = "NEIGHBOR"
    else:
        tier = "NONE"
    return MismatchVector(distances, aggregate, tier)


def match(scenario: Scenario, experiment: ExperimentRecord, policy: MatchPolicy) -> MismatchVector:
    """Match one scenario to one experiment record."""
    return match_conditions(scenario.conditions, experiment.conditions, policy)


__all__ = ["MismatchVector", "match", "match_conditions"]
