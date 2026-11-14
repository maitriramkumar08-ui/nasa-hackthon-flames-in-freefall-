# Development guide

This guide keeps PYRA's implementation and review process consistent. It is part of the
repository's normal project documentation and applies to code, tests, data readers and
scientific documentation.

## Scope and scientific boundaries

- PYRA covers spacecraft and habitat fire safety, including microgravity and partial gravity.
- Every public result carries a unit, uncertainty and one of the documented statuses:
  Measured, Derived, Simulated, Scenario or Interpretation.
- A result may not have a stronger status than its inputs, and no public API emits an
  unqualified prediction.
- Model-supported claims require a model card whose validation envelope covers the scenario.
- Do not invent dataset identifiers, file formats, API fields, constants or validation claims.
  Use an explicit verification note or a failing placeholder until the source is checked.
- Every formula and physical constant needs a source reference in code or documentation.

## Implementation conventions

- Prefer pure functions, explicit random seeds and no hidden global state.
- Keep the scientific core independent of simulators and education packages; adapters depend
  on the core, never the reverse.
- Propagate warnings into result and report objects instead of silencing them.
- Support Python 3.11 or newer with type hints, pydantic schemas, Pint units and xarray arrays
  where those abstractions are appropriate.

## Tests and review

Write tests with the change. Derivations should have synthetic-truth tests, properties should
cover invariants, and readers should use real fixtures or clearly labelled synthetic fixtures.
Record scientific choices such as tolerances, thresholds and formulas in a short ADR under
`docs/adr/`.

Before opening or merging a change, run:

```text
ruff check src tests
mypy src
pytest
```

Keep commits focused and update `docs/feature_quick_reference.md` and
`docs/command_cheatsheet.md` whenever a public feature or command changes. If a requirement or
scientific choice is ambiguous, document the question and resolve it from the cited source
before implementing it.
