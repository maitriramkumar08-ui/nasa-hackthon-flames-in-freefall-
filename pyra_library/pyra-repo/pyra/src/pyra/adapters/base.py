"""Common simulator adapter protocol and result object."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pyra.adapters.envelope import EnvelopeCheck, EnvelopeGatePolicy, check_envelope
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
    """Refuse a model-supported claim when the card records no validation evidence.

    This is only a presence check: it asks whether *any* evidence was recorded, not
    whether that evidence reaches the scenario being claimed. A card validated in an
    Earth-gravity bench test passes this gate for a microgravity scenario. For a claim
    about particular conditions, use :func:`require_in_envelope` instead.
    """
    if not card.validated:
        raise ClaimGateError(f"model {card.name!r} has no validation evidence")


def require_in_envelope(
    card: ModelCard, scenario: Scenario, *, policy: EnvelopeGatePolicy | None = None
) -> EnvelopeCheck:
    """Refuse a model-supported claim unless the scenario sits inside the envelope.

    Returns the :class:`~pyra.adapters.envelope.EnvelopeCheck` on success, so a caller
    can record which evidence entry supported the claim. Raises ``ClaimGateError``
    carrying the per-axis reasons when no recorded entry covers the scenario.

    Passing this gate means a human recorded evidence spanning these conditions. It is
    not a safety certification, and it does not verify the recorded limits.
    """
    check = check_envelope(card, scenario, policy=policy)
    if not check.inside:
        reasons = "; ".join(check.reasons())
        raise ClaimGateError(
            f"model {card.name!r} version {card.version!r} has no validation evidence "
            f"covering scenario {scenario.scenario_id!r}: {reasons}"
        )
    return check


__all__ = [
    "ClaimGateError",
    "SimulationResult",
    "SimulatorAdapter",
    "require_in_envelope",
    "require_validated",
]
