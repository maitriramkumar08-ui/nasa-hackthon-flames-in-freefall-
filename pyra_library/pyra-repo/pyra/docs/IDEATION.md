# PYRA / pyrakit: design and ideation base

This is the reasoning behind the library: what it is for, what it refuses to do, which
ideas are borrowed and from where, and how the parts fit together. It is a design
document, not a tutorial. Start at `usage.md` if you want to use the library.

Status: this document describes a target. Sections marked **built** exist today;
sections marked **planned** do not. Nothing here should be read as a claim that the code
already does it.

---

## 1. What this library is for

PYRA answers one question honestly: **given what has actually been measured about fire in
microgravity, what can be said about a fire in this habitat, and what cannot?**

It is not a fire simulator competing with FDS or Cantera. It is the layer around a
simulator that keeps track of where the evidence is, what a result's epistemic status is,
and whether a claim is supported by anything at all.

### Scope discipline

The domain is spacecraft fire safety. It is deliberately narrow.

Broadening to "space exploration" generally would destroy the thing that makes the library
coherent: every type in it assumes conditions describable by gravity, pressure, oxygen
fraction, flow and fuel. A library that also handles orbital mechanics would share nothing
with this except the word "space".

The ecosystem pattern from `astropy` is the right answer to growth: a small, strict core,
with separate affiliated packages for other domains that depend on the core's types rather
than enlarging them. If a second domain is ever needed, it attaches; it does not merge.

### The thesis: negative space

Most tools in this area answer every question asked of them. PYRA's distinguishing feature
is that it declines, and says precisely why.

The scientific reason is specific. Without buoyancy there is no rising plume to carry
smoke away and draw fresh air in, so the dominant transport mechanism behind Earth
flammability testing is simply absent in orbit. Earth data therefore does not transfer by
default, and a confident number extrapolated across that gap is worse than no number,
because it is actionable and wrong.

---

## 2. Design principles

These are testable, not aspirational. Each one is enforced somewhere.

1. **A value carries its own meaning.** Magnitude, unit, uncertainty, epistemic status and
   provenance travel together. There are no bare floats in the public API. *(built:
   `Quantity`, `Measure`)*
2. **Status can only weaken.** Combining values takes the weakest status, so a simulated
   or hypothetical input can never silently become evidence downstream. *(built: `join`)*
3. **Absence is recorded, not defaulted.** An unknown uncertainty is `None`, not zero. An
   unset field is unset, not a guess. *(built: `u_kind="unknown"`, optional form fields)*
4. **Claims are gated on the scenario, not on paperwork.** Asking "is this model
   validated?" is the wrong question; the right one is whether the recorded evidence
   reaches *these conditions*. *(built: `require_in_envelope`)*
5. **Refusals explain themselves.** Every rejection names the axis, the recorded limit and
   the distance. A refusal with no reason is a bug. *(built: `EnvelopeCheck.explain`)*
6. **Failures are loud and early.** A malformed model card raises on read rather than
   widening an envelope silently. *(built: `parse_envelope`)*
7. **The library holds itself to its own standard.** PYRA's own solver ships a model card
   with a narrow envelope and passes through the same gate as a third-party engine.
   *(planned)*
8. **Every documented example runs in CI.** Documentation that drifts from the code is a
   defect. *(built: doctests over `usage.md`)*

---

## 3. Prior art: what is borrowed, and from where

The point of this section is that almost nothing here is novel in isolation. The
contribution is the combination, applied to a domain where it is usually missing.

### Values, units and metadata

| Source | Idea | How it is used here |
| --- | --- | --- |
| **Pint** | A single unit registry; dimensionality checked, not string-matched | Already the only source of unit truth. Envelope limits are converted before comparison, so kPa and Pa cannot be confused |
| **pydantic** | Parse, don't validate: invalid states unrepresentable | `Conditions`, `Scenario`, `ModelCard` are frozen and validated at construction |
| **astropy.nddata** | One object carries data, uncertainty, mask and metadata together | The model for `Quantity`; the same principle should extend to array data |
| **astropy.units.physical** | Dimensional analysis as a first-class operation | Direction for `physics/similarity.py` |
| **xarray** | Labelled dimensions, coordinates and attributes on N-D arrays | The right container for solver field output as `SimulationOutput` grows beyond channels |

