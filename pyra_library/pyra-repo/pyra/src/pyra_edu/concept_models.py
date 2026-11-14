"""Lightweight activities that demonstrate concepts without predicting fire behavior."""

from __future__ import annotations

from pyra.service.simple import simulate_decay


def decay_activity(*, duration_s: float = 10.0, steps: int = 21) -> dict[str, object]:
    """Return a fictional exponential trace and a clear teaching label."""
    return {
        "title": "Exponential decay (concept sketch)",
        "label": "FICTIONAL TEACHING EXAMPLE — NOT A FIRE MODEL",
        "trace": simulate_decay(duration=duration_s, steps=steps),
    }


__all__ = ["decay_activity"]
