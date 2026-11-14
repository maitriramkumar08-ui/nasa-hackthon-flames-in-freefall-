"""Small replay checks for immutable Quantity artifacts and ledgers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pyra.provenance.ledger import Ledger
from pyra.provenance.status import Quantity


@dataclass(frozen=True)
class ReplayResult:
    checked: int
    invalid_artifacts: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.invalid_artifacts


def replay_quantities(quantities: Iterable[Quantity]) -> ReplayResult:
    """Recompute artifact identities for quantities already loaded in memory."""
    values = tuple(quantities)
    invalid = tuple(q.prov.artifact_id for q in values if not q.verify())
    return ReplayResult(checked=len(values), invalid_artifacts=invalid)


def inspect_ledger(path: str) -> ReplayResult:
    """Parse a ledger and report how many provenance entries were readable."""
    entries = Ledger(path).entries()
    return ReplayResult(checked=len(entries), invalid_artifacts=())


__all__ = ["ReplayResult", "inspect_ledger", "replay_quantities"]
