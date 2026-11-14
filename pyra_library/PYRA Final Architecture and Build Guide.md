# PYRA: Final Architecture and Build Guide

*Predictive Hazard & Reliability Atlas for Spacecraft Fire Safety. A fire-only Python library that connects NASA microgravity combustion evidence to spacecraft fire simulations, with research, education and build interfaces. Final consolidated version, 14 November 2026. 'Predictive' names the long-term goal; the library claims prediction only where validation supports it (section 1).*

Package and API choices below come from my knowledge of the scientific Python ecosystem. Versions, licences and exact APIs were not re-verified and must be checked at implementation time.

## 0. Final decisions and reading map

PYRA is a fire-only library: its value is a trustworthy bridge between NASA microgravity combustion evidence and the simulations used for spacecraft fire safety. Five decisions govern everything below.

1. **Scope is spacecraft and habitat fire only** (microgravity and partial gravity). It is not a general NASA data library. Breadth would dilute the physics, the validation and the credibility. Other domains could reuse the adapter and schema design later, but that is out of scope for v1.
2. **Physics and simulation come first.** The engine verifies the physics it implements itself (calorimetry, scaling, reduced-order models) and delegates flame-resolved and vehicle-scale simulation to external codes that carry validation evidence (section 17).
3. **The library is the core.** The CLI, notebooks, education web app and educator kit are thin interfaces that call the library through a public interface and never modify evidence (sections 18 and 19).
4. **No unqualified predictions.** Every output is typed Measured, Derived, Simulated, Scenario or Interpretation. A model-supported statement requires a validated model whose envelope covers the scenario (sections 1, 3 and 9).
5. **The library is built with an AI-assisted, test-first workflow** using the project rules and prompt library in section 20.

| If you want to... | Read |
| --- | --- |
| Understand what PYRA will and will not claim | 1, 3, 9, 17 |
| Implement the core library | 4 to 14, 19, 20 |
| Understand the physics and external simulation coupling | 7, 9, 17 |
| Plan the education and outreach layer | 18, 19 |
| Build it with an AI coding assistant | 20 |
| Check the research basis and sources | 21 |
| See the combined plan | 15 (core phases) and 19 (consolidated roadmap) |

## 1. Scope, and what PYRA must not claim

PYRA organizes, compares and interprets experimental evidence relative to simulation scenarios. It is built around capability tiers:

| Tier | Capability | Needs a validated external model? |
| --- | --- | --- |
| T0 | Access, normalize and catalogue experiments | No |
| T1 | Match scenarios to experiments; report evidence coverage and gaps | No |
| T2 | Compare simulation output with measurements, with uncertainty | A simulation supplied by the user |
| T3 | Calibrate effective parameters; interpolate inside the measured envelope | No, but claims are statistical and bounded |
| T4 | Predict fire behaviour outside measured conditions | Yes: a validated model plus a declared validity envelope |

**Hard rule.** PYRA never emits an unqualified prediction. Every output is a typed statement (section 3). A T4-style statement is produced only if a registered ModelCard has a validation envelope covering the scenario, and the envelope is itself computed from comparisons against measurements. Otherwise PYRA outputs coverage and gap analysis. Statistical surrogates are labelled empirical interpolation and refuse to answer outside the data envelope by default.

## 2. Design principles

1. Epistemic status is a type, not a comment.
2. Artifacts are immutable and content-addressed. Transformations are registered functions recorded in a lineage graph.
3. Every quantity carries a unit (pint) and an uncertainty, including an explicit unknown.
4. Simulators live behind adapters. The core never imports a simulator.
5. Refuse loudly: an out-of-envelope request returns a Warning object that propagates into every report.
6. Small mandatory dependency set; heavy features are optional extras.

## 3. Measured, derived, simulated, hypothetical and interpreted

Five statuses, ordered by distance from direct observation:

- **MEASURED**: read from a source file or sensor channel; only unit conversion applied.
- **DERIVED**: computed from measured values by a registered, versioned algorithm (for example heat release from oxygen consumption). Carries method id, parameters and propagated uncertainty.
- **SIMULATED**: output of an external model run.
- **SCENARIO**: hypothetical or user-specified conditions, including proposed experiments.
- **INTERPRETATION**: meaning attached to results: model-supported statements, regime labels, cluster assignments, recommendations, narrative text.

**Propagation rule:** the status of a result is the maximum over its inputs. A calibrated parameter (needs a simulator) is therefore at least SIMULATED and is displayed as model-conditional. Nothing that touches a SCENARIO can be reported as measured. Registered DERIVED methods may declare a maximum input status; the framework rejects violations at call time.

```python
from dataclasses import dataclass
from enum import IntEnum

class Status(IntEnum):
    MEASURED = 0
    DERIVED = 1
    SIMULATED = 2
    SCENARIO = 3
    INTERPRETATION = 4

def join(*s: Status) -> Status:
    return max(s)   # never more certain than the weakest input

@dataclass(frozen=True)
class Provenance:
    artifact_id: str             # sha256 of canonical content
    parents: tuple[str, ...]     # lineage
    activity: str                # function id + version
    params: dict
    source_ref: str | None       # DOI / URL / PSI id + file hash + location
    code_version: str            # git commit
    env_hash: str                # hash of resolved dependency set
    created_utc: str

@dataclass(frozen=True)
class Quantity:
    value: object                # float or xarray.DataArray
    unit: str
    u: object | None             # standard uncertainty
    u_kind: str                  # 'type_a' | 'type_b' | 'assumed' | 'unknown'
    status: Status
    prov: Provenance
```

## 4. Package architecture

| Module | Responsibility |
| --- | --- |
| `pyra.schema` | pydantic models: ExperimentRecord, Conditions, FuelSpec, SourceRef, ModelCard; published JSON Schema |
| `pyra.units` | pint registry, domain units (mole fraction, kPa, cm/s), unit validation |
| `pyra.io` | Ingestion. Manifest-driven PSI fetcher (DOI, file hash), local loaders, reader registry keyed by investigation and file pattern |
| `pyra.normalize` | Channel vocabulary, time-base alignment, QC flags, gap handling. No silent smoothing |
| `pyra.conditions` | Conditions class, atmosphere helpers, similarity features |
| `pyra.catalog` | Local index (Parquet + DuckDB), queries over conditions and outcomes |
| `pyra.derive` | Measurement processing: oxygen-consumption heat release, enthalpy balance, spread rate, event detection, sensor lag |
| `pyra.matching` | Scenario-to-experiment matching |
| `pyra.coverage` | Envelope and gap analysis |
| `pyra.compare` | Observation operators, alignment, metrics, discrepancy ledger |
| `pyra.uq` | Propagation, calibration, model discrepancy, identifiability |
| `pyra.sensitivity` | Sensitivity analysis wrappers |
| `pyra.surrogate` | GP interpolation and flammability-boundary models with applicability guard |
| `pyra.cluster` | Regime exploration |
| `pyra.recommend` | Experiment recommendation |
| `pyra.adapters` | Simulator interface and concrete adapters |
| `pyra.provenance` | Lineage graph, hashing, run manifests, PROV and RO-Crate export |
| `pyra.report` | HTML/PDF reports with status legend and ledger references |
| `pyra.viz` | Coverage maps, comparison plots, status-aware styling |
| `pyra.cli` | `pyra ingest`, `pyra match`, `pyra compare`, `pyra report`, `pyra replay` |

