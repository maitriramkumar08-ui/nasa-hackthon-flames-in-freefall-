# Changelog

## Unreleased

- Added a scenario-aware claim gate. `pyra.adapters.require_in_envelope(card, scenario)` and
  `check_envelope(...)` read the limits recorded on each model-card evidence entry and refuse a
  claim whose conditions fall outside them, axis by axis, with unit conversion. The previous
  `require_validated(card)` remains but is only a presence check: it accepts an Earth-gravity-only
  model for a microgravity scenario, which is why it is no longer the gate to reach for. An
  evidence entry recording no limits now covers nothing, an unknown axis name raises instead of
  silently widening the envelope, and the required-axis set is an explicit `EnvelopeGatePolicy`
  rather than an implicit assumption.
- Documented the envelope format in `model_cards/template.yaml` and added the runnable
  `examples/envelope_gate.py`, both exercised by the test suite.
- Added a beginner Fire Playground with presets, editable environment fields, a static flame
  illustration and an explicitly limited oxygen trace.
- Added `compare_values` as a same-unit scalar shortcut while retaining all evidence-aware
  comparison functions.
- Added guided learning steps from interactive exploration through evidence handling to advanced
  analysis.
- Added Pint and pydantic schemas, S0 calorimetry, uncertainty propagation, and manifest-driven I/O.
- Added PSI metadata/raw-file audit readers, matching, coverage, comparison metrics, callable adapters,
  status-aware HTML reports, replay inspection, and beginner CLI helpers.
- Improved PSI reader errors for archives with missing or ambiguous metadata and for empty or
  malformed PSI-159 setpoint files.
- Made the learning trace helper usable with defaults, reject non-finite inputs, and clarified its
  example and beginner API reference.
- Added an explicitly limited well-mixed zone concentration simulation and a PSI-159 condition
  record that preserves raw fields until calibration and mappings are verified.
- Replaced education-layer placeholders with a fictional trace activity, plain-language status
  labels and a small evidence-or-concept-sketch lesson check.
- Added executable usage examples and 90+ tests covering the implemented layers.

The project remains pre-alpha. Calibrated investigation readers, external simulator adapters, and
validated prediction envelopes are not implied by these entries.
