# PYRA command cheat sheet

Run these from the PYRA repository root after installing the package in editable mode.

```text
python -m pip install -e ".[dev]"
pyra demo
pyra simulate --initial 2 --rate 0.5 --duration 10 --steps 100
pyra simulate --window
pyra zone
pyra zone --initial 0.21 --inlet 0.21 --exchange-rate 0.1 --source-rate 0.001 --duration 60
pyra zone --window
pyra playground
pyra replay path/to/ledger.jsonl
python scripts/gen_api_docs.py
ruff check src tests
mypy src
pytest
git status --short --branch
git log -5 --oneline
```

Python first-program commands:

```python
import pyra as pk

hrr = pk.heat_release(0.21, 0.20, 0.01, 13_100_000, source_ref="doi:10.0000/example|synthetic")
trace = pk.simulate_decay(1.0, 0.5, 4.0)
pk.show_simulation(trace)
zone = pk.simulate_zone()  # simplified single-zone concentration exercise
pk.fire_playground()        # editable educational GUI
quick = pk.compare_values(observed=100, predicted=104, unit="W", tolerance=5)

from pyra_edu import decay_activity
lesson_example = decay_activity()  # fictional trace, clearly labelled
```

The simulation trace is fictional and for UI learning. The heat-release helper is provenance-aware
and requires a source reference. `replay` checks that a JSONL provenance ledger can be read; it does
not rerun an external simulator.

`pyra playground` opens the Fire Playground. Its flame graphic is a schematic; the graph models
only the simplified well-mixed oxygen balance. Use `compare_values` for a quick same-unit check;
use `pyra.compare` for evidence, uncertainty, and time-series analysis.

Keep this document command-only and copy-pasteable. Put explanations in `docs/usage.md`.