Dependency direction: `schema/units/provenance` at the bottom; `io/normalize/derive/conditions/catalog` above; `matching/coverage/compare/uq/surrogate` above those; `adapters` and `report` at the top. `adapters` may import the core; the core never imports `adapters`.

Ingestion caveat: per-investigation file mappings will be hand-curated YAML maintained in the repository, not auto-discovered. I could not confirm PSI file formats or whether every needed sensor stream is public. A data audit gates every reader.

## 5. Data formats

- **Time series:** xarray Dataset. Dimensions: time, optionally channel, x, y. Per variable attributes: units, status, uncertainty companion `<name>_u`, QC flag companion, provenance id. Stored as Zarr (large) or NetCDF4.
- **Catalogue:** Parquet (pyarrow) queried with DuckDB.
- **Video:** store a reference (URL or DOI, content hash) and extracted features, not the frames. Optional frame cache.
- **Metadata:** pydantic models serialized to JSON or YAML with `schema_version`.
- **Provenance:** append-only JSON Lines ledger; export as W3C PROV-JSON and RO-Crate bundles.
- **Interchange with non-Python tools:** scenario JSON (schema-validated) in, NetCDF plus manifest out.
- **Hashing:** SHA-256 over canonical bytes (sorted keys, normalized floats) so hashes are stable across machines.

## 6. Conditions, similarity features and matching

### 6.1 Conditions

```python
@dataclass
class Conditions:
    gravity_g: Quantity              # units of g0. Microgravity is a measured residual, not exactly 0
    pressure: Quantity
    o2_mole_fraction: Quantity
    diluent: str
    flow_velocity: Quantity | None
    flow_mode: str                   # 'quiescent' | 'forced' | 'buoyant' | 'unknown'
    temperature: Quantity | None
    fuel: 'FuelSpec'                 # material, thickness, width, length, density, treatment
    configuration: str               # 'concurrent' | 'opposed' | 'droplet' | 'jet' | 'enclosed' | 'other'
    length_scale: Quantity
    def features(self, atm: 'AtmosphereModel') -> dict[str, Quantity]: ...
```

`features()` returns DERIVED similarity features, for example oxygen mass fraction, a buoyancy-to-forced-flow ratio (Grashof over Reynolds squared) and thickness-to-length ratios. Equivalence between conditions under such features is a hypothesis, never a proof, and is recorded as such.

### 6.2 Matching algorithm

The catalogue is small (under about 10^4 records), so brute-force vectorized numpy is fine. A `cKDTree` is added only if needed.

1. **Hard gates.** Configuration (concurrent versus opposed, droplet, jet), fuel class and flow mode must agree, or the tier is NONE. These are different physical regimes and are not averaged away.
2. **Per-dimension normalized differences.** `d_k = |a_k - b_k| / tau_k`, where `tau_k = sqrt(u_a^2 + u_b^2 + tol_k^2)`. Pressure and gravity are compared in log space. Gravity near zero uses a floor `g_floor` (a parameter, default documented in config) so that 1e-5 g and 1e-3 g are not treated as infinitely different.
3. **Tiering.** EXACT: all `d_k <= 1`. NEIGHBOR: all `d_k <= d_max` and an aggregate `D = (sum_k w_k d_k^2)^(1/2)` below a threshold. ANALOG: matches only after applying a registered ScalingRelation (section 7.3). NONE otherwise.
4. **Ranking.** Non-dominated (Pareto) sorting on the mismatch vector, not a single scalar, because a match that is off in oxygen only and one that is off in pressure only are not comparable.
5. **Output.** A per-dimension MismatchVector is always retained. The scalar `D` is for sorting only.

Weights `w_k` and tolerances `tol_k` live in a versioned MatchPolicy file. They are expert settings, and sensitivity of rankings to them is reportable.

### 6.3 Evidence coverage

- Per scenario: normalized distance to the k nearest matched experiments and local count.
- Count independent sources (distinct investigations or platforms), not runs; repeated runs of one apparatus are not independent evidence.
- Convex hulls (scipy Delaunay) are used only in 2 to 4 dimensional projections. In higher dimensions hulls are unreliable, so coverage uses kNN-distance thresholds.
- Outputs: coverage maps (for example O2 versus pressure at a given gravity class and flow bin), a ranked gap list, and a per-scenario coverage verdict feeding the claim gate.

## 7. Comparing measurements with simulations

### 7.1 Observation operators

The simulation is mapped to what the instrument would have seen, not the reverse. Operators in PYRA: point sampling at sensor coordinates, first-order sensor lag, sampling-line delay, averaging windows, resampling. Line-of-sight camera operators and radiation-error models are provided as plug-in interfaces; simple versions are included but flagged as approximations.

### 7.2 Comparison layers

1. **Feature comparison.** The same event definitions on both sides (ignition, steady spread rate, peak heat release, extinction time, temperature rise). Thresholds are parameters recorded in provenance.
2. **Time-series comparison.** Event-anchored alignment first, bounded cross-correlation lag second. Dynamic time warping is off by default because it can hide timing errors. Metrics: bias, relative difference, normalized RMSE, and a z-score using combined uncertainty `u_c^2 = u_meas^2 + u_sim^2 + u_disc^2`. For model-level summaries, bias and scatter over many experiments follow the style of fire-model validation guides.
3. **Mismatch accounting.** Each comparison carries the MismatchVector. Differences are interpreted only within the declared mode.

### 7.3 Handling differences in gravity, oxygen, pressure, flow, fuel, geometry, scale and measurement method

Preferred strategy: **hindcast.** Ask the simulator to run the experiment's actual conditions (`adapter.at(conditions, base)`) rather than adjusting the data. Fall back to the table below only when that is impossible.

| Factor | Primary handling | Fallback | Blocked when |
| --- | --- | --- | --- |
| Gravity | Hindcast at measured gravity | Registered scaling relation | No relation and no hindcast |
| Oxygen, pressure, flow | Hindcast | Tolerance bands; local sensitivity from the simulator if available | Beyond tolerance with no sensitivity |
| Fuel | Hindcast with matched properties | Property-class grouping, reported as contextual only | Different fuel class |
| Geometry and configuration | Hard gate | None | Always blocked across configurations |
| Scale | Compare dimensionless features only if a registered relation exists | Side-by-side context | No relation |
| Measurement method | Observation operator | Add method uncertainty to `u_disc` | Quantity not observable by the method |

Modes: `direct` (within tolerance), `scaled` (a ScalingRelation with literature reference and declared validity is applied; result status INTERPRETATION), `contextual` (plotted side by side, no quantitative claim). Pressure-gravity modelling and similar relations are registered only with citations and validity ranges. NASA authors note that the link between pressure modelling and true partial-gravity flames has not been established, so no such relation is trusted by default.

## 8. Uncertainty, sensitivity, interpolation, clustering, recommendation

