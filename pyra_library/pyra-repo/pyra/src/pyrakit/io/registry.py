"""Reader registry keyed by investigation, file pattern and version."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

Reader = Callable[[Path], Any]


@dataclass(frozen=True)
class ReaderKey:
    investigation: str
    file_pattern: str
    version: str


class ReaderRegistry:
    """Explicit, hand-curated reader registry; there is no auto-discovery."""

    def __init__(self) -> None:
        self._entries: list[tuple[ReaderKey, Reader]] = []

    def register(self, key: ReaderKey, reader: Reader) -> None:
        if any(existing == key for existing, _ in self._entries):
            raise ValueError(f"reader already registered for {key}")
        self._entries.append((key, reader))

    def lookup(self, investigation: str, filename: str, version: str) -> Reader:
        for key, reader in self._entries:
            if (
                key.investigation == investigation
                and key.version == version
                and fnmatch(filename, key.file_pattern)
            ):
                return reader
        raise KeyError(f"no reader for {investigation}/{filename} version {version}")


__all__ = ["ReaderKey", "ReaderRegistry"]
