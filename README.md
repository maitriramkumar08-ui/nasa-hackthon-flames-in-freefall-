# PYRA: Predictive Hazard & Reliability Atlas

NASA Space Apps 2026, spacecraft fire safety challenge.

PYRA shows what NASA's microgravity combustion data actually tells you about fire in a
habitat, how close the nearest evidence is, and where there is no evidence at all.
It does not predict fires and it does not label materials safe or unsafe.

## The problem

Fire behaves differently in microgravity. Without buoyancy there is no rising hot plume
to carry smoke away and pull fresh air in, so flames spread, starve and self-extinguish
on terms that Earth-based flammability testing does not reproduce.

The data that describes this is small. A handful of investigations — BASS-II, FLEX,
Saffire, SPICE, ACME — is most of what has ever been measured, and each covers a narrow
band of oxygen, pressure, flow and fuel. Meanwhile the questions being asked are moving
away from that band: Artemis and Gateway raise oxygen fractions and lower pressures, and
a spacesuit sits near 100% oxygen at about 30 kPa.

So the dangerous failure is not a missing model. It is a confident answer produced by
extrapolating a 1 g bench test, or a single microgravity run, into conditions nobody has
ever tested. PYRA is built to make that specific mistake hard to commit by accident.

## What it does

It reads the NASA evidence, records the conditions each investigation actually covered,
and then, for any scenario you ask about, tells you one of three things: this is covered
by evidence, this is near evidence and here is how far off, or nobody has tested this.

The third answer is the one most tools will not give you, and it is the one that matters.

## Try it

From the repository root, with Python 3.11 or newer:

```bash
python tools/psi_evidence_report.py
```

That checks every supplied NASA file against its recorded SHA-256, reads the
investigation metadata straight out of the PSI archives, and then reports, scenario by
scenario, exactly which variable stops the evidence from reaching it.

Today it answers "no evidence" for all five habitat scenarios, and names the missing
axis for each. That is a real result about the state of the data, not a placeholder.

## What makes it different

Most tools in this space answer every question. PYRA's distinguishing feature is that it
refuses to, and says precisely why.

That refusal is enforced by a library we wrote for this problem, **pyrakit**, which lives
in `pyra_library/pyra-repo/pyra/`. It is the reusable part of the project, usable outside
this repository, and it contains four ideas we have not seen combined elsewhere:

- **A scenario-aware claim gate.** Asking "is this model validated?" is the wrong
  question. `require_in_envelope(card, scenario)` asks whether the recorded evidence
  reaches *these conditions*, axis by axis, with unit conversion. A model validated at
  1 g is refused for a microgravity scenario, and the refusal names the axis and the
  distance.
- **Status that can only weaken.** Every value carries an epistemic status, and combining
  them takes the weakest. A simulation fed a hypothetical input yields a hypothetical
  result; it cannot quietly become evidence further down a calculation.
- **Provenance with tamper detection.** Values carry a content hash and a lineage graph,
  so a number that was edited after the fact fails verification instead of passing
  silently.
- **An engine bridge that does not trust the engine.** An external solver runs as a
  separate process over a documented JSON contract. Its output is structurally validated
  — units parsed, series lengths matched against the time base — before anything plots it.

The honest framing: PYRA is the evidence and validation layer, not the solver. A solver
can be plugged in; what PYRA adds is the discipline around it.

## Educational impact

The same machinery teaches the reasoning it enforces.

Fire safety is usually taught with formulas. The harder lesson — that a number means
nothing without its units, its uncertainty, its source and the conditions it was measured
under — is normally learned late, by being wrong in public. PYRA makes that lesson
structural: a beginner who opens the Fire Playground sees every view labelled by where it
came from, and cannot confuse a drawing with a solver result, because the window says
which it is.

The learning path runs from changing one setting in a window, through units and evidence
status, to measured PSI data, and ends at uncertainty-aware comparison against real
experiments. Each step is runnable, and the beginner interface is the same library the
advanced path uses — not a simplified toy that has to be unlearned.

```python
import pyrakit as pk

run = pk.run_fire_test(fuel="PMMA", oxygen_fraction=0.21, gravity_g=0.0)
print(run.summary())
```

That prints its own scope limits alongside its numbers, every time.

## The NASA data

Nine supplied files in `datasets/`, covering five investigations, all checksum-verified:

| Investigation | PSI study | DOI |
| --- | --- | --- |
| Burning and Suppression of Solids-II | PSI-25 | 10.60555/4qc4-de67 |
| Flame Extinguishment Experiment | PSI-69 | 10.60555/mbq8-0451 |
| Spacecraft Fire Safety Experiment-I | PSI-98 | 10.60555/0t15-1z43 |
| Smoke Point In Co-flow Experiment | PSI-107 | 10.60555/9kbh-e962 |
| ACME chamber / PSI-159 raw setpoints | PSI-159 | see `datasets/manifest.csv` |

`sources/sources.csv` tracks 23 documentary sources. Four have been checked against the
NTRS records and the supplied archives; the log is in `sources/verification_log.md`.
One of those checks rejected a source: NTRS 20170002628 is a July 2016 status
presentation with no abstract, so it cannot report Saffire I-III results, and it is
marked accordingly rather than quietly used.

Nineteen sources remain unverified. That number is published here deliberately. A
project about where evidence runs out has to apply the same standard to its own source
list.

## Layout

| Path | What it is |
| --- | --- |
| `pyra/` | The application: fact-sheet ingestion, SQLite build, ranking, gap engine, retrieval |
| `pyra_library/pyra-repo/pyra/` | **pyrakit**, the reusable library, with its own tests and docs |
| `datasets/` | The supplied NASA files, unmodified, with checksums |
| `sources/` | The documentary source list and its verification log |
| `tools/` | Checkers and the evidence report |
| `docs/WORKFLOW.md` | Contributor process: verifying sources, building the database |

Note that `pyra/` (the application) and `pyrakit` (the library) are different packages
with different jobs. The library was renamed from `pyra` to `pyrakit` precisely so the
two can never be confused by an import.

## What PYRA will not claim

- It does not predict whether a material will burn in a given habitat.
- It does not certify anything as safe.
- Its built-in simulation is a simplified oxygen balance for teaching, clearly labelled
  as such, and is not a flame solver.
- A result marked `SIMULATED` is a model output. It is not evidence, and PYRA will not
  let it be presented as evidence.

Where the evidence does not reach, the honest answer is that nobody knows yet. PYRA is
built to give that answer clearly instead of hiding it behind a number.