### 8.1 Uncertainty sources

Measurement (calibration, resolution), processing (thresholds, filters), parametric (model inputs), model discrepancy, numerical (grid, time step), and representativeness (run-to-run variability, condition mismatch). Each is a separate entry in an uncertainty budget.

### 8.2 Methods

- **Propagation through derived quantities.** Monte Carlo with scipy.stats.qmc sampling and correlated errors (numpy Generator, explicit seeds). First-order Jacobian propagation for simple algebra.
- **Forward UQ of a simulator.** PYRA generates designs (Latin hypercube or Sobol sequences); the user's simulator runs externally; results feed a surrogate (GP, or polynomial chaos via chaospy or OpenTURNS).
- **Calibration.** Bayesian, for a small number of effective parameters (for example an effective heat-transfer coefficient): emcee for about 10 parameters or fewer, NumPyro or PyMC for hierarchical models. The likelihood must handle autocorrelated residuals (AR(1) or GP residual); treating time samples as independent overstates precision.
- **Model discrepancy.** Optional Kennedy-O'Hagan GP discrepancy term so parameters do not absorb model error. Parameter and discrepancy can be confounded, so identifiability is always checked.
- **Identifiability report.** Prior-to-posterior contraction, posterior correlations, profile likelihood and Fisher-information eigenvalues. A parameter calibrated from one sensor and checked against others is flagged if the check data barely constrain it.
- **Sensitivity.** SALib: Morris screening, Sobol indices, and moment-independent delta or PAWN measures. Sobol assumes independent inputs; correlated inputs get a warning. Run on a surrogate, not directly on expensive simulations.

### 8.3 Interpolation and extrapolation

- **Regression-type quantities:** GP regression (scikit-learn first; GPyTorch or GPJax optional) with Matern kernels, log-warped pressure and gravity, heteroscedastic noise from measurement uncertainty, and a platform covariate.
- **Flammability boundaries:** outcomes (burn, quench, blow-off) are binary or categorical, and many are censored: a flame still burning at the end of a short test is not a confirmed steady flame, and an extinguished flame in a short test may reflect test duration. Model with GP classification or Bayesian logistic regression plus a duration or censoring term.
- **No monotonicity constraints in gravity.** NASA literature reports non-monotonic gravity dependence of flammability, so monotone priors would be physically wrong.
- **Applicability guard.** Predictions are returned only when the scenario passes the coverage gate. GP variance is not a reliable extrapolation uncertainty, so outside the envelope PYRA returns a refusal with the nearest evidence, not a number. Extrapolation requires a validated external model or registered scaling relation, and the result is labelled accordingly.

### 8.4 Clustering

scikit-learn HDBSCAN or agglomerative clustering on conditions plus extracted outcome features (not raw time series, to avoid DTW artifacts). Stability is tested by bootstrap (adjusted Rand index). Clusters are INTERPRETATION; regime names come only from a user-supplied mapping to literature labels. With few independent experiments, clustering is exploratory.

### 8.5 Experiment recommendation

Three strategies, all outputs typed SCENARIO with the rationale recorded:

1. **Coverage gap:** greedy k-center selection to maximally reduce the distance from target scenarios to evidence.
2. **Boundary refinement:** uncertainty sampling or expected information gain (BALD-style) on the boundary classifier.
3. **Calibration design:** expected information gain on parameters via a surrogate (needs a simulator).

Facility feasibility (achievable gravity, duration, size) is a user-supplied constraint set. PYRA does not know hardware limits, and recommendations are not cost-aware by default.

## 9. External simulation interface

The contract is file-based and language-agnostic, with a Python protocol on top.

```python
from typing import Protocol
from pathlib import Path

@dataclass
class ValidationEvidence:
    exp_ids: list[str]; quantity: str; metric: str; result: dict
    envelope: dict                 # condition box or hull over which this holds

@dataclass
class ModelCard:
    name: str; version: str; code_hash: str; licence: str
    physics_summary: str; limitations: list[str]
    envelope: list[ValidationEvidence]   # empty means unvalidated

class SimulatorAdapter(Protocol):
    card: ModelCard
    def build_input(self, s: 'Scenario', workdir: Path) -> 'InputDeck': ...
    def run(self, deck: 'InputDeck', *, timeout: float | None = None) -> 'RunHandle': ...
    def collect(self, h: 'RunHandle') -> 'SimulationResult': ...   # status SIMULATED
    def at(self, c: Conditions, base: 'Scenario') -> 'Scenario': ...   # hindcast scenario
```

Adapters, in implementation order:

1. **ImportAdapter:** reads results produced elsewhere (FDS output via fdsreader or pyfdstools; CSV; NetCDF). This is the minimum viable adapter, since users already run their own models.
2. **CallableAdapter:** wraps a Python function from scenario to arrays, for custom simulations.
3. **TemplateCLIAdapter:** Jinja2 input-deck templates plus subprocess in an isolated working directory; records stdout, executable version and input hashes. Suits FDS and similar codes.
4. **OpenFOAM adapter:** case templating with foamlib or plain file generation; verify maturity before depending on it.
5. **Remote or batch execution:** optional later.

`SimulationResult` is an xarray Dataset plus an OutputMap (which output corresponds to which sensor or feature), always status SIMULATED, always carrying the ModelCard id.

**Claim gate.** A model-supported statement is allowed only if (a) the ModelCard has ValidationEvidence, (b) the scenario lies inside that envelope, and (c) coverage by experiments passes. PYRA can generate ValidationEvidence from its own compare module, which is the intended path.

## 10. Build, borrow, or require external validation

| Capability | PYRA implements | Builds on | Needs validated external model |
| --- | --- | --- | --- |
| Units, labelled arrays, storage | Thin wrappers | pint, numpy, xarray, pandas, zarr, netCDF4, pyarrow, DuckDB | No |
| Schemas | Domain models | pydantic | No |
| Status lattice, lineage, ledger | Yes | `prov`, `ro-crate-py` for export | No |
| Combustion derivations (O2 calorimetry, enthalpy balance, spread rate, events) | Yes (domain-specific, tested against published values) | numpy, scipy | No |
| Image features | Wrapper with uncertainty | OpenCV, scikit-image, optionally SAM2 | No |
| Matching and coverage | Yes | scipy.spatial | No |
| Observation operators | Simple ones | scipy.signal | Camera and radiation operators need validated instrument models |
| Comparison metrics, discrepancy ledger | Yes | numpy | No |
| Propagation, QMC | Orchestration | scipy.stats.qmc, `uncertainties` (optional) | No |
| Bayesian calibration | Model wrappers, identifiability diagnostics | emcee, NumPyro, PyMC | Calibration is conditional on the simulator |
| Sensitivity | Wrapper | SALib | No |
| GP interpolation, classifiers | Applicability guard, censoring | scikit-learn, GPyTorch or GPJax | No; extrapolation is refused |
| Clustering | Stability checks | scikit-learn | No |
| Experiment design | Utilities on GP posteriors | BoTorch (optional) | Calibration design needs a simulator |
| FDS I/O | Thin adapter | fdsreader, pyfdstools | The FDS model itself |
| Reports | Assembly and legends | Jinja2, matplotlib, Plotly, WeasyPrint | No |
| CLI, pipelines | Yes | typer; Snakemake or DVC optional | No |
| **Predicting spread, extinction, heat release or smoke transport at unmeasured conditions** | **No** | **None** | **Yes** |
| **Partial-gravity behaviour, scale-up to vehicles, toxicity** | **No** | **None** | **Yes, with a declared envelope** |

