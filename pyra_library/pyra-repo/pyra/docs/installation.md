# Installation

PYRA is pre-alpha and **not published on PyPI**. Install it from a checkout of the repository
(Python 3.11 or newer):

```bash
git clone <your repository url> pyra && cd pyra
python -m venv .venv && source .venv/bin/activate
pip install -e .            # core: numpy, scipy, pydantic, pint, xarray
pip install -e ".[dev]"     # plus pytest, hypothesis, ruff, mypy, nox, mkdocs
```

Optional extras: `uq`, `gp`, `vision`, `report`, `fds`, `edu`, `service`. Several extras are
placeholders until their packages are chosen (see `TODO(verify)` in `pyproject.toml`).

Check that it works:

```bash
python -c "import pyrakit; print(pyrakit.__version__)"
python examples/quickstart.py
pytest
```

The provenance layer (`pyrakit.provenance`, everything in the quickstart) uses only the Python
standard library, so it works before the heavier dependencies are installed.

!!! note "Status"
    Implemented: provenance (P1), Pint and pydantic schemas (P2), S0 calorimetry/UQ primitives (P3),
    manifest-driven local I/O, PSI metadata ZIP extraction and raw PSI-159 setpoint parsing (P4
    foundation), plus matching, coverage, comparison, adapters, reports, replay and the beginner
    API. Readers preserve raw values and do not imply calibration. Catalog backends and calibrated
    investigation readers remain gated on verified source mappings and calibration evidence; see
    `docs/data_audit.md`.
