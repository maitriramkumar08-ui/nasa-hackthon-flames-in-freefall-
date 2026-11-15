"""Transparent benchmark scoring for model predictions against PYRA evidence."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from pyrakit.compare.metrics import _converted
from pyrakit.provenance import Quantity, Status


@dataclass(frozen=True)
class ModelEvaluation:
    """A benchmark result, never a universal reliability guarantee."""

    score: float
    n_cases: int
    passed_cases: int
    mean_absolute_error: float
    mean_normalized_error: float | None
    independent_sources: int
    status: Status
    caveats: tuple[str, ...]


def evaluate_model(
    observations: Sequence[Quantity],
    predictions: Sequence[Quantity],
    *,
    tolerance: float,
    source_ids: Sequence[str] | None = None,
) -> ModelEvaluation:
    """Score predictions by the percentage within an explicit absolute tolerance.

    The tolerance is a benchmark choice supplied by the caller. Units are
    converted to each observation's unit, and uncertainty-normalized errors are
    reported when both sides provide uncertainty. The score covers only these
    cases and sources; it is not a safety or deployment certification.
    """
    if not observations or len(observations) != len(predictions):
        raise ValueError("observations and predictions must have the same non-zero length")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if source_ids is not None and len(source_ids) != len(observations):
        raise ValueError("source_ids must match the number of cases")
    errors: list[float] = []
    normalized: list[float] = []
    passed = 0
    for observation, prediction in zip(observations, predictions, strict=True):
        predicted, predicted_u = _converted(prediction, observation.unit)
        observed, observed_u = _converted(observation, observation.unit)
        error = abs(predicted - observed)
        errors.append(error)
        if error <= tolerance:
            passed += 1
        if predicted_u is not None and observed_u is not None:
            denominator = math.hypot(predicted_u, observed_u)
            if denominator > 0:
                normalized.append(error / denominator)
    caveats: list[str] = []
    independent_sources = len(set(source_ids)) if source_ids is not None else 0
    if source_ids is None:
        caveats.append("independent source IDs were not supplied")
    elif independent_sources < 2:
        caveats.append("benchmark uses fewer than two independent sources")
    if any(item.status > Status.DERIVED for item in observations):
        caveats.append("some observations are above DERIVED status")
    return ModelEvaluation(
        score=100.0 * passed / len(errors),
        n_cases=len(errors),
        passed_cases=passed,
        mean_absolute_error=sum(errors) / len(errors),
        mean_normalized_error=None if not normalized else sum(normalized) / len(normalized),
        independent_sources=independent_sources,
        status=Status.INTERPRETATION,
        caveats=tuple(caveats),
    )


__all__ = ["ModelEvaluation", "evaluate_model"]
