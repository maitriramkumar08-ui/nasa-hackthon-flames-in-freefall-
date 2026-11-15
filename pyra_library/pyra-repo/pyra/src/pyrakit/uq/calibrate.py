"""Small resampling utility; not a substitute for parameter calibration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, pstdev

import numpy as np


@dataclass(frozen=True)
class BootstrapSummary:
    estimate: float
    standard_error: float
    lower: float
    upper: float
    n_resamples: int
    seed: int


def bootstrap_mean(
    values: Sequence[float], *, n_resamples: int = 2000, seed: int = 0, confidence: float = 0.95
) -> BootstrapSummary:
    """Estimate a mean and percentile interval by explicit-seed bootstrap resampling.

    This summarizes observed values; it does not calibrate a simulator parameter
    or convert a model into a validated predictor.
    """
    if not values or n_resamples < 2 or not 0 < confidence < 1:
        raise ValueError("values, n_resamples >= 2, and 0 < confidence < 1 are required")
    observations = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(observations)):
        raise ValueError("values must be finite")
    rng = np.random.default_rng(seed)
    samples = rng.choice(observations, size=(n_resamples, observations.size), replace=True).mean(
        axis=1
    )
    tail = (1 - confidence) / 2
    return BootstrapSummary(
        estimate=float(mean(observations)),
        standard_error=float(pstdev(samples.tolist())),
        lower=float(np.quantile(samples, tail)),
        upper=float(np.quantile(samples, 1 - tail)),
        n_resamples=n_resamples,
        seed=seed,
    )


__all__ = ["BootstrapSummary", "bootstrap_mean"]
