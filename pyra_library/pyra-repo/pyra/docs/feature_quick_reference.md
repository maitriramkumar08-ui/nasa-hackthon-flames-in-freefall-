# PYRA feature reference

PYRA is a Python library for spacecraft and habitat fire-safety evidence.

- Statuses: `MEASURED`, `DERIVED`, `SIMULATED`, `SCENARIO`, `INTERPRETATION`.
- Provenance: immutable quantities, SHA-256 artifact IDs, JSONL ledger, lineage checks, replay checks.
- Units: Pint registry and dimensional validation.
- Schemas: pydantic models for conditions, fuels, experiments, scenarios, sources, and model cards.
- S0 physics: oxygen-consumption HRR, enthalpy balance, species generation, uncertainty propagation.
- PSI I/O: metadata ZIP reader, raw PSI-159 setpoint reader, CSV reader, hash-checked manifests.
- Data audit: supplied BASS-II, FLEX, SAFFIRE-I, SPICE, and PSI-159 files documented with limits.
- Matching: configuration/fuel/flow gates, gravity/pressure log distances, mismatch vectors, Pareto fronts.
- Coverage: nearest evidence, independent-source counts, explicit `none` coverage result.
- Comparison: sensor lag, bias, relative difference, z-score, benchmark model score.
- Adapters: callable simulator boundary, model-card validation gate, hindcast scenarios.
- Reports: self-contained HTML with statuses and IDs.
- Beginner API: `import pyra as pk`, `heat_release`, `simulate_decay` (works with defaults),
  `show_simulation`, `measured`, `scenario`.
- CLI: `demo`, `simulate`, and `replay` commands.

Limits: calibrated investigation readers, external CFD adapters, Bayesian calibration, surrogate
models, and universal reliability claims are not implemented. Results are evidence-bounded.

Update this file whenever a public feature or supported command is added or removed.
