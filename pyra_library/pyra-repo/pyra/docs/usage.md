# Using PYRA

Every example on this page is executed by the test suite (`tests/unit/test_docs.py`), so it matches
the code. The data below is **illustrative only**: the reference strings are placeholders, not real
datasets, and nothing here is a physical claim.

## 1. Quantities carry a status

```python
>>> from pyra import Quantity, Status
>>> p = Quantity.measured(
...     101.3, "kPa", 0.5, "type_b",
...     source_ref="doi:10.0000/example|sha256:00|row 12",   # placeholder source
...     created_utc="2026-11-15T00:00:00Z",
... )
>>> p.status.name, p.unit, p.u
('MEASURED', 'kPa', 0.5)
>>> len(p.prov.artifact_id)      # SHA-256 hex digest
64

```

`Quantity.measured` insists on a source reference. A quantity with no known uncertainty must say so
explicitly (`u=None`, `u_kind="unknown"`):

```python
>>> Quantity.measured(1.0, "kPa", None, "unknown", source_ref="")
Traceback (most recent call last):
    ...
ValueError: MEASURED requires a source_ref (DOI/URL, file hash, location)

```

## 2. Status can only get weaker down a chain

`Quantity.derive` computes the status of a result as the maximum over its inputs (the order is
`MEASURED < DERIVED < SIMULATED < SCENARIO < INTERPRETATION`). Mixing in a hypothetical scenario
makes the whole result a scenario; it can never be reported as measured:

```python
>>> target = Quantity.scenario(50.0, "kPa", None, "unknown", activity="user_input")
>>> ratio = Quantity.derive(
...     target.value / p.value, "dimensionless", None, "unknown",
...     parents=[p, target], activity="pressure_ratio@1",
... )
>>> ratio.status.name
'SCENARIO'
>>> ratio.status > Status.MEASURED
True

```

A method can also refuse inputs that are too weak for it:

```python
>>> Quantity.derive(
...     1.0, "kW", None, "unknown", parents=[target], activity="heat_release@1",
...     max_input_status=Status.DERIVED,
... )
Traceback (most recent call last):
    ...
pyra.provenance.status.StatusInputError: heat_release@1: input status SCENARIO exceeds the maximum allowed DERIVED

```

## 3. Identity and tamper detection

An artifact id hashes the content, the parents, the activity, its parameters and the source
reference. It does not include timestamps or environment details, so it is reproducible:

```python
>>> import dataclasses
>>> p.verify()
True
>>> dataclasses.replace(p, value=99.0).verify()
False

```

The hashing helper is public too. Dictionary order never matters:

```python
>>> from pyra import sha256_hex
>>> sha256_hex({"a": 1, "b": 2}) == sha256_hex({"b": 2, "a": 1})
True

```

## 4. Record everything in a ledger and check the lineage

```python
>>> import pathlib, tempfile
>>> from pyra import Ledger, LedgerEntry, LineageGraph
>>> ledger = Ledger(pathlib.Path(tempfile.mkdtemp()) / "ledger.jsonl")
>>> [ledger.append(LedgerEntry.from_quantity(q)) for q in (p, target, ratio)]
[True, True, True]
>>> ledger.append(LedgerEntry.from_quantity(p))      # same artifact again: reported, not duplicated
False
>>> graph = LineageGraph.from_ledger(ledger)
>>> graph.verify()                                    # empty list means no problems found
[]
>>> sorted(graph.ancestors(ratio.prov.artifact_id)) == sorted([p.prov.artifact_id, target.prov.artifact_id])
True

```

The ledger is append-only JSON Lines, one record per line, so it can be inspected with any text
tool. A corrupt line raises `LedgerCorruptError` with the file and line number.

## 5. Where to go next

* `docs/api.md`: every public name in `pyra.provenance` with its signature.
* `examples/quickstart.py`: this page as a runnable script.
* `docs/architecture.md`: what PYRA will and will not claim.