### Combustion and fire science

| Source | Idea | How it is used here |
| --- | --- | --- |
| **Cantera** | Thermodynamics, kinetics, transport; 1-D flame solvers (`FreeFlame`, `CounterflowDiffusionFlame`) | **Adapt, do not reimplement.** Cantera is the obvious first real adapter: it is mature, validated and open. PYRA's job is to wrap it with a model card and an envelope |
| **FDS (NIST)** | The standard fire CFD code; well-defined output formats | Second adapter target. `fdsreader` is already an optional dependency |
| **NASA-STD-6001** | Standardised upward flame propagation test | The Earth-normative baseline that PYRA exists to say does *not* transfer |
| **OpenFOAM** | General CFD with combustion solvers | Third adapter target; stub already exists |

The single most important decision in this section: **PYRA does not try to beat Cantera at
combustion.** Where a validated solver exists, PYRA adapts it. The one solver PYRA owns
(section 5) exists because nothing lightweight covers opposed-flow spread over a thin solid
at interactive speed, not because reimplementation is a goal.

### Evidence, provenance and reproducibility

| Source | Idea | How it is used here |
| --- | --- | --- |
| **W3C PROV-O** | Provenance as a standard graph of Entity, Activity and Agent | Export the ledger as PROV-JSON so lineage is interoperable, not bespoke. Fills `provenance/export_prov.py` |
| **ISA-Tab / isatools** | Investigation / Study / Assay metadata hierarchy | **The NASA PSI archives are literally ISA-Tab** (`i_Investigation.txt`, `s_PSI-*.txt`). Read them with the real model instead of ad-hoc parsing |
| **RO-Crate** | Package data, metadata and provenance into one citable object | Fills `service/export_bundle.py`: a run should export as a self-describing bundle |
| **DataCite / CITATION.cff** | Citable software and datasets with DOIs | Already present; connect model cards to dataset DOIs |
| **MLflow, DVC** | A run is a first-class, queryable object with parameters, metrics and artifacts | The shape `EngineStudy` is reaching for; borrow the vocabulary, not the dependency |
| **Pandera, Great Expectations** | Declarative data contracts that produce a validation *report*, not just a boolean | Direction for `normalize/qc.py`: QC should explain, like the envelope gate does |

### Uncertainty and sensitivity

| Source | Idea | How it is used here |
| --- | --- | --- |
| **SALib** | Sobol and Morris sampling and index estimation | The reference for `sensitivity/`; already an optional dependency |
| **emcee** | Ensemble MCMC for calibration | `uq/calibrate.py` |
| **GUM (JCGM 100:2008)** | Type A / Type B uncertainty classification | Already encoded in `u_kind`; keep the vocabulary standard rather than inventing one |
| **scikit-learn, GPy** | Gaussian-process surrogates with predictive variance | `surrogate/` — deferred; only useful once there is a solver worth emulating |

### Rust in Python

| Source | Idea | How it is used here |
| --- | --- | --- |
| **Polars, Ruff, pydantic-core** | Proof that a Rust core behind a Python API is a mainstream, maintainable architecture | The precedent for section 5 |
| **PyO3** | Safe Rust bindings to CPython | The binding layer |
| **rust-numpy** | Zero-copy views between `numpy` arrays and `ndarray` | Arrays cross the boundary without copying |
| **maturin** | Build and publish mixed Rust/Python wheels | Build backend |
| **rayon** | Data parallelism from a sequential iterator | Monte Carlo and parameter sweeps |

### Teaching

| Source | Idea | How it is used here |
| --- | --- | --- |
| **Diátaxis** | Four documentation modes: tutorial, how-to, reference, explanation, never mixed | Restructure `docs/`; most confusion in this project came from mixing them |
| **Jupyter / MyST / Sphinx-Gallery** | Executable prose; the example *is* the test | Already true via doctests; extend to notebooks |
| **nbgrader** | Exercises with machine-checkable answers | Direction for `learn/`, which `edu/badges.py` already gestures at |
| **Software Carpentry** | Teach the workflow, not just the syntax | The learning spine in section 6 |

