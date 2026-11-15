# Using PYRA

Every example on this page is executed by the test suite (`tests/unit/test_docs.py`), so it matches
the code. The data below is **illustrative only**: the reference strings are placeholders, not real
datasets, and nothing here is a physical claim.

## Fire Playground: start by exploring

After installing PYRA and opening a VS Code terminal in the project folder, run:

```text
pyra playground
```

In Python code, the new short import is `import pyra_library as pk`. The earlier
`import pyra as pk` form remains supported too.

The window lets you change a fuel label, gravity, oxygen fraction, pressure, temperature, air
exchange, oxygen sink and duration. Choose a preset or edit the boxes and click **Run scenario**.
The drawing is a static flame illustration. The graph shows the oxygen-only, well-mixed zone
equation; only starting oxygen, air exchange, oxygen sink and duration affect that graph. Fuel,
gravity, pressure and temperature are displayed for scenario context but do not change the
calculation. This is a guided learning exercise, not a validated fire simulation or safety
prediction.

When you want to save or repeat an exercise in a Python file, use the same model directly:

```python
import pyra_library as pk

scenario = pk.FireScenario(
    fuel="PMMA (example fuel)",
    gravity_g=1.0,
    oxygen_fraction=0.21,
    pressure_kpa=101.3,
    temperature_k=293.15,
)
trace = pk.simulate_fire_scenario(scenario)
pk.show_simulation(tuple(zip(trace.time_s, trace.concentration, strict=True)))
```

Start with the GUI. Move to the code version when you want to save or repeat an experiment.

## Start here: what the numbers mean

The first example estimates heat-release rate from oxygen use. It multiplies three ideas:

1. Oxygen fraction went down from `0.21` to `0.20`. Those are fractions, so this means 21% in and
   20% out. The difference is `0.01`, or one percentage point.
2. Gas mass flow is `0.01 kg/s`: one hundredth of a kilogram of gas passes each second.
3. `13_100_000 J/kg` is the example's assumed energy released per kilogram of oxygen consumed.
   It is an input, not a universal constant chosen by PYRA.

The basic arithmetic is `0.01 × 0.01 × 13,100,000 = 1,310`. The result unit is watts because
`(kg/s) × (J/kg) = J/s`, and one joule per second is one watt. `hrr` is just a variable name for
the result. `hrr.value` is its numerical value, `hrr.unit` says what that value measures, and
`hrr.status` says it was calculated (`DERIVED`) rather than directly measured.

The source string in this example is deliberately fake and says `synthetic`. Replace it with the
real DOI, file hash and row location when using actual data. The example leaves uncertainty at
zero to keep the first calculation simple; real analysis should pass the measurement and
calibration uncertainties. `n=128` controls the number of uncertainty-propagation samples, while
`seed=0` makes those samples repeatable. These do not change the basic arithmetic above.

Python's `>>>` and `...` marks below are interactive-shell prompts. **Do not type those marks into
a `.py` file.** In a regular file, keep only the Python code, such as the complete example below.

Save this as `first.py` in your project folder and click **Run Python File** in VS Code:

```python
import pyra_library as pk

hrr = pk.heat_release(
    o2_in=0.21,
    o2_out=0.20,
    mass_flow=0.01,
    energy_per_kg_o2=13_100_000,
    source_ref="synthetic-example",
)

print(f"Estimated heat release: {hrr.value:.0f} {hrr.unit}")
print(f"Result kind: {hrr.status.name}")
```

If you are typing directly at Python's `>>>` prompt instead of running a file, first type the
import line. That line creates the short name `pk`; Python does not know `pk` until you create it:

```pycon
>>> import pyra_library as pk
>>> hrr = pk.heat_release(0.21, 0.20, 0.01, 13_100_000, source_ref="synthetic-example")
>>> round(hrr.value), hrr.unit, hrr.status.name
(1310, 'W', 'DERIVED')

```

If you see `NameError: name 'pk' is not defined`, run `import pyra_library as pk` first. In a `.py` file,
keep that import at the top of the file. When copying from examples that show `>>>` or `...`, those
symbols are shell prompts and should not be copied into the file.