## 11. Provenance, reproducibility, traceability

- **Artifact identity:** `artifact_id = sha256(canonical bytes)`; each artifact lists parent ids, the activity (function, version, parameters), agent (software or human), code commit and environment hash.
- **Source pointers:** DOI or URL, access date, original file hash, investigation id and version, filename, and row or column location for key extracted numbers.
- **Run manifest:** `pyra.lock.json` records package versions (importlib.metadata), Python version, platform, seeds and configuration hash.
- **Caching:** keyed by hash of (function, inputs, parameters).
- **Replay:** `pyra replay manifest.json` re-executes the lineage and compares output hashes; numerical tolerance is configurable for floating-point differences.
- **Human decisions** (manual QC masks, tolerance choices) are recorded as agent actions and typed INTERPRETATION.
- **Reports** embed the status legend and a ledger id on every figure and table row. Export as PROV-JSON or RO-Crate for archiving.

## 12. Proposed folder structure

```text
pyra/
  pyproject.toml            # hatchling or setuptools; extras: uq, gp, vision, report, fds
  src/pyra/
    __init__.py
    schema/        conditions.py experiment.py scenario.py modelcard.py
    units/         registry.py
    provenance/    status.py ledger.py hashing.py lineage.py export_prov.py manifest.py
    io/            psi.py local.py readers/  mappings/*.yaml
    normalize/     channels.py timebase.py qc.py
    conditions/    atmosphere.py similarity.py scaling.py
    catalog/       index.py query.py
    derive/        heat_release.py enthalpy.py spread.py events.py lag.py flame_features.py
    matching/      policy.py match.py pareto.py
    coverage/      envelope.py gaps.py
    compare/       operators.py align.py metrics.py ledger.py
    uq/            propagate.py calibrate.py discrepancy.py identifiability.py
    sensitivity/   sobol.py morris.py
    surrogate/     gp.py boundary.py guard.py
    cluster/       regimes.py
    recommend/     gaps.py boundary.py design.py
    adapters/      base.py importer.py callable.py template_cli.py fds.py openfoam.py
    report/        templates/ build.py
    viz/           coverage.py compare.py style.py
    cli.py
  tests/           unit/ property/ synthetic_truth/ regression/ golden/
  docs/            architecture.md tutorials/ mapping_guide.md
  data_manifests/  investigations/*.yaml   # DOIs and hashes only, no data
  examples/        notebooks/
```

## 13. Example usage (illustrative; identifiers are placeholders)

```python
import pyra
from pyra.io import psi
from pyra.derive import heat_release_o2
from pyra.matching import match, MatchPolicy
from pyra.coverage import coverage
from pyra.compare import compare, SensorLag
from pyra.adapters import ImportAdapter
from pyra.report import build_report

cat = pyra.Catalog.open('~/.pyra/catalog')
exp = psi.load('INVESTIGATION_ID', run='RUN_ID', catalog=cat)   # status MEASURED

# DERIVED quantity with propagated uncertainty
hrr = heat_release_o2(o2_in=exp.channels['o2_in'], o2_out=exp.channels['o2_out'],
                      flow=exp.channels['flow'], e_per_kg_o2=13.1e6, n=4096, seed=0)
assert hrr.status.name == 'DERIVED'

# User-supplied simulation results, produced elsewhere
sim = ImportAdapter(card=pyra.ModelCard.load('fds_cygnus.card.yaml')).collect('runs/cygnus_01/')

policy = MatchPolicy.load('policies/default.yaml')
matches = match(sim.scenario, cat, policy)          # per-dimension mismatch retained
cov = coverage([sim.scenario], cat, policy)         # gaps and independent-source counts

cmp = compare(exp, sim, operator=SensorLag(tau_s=5.0),
              features=['t_ignition', 'peak_hrr', 'temp_rise'],
              mode='direct', mismatch=matches[0].mismatch)

build_report([cmp, cov], out='report.html')         # status legend + ledger ids on every number
```

Expected behaviour on out-of-envelope input: `compare(..., mode='direct')` raises a `MismatchTooLarge` warning object carried into the report, and `BoundaryModel.predict` returns a refusal with the nearest evidence.

## 14. Validating PYRA itself

- **Property tests (hypothesis):** status join is monotone; unit-inconsistent operations fail; hashes are stable.
- **Synthetic-truth tests:** generate fake sensor data from a known source term plus noise; check that recovered values and credible intervals achieve nominal coverage (simulation-based calibration).
- **Regression tests:** reproduce numbers from published papers using digitized values, flagged as such.
- **Golden-file reports** and replay tests.
- CI: ruff, mypy, pytest, nox. Docs: MkDocs or Sphinx.

## 15. Implementation roadmap

| Phase | Scope | Exit criterion |
| --- | --- | --- |
| 0 (hackathon, about 48 h) | One vertical slice: one dataset, derived heat release with error bars, status labels, one comparison with a published or user curve, ledger | Slice reproducible from a manifest; claims limited to T0-T2 |
| 1 (v0.1, 4 to 6 weeks) | schema, units, provenance, io for 2 investigations, normalize, derive, catalog | Synthetic-truth tests pass; data audit documented |
| 2 (v0.2) | matching, coverage, compare, ImportAdapter (FDS), report | Reproduce one published model-versus-data comparison |
| 3 (v0.3) | uq: propagation, calibration, identifiability; sensitivity; CallableAdapter, TemplateCLIAdapter | Calibration recovers known parameters on synthetic data at nominal coverage |
| 4 (v0.4) | surrogate with guard, boundary models with censoring, clustering, recommendation | Held-out experiments fall inside predicted intervals at nominal rates; refusal logic tested |
| 5 (v1.0) | ModelCard validation envelopes, claim gate, docs, packaging, external review | Independent user reproduces a case study |

## 16. Risks and open questions

- PSI file formats and sensor availability are unverified; each reader is real manual work.
- Few independent flights and experiments limit statistical power; keep claims inferential and modest.
- Parameter and discrepancy confounding can make calibrations look more certain than they are.
- Scaling relations across gravity, pressure and scale may lack validation; PYRA registers them only with literature references and treats results as INTERPRETATION.
- Tolerances and weights in MatchPolicy are expert judgements; publish them and test sensitivity.
- Maintaining adapters for evolving external codes is an ongoing cost.

## 17. Physics and simulation layer

Physics is where PYRA earns or loses trust. The rule: PYRA implements only physics it can verify against analytical results, and it delegates flame-resolved and vehicle-scale simulation to external codes whose ModelCards carry validation evidence.

### 17.1 The simulator ladder

