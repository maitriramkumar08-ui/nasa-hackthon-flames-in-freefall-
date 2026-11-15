"""P1: lineage graph over ledger entries."""

import dataclasses

import pytest

from pyrakit.provenance.ledger import Ledger, LedgerEntry
from pyrakit.provenance.lineage import LineageCycleError, LineageGraph
from pyrakit.provenance.status import Provenance, Quantity, Status


def prov(artifact_id: str, parents: tuple[str, ...] = ()) -> Provenance:
    return Provenance(
        artifact_id=artifact_id, parents=parents, activity="t@1", params={},
        source_ref=None, code_version="unknown", env_hash="unknown",
        created_utc="2026-01-01T00:00:00Z",
    )


def entry(artifact_id: str, status: Status, parents: tuple[str, ...] = ()) -> LedgerEntry:
    return LedgerEntry(prov=prov(artifact_id, parents), status=status, unit=None)


def test_ancestors_descendants_and_order(tmp_path) -> None:
    m = Quantity.measured(1.0, "kW", 0.1, "type_b", source_ref="r")
    d1 = Quantity.derive(2.0, "kW", 0.1, "assumed", parents=[m], activity="a")
    d2 = Quantity.derive(3.0, "kW", 0.1, "assumed", parents=[d1, m], activity="b")
    ledger = Ledger(tmp_path / "l.jsonl")
    for q in (m, d1, d2):
        ledger.append(LedgerEntry.from_quantity(q))
    g = LineageGraph.from_ledger(ledger)
    ids = [q.prov.artifact_id for q in (m, d1, d2)]
    assert g.ancestors(ids[2]) == {ids[0], ids[1]}
    assert g.ancestors(ids[0]) == set()
    assert g.descendants(ids[0]) == {ids[1], ids[2]}
    assert g.topological_order() == ids
    assert g.verify() == []
    with pytest.raises(KeyError):
        g.ancestors("unknown-id")


def test_missing_parent_is_flagged() -> None:
    g = LineageGraph([entry("c", Status.DERIVED, ("ghost",))])
    issues = g.verify()
    assert [i.kind for i in issues] == ["missing_parent"]
    assert issues[0].artifact_id == "c"


def test_status_downgrade_is_flagged() -> None:
    g = LineageGraph([
        entry("s", Status.SCENARIO),
        entry("c", Status.DERIVED, ("s",)),   # impossible under the propagation rule
    ])
    assert [i.kind for i in g.verify()] == ["status_downgrade"]


def test_equal_or_higher_status_is_fine() -> None:
    g = LineageGraph([
        entry("m", Status.MEASURED),
        entry("d", Status.DERIVED, ("m",)),
        entry("i", Status.INTERPRETATION, ("d",)),
    ])
    assert g.verify() == []


def test_cycle_is_detected() -> None:
    g = LineageGraph([entry("a", Status.DERIVED, ("b",)), entry("b", Status.DERIVED, ("a",))])
    with pytest.raises(LineageCycleError):
        g.topological_order()
    assert "cycle" in [i.kind for i in g.verify()]


def test_entries_are_not_mutated() -> None:
    e = entry("m", Status.MEASURED)
    LineageGraph([e]).verify()
    assert dataclasses.is_dataclass(e)