The named arguments (`o2_in=...`) make each number's purpose easier to recognize. In actual
research, replace the sample values and source with verified measurements and document
uncertainties; this short example is for learning the API.

## Basic terms

| Term | Plain meaning in PYRA |
| --- | --- |
| Quantity | A value stored with a unit, uncertainty, status and source history. |
| Unit | What a number measures, such as `kPa`, `kg/s` or `W`. |
| Uncertainty | A stated range of doubt around a value; `unknown` means it has not been provided. |
| Source reference | Where a value came from, such as a DOI, file hash and row. |
| Provenance | The recorded source and calculation history for a result. |
| Status | Whether a value was measured, calculated, simulated, hypothetical or interpreted. |
| Scenario | A set of hypothetical inputs to explore; it is not an observation. |
| Simulation | A calculation that steps or solves a model; its result depends on model assumptions. |
| Calibration | Connecting instrument readings to physical values using a documented reference. |
| Validation | Checking model results against independent evidence within a stated range of conditions. |
| Evidence envelope | The conditions where a model has supporting validation evidence. |

PYRA uses `MEASURED`, `DERIVED`, `SIMULATED`, `SCENARIO` and `INTERPRETATION`. These labels are
not grades: they tell you what kind of support a result has. A simulation does not become a
measurement just because its output looks precise.

## 1. Your first small PYRA program

You can start with a normal Python file and use a short alias. The heat-release helper keeps the
source reference and returns a provenance-aware `Quantity` immediately:

```python
>>> import pyra_library as pk
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

These `simulate` commands make a fictional exponential curve for learning the plotting tools;
they do **not** model a fire. For a simple fire-related concentration exercise, use the separate
single-zone model:

```powershell
pyra zone
pyra zone --initial 0.21 --inlet 0.21 --exchange-rate 0.1 --source-rate 0.001 --duration 60
pyra zone --initial 0.21 --inlet 0.21 --exchange-rate 0.1 --source-rate 0.001 --duration 60 --window
```

`exchange-rate` and `source-rate` are in `1/s`; concentrations are fractions from 0 to 1. The
program prints a JSON trace or opens a plot window. This is a deliberately small, well-mixed
teaching model; it leaves out combustion, heat transfer, buoyancy, walls and spatial differences.
Treat it as a way to see how simple inputs affect a curve, not as a fire-safety prediction.

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

For a first comparison of two scalar values already in the same unit, use the quick helper:

```python
>>> quick = pk.compare_values(observed=100, predicted=104, unit="W", tolerance=5)
>>> quick.difference, quick.within_tolerance, quick.relative_difference_percent
(4, True, 4.0)

```

`difference` means predicted minus observed. `tolerance` is a limit you choose for the exercise.
This shortcut does not handle uncertainty, convert between units, align time series, or validate a
model. Use the evidence-aware `pyra.compare` tools for scientific comparisons.

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

## Learning path

1. **Explore:** open `pyra playground`, change one setting at a time and distinguish displayed
   scenario fields from values used in the simple concentration calculation.
2. **Write a first program:** use `import pyra_library as pk`, named arguments and `print` in a `.py` file.
3. **Understand evidence:** learn units, uncertainty, status and source references; then inspect a
   PSI raw-condition record without assuming its sensor values are calibrated.
4. **Analyze:** try `compare_values`, then advance to `pyra.compare`, matching and evidence reports
   with real, sourced records and documented uncertainty.

You can stop after any step and still use the beginner tools. The advanced analysis API remains
available without making the learning exercises depend on it.

## 12. Small education helpers

The education package stays deliberately small: a fictional trace, readable result labels, and a
check that lesson material either cites an evidence ID or labels itself as a concept sketch.

```python
>>> from pyra_edu import decay_activity, check_lesson, status_badge
>>> decay_activity(steps=3)["label"]
'FICTIONAL TEACHING EXAMPLE — NOT A FIRE MODEL'
>>> check_lesson(title="Exponential curves", concept_sketch=True).ok
True
>>> status_badge("SIMULATED")
'SIMULATED: Simulation output'

```
