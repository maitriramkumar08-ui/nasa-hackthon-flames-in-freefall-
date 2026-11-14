"""Quickstart: status-typed quantities, a ledger and a lineage check. Data is illustrative only."""

import tempfile
from pathlib import Path

from pyra import Ledger, LedgerEntry, LineageGraph, Quantity, Status

pressure = Quantity.measured(
    101.3, "kPa", 0.5, "type_b",
    source_ref="doi:10.0000/example|sha256:00|row 12",   # placeholder, not a real dataset
)
target = Quantity.scenario(50.0, "kPa", None, "unknown", activity="user_input")
ratio = Quantity.derive(
    target.value / pressure.value, "dimensionless", None, "unknown",
    parents=[pressure, target], activity="pressure_ratio@1",
)

ledger = Ledger(Path(tempfile.mkdtemp()) / "ledger.jsonl")
for q in (pressure, target, ratio):
    ledger.append(LedgerEntry.from_quantity(q))

graph = LineageGraph.from_ledger(ledger)
print("ratio status:", ratio.status.name)                    # SCENARIO: it touches a scenario
print("lineage problems:", graph.verify())                   # []
print("ancestors of ratio:", len(graph.ancestors(ratio.prov.artifact_id)))
assert ratio.status is Status.SCENARIO
