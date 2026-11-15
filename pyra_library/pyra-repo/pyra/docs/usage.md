# Using PYRA

Every example on this page is executed by the test suite (`tests/unit/test_docs.py`), so it matches
the code. The data below is **illustrative only**: the reference strings are placeholders, not real
datasets, and nothing here is a physical claim.

## Fire Playground: start by exploring

After installing PYRA and opening a VS Code terminal in the project folder, run:

```text
pyra playground
```

In Python code the import is `import pyrakit as pk`. One name covers the whole toolkit:
the short beginner helpers and the full API are the same import.

The library used to be called `pyra`, and was split across `pyra` and `pyra_library`.
Both old names still work, so older code and notebooks keep running, but everything
below uses `pyrakit`. If you meet `import pyra as pk` in an older example, it is the
same library under its previous name.

The window lets you change a fuel label, gravity, oxygen fraction, pressure, temperature, air
exchange, oxygen sink and duration. Choose a preset or edit the boxes and click **Run scenario**.
The scenario fields scroll; the Run and Cancel buttons stay pinned below them.

### What exactly is that graph?

It is **oxygen mole fraction on the vertical axis against time in seconds on the horizontal
axis**. Nothing else. It is not flame height, not temperature, not spread rate, not heat.

Picture one sealed box of air with a fire inside, and assume the air in it is stirred so
well that every point has the same oxygen fraction. That assumption is what "well-mixed
single zone" means, and it is the whole model. Two things then compete:

- **Ventilation refills oxygen.** Fresh air enters at rate `k` (the *air exchange rate*,
  per second) carrying oxygen fraction `C_in`.
- **The fire consumes oxygen.** It removes oxygen at a constant rate `S` (the *oxygen sink
  rate*, per second).

Written out, the line being plotted is the exact solution of

```text
dC/dt = k * (C_in - C) - S
```

The useful thing to notice is that the curve does not fall forever. It flattens towards a
balance point where refill and consumption cancel:

```text
C_equilibrium = C_in - S / k
```

With the defaults (`C_in = 0.21`, `S = 0.001/s`, `k = 0.02/s`) that is
`0.21 - 0.001/0.02 = 0.16`. The curve starts at 0.21 and bends towards 0.16. It approaches
it with a time constant of `1/k = 50 s`, so after the default 60 seconds it has travelled
most but not all of the way, reaching about **0.175**:

```python
>>> import pyrakit as pk
>>> run = pk.run_fire_test()
>>> round(run.trace.concentration[0], 4), round(run.trace.concentration[-1], 4)
(0.21, 0.1751)

```

### What each knob does to the curve

Change one at a time and watch the balance point move:

| Change | Equilibrium becomes | Value at 60 s |
| --- | --- | --- |
| defaults | 0.160 | 0.1751 |
| oxygen sink doubled to 0.002/s | 0.110 | 0.1401 |
| oxygen sink halved to 0.0005/s | 0.185 | 0.1925 |
| air exchange set to 0 (no ventilation) | none; falls forever | 0.1500 |

That last row is the interesting one. With no ventilation there is no balance point, so the
line becomes straight and simply drops until the oxygen runs out. In a real spacecraft that
is the dangerous direction, and it is why ventilation appears in fire-safety arguments at
all.

```python
>>> sealed = pk.run_fire_test(air_exchange_per_s=0.0)
>>> round(sealed.trace.concentration[-1], 4)
0.15

```

### What the graph is not

Fuel, gravity, pressure and temperature are recorded on the scenario and shown in the
window, but **they do not appear anywhere in the equation above**, so changing them does
not move the line. That is deliberate and it is the honest state of affairs: PYRA has no
validated flame solver, so it does not pretend that gravity changes this curve.

The model also states its own limits, which you can read directly:

```python
>>> for note in run.trace.assumptions:
...     print(note)
well-mixed single zone
constant ventilation rate
constant concentration source rate
no chemistry, heat transfer, or spatial gradients

```

So: use it to build intuition about ventilation versus consumption, which is a real and
useful idea. Do not use it to predict a fire. A real flame solver is connected through an
adapter instead, and section 10.1 covers that.

When you want to save or repeat an exercise in a Python file, use the same model directly:

```python
import pyrakit as pk

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

For the same built-in learning model in one function call:

```python
import pyrakit as pk

