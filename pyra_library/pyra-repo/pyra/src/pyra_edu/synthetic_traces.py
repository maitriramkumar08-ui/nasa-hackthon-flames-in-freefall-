"""Fictional traces for classroom plotting and coding exercises."""

from pyra_edu.concept_models import decay_activity


def make_decay_trace(
    *, duration_s: float = 10.0, steps: int = 21
) -> tuple[tuple[float, float], ...]:
    """Return only the sample points from the clearly labelled decay activity."""
    trace = decay_activity(duration_s=duration_s, steps=steps)["trace"]
    if not isinstance(trace, tuple):
        raise TypeError("internal teaching trace must be a tuple")
    return trace


__all__ = ["make_decay_trace"]