---

## 4. Architecture

### Layers

Dependencies point downward only; this is enforced by a test.

```
  studio      playground, CLI, workflows, export          (user-facing)
  learn       lessons, explainers, guided paths
  analysis    compare, matching, coverage, uq, sensitivity
  models      adapters, model cards, envelopes, simulation contract
  physics     similarity, calorimetry, zone, flame
  evidence    schema, provenance, ledger, io, catalog
  core        the Rust numerical kernel                   (no domain knowledge)
```

`core` knows nothing about fire. It takes arrays and parameters and returns arrays. All
meaning — units, status, provenance — is attached above it. That boundary is what keeps the
Rust surface small and stable.

### Data flow

```
  PSI archive / NTRS paper
        -> evidence.io          parse, hash, record source
        -> evidence.schema      validated Conditions with units
        -> models.ModelCard     what was covered, as an envelope
                                           |
  user scenario -> studio form -> schema.Scenario
                                           |
                                  models.require_in_envelope
                                     /                \
                            refuses, with           permits
                            the failing axis           |
                                                core.flame_spread
                                                       |
                                          simulation.SimulationOutput
                                                       |
                                     analysis.compare vs experiment
                                                       |
                                           studio.explain / report
```

---

## 5. The Rust core

**Decision: the numerical core is Rust, and it is the only implementation that ships.**

### What goes in

Each of these is a tight numerical loop with a stable, array-shaped signature:

- **1-D flame spread** over a thin solid in opposed or concurrent flow. The solver the
  project currently lacks, and the reason the Playground graph is only an oxygen balance.
- **Zone model integration**, replacing the closed-form single-zone solution so that
  time-varying ventilation becomes possible.
- **Monte Carlo uncertainty propagation**, currently `n=1024` in Python; in Rust 10⁶
  samples is cheap, which turns noisy histograms into smooth distributions.
- **Sobol and Morris sampling and indices**, which need thousands of model evaluations.
- **Parameter sweeps** over a scenario grid, parallel via `rayon`.

### Why not write everything in Rust?

This is the right question to ask, and the answer is not "because Python is easier". It is
worth separating two claims that sound alike:

- **"All computation happens in Rust."** This is correct and is what this document
  specifies. No numerical loop should live in Python.
- **"All code is Rust."** This is a different claim, and the case against it is specific.

#### What the measurements say

Timings from this library on the development machine, median of repeated runs:

| Operation | Time | What dominates |
| --- | --- | --- |
| Zone solve, 61 steps | 17.4 us | Arithmetic |
| `run_fire_test`: solve plus schema validation plus wrapping | 28.1 us | Arithmetic (62%) |
| `heat_release`, Monte Carlo n=1024 | 2.8 ms | Arithmetic |
| `heat_release`, Monte Carlo n=65536 | 143 ms | Arithmetic |

Two things follow.

The schema, validation and object-wrapping layer costs about **11 microseconds** per call.
Rewriting that in Rust saves microseconds that nobody will ever observe, at the cost of
losing `pydantic` and `pint`. That is a bad trade at any exchange rate.

The Monte Carlo at 65536 samples takes **143 milliseconds** and scales linearly, so a
million samples would take roughly 2.2 seconds. That is exactly the kind of number that
makes a learner stop exploring. A 20x speedup turns it into something interactive. **That**
is where Rust belongs, and the measurement says so without anyone needing an opinion.

The rule that falls out: **Rust where the loop count is large and the signature is
array-shaped. Python where the work is one-shot and the value is in the metadata.**

#### The ecosystem argument, which is the strongest one

Performance is not the reason Python stays. Dependencies are.

The library currently rests on `pint` for units, `pydantic` for schema, and `numpy` and
`scipy` for numerics. Section 3 commits to adapting **Cantera** rather than reimplementing
combustion, and plans adapters for **FDS** via `fdsreader`, plus **SALib** for sensitivity
and **emcee** for calibration. Section 8 adds **REBOUND**, **poliastro**, **Skyfield** and
**spiceypy**.

