"""Small local readers used before investigation-specific mappings exist."""

from __future__ import annotations

import csv
from pathlib import Path


class LocalCSVReader:
    """Read a CSV into records without guessing scientific channel semantics."""

    def read(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))


__all__ = ["LocalCSVReader"]
