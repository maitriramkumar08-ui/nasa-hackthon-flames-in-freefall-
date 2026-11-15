"""Scenario-aware validation-envelope checks for the model claim gate.

``require_validated`` only asks whether a model card carries *any* validation
evidence. That is not enough to support a claim about a particular scenario: a card
validated in an Earth-gravity bench test says nothing about a microgravity flame.
This module reads the ``envelope`` recorded on each model card evidence entry and
reports, axis by axis, whether one scenario falls inside it.

Nothing here validates a model. It compares a scenario against limits a human wrote
on the card, so a card with absent, wrong or optimistic limits still produces a
wrong answer. An entry that declares no limits at all never counts as covering.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pyrakit.schema import Conditions, ModelCard, Scenario, ValidationEvidence
from pyrakit.units import quantity

# Numeric envelope axes: the attribute read from ``Conditions`` and the unit that
# recorded limits are converted into before any comparison.
NUMERIC_AXES: Mapping[str, str] = {
    "gravity_g": "dimensionless",
    "pressure": "pascal",
    "o2_mole_fraction": "dimensionless",
    "flow_velocity": "meter / second",
    "temperature": "kelvin",
    "length_scale": "meter",
}

# Categorical axes, compared as case-folded strings.
CATEGORICAL_AXES: Mapping[str, str] = {
    "diluent": "diluent",
    "flow_mode": "flow_mode",
    "configuration": "configuration",
    "fuel_material": "fuel.material",
}

#: Axes a card must bound before PYRA treats a scenario as covered. This is a
#: documented starting policy for spacecraft fire scenarios, not a claim about which
#: variables are physically sufficient.
DEFAULT_REQUIRED_AXES: tuple[str, ...] = ("gravity_g", "o2_mole_fraction", "pressure")


@dataclass(frozen=True)
class EnvelopeGatePolicy:
    """Which axes a model card must declare before a scenario can be called covered.

    The default ``required_axes`` is a starting policy, not a physical sufficiency
    claim. Widen it whenever the quantity being claimed depends on more variables.
    """

    required_axes: tuple[str, ...] = DEFAULT_REQUIRED_AXES

    def __post_init__(self) -> None:
        unknown = [
            axis
            for axis in self.required_axes
            if axis not in NUMERIC_AXES and axis not in CATEGORICAL_AXES
        ]
        if unknown:
            raise ValueError(f"unknown envelope axes in required_axes: {sorted(unknown)}")


@dataclass(frozen=True)
class NumericLimit:
    """An inclusive recorded range for one numeric axis, in that axis's canonical unit."""

    axis: str
    low: float
    high: float
    unit: str

    def describe(self) -> str:
        low = "-inf" if self.low == -math.inf else f"{self.low:g}"
        high = "inf" if self.high == math.inf else f"{self.high:g}"
        return f"{low} to {high} {self.unit}"


@dataclass(frozen=True)
class CategoricalLimit:
    """The set of recorded values for one categorical axis."""

    axis: str
    allowed: tuple[str, ...]

    def describe(self) -> str:
        return "one of " + ", ".join(self.allowed)


Limit = NumericLimit | CategoricalLimit


@dataclass(frozen=True)
class AxisCheck:
    """Whether one scenario axis falls inside one recorded limit."""

    axis: str
    inside: bool
    scenario_value: float | str | None
    allowed: str
    reason: str = ""


@dataclass(frozen=True)
class EvidenceCheck:
    """How one validation-evidence entry relates to one scenario."""

    quantity: str
    metric: str
    experiment_ids: tuple[str, ...]
    axes: tuple[AxisCheck, ...]
    missing_required_axes: tuple[str, ...]

    @property
    def outside(self) -> tuple[AxisCheck, ...]:
        """The declared axes whose scenario value falls outside the recorded limit."""
        return tuple(check for check in self.axes if not check.inside)

    @property
    def covers(self) -> bool:
        """Whether this entry bounds every required axis and the scenario sits inside."""
        return bool(self.axes) and not self.outside and not self.missing_required_axes

    def reason(self) -> str:
        """One plain-language sentence explaining this entry's verdict."""
        sources = ", ".join(self.experiment_ids)
        label = f"evidence for {self.quantity!r} ({self.metric}) from {sources}"
        if not self.axes:
            return f"{label} records no envelope limits, so it cannot cover any scenario"
        if self.missing_required_axes:
            missing = ", ".join(self.missing_required_axes)
            return f"{label} does not bound the required axes: {missing}"
        if self.outside:
            details = "; ".join(check.reason for check in self.outside)
            return f"{label} does not reach this scenario: {details}"
        return f"{label} covers this scenario"