Not one of those has a Rust equivalent of comparable maturity. Several have no Rust
binding at all. Choosing all-Rust does not mean porting some code; it means either
rewriting `pint` and `pydantic`, or giving up Cantera and doing combustion ourselves,
which section 3 explicitly rejects as the project's worst possible use of time.

Rust does have `uom` for units, `serde` for serialisation, `ndarray` for arrays and
`plotters` for charts, and they are good. But they do not cover a combustion solver, a
PSI/ISA-Tab reader, an MCMC sampler and a Sobol estimator, which is what this project
actually needs.

#### The audience argument

This is an educational library for people studying fire safety and combustion. They write
Python. They work in notebooks. A Rust-only library would be technically excellent and
almost entirely unused by the people it is for, and "can a student import it and poke at
it" is a product requirement, not a convenience.

#### The honest counter-argument

If the primary goal is **to learn Rust deeply**, then all-Rust is genuinely the better
choice for that goal, and the ecosystem argument is beside the point: nobody learns a
language by writing glue around someone else's solver.

Those two goals do not have to be traded off, and the resolution shapes the design:

**Write the Rust crate as a legitimate standalone library, with the Python bindings as one
consumer of it rather than its only reason to exist.**

```text
pyrakit-core/          a real Rust crate; usable from Rust with no Python anywhere
  src/lib.rs           flame spread, zone, monte carlo, sobol, nbody, geodesics
  benches/             criterion benchmarks
  examples/            runnable pure-Rust examples

pyrakit/               Python distribution
  rust/                thin PyO3 binding layer that depends on pyrakit-core
  python/pyrakit/      API, schema, provenance, orchestration
```

Under that split, "all the simulation is in Rust" is literally true, the crate stands on
its own merits, the Rust is learned properly rather than as binding boilerplate, and
Python users still get a library they can actually use. The binding layer is deliberately
thin and boring, which is what a binding layer should be.

#### What is therefore in each language

**Rust, without exception:** flame spread, zone integration, Monte Carlo propagation,
Sobol and Morris indices, parameter sweeps, N-body force summation, Barnes-Hut traversal,
geodesic integration.

**Python:** schema and validation, provenance and lineage, the ledger, file readers,
adapters to external engines, the CLI, the Playground, and all teaching material.

**Neither, by choice:** combustion chemistry, transport properties and detailed kinetics.
Those come from Cantera, which has decades of validation behind it. Reimplementing them in
any language would be the single worst use of time available to this project.

### The boundary rule

**Arrays and plain numbers cross; objects do not.** No PyO3 type mirrors a pydantic model.
Keeping the interface array-shaped is what lets `pyrakit-core` stand alone as a Rust crate
rather than becoming a pile of binding glue.

### The cost, stated plainly

Making Rust the only implementation means `pip install` from source requires a Rust
toolchain. Mitigations, in order of importance:

1. **Publish wheels in CI** for Linux, macOS and Windows via `maturin-action`. Almost
   nobody then compiles anything, and `pip install pyrakit` stays a single command.
2. **Pin the toolchain** in `rust-toolchain.toml` so builds are reproducible.
3. **Document the source path** for contributors who want to build locally.

### Keeping the validation discipline without a shipped fallback

Dropping the pure-Python backend removes the obvious way to prove the Rust is right. The
replacement, which is stricter:

- A **Python reference implementation lives in `tests/reference/`**, is never shipped, and
  is written for clarity rather than speed.
- Property tests assert the Rust kernel and the reference agree within tolerance over
  randomly generated inputs (`hypothesis`).
- Where a closed-form solution exists — the constant-coefficient zone model, de Ris's
  opposed-flow spread limit — the kernel is checked against **analytic truth**, not just
  against another implementation.
- Conservation invariants are asserted as properties: mass and energy balance, oxygen
  bounded in [0, 1], monotonic time.

This is better than a shipped fallback. A fallback proves two implementations agree; an
analytic check proves one of them is right.

### Honesty constraint on our own solver

