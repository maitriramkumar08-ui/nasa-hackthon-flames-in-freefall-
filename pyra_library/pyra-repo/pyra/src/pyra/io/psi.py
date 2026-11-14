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

from pyra.schema.psi import PSIConditionRecord


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
        metadata_files = tuple(
            name for name in members if Path(name).name.startswith("i_") and not name.endswith("/")
        )
        if len(metadata_files) != 1:
            raise ValueError(
                f"Expected exactly one investigation metadata file (i_*); found {len(metadata_files)}"
            )
        investigation_name = metadata_files[0]
        fields = _fields(archive.read(investigation_name).decode("utf-8", "replace"))
    if not fields:
        raise ValueError(f"Investigation metadata file {investigation_name!r} contains no tab fields")
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
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])))
    if not reader.fieldnames or not any(name.strip() for name in reader.fieldnames):
        raise ValueError("PSI-159 setpoint file is missing a usable CSV header")
    rows = tuple(reader)
    if not rows:
        raise ValueError("PSI-159 setpoint file contains no setpoint rows")
    return PSI159Setpoints(metadata=metadata, rows=rows)


def psi159_condition_record(
    setpoints: PSI159Setpoints,
    *,
    row_index: int,
    source_id: str,
    source_uri: str | None = None,
) -> PSIConditionRecord:
    """Wrap one PSI-159 setpoint row as raw conditions, without voltage calibration."""
    if row_index < 0:
        raise IndexError("row_index must be non-negative")
    try:
        row = setpoints.rows[row_index]
    except IndexError as error:
        raise IndexError(f"PSI-159 row_index {row_index} is outside the available setpoint rows") from error
    raw_fields = {f"metadata.{key}": value for key, value in setpoints.metadata.items()}
    raw_fields.update({f"setpoint.{key}": value for key, value in row.items() if value is not None})
    return PSIConditionRecord(
        investigation_id="PSI-159",
        source_id=source_id,
        source_uri=source_uri,
        test_point_id=setpoints.metadata.get("Test Point"),
        raw_fields=raw_fields,
        mapping_status="raw",
        mapping_note="Controller setpoints are preserved in source units; calibration is unavailable.",
    )


__all__ = [
    "PSI159Setpoints",
    "PSIMetadata",
    "psi159_condition_record",
    "read_psi159_setpoints",
    "read_psi_metadata_zip",
]