| Tier | What it is | Where it lives | Claim it supports |
| --- | --- | --- | --- |
| S0 | Analytic and scaling relations: oxygen-consumption and enthalpy calorimetry, buoyancy-to-flow ratio, mole-to-mass-fraction conversion | `pyra.physics` | Derived quantities with propagated uncertainty |
| S1 | Reduced-order models: well-mixed compartment, sensor lag, lumped thermal response, optional thin-fuel thermal-theory spread relation | `pyra.physics` | Verified against closed-form solutions; test-bed and hindcast use; no standalone prediction |
| S2 | Vehicle-scale CFD with source terms (FDS-type) and custom Python models | External, through an adapter | Model-supported statements inside the validated envelope |
| S3 | Flame-resolved CFD and research codes (detailed pyrolysis, radiation, chemistry) | External, through an adapter | Mechanism studies; PYRA supplies data, comparison and uncertainty |

NASA's own Saffire work on Cygnus is an S2 precedent: the FDS model uses no flame or combustion properties and instead injects heat and species source terms derived from experimental inlet and outlet measurements (section 21). That is the integration point PYRA targets first.

### 17.2 `pyra.physics` modules and signatures

```python
# scaling.py (S0)
def buoyancy_ratio(g: Quantity, length: Quantity, flow_velocity: Quantity,
                   thermal_expansion: float, delta_t: Quantity) -> Quantity: ...
    # Richardson-type ratio g*beta*dT*L/U^2. Returns DERIVED with a formula id.
def oxygen_partial_pressure(pressure: Quantity, o2_mole_fraction: Quantity) -> Quantity: ...
def mole_to_mass_fraction(x: dict[str, float], molar_mass: dict[str, float]) -> dict[str, float]: ...

# calorimetry.py (S0)
def hrr_oxygen_consumption(o2_in: Quantity, o2_out: Quantity, mass_flow: Quantity,
                           e_per_kg_o2: Quantity, n: int = 4096, seed: int = 0) -> Quantity: ...
def hrr_enthalpy_balance(t_in: Quantity, t_out: Quantity, mass_flow: Quantity,
                         cp: Quantity, loss_model: 'LossModel | None' = None) -> Quantity: ...
def species_generation(c_in: Quantity, c_out: Quantity, mass_flow: Quantity) -> Quantity: ...

# zone.py (S1)
class WellMixedZone:
    def __init__(self, volume: Quantity, ventilation: Quantity, leak: Quantity | None,
                 species: list[str]): ...
    def integrate(self, sources: 'SourceTerms', t_eval, y0: dict) -> 'xr.Dataset': ...
    # Verified against closed-form exponential solutions for constant source and flow.

# sensor.py (S1)
def apply_first_order_lag(signal: 'xr.DataArray', tau: Quantity) -> 'xr.DataArray': ...
def invert_first_order_lag(signal: 'xr.DataArray', tau: Quantity, regularization: float) -> 'xr.DataArray': ...
    # Warns about noise amplification; never silent.

# spread.py (S1, experimental flag)
class ThinFuelThermalSpread:
    card: ModelCard
    def rate(self, c: Conditions, params: dict) -> Quantity: ...
    # The relation comes from the primary literature at implementation time and is
    # verified against its published limiting cases. Not used for microgravity
    # claims until a ValidationEvidence entry covers the scenario.
```

Constants and formulas carry a source reference in code comments. A formula without a reference is a defect. The 13.1 MJ per kg of oxygen consumed value is the one NASA's Saffire modelling paper uses for battery tests; any other value needs its own reference.

### 17.3 The evidence loop with external simulations

```text
experiment sensors --derive source terms (S0, with uncertainty)--> heat and species ramps
ramps --adapter.build_input--> external model (S2 or S3) --run or import--> SimulationResult
SimulationResult --observation operator--> synthetic sensor traces
synthetic traces vs measured traces --compare (mismatch-aware)--> ComparisonResult
ComparisonResult --calibrate effective parameters + identifiability--> Posterior
Posterior + ComparisonResult --> ValidationEvidence --> ModelCard envelope
ModelCard envelope + coverage --> claim gate for model-supported statements
```

Each arrow is a recorded, hashed step in the lineage graph. If a hindcast on held-out experiments fails beyond combined uncertainty, the envelope shrinks automatically and later reports say so.

### 17.4 What needs validated external models

| Phenomenon | What is needed | PYRA's role |
| --- | --- | --- |
| Flame shape, spread rate and extinction at unmeasured conditions | A flame-resolved model with validated pyrolysis, radiation and chemistry for the specific fuel and geometry | Data, matching, comparison and uncertainty. No predictions |
| Partial gravity (Moon, Mars) behaviour | No validated model I know of; evidence is sparse and non-monotonic in gravity | Coverage, gaps and experiment recommendations only |
| Vehicle-scale smoke and species transport | An FDS-type model with source terms validated against Saffire-like data | Source terms, hindcast, calibration, evidence ledger |
| Material flammability ranking for spacecraft | Standards and test evidence | Evidence ledger and comparison. No ranking claims |
| Toxicity and health limits | External standards and medical authority | Out of scope |

### 17.5 Verification and validation gates