The flame solver is a simplified model and will be labelled as one. It ships with a model
card declaring a deliberately narrow validation envelope, and callers reach it through
`require_in_envelope` exactly as they would a third-party engine. If the project will not
hold its own solver to that standard, the standard is decoration.

---

## 6. The learning spine

Each step is runnable, and each produces something the next step consumes. Ordered so that
no step requires an idea from a later one.

| # | Step | Teaches | Artifact |
| --- | --- | --- | --- |
| 1 | First program | The API exists; a script must `print` | `heat_release_example.py` |
| 2 | Units and status | A number without a unit is not a measurement | `Quantity`, `Measure` |
| 3 | Provenance | Where did this come from, and has it been altered | `explain()` |
| 4 | Real NASA data | Reading PSI archives; metadata is evidence too | `psi_evidence_report.py` |
| 5 | Similarity | Why Earth data does not transfer; dimensionless groups | `transferability()` |
| 6 | Running a solver | Models produce output, not truth | `core.flame_spread` |
| 7 | Uncertainty | Inputs are distributions, so outputs are too | Monte Carlo propagation |
| 8 | Comparison | Scoring a model against an experiment, with tolerance | `pyrakit.compare` |
| 9 | Writing an adapter | Integrating any engine behind the contract | `fake_engine.py` |
| 10 | Contributing evidence | Verifying a source, filling a model card | `verification_log.md` |

Step 5 is the intellectual centre and is currently missing entirely.

### Why dimensionless numbers matter here

`conditions/scaling.py`, `conditions/similarity.py` and `physics/scaling.py` are all empty
stubs today, and they are the most important gap in the library.

Grashof number scales with gravity. As *g* → 0, Gr → 0, and buoyant transport — the
mechanism underpinning Earth flammability testing — vanishes. Reynolds, Damköhler and
Péclet then say which of the remaining mechanisms still dominate.

That is not decoration. It is the mathematical statement of the project's thesis, it is how
combustion scientists actually reason about transfer, and the library currently cannot
express it.

---

## 7. Higher-order API

Functions that coordinate real work rather than wrapping a formula.

**`explain(quantity) -> str`** *(planned)*
Walks a value's lineage and narrates it: what it was derived from, which inputs were
measured versus assumed, what its status means, and whether its hash still verifies. The
lineage graph and tamper detection are already built; nothing reads them aloud. This is
the best single teaching function available at low cost.

**`transferability(source, target) -> TransferReport`** *(planned)*
Compares two condition sets by dimensionless group and reports which physics still carries
over. *"Reynolds matches within 8%. Grashof differs by five orders of magnitude: buoyant
transport does not transfer. Do not extrapolate flame height."*

**`nearest_evidence(scenario, catalogue) -> Ranking`** *(planned)*
Not merely covered or uncovered, but how far and along which axis, naming the closest real
experiment. The per-axis distance is already computed inside the envelope check; this
surfaces it as a question anyone can ask.

**`sweep(scenario, over=..., values=[...]) -> SweepResult`** *(planned)*
A parameter study returning a comparable set. How people actually learn a model's
behaviour, and the natural bridge into sensitivity analysis.

**`run_engine_study(...)` → `EngineStudy`** *(built)*
Gates, runs, records the scenario beside the output, optionally compares against a
measurement.

---

## 8. A second domain: celestial simulation

**Status: planned, and deliberately separate from the fire-safety core.**

### Why this is not scope creep, and the condition that keeps it from becoming so

Section 1 argues against broadening to "space exploration" generally, and that argument
still holds: the fire-safety types assume a combustion scenario and would be ruined by
being made generic.

Celestial simulation attaches a different way. It does not extend the fire types; it
*reuses the discipline*. The claim gate, the status algebra and the model card are not
about fire at all. They are about any model with a limited domain of validity, and
gravitational solvers have exactly that:

- A **Newtonian N-body** integrator is valid until a close encounter makes the timestep
  inadequate, or until relativistic corrections matter near a compact object.
- A **Schwarzschild geodesic** integrator assumes a non-rotating, uncharged, isolated
  mass, and says nothing correct about a spinning black hole, where the Kerr metric is
  needed instead.
