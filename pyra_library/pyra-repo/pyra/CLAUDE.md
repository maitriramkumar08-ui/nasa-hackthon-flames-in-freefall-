Project: PYRA, a Python library for spacecraft and habitat fire safety evidence.
Scope: fire only (microgravity and partial gravity). Do not generalize to other NASA domains.
Source of truth: the architecture document (docs/architecture.md), sections 1 to 20.

Rules:
1. Every quantity is a Quantity with unit, uncertainty and Status (Measured, Derived, Simulated, Scenario, Interpretation).
   Status of a result is the maximum of its inputs. Never downgrade it.
2. Never output an unqualified prediction. Model-supported statements need a ModelCard whose envelope covers the scenario.
3. Do not guess external file formats, dataset ids, API fields or physical constants. Stub them with TODO(verify) and a failing-loudly placeholder.
4. Every formula and constant has a source reference in a comment. No reference means a defect.
5. Pure functions where possible; randomness takes an explicit seed; no hidden global state.
6. The core never imports simulators or education packages. Adapters import the core, never the reverse.
7. Warnings are objects that propagate into reports. Never silence them.
8. Python 3.11+, type hints everywhere, pydantic for schemas, pint for units, xarray for arrays.
9. Tests: pytest, hypothesis for properties, synthetic-truth tests for derivations. Write tests first.
10. Small commits. Run ruff, mypy and pytest before reporting done, and paste the results.
11. If a requirement is ambiguous or a scientific choice is needed, stop and ask. Do not invent.
