"""Simple observation operators for one-dimensional traces."""

from __future__ import annotations

import math
from collections.abc import Sequence


def first_order_lag(signal: Sequence[float], *, dt: float, tau: float) -> tuple[float, ...]:
    """Apply the exact piecewise-constant first-order sensor lag recurrence."""
    if dt <= 0 or tau <= 0:
        raise ValueError("dt and tau must be positive")
    if not signal:
        return ()
    alpha = 1.0 - math.exp(-dt / tau)
    output = [float(signal[0])]
    for value in signal[1:]:
        output.append(output[-1] + alpha * (float(value) - output[-1]))
    return tuple(output)


__all__ = ["first_order_lag"]
