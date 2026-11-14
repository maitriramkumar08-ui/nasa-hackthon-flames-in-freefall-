# Contributing to PYRA

Keep changes small and explain the scientific boundary they touch. Read `docs/development.md`
and the architecture document before changing a layer.

Every public API addition needs an executable example in `docs/usage.md`, tests, and regenerated
`docs/api.md`. Do not invent PSI file formats, calibration constants, or validation claims. Put
scientific choices in a short ADR under `docs/adr/`.

Keep `docs/feature_quick_reference.md` and `docs/command_cheatsheet.md` updated whenever a public
feature or supported command changes.

Before opening a change, run:

```text
ruff check src tests
mypy src
pytest
```

The project is pre-alpha and is not endorsed by NASA.
