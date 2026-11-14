# Using PYRA

Every example on this page is executed by the test suite (`tests/unit/test_docs.py`), so it matches
the code. The data below is **illustrative only**: the reference strings are placeholders, not real
datasets, and nothing here is a physical claim.

## 1. Your first small PYRA program

You can start with a normal Python file and use a short alias. The heat-release helper keeps the
source reference and returns a provenance-aware `Quantity` immediately:

```python
>>> import pyra as pk
>>> hrr = pk.heat_release(
...     0.21, 0.20, 0.01, 13_100_000,
...     source_ref="doi:10.0000/example|synthetic", n=128, seed=0,
... )
>>> round(hrr.value), hrr.unit, hrr.status.name
(1310, 'W', 'DERIVED')

```

For a simple visual experiment, make a fictional trace with sensible defaults and open a small window:

```python
>>> trace = pk.simulate_decay(steps=5)
>>> trace[0], trace[-1][0]
((0.0, 1.0), 10.0)
>>> # In a desktop script, call: pk.show_simulation(trace, title="Decay example")
```

`simulate_decay` is deliberately a toy UI example; it is not a fire model and carries no scientific
claim. `show_simulation` uses the standard-library Tkinter window for local desktop programs.

For a transparent single-zone concentration exercise, use the exact constant-input solution:

```python
>>> zone = pk.simulate_zone(initial_concentration=0.21, inlet_concentration=0.21,
...                        exchange_rate_per_s=0.1, source_rate_per_s=0.001,
...                        duration_s=10, steps=3)
>>> zone.status, len(zone.time_s), round(zone.concentration[-1], 4)
('SIMULATED', 3, 0.2163)
```

This model evolves `dC/dt = k * (C_in - C) + S` and assumes one well-mixed zone, constant
ventilation and a constant source. It omits chemistry, heat transfer, buoyancy and spatial
gradients; it is a learning and sensitivity tool, not a validated fire simulation.

For small scripts, the shorter constructors keep the status choice visible:

```python
>>> pk.measured(21.0, "percent", source_ref="doi:10.0000/example|synthetic").status.name
'MEASURED'
>>> pk.scenario(0.5, "dimensionless").status.name
'SCENARIO'

```

The same toy trace is available from a terminal:

```text
pyra demo
pyra simulate --initial 2 --rate 0.5 --duration 10 --steps 100
pyra simulate --window
```

## 2. Running a callable model safely

Small Python models can run behind a `CallableAdapter`. The result is marked `SIMULATED`, and a
model-supported claim is refused until the model card contains validation evidence:

```python
>>> from pyra.adapters import CallableAdapter
>>> from pyra.schema import Conditions, ModelCard, Scenario
>>> card = ModelCard(name="toy", version="1", code_hash="local", licence="MIT", physics_summary="demo")
>>> adapter = CallableAdapter(card, lambda scenario: {"answer": 42})
>>> result = adapter.run(Scenario(scenario_id="demo", conditions=Conditions.model_validate({
...     "gravity_g": {"value": 1e-5, "unit": "dimensionless"},
...     "pressure": {"value": 101, "unit": "kPa"},
...     "o2_mole_fraction": {"value": 0.21, "unit": "dimensionless"},
...     "diluent": "nitrogen", "flow_mode": "forced", "fuel": {"material": "PMMA"},
...     "configuration": "concurrent", "length_scale": {"value": 0.02, "unit": "m"},
... })))
>>> result.status.name, result.outputs["answer"]
('SIMULATED', 42)

```

The callable adapter is a development and test boundary; it does not validate a model or make a
prediction outside a registered evidence envelope.

## 3. Benchmarking a model against supplied evidence

You can score a model on a set of measured cases when you provide the tolerance and source IDs
explicitly:

```python
>>> from pyra.compare import evaluate_model
>>> observations = [pk.measured(10, "kW", source_ref="doi:10.0000/example|case-1"),
...                 pk.measured(20, "kW", source_ref="doi:10.0000/example|case-2")]
>>> predictions = [pk.measured(10.2, "kW", source_ref="model|run-1"),
...                pk.measured(23, "kW", source_ref="model|run-2")]
>>> evaluation = evaluate_model(observations, predictions, tolerance=1.0, source_ids=["BASS-II", "SAFFIRE-I"])
>>> evaluation.score, evaluation.passed_cases, evaluation.status.name
(50.0, 1, 'INTERPRETATION')

```

This is a benchmark score for the supplied cases and tolerance. It is not a universal model reliability
rating, a fire-safety certification, or evidence that a model generalizes beyond the supplied
investigations.

## 4. Quantities carry a status

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

## 5. Status can only get weaker down a chain

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

## 6. Identity and tamper detection

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

## 7. Record everything in a ledger and check the lineage

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

## 8. Conditions are schema-validated

Metadata models use Pint-compatible unit strings and keep microgravity as a measured residual in
units of `g0` or a dimensionless multiple of it. The example uses a placeholder source and
fictional conditions:

```python
>>> from pyra.schema import Conditions, FuelSpec, Measure, Scenario
>>> c = Conditions(
...     gravity_g=Measure(value=1e-5, unit="dimensionless", u=1e-6, u_kind="type_a"),
...     pressure=Measure(value=101.3, unit="kPa", u=0.1, u_kind="type_b"),
...     o2_mole_fraction=Measure(value=0.21, unit="mole_fraction", u=0.001, u_kind="type_b"),
...     diluent="nitrogen", fuel=FuelSpec(material="PMMA"),
...     configuration="concurrent", length_scale=Measure(value=2, unit="cm"),
... )
>>> Scenario(scenario_id="synthetic-1", conditions=c).conditions.pressure.unit
'kPa'

```

## 9. S0 calorimetry keeps the energy equivalence explicit

The oxygen-consumption transform takes the energy per mass of oxygen as an input. This keeps the
choice of literature value visible in provenance; PYRA does not silently choose one:

```python
>>> from pyra.physics.calorimetry import hrr_oxygen_consumption
>>> src = "doi:10.0000/example|sha256:00|synthetic"
>>> m = lambda value, unit, u: Quantity.measured(value, unit, u, "type_b", source_ref=src)
>>> hrr = hrr_oxygen_consumption(m(0.21, "dimensionless", 1e-6), m(0.20, "dimensionless", 1e-6),
...     m(0.01, "kg/s", 1e-6), m(13_100_000, "J/kg", 100), n=256, seed=0)
>>> hrr.status.name
'DERIVED'
>>> round(hrr.value)
1310

```

## 10. Evidence files are manifest-driven

The ingestion layer records a URL or DOI, access date, and SHA-256 before a file is accepted. A
transport is injected for offline tests; no PSI file format is guessed by the generic reader:

```python
>>> import hashlib
>>> from datetime import date
>>> from pyra.io import ManifestEntry, fetch
>>> payload = b"time,value\\n0,1\\n"
>>> entry = ManifestEntry(
...     investigation="synthetic", file_pattern="trace.csv", version="1",
...     sha256=hashlib.sha256(payload).hexdigest(), access_date=date(2026, 11, 15),
...     url="https://example.invalid/trace.csv",
... )
>>> path = fetch(entry, __import__("pathlib").Path(__import__("tempfile").mkdtemp()) / "trace.csv",
...              transport=lambda _: payload)
>>> path.read_bytes() == payload
True

```

## 11. Where to go next

* `docs/api.md`: every public name in `pyra.provenance` with its signature.
* `examples/quickstart.py`: this page as a runnable script.
* `docs/architecture.md`: what PYRA will and will not claim.
