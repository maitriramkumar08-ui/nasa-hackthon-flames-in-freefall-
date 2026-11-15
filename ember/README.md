# EMBER: a multi-agent fire-safety team for NASA Space Apps 2026, "Flame in Freefall"

**EMBER** (Evidence-based Microgravity Burn Expert Reasoners) is a LangGraph agent team. It reads NASA's
microgravity combustion investigations (Physical Science Informatics, PSI) and assesses fire safety for a chosen mission:
ISS, Gateway, a lunar habitat, a Mars transit vehicle or a Mars surface habitat. It uses the same architecture as the HUKUM
prototype: a supervisor, a review loop, a human-approval step, an offline-safe LLM and an SSE event stream to the browser.

```
START -> supervisor -> librarian -> mission_profiler -> physicist -> risk_ranker <-> skeptic (loop, max 3 passes)
                    -> incident_analyst -> gap_hunter -> safety_officer (interrupt: human approves) -> reporter -> END
```

| Agent | Output key | What it does |
|---|---|---|
| Librarian | `corpus` | Loads 25 PSI records, drops non-combustion ones, tags topic / phase / materials / atmosphere |
| Mission Profiler | `mission` | Gravity, cabin pressure, O2 %, fan flow, comm delay, oxygen sources |
| Physicist | `physics` | Buoyant flow vs fan flow gives the flame regime (forced / mixed / buoyant / quiescent), and how relevant Earth screening tests are |
| Risk Ranker | `risk` | Ranks cabin materials by O2 margin to their estimated flammability limit, with an uncertainty band and evidence |
| Skeptic | `review` | Rejects "measured" claims that no PSI test supports at this gravity and atmosphere, and sends the ranking back |
| Incident Analyst | `incidents` | Apollo 1, Apollo 13 and Mir broken into oxidizer / fuel / ignition / detection / suppression / escape, matched to the mission |
| Gap Hunter | `gaps` | Gravity x atmosphere x topic coverage matrix, ranked gaps, and a proposed experiment |
| Safety Officer | `actions` | Recommendations linked to evidence; pauses for human approval |

**The demo moment:** run *Lunar habitat*. On pass 1 the Risk Ranker calls cotton and PMMA "measured", because they were
tested on the ISS. The Skeptic blocks that: no PSI combustion investigation has ever run in partial gravity. Pass 2 relabels
every claim and widens the uncertainty bands, and the Gap Hunter turns that gap into the next experiment.

## Run

```bash
pip install -r agents/requirements.txt
python -m agents.server              # http://127.0.0.1:8000/agents.html   (PORT=9000 to change)
python -m agents.tests.test_graph    # offline tests
python -m agents.record_demo lunar   # re-record the replay used when no server is running
```

Without the Python server (for example `python -m http.server`, or GitHub Pages), `agents.html` replays `agents/data/demo_run.json`.

**LLM:** offline by default and deterministic. Put `GROQ_API_KEY` in `agents/.env` to have the model write the reasoning text and
route the goal. A sentence from the model containing a number that is not in the tool data is replaced by the scripted
sentence (`llm.grounded`). `EMBER_OFFLINE=1` forces offline mode.

API: `GET /api/health`, `GET /api/graph`, `POST /api/run {goal, mode: full|risk|gaps|lessons|custom, scenario: {mission, pilot_mode, materials?, fan_m_s?}}`,
`GET /api/stream/{id}` (SSE), `POST /api/resume/{id} {decision, ids}`, `GET /api/state/{id}`, `POST /api/ask {agent, question}`.

## Data and honesty notes (read before presenting)

- `agents/data/psi_combustion.json`: IDs, titles and types are copied from the PSI search (retrieved 2026-11-15). Topic, material and
  atmosphere tags are EMBER's. BASS-II (PSI-25), Saffire-I (PSI-98) and ACME BRE (PSI-20) were checked against their PSI pages
  (`verified: true`). Check the rest before you rely on them. Cite PSI data by its DOI.
- ACME BRE lists the NASA-considered atmospheres used here: 14.7 psia / 21%, 10.2 / 26.5% and 8.2 / 34% O2. Which atmosphere a
  given future vehicle will use is a **scenario assumption** and is labelled as such.
- Material limits use approximate normal-gravity limiting oxygen index values from the literature. The microgravity and pressure
  corrections (`ASSUMPTIONS` in `agents/tools/fire_tools.py`) are placeholders to calibrate against BASS-II / Saffire data. Present
  the output as a screening ranking with uncertainty, not as flight certification.
- Flame-regime physics is order-of-magnitude scaling (buoyant velocity ~ sqrt(g L dT/T)), shown with its assumptions.
