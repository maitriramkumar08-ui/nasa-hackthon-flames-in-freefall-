"""A transparent, well-mixed scalar zone model for learning and sensitivity studies.

This reduced-order model evolves one concentration under constant ventilation and a
constant source. It omits heat release, buoyancy, chemistry, stratification and wall effects;
it is not a validated fire model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneTrace:
    """Time series returned by :func:`simulate_zone` (concentration is dimensionless)."""

    time_s: tuple[float, ...]
    concentration: tuple[float, ...]
    status: str = "SIMULATED"
    assumptions: tuple[str, ...] = (
        "well-mixed single zone",
        "constant ventilation rate",
        "constant concentration source rate",
        "no chemistry, heat transfer, or spatial gradients",
    )


def simulate_zone(
    *,
    initial_concentration: float = 0.21,
    inlet_concentration: float = 0.21,
    exchange_rate_per_s: float = 0.0,
    source_rate_per_s: float = 0.0,
    duration_s: float = 60.0,
    steps: int = 121,
) -> ZoneTrace:
    """Simulate a single well-mixed concentration with constant inputs.

    The integrated balance is ``dC/dt = k * (C_in - C) + S``, where ``k`` is
    the air-exchange rate [1/s], and ``S`` is a concentration source rate [1/s].
    The exact constant-coefficient solution is used at evenly spaced times. This
    equation is a teaching abstraction; choose inputs and interpret outputs with
    domain expertise.
    """
    values = (
        initial_concentration,
        inlet_concentration,
        exchange_rate_per_s,
        source_rate_per_s,
        duration_s,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("zone model inputs must be finite")
    if not 0 <= initial_concentration <= 1 or not 0 <= inlet_concentration <= 1:
        raise ValueError("concentrations must be between 0 and 1")
    if exchange_rate_per_s < 0 or duration_s <= 0 or steps < 2:
        raise ValueError("exchange rate must be non-negative, duration positive, steps >= 2")

    times = tuple(duration_s * i / (steps - 1) for i in range(steps))
    if exchange_rate_per_s == 0:
        concentrations = tuple(initial_concentration + source_rate_per_s * t for t in times)
    else:
        equilibrium = inlet_concentration + source_rate_per_s / exchange_rate_per_s
        concentrations = tuple(
            equilibrium + (initial_concentration - equilibrium) * math.exp(-exchange_rate_per_s * t)
            for t in times
        )
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in concentrations):
        raise ValueError("simulated concentration left the valid [0, 1] range")
    return ZoneTrace(time_s=times, concentration=concentrations)


__all__ = ["ZoneTrace", "simulate_zone"]
