# PYRA

Predictive Hazard & Reliability Atlas for spacecraft fire safety.

**What it is:** a fire-only Python library that organizes NASA microgravity combustion evidence and compares it
with simulations, labelling every output as Measured, Derived, Simulated, Scenario or Interpretation.

**What it is not:** a predictor. It never emits an unqualified prediction (architecture section 1).
Not endorsed or adopted by NASA or any programme named in the architecture document.

Status: pre-alpha. Implemented: P0/P1 provenance foundations, P2 Pint and pydantic schemas, and the
P3 S0 calorimetry/UQ foundation. External readers, matching and simulation adapters remain gated on
their documented data and validation decisions.

```python
import pyra as pk

hrr = pk.heat_release(
    0.21, 0.20, 0.01, 13_100_000,
    source_ref="doi:10.0000/example|synthetic",
)
print(hrr.value, hrr.unit, hrr.status.name)   # 1310 W DERIVED
```

For a local visual demo, run `pyra simulate --window`. For machine-readable output, run
`pyra simulate --steps 20`; it prints JSON and does not open a window.

Install from a checkout with `pip install -e .` (not on PyPI). Docs: `docs/installation.md`,
`docs/usage.md` (every example is run by the tests), `docs/api.md`. Design: `docs/architecture.md`.
Development conventions: `docs/development.md`.
