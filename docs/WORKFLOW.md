# Team workflow: verifying sources and building the database

This is the working process for contributors. The project overview lives in the
top-level `README.md`.

## Phase 0: setup and source verification

The goal of Phase 0 is to agree on the rules and check our sources before anyone writes app code.
Nothing goes into the database until a person has checked it.

| File | What it is | What you do with it |
| --- | --- | --- |
| `docs/RULES.md` | The 10 rules in plain words | Read it once, keep it open |
| `docs/TEAM.md` | Roles and the scope freeze | Put your name next to your role |
| `sources/sources.csv` | Every source we need to check (23 rows) | Take some rows, open each source, fill in the empty columns |
| `config/decisions.json` | Tech and number choices (database, weights, tolerances...) | Discuss as a team, change values if needed, add your name to `confirmed_by` |
| `tools/check_phase0.py` | Tells you what's still missing (the checks are in `tools/phase0/`) | Run it until it says "Phase 0 done" |

## How to check a source (sources.csv)

For each row you take:

1. Put your name in `assigned_to`.
2. Open the source (search the NTRS number on the NASA Technical Reports Server, or find the PSI page).
3. Fill in `url` (the link you actually opened), `access_date` (YYYY-MM-DD),
   `contents` (one line), and `fields_taken` (what we'll use, e.g. "O2 range; pressure; fuel").
4. If the link is dead or the content doesn't match the master doc, write that in `contents`.
   Don't quietly fix it.
5. Put your name in `verified_by` only once you've read it yourself.

Tip: avoid commas inside a cell, or the CSV gets messy. Use `;` instead.

## Run the checker

You only need Python 3. Nothing to install.

```
python tools/check_phase0.py
python -m unittest discover tests
```

The checker lists every source that's missing a url, date or verifier, and every decision nobody has confirmed yet.
It also checks that the ranking weights add up to 1.

## Phase 1: data foundation (`pyra/`)

Turn the verified sources into one SQLite database. Still plain Python 3, nothing to install.

### How a paper gets into the database

1. Run **Prompt 1** on the paper's text. Save the JSON in `data/factsheets/drafts/`
   (start from `data/factsheets/TEMPLATE.json`). Add a line to `prompts/LOG.md`.
2. Run **Prompt 12** on it. Fix whatever it flags.
3. A second person checks every number against the paper, then fills in `_review`
   (`checked_by`, `prompt12_passed: true`).
4. `python -m pyra validate data/factsheets/drafts/<file>.json` must say `ready`.
5. Move the file to `data/factsheets/verified/` and rebuild.

Several papers about the same investigation means several sheets with the same `acronym`.
They share one investigation in the database. Add `test_runs` only for the one or two
investigations the demo needs.

### Commands

```
python -m pyra build                  # rebuild data/pyra.db from data/factsheets/verified
python -m pyra check                  # data-quality checks (impossible values, duplicates, missing sources)
python -m pyra spotcheck              # 10 random numbers to check by hand against the paper
python -m pyra validate FILE...       # check sheets without loading them
```

The database is rebuilt from the sheets every time, so never edit it by hand (it's git-ignored).

### The code, one job per file

| File | Job |
| --- | --- |
| `pyra/units.py` | Unit conversion: psi/kPa/Pa/atm, cm/s/m/s/mm/s, C/K, mm/cm/m, ms/s |
| `pyra/factsheet.py` | Checks one sheet: errors reject it, warnings get it loaded but flagged |
| `pyra/schema.sql` | The tables, with comments |
| `pyra/db.py` | Opens or creates the SQLite file |
| `pyra/loader.py` | Puts checked sheets into the tables, one transaction per sheet |
| `pyra/quality.py` | Data-quality checks. Each check is one SQL query, so adding one is one entry |
| `pyra/cli.py` | The commands above |
| `tests/fixtures/` | Test-only sheets and eval docs, all marked `NOT REAL DATA`. The app never loads them |

What the loader guarantees:
- No source (url or NTRS id) and no second checker means the sheet is rejected.
- Every number keeps `original_value` and `original_unit`. The converted value goes in
  `normalized_value`/`normalized_unit` with `conversion_method`.
- Missing values are `NULL` with `is_missing = 1`, never 0. Text like "microgravity" is kept
  as text and is never turned into a number.

The tables are a slimmed-down version of the plan's list. A material is a column in `fuels`,
`experiment` is a column in `test_runs`, and every fact points at its publication and page,
so there's no separate citations table. `research_gaps` comes in Phase 2, which computes it.

### Phase 1 is done when

- `data/factsheets/verified/` has 15 to 20 investigations with O₂, pressure, flow, gravity, fuel,
  hardware, sensors and source filled in where the papers give them
- `python -m pyra build` rejects nothing, and `python -m pyra check` reports 0 problems
- someone has run `spotcheck` and confirmed the rows against the papers
- `python -m unittest discover tests` passes
