# Changelog

## Unreleased

- Added `pyra.simulation`, the contract an external engine reports through: a seconds time
  base, channels tagged with Pint-parsable units, optional flame-front geometry and mesh
  information, engine warnings, and output file locations. Structural mistakes (a channel
  length that does not match the time base, an unparsable unit, a time base that does not
  increase) are refused with a specific message rather than surfacing halfway through a plot.
- Added `pyra.adapters.ExternalEngineAdapter`, which runs a locally installed engine as a
  child process over that contract. PYRA takes no dependency on any engine, so one can be
  written in any language and swapped freely. Runs are cancellable and time-bounded, and a
  cancelled engine is killed and reaped. `run()` explores; `run_supported()` additionally
  requires the scenario to fall inside the model card's recorded envelope, checked before
  the engine starts.
- Added `pyra.service.workflow.run_engine_study`, one call that gates, runs, writes the
  scenario beside the output so the run can be reproduced, and optionally compares a channel
  against a measurement in that channel's own unit.
- Extended the Playground scenario form into typed fields covering flow, fuel geometry,
  ignition and known uncertainties, and added `FireScenario.to_scenario()` to convert it
  into a validated `Scenario`. A blank optional field records "not set" rather than zero.
- Labelled every Playground view by where it came from: a schematic drawing, the simplified
  learning model, or external solver output. The schematic flame is replaced by real geometry
  only when an engine returns a flame front. Added run, cancel, progress, error reporting and
  a playback timeline.
- Fixed a confusing `ImportError` when a local directory named `pyra` shadows the installed
  library; the error now names the shadowing directory and says how to avoid it.

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
