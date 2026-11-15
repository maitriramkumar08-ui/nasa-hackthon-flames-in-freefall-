"""Small, approachable helpers for notebooks and first PYRA programs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from pyrakit.physics.calorimetry import hrr_oxygen_consumption
from pyrakit.provenance import Quantity
from pyrakit.units import quantity


@dataclass(frozen=True)
class QuickComparison:
    """Plain-language scalar comparison for a first comparison exercise."""

    observed: float
    predicted: float
    difference: float
    unit: str
    tolerance: float
    within_tolerance: bool
    relative_difference_percent: float | None
    status: str = "INTERPRETATION"


def compare_values(
    observed: float, predicted: float, *, unit: str, tolerance: float
) -> QuickComparison:
    """Compare two values already expressed in the same unit.

    This is an orientation helper, not the full evidence-aware comparison API. It does
    not assess uncertainty, align time series or validate a simulator.
    """
    if not all(math.isfinite(value) for value in (observed, predicted, tolerance)):
        raise ValueError("observed, predicted, and tolerance must be finite numbers")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    quantity(1.0, unit)  # Validate that the unit is recognized.
    difference = predicted - observed
    relative = None if observed == 0 else 100.0 * difference / abs(observed)
    return QuickComparison(
        observed=observed,
        predicted=predicted,
        difference=difference,
        unit=unit,
        tolerance=tolerance,
        within_tolerance=abs(difference) <= tolerance,
        relative_difference_percent=relative,
    )


def measured(
    value: float,
    unit: str,
    *,
    source_ref: str,
    uncertainty: float | None = None,
    u_kind: str = "unknown",
) -> Quantity:
    """Create one traceable measured quantity with a short signature."""
    return Quantity.measured(value, unit, uncertainty, u_kind, source_ref=source_ref)


def scenario(
    value: float,
    unit: str,
    *,
    uncertainty: float | None = None,
    u_kind: str = "unknown",
    activity: str = "user_input",
) -> Quantity:
    """Create one explicitly hypothetical scenario quantity."""
    return Quantity.scenario(value, unit, uncertainty, u_kind, activity=activity)


def heat_release(
    o2_in: float,
    o2_out: float,
    mass_flow: float,
    energy_per_kg_o2: float,
    *,
    source_ref: str,
    o2_uncertainty: float = 0.0,
    mass_flow_uncertainty: float = 0.0,
    energy_uncertainty: float = 0.0,
    n: int = 1024,
    seed: int = 0,
) -> Quantity:
    """Compute a simple oxygen-consumption HRR from SI-valued numbers."""

    def measured(value: float, unit: str, uncertainty: float) -> Quantity:
        return Quantity.measured(value, unit, uncertainty, "type_b", source_ref=source_ref)

    return hrr_oxygen_consumption(
        measured(o2_in, "dimensionless", o2_uncertainty),
        measured(o2_out, "dimensionless", o2_uncertainty),
        measured(mass_flow, "kg/s", mass_flow_uncertainty),
        measured(energy_per_kg_o2, "J/kg", energy_uncertainty),
        n=n,
        seed=seed,
    )


def simulate_decay(
    initial: float = 1.0, rate: float = 0.5, duration: float = 10.0, *, steps: int = 100
) -> tuple[tuple[float, float], ...]:
    """Return a fictional exponential trace for learning and UI experiments.

    With no arguments this makes a ready-to-plot example trace. It is a mathematical
    demonstration, not a fire model or a calibrated physical result.
    """
    if not all(math.isfinite(value) for value in (initial, rate, duration)):
        raise ValueError("initial, rate, and duration must be finite numbers")
    if initial < 0 or rate < 0 or duration <= 0 or steps < 2:
        raise ValueError("initial/rate must be non-negative, duration positive, steps >= 2")
    return tuple(
        (
            duration * index / (steps - 1),
            initial * math.exp(-rate * duration * index / (steps - 1)),
        )
        for index in range(steps)
    )


def show_simulation(
    points: Sequence[tuple[float, float]], *, title: str = "PYRA simulation"
) -> None:
    """Open a tiny Tkinter line plot for a sequence of ``(time, value)`` points."""
    if not points:
        raise ValueError("points must not be empty")
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        raise ValueError("simulation points must contain only finite numbers")
    import tkinter as tk

    width, height, margin = 760, 420, 45
    root = tk.Tk()
    root.title(title)
    canvas = tk.Canvas(root, width=width, height=height, background="white")
    canvas.pack()
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    x_min, x_max = min(xs), max(xs) or 1.0
    y_min, y_max = min(ys), max(ys)
    if y_max == y_min:
        y_max = y_min + 1.0

    def project(x: float, y: float) -> tuple[float, float]:
        px = margin + (x - x_min) / (x_max - x_min) * (width - 2 * margin)
        py = height - margin - (y - y_min) / (y_max - y_min) * (height - 2 * margin)
        return px, py

    canvas.create_line(margin, margin, margin, height - margin, fill="#444")
    canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#444")
    projected = [project(x, y) for x, y in points]
    for start, end in zip(projected, projected[1:], strict=False):
        canvas.create_line(*start, *end, fill="#1464f4", width=2)
    root.mainloop()


__all__ = [
    "QuickComparison",
    "compare_values",
    "heat_release",
    "measured",
    "scenario",
    "show_simulation",
    "simulate_decay",
]
