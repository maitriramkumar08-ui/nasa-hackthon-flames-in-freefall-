"""Replay and ledger inspection contracts."""

import json

from pyra import Ledger, LedgerEntry, Quantity
from pyra.cli import main
from pyra.provenance import inspect_ledger


def test_replay_inspects_a_ledger(tmp_path, capsys) -> None:
    quantity = Quantity.measured(
        1.0, "kW", 0.1, "type_b", source_ref="doi:10.0000/example|synthetic"
    )
    path = tmp_path / "ledger.jsonl"
    Ledger(path).append(LedgerEntry.from_quantity(quantity))
    assert inspect_ledger(path).checked == 1
    main(["replay", str(path)])
    assert json.loads(capsys.readouterr().out) == {"checked": 1, "ok": True}
