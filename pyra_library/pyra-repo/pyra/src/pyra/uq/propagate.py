"""Monte Carlo uncertainty propagation with explicit, reproducible seeds."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
from scipy.stats import qmc  # type: ignore[import-untyped]

from pyra.provenance.status import Quantity, Status
from pyra.units import quantity


def propagate(
    function: Callable[[tuple[float, ...]], float],
    inputs: Sequence[Quantity],
    *,
    output_unit: str,
    n: int = 4096,
    seed: int = 0,
    activity: str = "uq.propagate",
) -> Quantity:
    """Propagate independent normal uncertainties through ``function``.

    The Sobol sequence is deterministic for a given seed.  This function does
    not guess uncertainty when an input declares ``u_kind='unknown'``.
    """
    if n < 2:
        raise ValueError("n must be at least 2")
    if any(item.u is None for item in inputs):
        raise ValueError("all inputs need known uncertainty for propagation")
    if any(item.status > Status.DERIVED for item in inputs):
        raise ValueError("propagation accepts only MEASURED or DERIVED inputs")

    dimension = len(inputs)
    exponent = max(1, math.ceil(math.log2(n)))
    sampler = qmc.Sobol(d=dimension, scramble=True, seed=seed)
    unit_cube = sampler.random_base2(exponent)[:n]
    # Avoid infinities at the exact endpoints of the normal inverse CDF.
    unit_cube = np.clip(unit_cube, np.finfo(float).eps, 1 - np.finfo(float).eps)
    from scipy.special import ndtri  # type: ignore[import-untyped]

    def sample_value(item: Quantity, probability: float) -> float:
        if item.u is None:
            raise ValueError("all inputs need known uncertainty for propagation")
        return float(item.value) + float(item.u) * float(ndtri(probability))

    samples: list[list[float]] = [
        [
            sample_value(item, float(p)) for item, p in zip(inputs, row, strict=False)
        ]
        for row in unit_cube
    ]
    values = np.asarray(
        [function(tuple(row)) for row in samples],
        dtype=np.float64,
    )
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("propagation function must return finite scalar values")
    result = Quantity.derive(
        float(np.mean(values)),
        output_unit,
        float(np.std(values, ddof=1)),
        "type_a",
        parents=list(inputs),
        activity=activity,
        params={"n": n, "seed": seed},
        max_input_status=Status.DERIVED,
    )
    # Constructing this once validates the requested output unit through Pint.
    quantity(result.value, result.unit)
    return result


__all__ = ["propagate"]
