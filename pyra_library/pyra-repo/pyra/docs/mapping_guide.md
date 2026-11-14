# Mapping guide

This guide explains how to add an investigation reader after reviewing its source files and
recording the resulting data audit. The steps below are intentionally conservative: an
unsupported file layout should remain an explicit gap until it can be verified.

## Before you start

- Keep original source files unchanged and record their origin, access date and SHA-256 hash.
- Inspect the actual files before defining columns or metadata fields.
- Add a small, redistributable fixture where permissions allow; otherwise use a synthetic
  fixture that reproduces the verified structure and label it clearly.
- Record unresolved interpretation or calibration questions in `docs/data_audit.md`.

## Reader workflow

1. Add or update the source manifest with investigation ID, source reference and file hashes.
2. Implement a reader under `src/pyra/io/readers/` that accepts a local path and returns the
   documented schema; do not silently infer missing units or conditions.
3. Preserve raw column names and record every normalization in provenance.
4. Reject ambiguous or malformed input with an actionable error. Do not guess a file version.
5. Test the reader against the verified fixture, including missing values, units, duplicate
   rows and unsupported variants.
6. Update the data audit, mapping guide examples, feature reference and API documentation.
7. Run the checks in `docs/development.md` and review the normalized output against the source.

## Reader record

For each supported file family, document the investigation, exact filename pattern or version,
required columns, units, row interpretation, missing-value rules, known limitations and fixture
provenance. Keep this record alongside the reader tests so future changes can be checked against
the same evidence.
