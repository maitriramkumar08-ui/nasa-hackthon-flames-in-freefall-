"""Dependency-light HTML reports with visible epistemic status."""

from __future__ import annotations

import html
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pyra.adapters import SimulationResult
from pyra.coverage import CoverageReport
from pyra.provenance import Quantity


def _row(item: Any) -> str:
    if isinstance(item, Quantity):
        return (
            f"<tr><td>Quantity</td><td>{html.escape(str(item.value))} {html.escape(item.unit)}</td>"
            f"<td>{item.status.name}</td><td>{html.escape(item.prov.artifact_id)}</td></tr>"
        )
    if isinstance(item, SimulationResult):
        return (
            f"<tr><td>Simulation {html.escape(item.scenario_id)}</td>"
            f"<td>{html.escape(str(dict(item.outputs)))}</td><td>{item.status.name}</td>"
            f"<td>{html.escape(item.model_card_id)}</td></tr>"
        )
    if isinstance(item, CoverageReport):
        return (
            f"<tr><td>Coverage {html.escape(item.scenario_id)}</td>"
            f"<td>{html.escape(item.verdict)}; "
            f"nearest={html.escape(str(item.nearest_distances))}</td>"
            f"<td>INTERPRETATION</td><td>coverage:{html.escape(item.scenario_id)}</td></tr>"
        )
    return (
        f"<tr><td>Object</td><td>{html.escape(str(item))}</td>"
        f"<td>UNKNOWN</td><td>not-recorded</td></tr>"
    )


def build_report(items: Iterable[Any], out: Path, *, title: str = "PYRA report") -> Path:
    """Write a self-contained HTML report and return its path."""
    rows = "\n".join(_row(item) for item in items)
    document = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>
<style>body{{font:16px system-ui;margin:2rem}} table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:.5rem;text-align:left}} th{{background:#eee}}</style></head>
<body><h1>{html.escape(title)}</h1><p>Status and provenance are shown for every result.</p>
<table><thead><tr><th>Type</th><th>Value</th><th>Status</th><th>Ledger or model ID</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    return out


__all__ = ["build_report"]
