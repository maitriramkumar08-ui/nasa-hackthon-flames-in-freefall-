# ADR 0002: Status propagation API

Status: accepted (software design).

## Decision
* `Status` is an `IntEnum` ordered by distance from observation; `join` is `max` and rejects plain ints.
* Only `Quantity.measured` (requires a `source_ref`) can produce MEASURED; `Quantity.scenario` produces
  SCENARIO; `Quantity.derive` computes `join(method_status, *parent statuses)` and requires
  `method_status >= DERIVED` and at least one parent.
* `max_input_status` on `derive` raises `StatusInputError` at call time (section 3).
* `LineageGraph.verify` independently flags missing parents, status downgrades and cycles in any
  ledger, so a forged or hand-edited record is caught even if it bypassed `derive`.

## Open point
Unit conversion of a measured value should stay MEASURED (section 3). It needs a dedicated
constructor, added with pint at P2, not a loophole in `derive`.
