"""Readers for the supplied PSI metadata and raw CSV formats.

These readers preserve source text and raw values. They do not infer calibration,
units, flame success, or links between separate PSI files.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PSIMetadata:
    investigation_id: str
    title: str
    approach: str | None
    doi: str | None
    members: tuple[str, ...]


@dataclass(frozen=True)
class PSI159Setpoints:
    metadata: dict[str, str]
    rows: tuple[dict[str, str], ...]


def _fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("\t")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def read_psi_metadata_zip(path: Path) -> PSIMetadata:
    """Read the hand-curated metadata text from a PSI ZIP archive."""
    with zipfile.ZipFile(path) as archive:
        members = tuple(archive.namelist())
        investigation_name = next(name for name in members if name.startswith("i_"))
        fields = _fields(archive.read(investigation_name).decode("utf-8", "replace"))
    return PSIMetadata(
        investigation_id=fields.get("Study Identifier", ""),
        title=fields.get("Study Title", ""),
        approach=fields.get("Comment[Approach]") or None,
        doi=fields.get("Comment[DOI]") or None,
        members=members,
    )


def read_psi159_setpoints(path: Path) -> PSI159Setpoints:
    """Read PSI-159's metadata row and raw setpoint rows without calibration."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) < 2:
        raise ValueError("PSI-159 setpoint file needs a metadata row and CSV header")
    metadata: dict[str, str] = {}
    for item in next(csv.reader([lines[0]])):
        key, separator, value = item.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    rows = tuple(csv.DictReader(io.StringIO("\n".join(lines[1:]))))
    return PSI159Setpoints(metadata=metadata, rows=rows)


__all__ = ["PSI159Setpoints", "PSIMetadata", "read_psi159_setpoints", "read_psi_metadata_zip"]
