# ADR 0001: Canonical hashing and artifact identity

Status: accepted (software design). Needs a scientist's review only for the float rule.

## Decision
* `artifact_id = sha256(canonical JSON)` of `{content, parents, activity, params, source_ref}`.
  `content` = value, unit, uncertainty, uncertainty kind and status.
* Excluded from the id: `code_version`, `env_hash`, `created_utc`. Ids must be reproducible across
  machines and time so `pyra replay` can compare hashes (section 11). Those fields stay in the record.
* Canonical JSON: sorted keys, compact separators, ASCII, NFC-normalized strings, tuples as lists,
  NaN and infinities as tagged objects, numpy arrays tagged with dtype and shape.
* Floats are rounded to **12 significant digits** and `-0.0` becomes `0.0`. `1` and `1.0` stay distinct.
* Anything else (sets, arbitrary objects, non-string keys, xarray objects) raises `TypeError`.

## Why 12 digits
It absorbs platform rounding noise (for example `0.1 + 0.2` versus `0.3`) while keeping far more
precision than any combustion sensor delivers. This is a design choice, not derived from the
instruments. Revisit after the data audit if any channel carries more than 12 meaningful digits.

## Consequences
* Ledger parameters are stored in canonical form, so they also keep 12 significant digits.
* Two different values that agree to 12 digits share an id; that is intended.
* xarray hashing (coordinates, attrs, dims) is deferred until the real xarray API can be checked.
