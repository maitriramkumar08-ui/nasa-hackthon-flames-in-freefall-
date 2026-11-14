"""Explicit, versioned matching policy."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MatchPolicy:
    """Tolerances and weights used by the mismatch engine.

    The defaults are a documented starting policy, not a claim of physical
    equivalence. Projects should version and review changes to this object.
    """

    version: str = "provisional-1"
    tolerances: dict[str, float] = field(default_factory=lambda: {
        "gravity_g": 0.25, "pressure": 0.02, "o2_mole_fraction": 0.01,
        "flow_velocity": 0.05, "length_scale": 0.01,
    })
    weights: dict[str, float] = field(default_factory=lambda: {
        "gravity_g": 1.0, "pressure": 1.0, "o2_mole_fraction": 1.0,
        "flow_velocity": 1.0, "length_scale": 1.0,
    })
    d_max: float = 3.0
    aggregate_max: float = 3.0
    g_floor: float = 1e-4

    def __post_init__(self) -> None:
        if self.g_floor <= 0 or self.d_max <= 0 or self.aggregate_max <= 0:
            raise ValueError("matching floors and thresholds must be positive")
        if set(self.tolerances) != set(self.weights):
            raise ValueError("tolerances and weights must define the same dimensions")
        if any(value <= 0 for value in self.tolerances.values()):
            raise ValueError("matching tolerances must be positive")
        if any(value < 0 for value in self.weights.values()) or not any(self.weights.values()):
            raise ValueError("weights must be non-negative and not all zero")


__all__ = ["MatchPolicy"]
