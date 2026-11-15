# PYRA

**Predictive Hazard & Reliability Atlas** is an educational and professional Python library for
spacecraft and habitat fire-safety work. Its goal is to make experimental evidence easier to
organize, inspect and compare, while keeping the assumptions and limits visible.

PYRA provides reusable building blocks for evidence provenance, units and uncertainty, heat-release
calculations, investigation data review, scenario matching, model comparison, reports and simple
interactive demonstrations. It is designed to support learning and research workflows—from a
first Python experiment to structured analysis—not to replace expert review or validated safety
engineering tools.

## What PYRA can and cannot say

Results are labelled Measured, Derived, Simulated, Scenario or Interpretation. PYRA does not make
unqualified fire-safety predictions or certify a design. A comparison or score applies only to the
cases, sources and assumptions supplied to it; it is not proof of general reliability.

This project is pre-alpha. Investigation-specific readers and external simulator integrations
depend on verified source formats and validation evidence. The software is not endorsed or adopted
by NASA or any programme named in its materials.

## A first calculation

```python
import pyrakit as pk

hrr = pk.heat_release(
    0.21, 0.20, 0.01, 13_100_000,
    source_ref="doi:10.0000/example|synthetic",
)
print(hrr.value, hrr.unit, hrr.status.name)   # 1310 W DERIVED
```

For a local visual demo, run `pyra simulate --window`. For machine-readable output, run
`pyra simulate --steps 20`; it prints JSON and does not open a window.

For an explicitly simplified run that returns a summary and can save its results, use
`pk.run_fire_test(...)`. `run.show()` opens its graph and `run.save("fire_run.json")` saves inputs,
assumptions, and the trace. This remains an educational oxygen-balance model, not a flame solver.
For classroom examples, `pyrakit.edu.decay_activity()` returns a fictional trace labelled as a
concept sketch.

For the friendly import surface, use `pyrakit`; the complete advanced API remains available
as `pyra` (for example, `from pyrakit.compare import evaluate_model`).

## Install and explore

PYRA is not published on PyPI. Install from a checkout with `pip install -e .`; see
[`docs/installation.md`](docs/installation.md), [`docs/usage.md`](docs/usage.md), and
[`docs/api.md`](docs/api.md). The feature overview is in
[`docs/feature_quick_reference.md`](docs/feature_quick_reference.md), and design details are in
[`docs/architecture.md`](docs/architecture.md). Development conventions are in
[`docs/development.md`](docs/development.md).