- A **Barnes-Hut approximation** with opening angle `theta` is an approximation whose
  error grows with `theta`; at `theta = 0` it degenerates to the exact O(N^2) sum.

Each of those is a validation envelope. Running a Newtonian integrator through a close
encounter and presenting the result as truth is the same mistake as extrapolating an
Earth-gravity flame test to orbit, and PYRA already has the machinery to refuse it.

That is the real argument for this module: **it demonstrates the framework generalises.**
A reader who sees the same gate refuse both a flame claim and an orbital claim understands
the idea far better than one who sees it applied once.

**The condition:** this lives as a separate, optional module that *depends on* the core
and is never imported by it. The dependency arrow points one way, enforced by the same
layering test that governs everything else. If that rule is ever relaxed, the fire-safety
core starts carrying gravitational baggage and section 1 was right after all.

### Why it is an excellent fit for the Rust core

Everything in this domain is a tight numerical loop over many bodies or many rays, with a
stable array-shaped signature. It is the clearest possible justification for section 5,
and it parallelises cleanly with `rayon`.

### Staged projects, easiest to hardest

**Stage A - Two-body and Kepler orbits.** Closed-form solutions exist, so this is where
the validation story is strongest. Propagate an orbit, recover the orbital elements, and
check them against the analytic answer.

**Stage B - N-body with a symplectic integrator.** The educational core of the whole
module, for one reason: **integrator choice is visible in the physics.** Naive Euler
spirals bodies outward and manufactures energy from nothing. RK4 is more accurate per step
but still drifts secularly. A symplectic integrator - leapfrog or velocity-Verlet -
conserves energy to a bounded oscillation over millions of steps because it preserves
phase-space volume. Plotting total energy against time for all three is one of the best
physics lessons available in a few hundred lines, and it is a lesson about *numerical
method*, not just about gravity.

**Stage C - Barnes-Hut.** Replace the O(N^2) force sum with a quadtree (2-D) or octree
(3-D), reducing it to O(N log N) and making tens of thousands of bodies interactive. This
is exactly what `TheSandwichCoder/GravSim` does in its `qtree.rs`. The teaching point is
the accuracy/speed trade-off made explicit through the opening angle `theta`, which is a
tunable approximation error and therefore a model-card envelope parameter.

**Stage D - Gravitational lensing by geodesic integration.** Trace rays *backwards* from
the camera through curved spacetime and see where they came from. In the Schwarzschild
metric the null geodesic equation, written in terms of `u = 1/r`, is

```text
d2u/dphi2 + u = 3 G M u^2 / c^2
```

where the right-hand term is the entire relativistic correction; drop it and a straight
line comes back. That single term is the whole of light bending, and being able to switch
it off is the clearest demonstration of general relativity a learner can run.

**Stage E - Accretion disk and realtime rendering.** The visually spectacular end state,
and where GPU compute becomes necessary. `kavan010/black_hole` reaches this with an OpenGL
compute shader (`geodesic.comp`) alongside a CPU reference (`CPU-geodesic.cpp`).

### Analytic checks: how to prove the solver is right

Consistent with section 5, correctness comes from analytic truth rather than from a second
implementation. This domain is unusually rich in exact answers:

| Check | Exact value | Catches |
| --- | --- | --- |
| Circular orbit period | Kepler's third law, `T^2 = 4 pi^2 a^3 / GM` | Force law and unit errors |
| Energy, symplectic integrator | Bounded oscillation, no secular drift | Wrong integrator or timestep |
| Angular momentum | Conserved exactly for central forces | Asymmetric force accumulation |
| Photon sphere | `r = 1.5 r_s` | Geodesic integration errors |
| Innermost stable circular orbit | `r = 3 r_s` | Effective-potential mistakes |
| Light deflection at the solar limb | 1.75 arcseconds | Magnitude of the relativistic term |
| Barnes-Hut at `theta = 0` | Identical to the direct O(N^2) sum | Tree traversal bugs |
| Two-body reduction | N-body with N=2 matches the Kepler solution | Multi-body bookkeeping |

The last one is a particularly good property test: the general solver must reproduce the
special case it contains.

