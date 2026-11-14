"""P1: append-only JSONL ledger."""

import json

import pytest

from pyra.provenance.ledger import (
    Ledger,
    LedgerConflictError,
    LedgerCorruptError,
    LedgerEntry,
)
from pyra.provenance.status import Quantity, Status


def make_chain() -> tuple[Quantity, Quantity]:
    m = Quantity.measured(1.0, "kW", 0.1, "type_b", source_ref="ref-1")
    d = Quantity.derive(
        2.0, "kW", 0.2, "assumed", parents=[m], activity="double@1", params={"k": 2}
    )
    return m, d


def test_append_and_read_back_in_order(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    m, d = make_chain()
    assert ledger.append(LedgerEntry.from_quantity(m)) is True
    assert ledger.append(LedgerEntry.from_quantity(d)) is True
    entries = ledger.entries()
    assert [e.prov.artifact_id for e in entries] == [m.prov.artifact_id, d.prov.artifact_id]
    assert entries[0].status is Status.MEASURED and entries[1].status is Status.DERIVED
    assert entries[1].unit == "kW"
    assert entries[1].prov.parents == (m.prov.artifact_id,)
    assert entries[1].prov.params == {"k": 2}
    assert ledger.get(d.prov.artifact_id) == entries[1]
    assert ledger.get("nope") is None


def test_every_line_is_one_json_object(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    for q in make_chain():
        ledger.append(LedgerEntry.from_quantity(q))
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert all(isinstance(json.loads(line), dict) for line in lines)


def test_appending_never_rewrites_existing_bytes(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    m, d = make_chain()
    ledger.append(LedgerEntry.from_quantity(m))
    before = path.read_bytes()
    ledger.append(LedgerEntry.from_quantity(d))
    assert path.read_bytes().startswith(before)


def test_reappending_the_same_artifact_is_reported_and_not_duplicated(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    m, _ = make_chain()
    assert ledger.append(LedgerEntry.from_quantity(m)) is True
    assert ledger.append(LedgerEntry.from_quantity(m)) is False
    assert len(ledger.entries()) == 1


def test_conflicting_entry_for_an_existing_id_raises(tmp_path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    m, _ = make_chain()
    entry = LedgerEntry.from_quantity(m)
    ledger.append(entry)
    forged = LedgerEntry(prov=entry.prov, status=Status.INTERPRETATION, unit=entry.unit)
    with pytest.raises(LedgerConflictError):
        ledger.append(forged)


def test_corrupt_line_is_refused_loudly_with_line_number(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    m, _ = make_chain()
    ledger.append(LedgerEntry.from_quantity(m))
    with path.open("ab") as fh:
        fh.write(b'{"artifact_id": "truncated\n')
    with pytest.raises(LedgerCorruptError, match=":2"):
        ledger.entries()


def test_missing_file_is_an_empty_ledger(tmp_path) -> None:
    assert Ledger(tmp_path / "absent" / "ledger.jsonl").entries() == []