run = pk.run_fire_test(
    fuel="PMMA",
    gravity_g=0.0,
    oxygen_fraction=0.21,
    pressure_kpa=101.3,
    temperature_k=293.15,
)
print(run.summary())
run.show()
```

`run_fire_test` runs PYRA's built-in oxygen-balance learning model only. It does not connect to
an external or friend-provided fire engine; that requires the engine's interface and validation
details.

For a complete run that prints a summary, saves a JSON record and performs a quick comparison,
run this copyable example from the PYRA repository folder:

```text
python examples/complete_fire_test.py
```

It writes `fire_test_result.json` in the current directory. To open the result graph, uncomment
`run.show()` in the example. The JSON preserves the inputs and model assumptions with the output.

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
import pyrakit as pk

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
>>> import pyrakit as pk
>>> hrr = pk.heat_release(0.21, 0.20, 0.01, 13_100_000, source_ref="synthetic-example")
>>> round(hrr.value), hrr.unit, hrr.status.name
(1310, 'W', 'DERIVED')

```

If you see `NameError: name 'pk' is not defined`, run `import pyrakit as pk` first. In a `.py` file,
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
>>> import pyrakit as pk
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
>>> from pyrakit.adapters import CallableAdapter
>>> from pyrakit.schema import Conditions, ModelCard, Scenario
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

### 2.1 Checking a scenario against the model's validation envelope

There are two different gates, and the difference matters.

`require_validated(card)` asks only **"did anyone record any validation evidence at all?"** That is
a presence check. A model tested only on an Earth-gravity laboratory bench passes it even when you
ask about a microgravity flame.

`require_in_envelope(card, scenario)` asks the question you usually mean: **"does the recorded
evidence actually cover these conditions?"** It reads the limits written on each evidence entry and
compares them with your scenario one variable at a time.

The limits live in each evidence entry's `envelope` dictionary. Each key is an *axis* — one
variable the evidence was gathered over. A numeric axis takes either a `[min, max]` pair, or a
`{"min": ..., "max": ..., "unit": ...}` mapping when you want to write the limits in a convenient
unit. PYRA converts the limits before comparing, so recording pressure in kPa and holding the
scenario in Pa is safe. A categorical axis such as `diluent` takes a string or a list of allowed
strings.

```python
>>> from pyrakit.adapters import ClaimGateError, check_envelope, require_in_envelope
>>> from pyrakit.schema import ValidationEvidence
>>> bench = ModelCard(
...     name="bench-flame", version="0.3", code_hash="sha256:demo", licence="MIT",
...     physics_summary="fictional bench-scale model",
...     envelope=[ValidationEvidence(
...         experiment_ids=["fictional-bench-01"],
...         quantity="flame_length", metric="bias", result={"bias": 0.0},
...         envelope={"gravity_g": [0.9, 1.1],
...                   "o2_mole_fraction": [0.18, 0.25],
...                   "pressure": {"min": 95, "max": 105, "unit": "kPa"}},
...     )],
... )
>>> def at_gravity(scenario_id, gravity_g):
...     return Scenario(scenario_id=scenario_id, conditions=Conditions.model_validate({
...         "gravity_g": {"value": gravity_g, "unit": "dimensionless"},
...         "pressure": {"value": 101.3, "unit": "kPa"},
...         "o2_mole_fraction": {"value": 0.21, "unit": "dimensionless"},
...         "diluent": "nitrogen", "flow_mode": "forced", "fuel": {"material": "PMMA"},
...         "configuration": "concurrent", "length_scale": {"value": 0.02, "unit": "m"},
...     }))

```

An Earth-gravity scenario sits inside this envelope; a microgravity one does not:

```python
>>> check_envelope(bench, at_gravity("earth-bench", 1.0)).inside
True
>>> microgravity = at_gravity("microgravity-demo", 0.00001)
>>> check_envelope(bench, microgravity).inside
False
>>> check_envelope(bench, microgravity).reasons()[0]
"evidence for 'flame_length' (bias) from fictional-bench-01 does not reach this
 scenario: gravity_g is 1e-05 dimensionless, outside the recorded 0.9 to 1.1 dimensionless"

```

The presence-only gate accepts that same microgravity claim, which is exactly why you should prefer
the scenario-aware one:

```python
>>> from pyrakit.adapters import require_validated
>>> require_validated(bench)                      # passes: the card has *some* evidence
>>> try:
...     require_in_envelope(bench, microgravity)   # refuses: the evidence stops at 0.9 g
... except ClaimGateError:
...     print("claim refused")
claim refused

```