@dataclass(frozen=True)
class EnvelopeCheck:
    """The result of checking one scenario against one model card's envelope."""

    card_name: str
    card_version: str
    scenario_id: str
    evidence: tuple[EvidenceCheck, ...]

    @property
    def covering(self) -> tuple[EvidenceCheck, ...]:
        """The evidence entries that fully cover this scenario."""
        return tuple(check for check in self.evidence if check.covers)

    @property
    def inside(self) -> bool:
        """Whether at least one evidence entry covers this scenario."""
        return bool(self.covering)

    def reasons(self) -> tuple[str, ...]:
        """One explanatory sentence per evidence entry."""
        if not self.evidence:
            return ("the model card records no validation evidence at all",)
        return tuple(check.reason() for check in self.evidence)

    def explain(self) -> str:
        """Return a plain-language report suitable for printing to a learner."""
        model = f"{self.card_name} {self.card_version}"
        verdict = "INSIDE" if self.inside else "OUTSIDE"
        lines = [
            f"Scenario {self.scenario_id!r} is {verdict} the recorded validation "
            f"envelope of model {model}.",
            "",
        ]
        lines += [f"- {reason}" for reason in self.reasons()]
        lines += [
            "",
            "Being inside a recorded envelope means a human logged evidence covering "
            "these conditions. It is not a safety certification, and it does not check "
            "that the recorded limits are themselves correct.",
        ]
        return "\n".join(lines)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _parse_numeric_limit(axis: str, spec: Any) -> NumericLimit:
    """Read ``[low, high]`` or ``{"min": .., "max": .., "unit": ".."}`` for one axis."""
    canonical = NUMERIC_AXES[axis]
    if isinstance(spec, Mapping):
        unknown = set(spec) - {"min", "max", "unit"}
        if unknown:
            raise ValueError(f"envelope axis {axis!r} has unknown keys: {sorted(unknown)}")
        if "min" not in spec and "max" not in spec:
            raise ValueError(f"envelope axis {axis!r} must record 'min' or 'max'")
        recorded_unit = spec.get("unit", canonical)
        if not isinstance(recorded_unit, str):
            raise ValueError(f"envelope axis {axis!r} has a non-string unit")
        low_raw, high_raw = spec.get("min", -math.inf), spec.get("max", math.inf)
    elif isinstance(spec, Sequence) and not isinstance(spec, str | bytes):
        if len(spec) != 2:
            raise ValueError(f"envelope axis {axis!r} must be a [min, max] pair")
        recorded_unit = canonical
        low_raw, high_raw = spec[0], spec[1]
    else:
        raise ValueError(
            f"envelope axis {axis!r} must be a [min, max] pair or a mapping with min/max"
        )

    for name, raw in (("min", low_raw), ("max", high_raw)):
        if not _is_number(raw) or math.isnan(float(raw)):
            raise ValueError(f"envelope axis {axis!r} has a non-numeric {name}")
    low, high = float(low_raw), float(high_raw)
    if low > high:
        raise ValueError(f"envelope axis {axis!r} has min above max")
    # Convert recorded limits into the canonical unit once, so the comparison against
    # the scenario never mixes units.
    if recorded_unit != canonical:
        low = float(quantity(low, recorded_unit).to(canonical).magnitude)
        high = float(quantity(high, recorded_unit).to(canonical).magnitude)
    return NumericLimit(axis=axis, low=low, high=high, unit=canonical)


def _parse_categorical_limit(axis: str, spec: Any) -> CategoricalLimit:
    values = [spec] if isinstance(spec, str) else spec
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise ValueError(f"envelope axis {axis!r} must be a string or a list of strings")
    if not values:
        raise ValueError(f"envelope axis {axis!r} must record at least one allowed value")
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError(f"envelope axis {axis!r} must contain non-empty strings")
    return CategoricalLimit(axis=axis, allowed=tuple(str(value) for value in values))


