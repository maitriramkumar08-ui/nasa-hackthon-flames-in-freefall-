"""Status-aware scalar comparison metrics."""

from __future__ import annotations

import math

from pyrakit.provenance import Quantity
from pyrakit.units import quantity


def _converted(value: Quantity, target: str) -> tuple[float, float | None]:
    converted = quantity(value.value, value.unit).to(target)
    uncertainty = None if value.u is None else quantity(value.u, value.unit).to(target)
    return float(converted.magnitude), None if uncertainty is None else float(uncertainty.magnitude)


def bias(measured: Quantity, simulated: Quantity) -> Quantity:
    """Return ``simulated - measured`` in the measured unit."""
    sim, sim_u = _converted(simulated, measured.unit)
    meas, meas_u = _converted(measured, measured.unit)
    uncertainty = None if sim_u is None or meas_u is None else math.hypot(sim_u, meas_u)
    return Quantity.derive(
        sim - meas,
        measured.unit,
        uncertainty,
        "type_b" if uncertainty is not None else "unknown",
        parents=[measured, simulated],
        activity="compare.bias",
    )


def relative_difference(measured: Quantity, simulated: Quantity) -> Quantity:
    """Return ``(simulated - measured) / measured`` as a dimensionless result."""
    delta = bias(measured, simulated)
    meas, _ = _converted(measured, measured.unit)
    if meas == 0:
        raise ZeroDivisionError("relative difference is undefined for a zero measurement")
    uncertainty = None if delta.u is None else abs(delta.u / meas)
    return Quantity.derive(
        delta.value / meas,
        "dimensionless",
        uncertainty,
        "type_b" if uncertainty is not None else "unknown",
        parents=[measured, simulated],
        activity="compare.relative_difference",
    )


def z_score(measured: Quantity, simulated: Quantity, *, discrepancy: float = 0.0) -> Quantity:
    """Return a z-score using combined measurement, simulation and discrepancy uncertainty."""
    delta = bias(measured, simulated)
    if measured.u is None or simulated.u is None:
        raise ValueError("z_score needs known uncertainty on both inputs")
    _, meas_u = _converted(measured, measured.unit)
    _, sim_u = _converted(simulated, measured.unit)
    denominator = math.sqrt((meas_u or 0.0) ** 2 + (sim_u or 0.0) ** 2 + discrepancy**2)
    if denominator == 0:
        raise ZeroDivisionError("z-score is undefined when combined uncertainty is zero")
    return Quantity.derive(
        delta.value / denominator,
        "dimensionless",
        None,
        "unknown",
        parents=[measured, simulated],
        activity="compare.z_score",
        params={"discrepancy": discrepancy},
    )


__all__ = ["bias", "relative_difference", "z_score"]
