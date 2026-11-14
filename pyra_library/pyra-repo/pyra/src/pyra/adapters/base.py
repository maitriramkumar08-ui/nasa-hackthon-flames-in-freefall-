"""Common simulator adapter protocol and result object."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pyra.provenance import Status
from pyra.schema import ModelCard, Scenario


@dataclass(frozen=True)
class SimulationResult:
    """A simulator output bundle with an explicit SIMULATED status."""

    scenario_id: str
    model_card_id: str
    status: Status
    outputs: Mapping[str, Any]


class SimulatorAdapter(Protocol):
    card: ModelCard

    def run(self, scenario: Scenario) -> SimulationResult: ...

    def at(self, conditions: Any, base: Scenario) -> Scenario: ...


class ClaimGateError(ValueError):
    """Raised when a model-supported claim lacks validation evidence."""


def require_validated(card: ModelCard) -> None:
    """Refuse a model-supported claim when its envelope is empty."""
    if not card.validated:
        raise ClaimGateError(f"model {card.name!r} has no validation evidence")


__all__ = ["ClaimGateError", "SimulationResult", "SimulatorAdapter", "require_validated"]
