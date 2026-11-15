# PYRA: Predictive Hazard & Reliability Atlas

NASA Space Apps 2026, spacecraft fire safety challenge.

PYRA shows what NASA's microgravity combustion data actually tells you about fire in a
habitat, how close the nearest evidence is, and where there is no evidence at all.
It does not predict fires and it does not label materials safe or unsafe.

## How to run it

You need Windows PowerShell and Python 3.11 or newer. The web app uses only the standard
library, so there is nothing to install.

```powershell
.\run.ps1
```

That builds `data/pyra.db` if it is missing, loads keys from `.env`, starts the server and
opens the browser at **http://127.0.0.1:8000**. Press Ctrl+C to stop it.

If PowerShell blocks the script, run
`powershell -ExecutionPolicy Bypass -File .\run.ps1` instead.

| Option | What it does |
| --- | --- |
| `-Port 9000` | Serve on another port (default 8000) |
| `-Planner auto\|offline\|claude\|groq` | Who drives the research assistant (default `auto`) |
| `-Build` | Rebuild `data/pyra.db` from `data/factsheets/verified/` first |
| `-Check` | Run the data-quality checks, then exit |
| `-Tests` | Run the Python tests and the flame model tests, then exit |
| `-TestAgent` | Run the research agent tests, then exit |
| `-NoBrowser` | Do not open the browser |
| `-Help` | Show these options |

### Adding data

PYRA only shows verified evidence. Until `data/factsheets/verified/` holds fact sheets,
the evidence views are empty. To add data, put verified sheets there and run
`.\run.ps1 -Build`. The process for checking a sheet is in `docs/WORKFLOW.md`.

### Language model (optional)

The app works offline with fixed rules and templates. To let a model write the wording,
copy `.env.example` to `.env` and set `GROQ_API_KEY` (or `ANTHROPIC_API_KEY` after
`pip install anthropic`). Every sentence a model writes is checked against PYRA's rules,
and numbers always come from code. Set `PYRA_AGENTS_OFFLINE=1` to force offline mode.

## What is in the app

| Tab | What it shows |
| --- | --- |
| Explore | Scenario, Coverage Map, coverage by axis, ranked investigations, research gaps, side-by-side compare |
| Ops | Crew and Controller views over one SIMULATED cabin telemetry stream |
| Builder | Early-design check of a cabin atmosphere and materials list against the evidence |
| Agents | A supervised team of eight evidence agents, with a human approval step |
| Assistant | A research agent that picks PYRA's tools and writes a cited, rule-checked answer |
| 3D demo | Habitat, Evidence Atlas and Data Pipeline in 3D, with an ILLUSTRATIVE flame model |

The header also has an Export menu (CSV, JSON, PDF report), an AI assistant side panel,
and a Round table page where the crew agents respond to a SIMULATED cabin alert.

Every value is labelled by where it came from: MEASURED, DERIVED, HYPOTHETICAL,
SIMULATED, PLACEHOLDER, ILLUSTRATIVE or INTERPRETATION.

## Repository layout

| Path | What it is |
| --- | --- |
| `run.ps1` | The one launcher for the project |
| `pyra/` | The application: fact-sheet loading, SQLite build, ranking, gap engine, retrieval, web server |
| `pyra/agents/` | The evidence agent team behind the Agents tab |
| `pyra/web/` | The web page, its scripts and styles |
| `demo/` | The 3D flame demo, served at `/demo/` |
| `config/` | Alert limits, design rules, environment presets and incidents |
| `data/factsheets/` | Fact sheets: `drafts/` to check, `verified/` to load |
| `datasets/` | The supplied NASA files, unmodified, with checksums |
| `sources/` | The documentary source list and its verification log |
| `pyra_library/pyra-repo/pyra/` | **pyrakit**, the reusable evidence and validation library |
| `tools/` | Checkers and the evidence report |
| `tests/` | Unit tests. `tests/fixtures/` holds test-only sheets marked NOT REAL DATA |
| `docs/` | Rules and the contributor workflow |
| `ember/` | The earlier LangGraph prototype the agent team was ported from |

The `pyra/` application and the `pyrakit` library are separate packages. The library was
renamed so that the two can never be confused by an import.

## What PYRA will not claim

- It does not predict whether a material will burn in a given habitat.
- It does not certify anything as safe.
- A result marked SIMULATED or ILLUSTRATIVE is a model output, not evidence, and PYRA will
  not let it be presented as evidence.

Where the evidence does not reach, the honest answer is that nobody knows yet. PYRA is
built to give that answer clearly instead of hiding it behind a number.
