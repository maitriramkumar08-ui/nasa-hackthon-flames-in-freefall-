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
python -c "import pyra; print(pyra.__version__)"
python examples/quickstart.py
pytest
```

The provenance layer (`pyra.provenance`, everything in the quickstart) uses only the Python
standard library, so it works before the heavier dependencies are installed.

!!! note "Status"
    Implemented: `pyra.provenance` (prompt P1). Everything else is a stub that imports but does
    nothing. Units and schemas are drafted on the `p2-draft` branch and not yet verified.
