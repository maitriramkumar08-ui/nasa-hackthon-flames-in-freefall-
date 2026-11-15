"""Adapter for a pure Python callable used in tests and small models."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pyrakit.adapters.base import SimulationResult
from pyrakit.provenance import Status
from pyrakit.schema import Conditions, ModelCard, Scenario


class CallableAdapter:
    """Run a user-supplied function without importing any simulator package."""

    def __init__(self, card: ModelCard, function: Callable[[Scenario], Mapping[str, Any]]) -> None:
        self.card = card
        self._function = function

    def run(self, scenario: Scenario) -> SimulationResult:
        return SimulationResult(
            scenario_id=scenario.scenario_id,
            model_card_id=self.card.name + ":" + self.card.version,
            status=Status.SIMULATED,
            outputs=dict(self._function(scenario)),
        )

    def at(self, conditions: Conditions, base: Scenario) -> Scenario:
        """Create a hindcast scenario with the supplied experimental conditions."""
        return base.model_copy(update={"conditions": conditions, "purpose": "hindcast"})


__all__ = ["CallableAdapter"]