### References, and what to take from each

| Source | What it is | What to take |
| --- | --- | --- |
| **`TheSandwichCoder/GravSim`** | N-body with collisions, pure Rust, separate `render.py` | The closest architectural match to what we want: Rust computes, Python renders. Its `qtree.rs` is a Barnes-Hut quadtree. Note it has no PyO3 and writes output for Python to read; ours should bind directly instead |
| **`kavan010/black_hole`** | C++17, OpenGL, geodesic ray tracing, accretion disk, spacetime grid | The staged ambition: 2-D lensing, then CPU geodesics, then a GPU compute shader. Keeping a CPU reference beside the GPU version is the same discipline as our reference implementations |
| **REBOUND** | The N-body integrator used in professional astronomy; C core with Python bindings | **The single best architectural reference for this project.** It is precisely "fast compiled core, ergonomic Python API". Study `WHFast` and `IAS15`, and how it exposes integrator choice as a first-class user decision |
| **poliastro / astropy** | Orbital mechanics built on `astropy.units` | Unit-safe orbital elements; confirms unit-carrying quantities work at this scale |
| **Skyfield** | High-precision positions from real ephemerides | Where real data enters, as opposed to synthetic initial conditions |
| **SPICE / spiceypy** | NASA NAIF's own ephemeris and geometry toolkit | The authoritative NASA source for real body positions. A direct NASA-data tie, as PSI is on the fire side |
| **Einstein Toolkit** | Research-grade numerical relativity | Only as a reality check on how far a learning project should go. Full numerical relativity is out of scope and should be said so plainly |
| **`ndarray`, `nalgebra`, `rayon`** | Rust numerics and data parallelism | The computational substrate |
| **`wgpu`** | Portable GPU compute in Rust | The route to stage E without tying to OpenGL |

### How it would be structured

```text
pyrakit_celestial/              separate distribution, depends on pyrakit
  rust/src/
    nbody.rs                    direct and Barnes-Hut force summation
    integrators.rs              euler, rk4, leapfrog: all three, to compare
    geodesic.rs                 Schwarzschild null geodesics
  python/pyrakit_celestial/
    bodies.py                   Body and System, built on pyrakit units and Quantity
    cards.py                    model cards and envelopes for each integrator
    lessons/                    the energy-drift comparison, the lensing toggle
```

Each integrator ships a model card. The Newtonian one declares that it is invalid inside
some multiple of the Schwarzschild radius; the Barnes-Hut one declares its `theta`. Asking
for a claim outside those limits is refused by the same gate the flame solver uses, which
is the whole point of putting this inside PYRA rather than writing a standalone simulator.

### Honest warning

This is a larger project than the flame solver, and the flame solver is already the thing
most likely to consume all available time. Stage A is an afternoon. Stage B is a weekend
and is where most of the teaching value sits. Stages D and E are substantial projects on
their own, and `kavan010/black_hole` has 2.7k stars precisely because doing them well is
hard.

For the hackathon submission specifically, this module is a **liability rather than an
asset**: the challenge is spacecraft fire safety, and Relevance is judged on tight
alignment. Build it after submission, or keep it clearly separate and leave it out of the
entry.

## 9. Recalibration of the current tree

### The naming problem

Today the library sits at `pyra_library/pyra-repo/pyra/`, three nested directories named
after a package that is now called `pyrakit`, inside a repository whose application
package is *also* called `pyra`. The GitHub repository has already been renamed to
`pyrakit`.

Target:

```text
pyrakit/                      (was pyra_library/pyra-repo/pyra/)
  core/                       standalone Rust crate, no Python anywhere
    Cargo.toml                publishable to crates.io in its own right
    src/lib.rs                flame, zone, monte carlo, sobol, nbody, geodesics
    benches/                  criterion benchmarks
    examples/                 runnable pure-Rust examples
  bindings/
    Cargo.toml                thin PyO3 layer depending on core
    src/lib.rs
  python/pyrakit/             the Python API
  pyproject.toml              build-backend = "maturin"
  rust-toolchain.toml         pinned, so builds are reproducible
  tests/
    reference/                pure-Python reference implementations, never shipped
  docs/
```

