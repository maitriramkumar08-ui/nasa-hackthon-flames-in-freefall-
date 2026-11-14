# PYRA: Predictive Hazard & Reliability Atlas

NASA Space Apps 2026, spacecraft fire safety challenge.

PYRA shows what NASA's microgravity combustion data actually tells you about fire in a
habitat, how close the nearest evidence is, and where there is no evidence at all.
It does not predict fires and it does not label materials safe or unsafe.

## Where we are: Phase 0 (setup and source verification)

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

## Next: Phase 1 (data foundation)

Once the checker passes: write a fact sheet for each paper, get a second person to check it,
then build the SQLite database and the loader.