def parse_envelope(envelope: Mapping[str, Any]) -> tuple[Limit, ...]:
    """Read one evidence entry's ``envelope`` mapping into typed, unit-resolved limits.

    Raises ``ValueError`` for an unknown axis or a malformed limit, so a typo in a
    model card fails loudly instead of silently widening the envelope.
    """
    limits: list[Limit] = []
    for axis, spec in envelope.items():
        if axis in NUMERIC_AXES:
            limits.append(_parse_numeric_limit(axis, spec))
        elif axis in CATEGORICAL_AXES:
            limits.append(_parse_categorical_limit(axis, spec))
        else:
            known = sorted({*NUMERIC_AXES, *CATEGORICAL_AXES})
            raise ValueError(f"unknown envelope axis {axis!r}; known axes are {known}")
    return tuple(limits)


def _scenario_numeric(conditions: Conditions, axis: str) -> float | None:
    """Return one scenario axis in its canonical unit, or ``None`` when unset."""
    measure = getattr(conditions, axis)
    if measure is None:
        return None
    canonical = NUMERIC_AXES[axis]
    return float(quantity(measure.value, measure.unit).to(canonical).magnitude)


def _scenario_categorical(conditions: Conditions, axis: str) -> str:
    if axis == "fuel_material":
        return conditions.fuel.material
    return str(getattr(conditions, axis))


def _check_numeric_axis(conditions: Conditions, limit: NumericLimit) -> AxisCheck:
    value = _scenario_numeric(conditions, limit.axis)
    if value is None:
        return AxisCheck(
            axis=limit.axis,
            inside=False,
            scenario_value=None,
            allowed=limit.describe(),
            reason=(
                f"the envelope bounds {limit.axis} to {limit.describe()} but the "
                f"scenario leaves it unset"
            ),
        )
    inside = limit.low <= value <= limit.high
    reason = (
        ""
        if inside
        else f"{limit.axis} is {value:g} {limit.unit}, outside the recorded {limit.describe()}"
    )
    return AxisCheck(
        axis=limit.axis,
        inside=inside,
        scenario_value=value,
        allowed=limit.describe(),
        reason=reason,
    )


def _check_categorical_axis(conditions: Conditions, limit: CategoricalLimit) -> AxisCheck:
    value = _scenario_categorical(conditions, limit.axis)
    inside = any(value.casefold() == allowed.casefold() for allowed in limit.allowed)
    return AxisCheck(
        axis=limit.axis,
        inside=inside,
        scenario_value=value,
        allowed=limit.describe(),
        reason="" if inside else f"{limit.axis} is {value!r}, not {limit.describe()}",
    )


def _check_axis(conditions: Conditions, limit: Limit) -> AxisCheck:
    if isinstance(limit, NumericLimit):
        return _check_numeric_axis(conditions, limit)
    return _check_categorical_axis(conditions, limit)


def _check_evidence(
    evidence: ValidationEvidence, scenario: Scenario, policy: EnvelopeGatePolicy
) -> EvidenceCheck:
    limits = parse_envelope(evidence.envelope)
    declared = {limit.axis for limit in limits}
    return EvidenceCheck(
        quantity=evidence.quantity,
        metric=evidence.metric,
        experiment_ids=tuple(evidence.experiment_ids),
        axes=tuple(_check_axis(scenario.conditions, limit) for limit in limits),
        missing_required_axes=tuple(axis for axis in policy.required_axes if axis not in declared),
    )


def check_envelope(
    card: ModelCard, scenario: Scenario, *, policy: EnvelopeGatePolicy | None = None
) -> EnvelopeCheck:
    """Report whether one scenario falls inside a model card's recorded envelope.

    This never raises for an out-of-envelope scenario; it returns a report whose
    ``inside`` flag and ``explain()`` text say what was checked and what failed. Use
    ``require_in_envelope`` when an out-of-envelope scenario must stop the run.
    """
    effective = policy or EnvelopeGatePolicy()
    return EnvelopeCheck(
        card_name=card.name,
        card_version=card.version,
        scenario_id=scenario.scenario_id,
        evidence=tuple(_check_evidence(item, scenario, effective) for item in card.envelope),
    )


__all__ = [
    "CATEGORICAL_AXES",
    "DEFAULT_REQUIRED_AXES",
    "NUMERIC_AXES",
    "AxisCheck",
    "CategoricalLimit",
    "EnvelopeCheck",
    "EnvelopeGatePolicy",
    "EvidenceCheck",
    "Limit",
    "NumericLimit",
    "check_envelope",
    "parse_envelope",
]
