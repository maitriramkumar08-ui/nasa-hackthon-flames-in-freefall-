"""Pareto ranking for mismatch vectors."""

from __future__ import annotations

from collections.abc import Sequence

from pyrakit.matching.match import MismatchVector


def pareto_front(vectors: Sequence[MismatchVector]) -> list[int]:
    """Return non-dominated vector indexes, preserving input order."""
    front: list[int] = []
    for index, candidate in enumerate(vectors):
        if candidate.tier == "NONE":
            continue
        dominated = False
        for other_index, other in enumerate(vectors):
            if index == other_index or other.tier == "NONE":
                continue
            keys = set(candidate.dimensions) | set(other.dimensions)
            no_worse = all(
                other.dimensions.get(key, float("inf"))
                <= candidate.dimensions.get(key, float("inf"))
                for key in keys
            )
            strictly_better = any(
                other.dimensions.get(key, float("inf"))
                < candidate.dimensions.get(key, float("inf"))
                for key in keys
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(index)
    return front


__all__ = ["pareto_front"]
