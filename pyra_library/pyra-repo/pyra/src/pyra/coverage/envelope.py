"""Evidence coverage summaries for one scenario."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pyra.matching import MatchPolicy, MismatchVector, match
from pyra.schema import ExperimentRecord, Scenario

CoverageVerdict = Literal["covered", "partial", "none"]


@dataclass(frozen=True)
class CoverageReport:
    scenario_id: str
    verdict: CoverageVerdict
    matches: tuple[MismatchVector, ...]
    nearest_distances: tuple[float, ...]
    independent_sources: int
    gaps: tuple[str, ...]


def coverage(
    scenario: Scenario,
    experiments: list[ExperimentRecord],
    policy: MatchPolicy,
    *,
    k: int = 3,
) -> CoverageReport:
    """Summarize evidence near a scenario; empty catalogues return ``none``."""
    if k < 1:
        raise ValueError("k must be positive")
    vectors = tuple(match(scenario, experiment, policy) for experiment in experiments)
    usable = tuple(vector for vector in vectors if vector.tier != "NONE")
    if not usable:
        return CoverageReport(
            scenario.scenario_id,
            "none",
            vectors,
            (),
            0,
            ("no matching experiment",),
        )
    nearest = tuple(sorted(vector.aggregate for vector in usable)[:k])
    sources = {
        experiment.source.source_id
        for experiment, vector in zip(experiments, vectors, strict=False)
        if vector.tier != "NONE"
    }
    if any(vector.tier == "EXACT" for vector in usable):
        verdict: CoverageVerdict = "covered"
        gaps: tuple[str, ...] = ()
    else:
        verdict = "partial"
        gaps = ("no exact match",)
    return CoverageReport(scenario.scenario_id, verdict, vectors, nearest, len(sources), gaps)


__all__ = ["CoverageReport", "coverage"]
