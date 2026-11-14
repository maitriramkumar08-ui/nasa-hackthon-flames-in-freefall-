"""Small, text-only labels for results shown in educational activities."""

from __future__ import annotations

from typing import Literal

StatusName = Literal["MEASURED", "DERIVED", "SIMULATED", "SCENARIO", "INTERPRETATION"]

_LABELS: dict[StatusName, str] = {
    "MEASURED": "Measured evidence",
    "DERIVED": "Calculated from evidence",
    "SIMULATED": "Simulation output",
    "SCENARIO": "Hypothetical scenario",
    "INTERPRETATION": "Interpretation",
}


def status_badge(status: StatusName) -> str:
    """Return a plain-language label while preserving the formal status name."""
    return f"{status}: {_LABELS[status]}"


__all__ = ["StatusName", "status_badge"]