`check_envelope` reports and never raises; `require_in_envelope` raises `ClaimGateError`. Use
`check_envelope(...).explain()` to print a plain-language paragraph naming the verdict and every
failing axis.

Three deliberate refusals are worth knowing about:

- An evidence entry with an **empty** `envelope` dictionary never covers anything. Recording no
  limits is not the same as having wide ones.
- An entry must bound every axis in the gate policy — by default `gravity_g`, `o2_mole_fraction`
  and `pressure` — or the scenario is not treated as covered. That default is a documented
  starting policy for spacecraft fire work, not a claim that those three variables are physically
  sufficient. Change it explicitly with `EnvelopeGatePolicy(required_axes=(...))`.
- An **unknown axis name** raises `ValueError`, so a typo in a model card fails loudly instead of
  silently widening the envelope.

Passing this gate means a human recorded evidence spanning your conditions. It is not a safety
certification, and PYRA cannot check whether the recorded limits are themselves right.

## 3. Benchmarking a model against supplied evidence

You can score a model on a set of measured cases when you provide the tolerance and source IDs
explicitly:

```python
>>> from pyrakit.compare import evaluate_model
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
model. Use the evidence-aware `pyrakit.compare` tools for scientific comparisons.

## 4. Quantities carry a status

```python
>>> from pyrakit import Quantity, Status
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
pyrakit.provenance.status.StatusInputError: heat_release@1: input status SCENARIO exceeds the maximum allowed DERIVED

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
>>> from pyrakit import sha256_hex
>>> sha256_hex({"a": 1, "b": 2}) == sha256_hex({"b": 2, "a": 1})
True

```

## 7. Record everything in a ledger and check the lineage

```python
>>> import pathlib, tempfile
>>> from pyrakit import Ledger, LedgerEntry, LineageGraph
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
>>> from pyrakit.schema import Conditions, FuelSpec, Measure, Scenario
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
>>> from pyrakit.physics.calorimetry import hrr_oxygen_consumption
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
>>> from pyrakit.io import ManifestEntry, fetch
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

## 10.1 Connecting a real simulation engine

PYRA does not contain a flame solver, and it never imports one. An engine runs as a
separate program, and PYRA talks to it over a documented JSON contract. That means an
engine can be written in any language, installed separately, and swapped without changing
PYRA.

### The three kinds of picture

The Playground can show three different things, and they are not interchangeable:

| What you see | Where it came from | What it is worth |
| --- | --- | --- |
| Schematic flame | A drawing | Nothing was computed. It does not respond to any setting. |
| Oxygen curve | PYRA's learning model | A well-mixed oxygen balance. Not a flame solver. |
| Solver output | An external engine | Depends entirely on that engine's model card and envelope. |

Every view in the window carries a banner naming which of the three it is, and the
schematic flame is replaced by real geometry only when an engine actually returns a flame
front. In code the same three are `ViewSource.SCHEMATIC`, `ViewSource.LEARNING_MODEL` and
`ViewSource.SOLVER`.

### From the beginner form to a validated scenario

The Playground's fields are plain numbers. `FireScenario.to_scenario(...)` turns them into
a real `Scenario` where every input carries its unit, and where a known uncertainty is
recorded as such:

```python
>>> from pyrakit.service.scenario_inputs import FireScenario
>>> form = FireScenario(oxygen_fraction=0.21, oxygen_uncertainty=0.005, pressure_kpa=101.3)
>>> built = form.to_scenario("bench-study", purpose="hindcast")
>>> built.conditions.pressure.value, built.conditions.pressure.unit
(101.3, 'kPa')
>>> built.conditions.o2_mole_fraction.u, built.conditions.o2_mole_fraction.u_kind
(0.005, 'type_b')

```

Leaving an uncertainty out records "not known", which is different from zero:

```python
>>> unknown = FireScenario().to_scenario("no-uncertainty")
>>> unknown.conditions.o2_mole_fraction.u, unknown.conditions.o2_mole_fraction.u_kind
(None, 'unknown')

```

### What an engine must return

An engine reads the scenario on stdin and writes a JSON object on stdout with
`scenario_id`, `model_card_id`, `engine_version`, `time_s` and `channels`. Optionally it
adds `flame_front`, `mesh`, `warnings`, `artifacts` and `assumptions`. Each channel names
its own unit, so an animation axis and a later comparison agree:

