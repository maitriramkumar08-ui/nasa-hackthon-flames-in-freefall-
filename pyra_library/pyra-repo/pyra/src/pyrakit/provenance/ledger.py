"""Append-only JSON Lines ledger (architecture sections 5 and 11).

One canonical JSON object per line. The file is only ever opened in append mode and each write is
flushed and fsynced. Re-appending an identical artifact is reported (returns False), a different
record under an existing id raises, and a corrupt line raises with its line number.

The ledger records provenance, not data: parameters are stored in canonical form, so floats keep
12 significant digits (docs/adr/0001). Lookups scan the file; fine for v0, index later if needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyrakit.provenance.hashing import canonical_bytes
from pyrakit.provenance.status import Provenance, Quantity, Status


class LedgerCorruptError(ValueError):
    """A ledger line could not be parsed."""


class LedgerConflictError(ValueError):
    """A different record already exists under this artifact id."""


@dataclass(frozen=True)
class LedgerEntry:
    """One ledger line: provenance, status name and unit of an artifact."""

    prov: Provenance
    status: Status
    unit: str | None = None

    @classmethod
    def from_quantity(cls, q: Quantity) -> LedgerEntry:
        """Entry describing ``q`` (its provenance, status and unit)."""
        return cls(prov=q.prov, status=q.status, unit=q.unit)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict; the status is stored by name."""
        d = self.prov.to_dict()
        d["status"] = self.status.name
        d["unit"] = self.unit
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LedgerEntry:
        """Inverse of ``to_dict``; raises KeyError or ValueError on malformed input."""
        unit = d["unit"]
        return cls(
            prov=Provenance.from_dict(d),
            status=Status[d["status"]],
            unit=None if unit is None else str(unit),
        )

    def identity_bytes(self) -> bytes:
        """Fields that must match for two entries to be 'the same record' (no timestamps)."""
        d = self.to_dict()
        for volatile in ("created_utc", "code_version", "env_hash"):
            d.pop(volatile)
        return canonical_bytes(d)


class Ledger:
    """Append-only JSON Lines file of artifact records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def entries(self) -> list[LedgerEntry]:
        """All entries in append order; a bad line raises LedgerCorruptError with its number."""
        if not self.path.exists():
            return []
        out: list[LedgerEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                try:
                    out.append(LedgerEntry.from_dict(json.loads(line)))
                except (ValueError, KeyError, TypeError) as exc:
                    raise LedgerCorruptError(f"{self.path}:{lineno}: {exc!r}") from exc
        return out

    def get(self, artifact_id: str) -> LedgerEntry | None:
        """The entry with this artifact id, or None."""
        for entry in self.entries():
            if entry.prov.artifact_id == artifact_id:
                return entry
        return None

    def append(self, entry: LedgerEntry) -> bool:
        """Append ``entry``. Returns False (and writes nothing) if an identical record exists."""
        existing = self.get(entry.prov.artifact_id)
        if existing is not None:
            if existing.identity_bytes() == entry.identity_bytes():
                return False
            raise LedgerConflictError(
                f"artifact {entry.prov.artifact_id} already recorded with different content"
            )
        line = canonical_bytes(entry.to_dict()) + b"\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return True
