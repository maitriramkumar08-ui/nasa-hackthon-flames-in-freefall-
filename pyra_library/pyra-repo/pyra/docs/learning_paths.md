# Learning paths

PYRA has one small beginner surface and a set of deeper tools behind it. You can stop at any stage;
the beginner functions do not require you to learn every advanced feature first.

## 1. Beginner: run and change an example

Start in the VS Code terminal with:

```text
pyra playground
```

Then create a Python file and use the friendly import:

```python
import pyra_library as pk

result = pk.heat_release(
    0.21, 0.20, 0.01, 13_100_000,
    source_ref="synthetic-example",
)
print(result.value, result.unit, result.status.name)
```

Learn variables, function arguments, units in printed output, and how to run a script. The four
positional values have a fixed order; named arguments are easier to read. The values and source
above are illustrative, not research data.

## 2. Explorer: use the small interactive tools

- `pk.playground()` opens the same Fire Playground as `pyra playground`.
- `pk.run_fire_test(...)` runs the built-in oxygen-only learning simulation and returns a summary
  plus a `run.show()` graph.
- `pk.compare(...)` compares two values already in the same unit using a tolerance you choose.
- `pk.simulate_zone()` returns the simple, assumption-labeled concentration exercise.
- `from pyra_edu import decay_activity` creates a fictional trace for a classroom exercise.

Change one input at a time. Read the model assumptions before interpreting the graph. The current
Fire Playground's flame is a schematic; the graph does not model fuel combustion or flame shape.

## 3. Analyst: work with sourced evidence

Learn `Quantity`, `Status`, units, uncertainty, source references, PSI raw condition records, and
manifest-based file hashes. Use `pyra.compare` when two numeric values are not enough and you need
uncertainty, units, time-series alignment, or case-by-case evaluation. Preserve the data source and
write down what was calibrated versus what remains a raw instrument reading.

## 4. Developer: connect a simulation model

Implement a `SimulatorAdapter` for the engine, provide a `ModelCard`, record input/output units,
software version and run provenance, then compare its outputs with independent experimental data.
Use validation evidence to define where the model is suitable. A non-empty model card alone does
not establish that it applies to every scenario; scenario-envelope checking is still a required
improvement before PYRA makes model-supported claims.

## Friendly and full import names

For a short first program, use `import pyra_library as pk`. The original `import pyra as pk` import
continues to work. Advanced modules remain available under `pyra`, for example
`from pyra.compare import evaluate_model` or `from pyra.schema import Conditions, Scenario`.