Splitting `core` from `bindings` is what makes "all the simulation is in Rust" literally
true while keeping the crate worth reading on its own. A reader who has never used Python
can `cargo run --example` their way through the physics.

### Module consolidation

42 of the library's module files are empty "not yet implemented" stubs. An empty
`recommend/boundary.py` is not a placeholder, it is a promise the repository does not keep.

| Package | Real lines | Action |
| --- | --- | --- |
| `service` | 1152 | Keep, rename to `studio` |
| `adapters` | 645 | Keep, fold into `models` with `simulation` |
| `provenance` | 607 | Keep, fold into `evidence` with `schema`, `io` |
| `simulation` | 333 | Keep, fold into `models` |
| `io` | 258 | Keep, fold into `evidence` |
| `physics` | 191 | Keep and grow: this is where `similarity` lands |
| `schema` | 179 | Keep, fold into `evidence` |
| `compare`, `matching`, `coverage`, `uq` | 153 / 142 / 54 / 106 | Keep, fold into `analysis` |
| `edu` | 63 | Keep, rename to `learn`, grow substantially |
| `report`, `units` | 50 / 38 | Keep as-is |
| `derive`, `normalize`, `conditions`, `catalog`, `cluster`, `recommend`, `surrogate`, `viz` | 4–7 each | **Delete.** Re-create only when something real is written. `conditions` reappears as `physics/similarity.py`; `viz` is already served by the playground |
| `sensitivity` | stub | Keep the name; implement in Rust |

Deleting the empty packages is the cheapest structural improvement available: it removes
roughly a third of the tree and makes what remains look finished rather than abandoned.

### Compatibility

`pyra` and `pyra_library` remain as thin aliases so existing scripts keep working. They
cost almost nothing and protect material already written against the old names.

---

## 10. Risks and open questions

**The solver is where projects die.** A 1-D flame spread solver is a real numerical
methods project, and "it runs" is not "it is right". The analytic checks in section 5 are
the mitigation, and they are not optional. If they cannot be made to pass, the correct
outcome is to ship no solver and adapt Cantera instead.

**Rust-only raises the contribution barrier.** A teammate without a toolchain cannot build
from source. CI wheels solve this for users but not for contributors.

**Scope creep toward "space exploration" would be fatal.** The types in this library
assume a combustion scenario. Resisting that expansion is a design decision, not an
oversight.

**The evidence layer is still mostly empty.** Four of 23 sources are verified and the
database has no factsheets. No amount of architecture substitutes for that, and it remains
the highest-value work in the project.

**Unresolved:** whether the Playground keeps a Tk front end or moves to a browser UI once
the solver is fast enough to animate. Tk is dependency-free and works offline; a browser
gives better plotting. Not urgent until the solver exists.

---

## 11. Order of work

Each stage is independently valuable and sets up the next. Stopping after any stage leaves
something coherent.

1. **Delete the empty stubs.** An hour; the repository immediately reads as finished.
2. **Flatten the directory nesting** to `pyrakit/`, with aliases kept.
3. **`explain()`.** Pure Python, uses what exists, demonstrates the differentiator aloud.
4. **`physics/similarity.py`.** Dimensionless groups; real science; justifies the thesis.
5. **Stand up the Rust core**: create `core/` as a standalone crate with one real kernel
   and a `criterion` benchmark, then `bindings/` with `maturin` and CI wheels. Proving the
   crate builds and runs with `cargo` alone, before any Python touches it, is what keeps
   the split honest.
6. **Monte Carlo propagation in Rust**, validated against the existing Python results.
7. **The flame solver**, with analytic checks, a model card and a narrow envelope.
8. **Sensitivity indices**, which need the solver to be worth sampling.

Stages 1 to 4 need no Rust at all. Stage 5 is the first that cannot be undone cheaply.

The celestial module in section 8 sits outside this sequence entirely. It shares the Rust
toolchain set up at stage 5 and the model-card machinery that already exists, so the
cheapest entry point is stage A once stage 5 is done. It should not displace any of the
eight stages above before the hackathon submission.