```python
>>> from pyrakit.simulation import SimulationOutput
>>> run = SimulationOutput.from_dict({
...     "scenario_id": "bench-study", "model_card_id": "demo:1", "engine_version": "0.1",
...     "time_s": [0.0, 1.0, 2.0],
...     "channels": {"hrr": {"unit": "kW", "long_name": "Heat release rate",
...                          "values": [0.0, 4.0, 6.0]}},
... })
>>> run.channel("hrr").label
'Heat release rate [kW]'
>>> run.duration_s, run.sample_at(1.6)
(2.0, 2)

```

Structural mistakes are refused here rather than halfway through a plot. A channel whose
length does not match the time base, a unit that does not parse, or a time base that does
not increase all raise `ValueError` naming the problem.

### Running a whole study in one call

`run_engine_study` is the coordinating function: it checks the validation envelope, runs
the engine, keeps the scenario beside the output so the run can be reproduced, and
optionally compares a channel against a measurement.

```text
python examples/engine_study.py
```

That example is runnable as-is, because it drives the fictional engine from PYRA's own
test suite. Its numbers are meaningless by construction. Point it at a real executable and
supply a real model card to do actual work.

The call looks like this. Note that `save_to` writes the scenario *and* the output side by
side, because an output without the scenario that produced it cannot be reproduced:

```python
study = run_engine_study(
    adapter,
    scenario,
    save_to="runs/bench-study",
    compare_channel="hrr",
    observed=2.0,
    tolerance=0.5,
)
print(study.summary())
```

The order matters: the envelope is checked **before** the engine starts, so an unsupported
study fails immediately instead of after a long solve. Exploring outside the envelope is
still allowed with `require_support=False`, and the summary then says plainly that it
happened, printing `Validation envelope: not checked. This run is exploration only and
cannot support a claim about these conditions.`

### Before you wire up your friend's engine

Four things are needed from whoever wrote it, and none of them is optional:

1. **How to run it** — the executable, and whether it needs a subcommand or config flag.
2. **Its output format** — if it does not already speak PYRA's contract, a small wrapper
   script that converts its native output is usually a few dozen lines.
3. **Its licence** — recorded on the model card, because it governs what you may publish.
4. **Its validation envelope** — the conditions it was actually compared against. Without
   this, PYRA will run the engine for exploration but will refuse to call any result
   supported, which is the correct behaviour rather than an obstacle.

Until all four exist, keep the engine in exploration mode. A result labelled `SIMULATED`
is a model output, never evidence.

## 11. Where to go next

* `docs/api.md`: every public name in `pyrakit.provenance` with its signature.
* `examples/quickstart.py`: this page as a runnable script.
* `examples/engine_study.py`: the whole engine flow, runnable without installing anything.
* `docs/architecture.md`: what PYRA will and will not claim.

## Learning path

1. **Explore:** open `pyra playground`, change one setting at a time, and read the banner that
   says whether you are looking at a drawing, the learning model, or solver output.
2. **Write a first program:** use `import pyrakit as pk`, named arguments and `print` in a `.py`
   file. Run `examples/complete_fire_test.py`.
3. **Understand evidence:** learn units, uncertainty, status and source references; then inspect a
   PSI raw-condition record without assuming its sensor values are calibrated.
4. **Make the scenario real:** move from the flat beginner form to a validated scenario with
   `FireScenario.to_scenario(...)`, where every input carries a unit and a known uncertainty.
5. **Drive a solver:** read section 10.1, then run `examples/engine_study.py`. Learn why the
   validation envelope is checked before the engine starts.
6. **Analyze:** try `compare_values`, then advance to `pyrakit.compare`, matching and evidence reports
   with real, sourced records and documented uncertainty.

You can stop after any step and still use the beginner tools. The advanced analysis API remains
available without making the learning exercises depend on it.

## 12. Small education helpers

The education package stays deliberately small: a fictional trace, readable result labels, and a
check that lesson material either cites an evidence ID or labels itself as a concept sketch.

```python
>>> from pyrakit.edu import decay_activity, check_lesson, status_badge
>>> decay_activity(steps=3)["label"]
'FICTIONAL TEACHING EXAMPLE — NOT A FIRE MODEL'
>>> check_lesson(title="Exponential curves", concept_sketch=True).ok
True
>>> status_badge("SIMULATED")
'SIMULATED: Simulation output'

```
