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
from pyra import Quantity, Status

p = Quantity.measured(101.3, "kPa", 0.5, "type_b", source_ref="doi:10.0000/example|sha256:00|row 12")
print(p.status.name)   # MEASURED
```

Install from a checkout with `pip install -e .` (not on PyPI). Docs: `docs/installation.md`,
`docs/usage.md` (every example is run by the tests), `docs/api.md`. Design: `docs/architecture.md`.
Project rules for AI-assisted work: `AGENTS.md`.