- **Verification (PYRA's own code):** closed-form comparisons, mass and energy balance residuals, convergence tests for the ODE solvers, unit-consistency property tests.
- **Validation (models, via ModelCards):** hindcasts against published or catalogued data, recorded as ValidationEvidence with the metric, result and condition envelope. Acceptance thresholds are set by the model owner and stored in the card, not invented by PYRA.
- **Kill criteria:** a reduced-order model that fails a hindcast beyond combined uncertainty is demoted to concept use; a calibration whose parameters are not identifiable is reported as unconstrained, not as a result.

### 17.6 Microgravity physics watch-list for implementers

- Without buoyancy, flow is set by imposed ventilation and geometry, so flow and fuel geometry matter more than in 1 g.
- Gravity dependence of flammability is non-monotonic near lunar gravity in NASA reports, so no monotone constraints in gravity.
- Test duration bounds what experiments can show: a few seconds in drop towers may suit the gas phase but not solid-phase heating.
- Cabin atmospheres differ from sea level; Saffire VI ran at 54.1 kPa and 31% oxygen, so oxygen fraction and oxygen partial pressure must be kept separate in every comparison.
- Flow shutoff after a fire is not obviously safe: smoldering can reignite when flow returns, while shutting flow can leave species such as HCl high in simulations.

## 18. Education and outreach interfaces

Education is an interface on the same engine, not a second product. Learners see the same experiments, conditions and uncertainty the researchers see, with the status types turned into plain-language badges. The scope stays fire-only: microgravity and partial-gravity combustion and spacecraft fire safety.

### 18.1 Design principle: epistemic honesty as pedagogy

| Library status | Learner-facing badge |
| --- | --- |
| Measured, Derived | Real evidence |
| Simulated | Model result |
| Scenario | What-if |
| Interpretation | Interpretation |
| `pyra-edu` concept model | Concept sketch |

Simplified teaching models live in a separate `pyra-edu` package so a cartoon can never be mistaken for engine output. The signature feature is a **has this been tested?** meter: when a learner sets gravity, oxygen, pressure, flow and fuel, the matching and coverage modules show the nearest real experiments and state plainly when none exist. There is no flame predictor in the learner interface.

### 18.2 Modules

| Module | What learners do | Library features used |
| --- | --- | --- |
| Why flames change | Compare real Earth and microgravity images; use a buoyancy-versus-flow concept sketch | Catalogue, `scaling.buoyancy_ratio`, badges |
| Condition explorer | Set gravity, oxygen, pressure, airflow and fuel; see nearest experiments and gaps | `matching`, `coverage` |
| Earth, microgravity, Moon, Mars | Compare evidence strength per environment, not just flame pictures | Coverage counts by independent platform |
| Case files | For a real experiment: what was tested, what was measured, what was derived, what is unknown | `ExperimentRecord`, ledger, curated limitations |
| Heat-release lab | Compute heat release from oxygen data with error bars | `calorimetry`, `propagate` |
| Lunar habitat challenge | Choose pressure, oxygen and ventilation; justify with cited evidence | Coverage, `recommend`, evidence ledger |
| Hypothetical fire investigation | Interpret clearly fictional sensor traces; weigh airflow shutoff | Synthetic-trace generator, `zone`, `compare` |

Challenge scoring rewards cited evidence, a stated unknown and a proposed experiment. It never outputs an invented fire-risk score.

### 18.3 Pathways

- **Grades 5 to 8:** observe real images, predict, compare. No equations; coarse controls.
- **Grades 9 to 12:** read graphs and uncertainty, write claim-evidence-reasoning arguments, run provided notebooks.
- **Undergraduate:** oxygen-consumption calorimetry with uncertainty, calibration against a toy model, a validation exercise.
- **Researchers:** the full library, CLI, API and evidence-ledger reports.
- **Public and outreach:** kiosk or livestream mode built on the case files and the evidence-gap meter.

Curriculum mapping (for example NGSS, or CBSE and NCERT locally) is not done yet and is a prototype-phase task.

### 18.4 Educator kit

Lesson plans with answer keys, 10-question quizzes per module, JupyterLite notebooks (browser-only, no server), a one-page teacher guide, a workshop outline, and a student research challenge in which teams find a coverage gap and propose an experiment. Classroom use needs no student accounts.

### 18.5 Branding and safety rules

- No NASA logos or insignia and no NASA name in the product name. NASA's guidelines say the insignia and logotype are not public domain and imagery may not imply endorsement of outside efforts.
- Attribute data and images, and show an independent-project notice. No programme in section 21 has endorsed or adopted PYRA.
- Do not encourage home fire experiments. Candle activities, where used, are teacher-supervised.
- Child privacy: no accounts for minors by default; check applicable law (COPPA, GDPR, India's DPDP Act) before adding any.

### 18.6 Prototype versus later

| Feature | Phase |
| --- | --- |
| Status badges, 3 to 5 case files, has-this-been-tested meter, evidence table by environment | Prototype |
| One JupyterLite notebook (heat release with error bars), one-page teacher guide, 10-question quiz | Prototype if the data audit passes; otherwise labelled synthetic data |
| Concept-sketch sliders for buoyancy and flow | Prototype, after expert review |
| Lunar habitat challenge, hypothetical fire investigation | Later: needs a rubric and teacher testing |
| Classroom dashboards, LMS export, accounts, adaptive pathways | Later: needs privacy work |
| Student research challenge with peer review | Later: needs moderation and mentors |
| Quantitative what-if outputs for learners | Only if a validated model covers the scenario |
| Localization and accessibility audit | Start early, finish later |

Plan pre and post concept checks and a few teacher pilots before claiming any learning gains.

## 19. Unified platform architecture

One engine, several interfaces. Arrows show which layer calls which; nothing above the engine can change evidence.

```text
 Researcher            Student               Educator
 CLI, notebooks, API   web app, notebooks    kits, quizzes, guides
     |                     |                     |
     |                     +----------+----------+
     |                                |
     |                   Lesson specs + pyra-edu concept models
     |                   (every claim cites an evidence id)
     |                                |
     +---------------+----------------+
                     |
        Service layer: Python API, JSON bundles, browser (Pyodide) build
                     |
   +-----------------------------------------------+
   | pyra engine                                   |
   |  provenance + status | matching + coverage    |
   |  derive | physics (S0, S1) | compare | uq     |
   |  surrogate | recommend | adapters | report    |
   +-----------------------------------------------+
                     |
        Evidence store: catalogue, hashes, ledger
                     |
        External simulators (FDS, custom Python, CFD) via adapters
```

### 19.1 Interface responsibilities

| Interface | Audience | Contains | Must not |
| --- | --- | --- | --- |
| `pyra` library, CLI, notebooks | Researchers, university users | Full engine, adapters, reports | Hide status or uncertainty |
| Service and static export | All interfaces | Read-only queries, pre-computed JSON bundles, Pyodide build | Write evidence |
| `pyra-edu` and lesson specs | Students, educators | Concept sketches, lesson content, quiz banks | Present sketches as evidence |
| Educator kit | Teachers | Plans, answer keys, notebooks, workshop outlines | Require student accounts |

### 19.2 Governance rules

1. **One-way dependency.** Education code calls only the service layer's public interface.
2. **Content lint in CI.** Every factual statement in a lesson spec carries an evidence id or a `concept_sketch` tag, or the build fails.
3. **Static first.** Pre-computed bundles plus a browser build serve schools with weak connectivity and avoid collecting student data. Test early whether pyarrow, DuckDB and other dependencies run under Pyodide; keep a pure-Python install path for the core.
4. **The scientific engine ships first.** No education feature is scheduled ahead of its library prerequisite.

### 19.3 Folders added to section 12

```text
src/pyra/physics/     scaling.py calorimetry.py zone.py sensor.py spread.py   # S0 and S1
src/pyra/service/     api.py export_bundle.py                                  # read-only
src/pyra_edu/         concept_models.py badges.py synthetic_traces.py lint.py
content/lessons/      *.yaml  (lesson specs: claims, evidence ids, prompts)
content/quizzes/      *.yaml
educator_kit/         plans/ answer_keys/ notebooks/ workshop/
model_cards/          *.card.yaml                                              # validated envelopes
pyproject extras:     uq gp vision report fds edu service
```

### 19.4 Consolidated roadmap

| Phase | Core library | Physics | Education | Exit criterion |
| --- | --- | --- | --- | --- |
| 0 (hackathon, about 48 h) | One vertical slice: load, derive heat release with error bars, status labels, ledger | `calorimetry` only | None, or one case file | Slice reproducible from a manifest; claims limited to access and comparison |
| 1 (v0.1) | schema, units, provenance, io for 2 investigations, normalize, catalogue | S0 complete | Badge design | Synthetic-truth tests pass; data audit documented |
| 2 (v0.2) | matching, coverage, compare, ImportAdapter (FDS) | `sensor`, `zone` with analytical verification | Case files, has-this-been-tested meter prototype | One published model-versus-data comparison reproduced |
| 3 (v0.3) | uq: propagation, calibration, identifiability; Callable and TemplateCLI adapters | Hindcast loop on a reduced-order model | JupyterLite heat-release notebook, teacher guide, quiz | Calibration recovers known parameters at nominal coverage |
| 4 (v0.4) | surrogate with guard, boundary models, clustering, recommend | Source-term export to FDS-type inputs | Evidence table by environment; concept sketches after review | Held-out experiments inside predicted intervals at nominal rates; refusals tested |
| 5 (v1.0) | ModelCards with validation envelopes, claim gate, docs, packaging | Optional `spread` model, flagged experimental | Missions and challenges after teacher testing | Independent user reproduces a case study; teacher pilots reported |
| 6 (later) | Remote execution, more investigations | Additional validated external models | Dashboards, LMS export, peer-reviewed student challenges | Privacy and accessibility review passed |

## 20. Build guide: prompting an AI coding assistant

Use one prompt per module, tests first, in the order below. The assistant writes code; you decide the science, the tolerances and what counts as validated.

### 20.1 Workflow

1. Put the project rules file (20.2) at the repository root before the first prompt.
2. Run one prompt from 20.4 per session or branch. Paste the prompt, the relevant section number of this document, and any fixtures.
3. Require tests before implementation, then run them yourself. Never accept a module whose tests the assistant did not run or could not run.
4. Review the diff against the review checklist (20.5). Merge only when CI is green.
5. Record every scientific decision (tolerances, thresholds, formulas) as a short ADR in `docs/adr/`.

### 20.2 Project rules file (AGENTS.md or CLAUDE.md)

```text
Project: PYRA, a Python library for spacecraft and habitat fire safety evidence.
Scope: fire only (microgravity and partial gravity). Do not generalize to other NASA domains.
Source of truth: the architecture document, sections 1 to 20.

Rules:
1. Every quantity is a Quantity with unit, uncertainty and Status (Measured, Derived, Simulated, Scenario, Interpretation).
   Status of a result is the maximum of its inputs. Never downgrade it.
2. Never output an unqualified prediction. Model-supported statements need a ModelCard whose envelope covers the scenario.
3. Do not guess external file formats, dataset ids, API fields or physical constants. Stub them with TODO(verify) and a failing-loudly placeholder.
4. Every formula and constant has a source reference in a comment. No reference means a defect.
5. Pure functions where possible; randomness takes an explicit seed; no hidden global state.
6. The core never imports simulators or education packages. Adapters import the core, never the reverse.
7. Warnings are objects that propagate into reports. Never silence them.
8. Python 3.11+, type hints everywhere, pydantic for schemas, pint for units, xarray for arrays.
9. Tests: pytest, hypothesis for properties, synthetic-truth tests for derivations. Write tests first.
10. Small commits. Run ruff, mypy and pytest before reporting done, and paste the results.
11. If a requirement is ambiguous or a scientific choice is needed, stop and ask. Do not invent.
```

### 20.3 Prompt template

```text
Context: PYRA architecture document, section <n>. Rules file applies.
Goal: <one sentence>.
Inputs and fixtures: <files, sample data, synthetic generators>.
Deliverables: <files, classes, function signatures>.
Tests first: <named tests, including properties and edge cases>.
Constraints: <dependencies allowed, performance, no network>.
Done when: tests, ruff and mypy pass, and you list every TODO(verify) you left.
Do not: <explicit non-goals>.
```

### 20.4 Prompt library

```text
P0 Scaffold. Create src-layout package pyra with hatchling, extras (uq, gp, vision, report, fds, edu, service),
ruff, mypy (strict on provenance and schema), pytest, nox, pre-commit, GitHub Actions CI, MkDocs skeleton, empty modules
per section 12 and 19.3. Done when CI is green on an empty test.

P1 Status and provenance. Implement Status, join, Provenance, Quantity, canonical hashing (SHA-256 of sorted-key JSON and
normalized floats), an append-only JSONL ledger, and lineage graph. Tests: join is monotone and associative (hypothesis);
hashes are stable across runs; modifying any parent changes the child id; a result can never have lower status than inputs.

P2 Units and schema. Add pint registry with domain units; pydantic models for Conditions, FuelSpec, SourceRef,
ExperimentRecord, Scenario, ModelCard; export JSON Schema. Tests: unit mismatch fails; round-trip serialization;
microgravity stored as measured residual g in units of g0, not exact zero.

P3 Calorimetry and propagation (S0). Implement hrr_oxygen_consumption, hrr_enthalpy_balance, species_generation and
propagate (Monte Carlo with scipy.stats.qmc, explicit seed). Tests: synthetic-truth (known source term plus noise recovers truth within the
nominal interval over many seeds); mass and energy balance residuals; refuses inputs with Status above Derived.
Do not hardcode any energy-per-oxygen value without a reference comment.

P4 Catalogue and io skeleton. Implement Catalog (Parquet plus DuckDB), reader registry keyed by (investigation, file pattern, version),
a manifest-driven fetcher that stores DOI, URL, access date and file hash, and a local CSV reader with fixtures.
Do not implement any PSI reader until I supply a real file; leave stubs that raise NotImplementedError with TODO(verify).

P5 Matching. Implement MatchPolicy (YAML), hard gates (configuration, fuel class, flow mode), per-dimension normalized differences
in log space for pressure and gravity with a g_floor, tiers EXACT, NEIGHBOR, ANALOG, NONE, Pareto ranking, and MismatchVector.
Tests: gates block cross-configuration matches; Pareto front on crafted cases; ranking changes are reported when weights change.

P6 Coverage. Implement per-scenario coverage, independent-source counts, kNN distance, 2D to 4D hull projections, gap list.
Tests: repeated runs from one apparatus count as one source; hull code refuses dimensions above 4.

P7 Compare. Implement observation operators (point sampling, first-order lag, delay, window), event extraction with recorded thresholds,
event-anchored alignment, metrics (bias, relative difference, NRMSE, z-score with combined uncertainty), and modes direct, scaled, contextual.
Tests: known lag is recovered; mode contextual never emits a quantitative claim; MismatchTooLarge propagates to the report object.

P8 Adapters. Implement SimulatorAdapter protocol, ModelCard with ValidationEvidence, ImportAdapter (FDS output via fdsreader or pyfdstools,
behind the fds extra), CallableAdapter, TemplateCLIAdapter (Jinja2, isolated workdir, version and input hashes).
Tests: a fake simulator end to end; hindcast scenario via adapter.at; claim gate refuses when the envelope is empty.

P9 Physics S1. Implement WellMixedZone and sensor lag with inversion. Tests: closed-form exponential solutions; conservation;
convergence order of the integrator; inversion warns on noise amplification.

P10 UQ. Implement calibrate (emcee), AR(1) or GP residual option, optional discrepancy term, identifiability report, SALib wrappers.
Tests: simulation-based calibration shows nominal coverage; a deliberately non-identifiable parameter is flagged.

P11 Surrogate and recommend. Implement GP regression with log-warped inputs, boundary classifier with duration censoring, applicability guard that refuses
outside the coverage gate, and k-center and uncertainty-sampling recommenders returning Scenario-status outputs. Tests: refusal outside envelope;
no monotone constraint in gravity; recommendations never carry Measured status.

P12 Report, CLI, replay. Implement Jinja2 HTML report with status legend and ledger ids on every number; typer CLI (ingest, match, compare, report, replay);
pyra replay recomputes lineage and compares hashes. Tests: golden report; replay detects a changed input.

P13 pyra-edu. Implement badges, synthetic fire-trace generator labelled fictional, lesson-spec loader, content lint (every claim has an evidence id or concept_sketch tag),
and case-file generator from ExperimentRecord. Tests: lint fails on an uncited claim; badges map every Status.

P14 Docs and release. Generate README, ARCHITECTURE.md from this document, mapping guide for new investigations, model-card template, CONTRIBUTING, CITATION.cff.
Check dependency licences (fdsreader is LGPL-licensed) before choosing the project licence. Done when no TODO(verify) remains in released code.
```

### 20.5 Review checklist and anti-hallucination rules

- Every physical constant and formula has a source you have opened yourself. Ask the assistant to list them and check each.
- No invented dataset ids, file layouts or API fields. Real files drive readers.
- Synthetic-truth tests exist for every derivation and calibration, and they would fail if the code were wrong.
- Status never decreases through any code path; grep for manual status assignment.
- Out-of-envelope behaviour is a refusal object, not a number.
- Education text cites evidence or is tagged as a concept sketch.
- `TODO(verify)` count is zero before any release.

### 20.6 Documentation set to maintain

README (what it is and is not), ARCHITECTURE.md (this document, trimmed), docs/adr/ (scientific and design decisions), docs/mapping\_guide.md (how to add an investigation reader), model\_cards/ (one per external model, with envelope and limitations), tutorials as notebooks, CONTRIBUTING.md, CHANGELOG.md and CITATION.cff.

## 21. Research basis: overlaps, corrections and sources

As of 14 November 2026. Most pages were consulted through search and only some were opened in full, so verify each before citing it in a paper. I could not read paywalled journals or internal NASA tooling, so absence of a finding is not proof of absence. None of the programmes or tools below has endorsed or adopted PYRA.

### 21.1 Existing work and where PYRA differs

| Existing work | What it does | What it lacks for PYRA's purpose | PYRA's distinct role |
| --- | --- | --- | --- |
| [NASA Physical Sciences Informatics](https://science.data.nasa.gov/features-events/physical-sciences-informatics-updates) | Hosts over 100 investigation datasets (about 30 TB) with DOIs | Cross-experiment analysis aimed at simulation validation | Catalogue, matching and evidence layer on top |
| [Microgravity Analytics Tool (G-SPACE)](https://science.nasa.gov/biological-physical/making-space-science-data-smarter-inside-the-microgravity-analytics-tool/) | Automated video segmentation and Earth-versus-space comparison inside PSI | As described: no simulation inputs, heat-release derivation, uncertainty budget or evidence ledger | Sensor-based source terms, mismatch-aware comparison, provenance |
| [SAM2 flame-diameter measurement](https://arxiv.org/pdf/2607.16587) | Segments droplet flames in PSI images with an uncertainty analysis | Droplet flames only; not simulation-facing | Segmentation is not a differentiator; wrap it with uncertainty if needed |
| [pyfdstools](https://github.com/johodges/pyfdstools/wiki/Home) and [fdsreader](https://pypi.org/project/fdsreader/0.8.3) | Read and write FDS files; apply validation-guide bias and spread | Know nothing about experiments or evidence coverage | Integrate through adapters; do not duplicate |
| [MaCFP](https://iafss.org/macfp/) | Community archive of terrestrial fire validation data | No microgravity equivalent found | The template for a microgravity validation archive |
| [Data-driven forecast of concurrent flame spread in microgravity](https://www.bohrium.com/paper-details/data-driven-forecast-of-concurrent-flame-spread-in-micro-gravity/812788805923766273-3804) | Combines data assimilation with a physical model, validated on large-scale microgravity data | A research method, not a reusable library | Spread forecasting is not a novelty claim for PYRA |
| [NASA Saffire FDS modelling paper](https://ntrs.nasa.gov/api/citations/20260001600/downloads/Spacecraft%20Fire%20Safety%20Predictions.pdf) | Vehicle-scale model driven by heat and species source terms derived from payload measurements | A bespoke, per-flight workflow | The integration step PYRA automates with uncertainty |
| [NASA-STD-7009B](https://standards.nasa.gov/node/263) | Credibility factors for models and simulations | I found no open, machine-readable implementation | Evidence ledger aligned to its factors |

### 21.2 Corrections to earlier ideation

- **PBRE is not a combustion experiment.** It studies gas and liquid flow in a packed column ([Cygnus OA-4 overview](https://spaceflight101.com/cygnus-oa4/?p=146)). It is excluded from PYRA's scope.
- **A smooth 0g-to-1g Gravity Dial is wrong.** Partial-gravity data exists (drop-tower, aircraft, sounding-rocket and centrifuge work), and NASA reports show non-monotonic gravity dependence ([Ferkul, LPSC 2026](https://ntrs.nasa.gov/api/citations/20260001966/downloads/Ferkul-Lunar%20and%20Planetary%20Science%20Conf%202026%20v2.pdf)). FM2 is described as the first combustion experiment on another planetary body ([NASA combustion science](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science)); I could not confirm it has flown.
- **A plain data loader has little value on its own.** PSI is standardizing metadata and offers cloud access, so the contribution must be analysis and evidence, not retrieval.
- **Research gaps from NASA's own white paper:** solid-phase parameters depend on geometry and scale, and ML correlations must stay grounded in physics ([Gollner et al.](https://ntrs.nasa.gov/api/citations/20210022402/downloads/217-_GollnerMichaelJ.pdf)).

### 21.3 Education and outreach references

- [Candle flame in microgravity activity](https://www.nasa.gov/?p=182151) and the [Microgravity Educator Guide](https://www.nasa.gov/stem-content/microgravity-educator-guide/): existing grade 5 to 12 materials.
- [Science Activation](https://science.nasa.gov/?p=58322) and eClips: NASA education networks that could be approached through formal routes.
- [TechRise](https://www.usa.gov/challenges/nasa-techrise-student-challenge) and the [Student Spaceflight Experiments Program](https://www.k-state.edu/research/funding-opportunity-docs/SSEP%207.9.25.pdf) (run by the National Center for Earth and Space Science Education, not NASA): student flight programmes.
- [PhET design principles](https://phet.colorado.edu/en/about) and [JupyterLite](https://www.zonca.dev/posts/2026-05-18-jupyterlite-no-server-needed): interaction and deployment models.
- [NASA brand and media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/): logo, imagery and endorsement rules.
- [Space Apps 2026 dates](https://www.therecursive.com/nasa-space-apps-challenge-2026-where-to-join-it-in-cee/): 14 to 15 November. I could not retrieve the challenge statement itself.

### 21.4 Open questions

- Which Saffire, BASS and SoFIE sensor time series are actually downloadable, and in what formats? Every reader depends on this audit.
- Has FM2 flown, and is any partial-gravity data public?
- Who will review combustion-physics content and the concept sketches before learners see them?
- Which curricula (for example NGSS, CBSE) should the lessons map to first?
