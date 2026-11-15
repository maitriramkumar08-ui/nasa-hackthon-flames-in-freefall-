"""Manifest records and hash-checked fetching primitives.

Manifests describe evidence; they never contain the evidence files themselves.
The transport is injected so tests and offline workflows make no network call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class FileHashMismatch(ValueError):
    """Raised when fetched bytes do not match a manifest hash."""


@dataclass(frozen=True)
class ManifestEntry:
    investigation: str
    file_pattern: str
    version: str
    sha256: str
    access_date: date
    url: str | None = None
    doi: str | None = None

    def __post_init__(self) -> None:
        if not self.investigation or not self.file_pattern or not self.version:
            raise ValueError("investigation, file_pattern and version are required")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256.lower()):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        if self.url is None and self.doi is None:
            raise ValueError("manifest needs a url or doi")

    def to_dict(self) -> dict[str, str | None]:
        return {
            "investigation": self.investigation,
            "file_pattern": self.file_pattern,
            "version": self.version,
            "sha256": self.sha256,
            "access_date": self.access_date.isoformat(),
            "url": self.url,
            "doi": self.doi,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ManifestEntry:
        return cls(
            investigation=str(value["investigation"]),
            file_pattern=str(value["file_pattern"]),
            version=str(value["version"]),
            sha256=str(value["sha256"]).lower(),
            access_date=date.fromisoformat(str(value["access_date"])),
            url=None if value.get("url") is None else str(value["url"]),
            doi=None if value.get("doi") is None else str(value["doi"]),
        )


def write_manifest(path: Path, entries: list[ManifestEntry]) -> None:
    """Write a stable, human-readable JSON manifest."""
    payload = [entry.to_dict() for entry in entries]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> list[ManifestEntry]:
    """Read a JSON manifest and validate every entry."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("manifest root must be a list")
    return [ManifestEntry.from_mapping(item) for item in raw]


def fetch(
    entry: ManifestEntry,
    destination: Path,
    *,
    transport: Callable[[str], bytes],
) -> Path:
    """Fetch one entry through an injected transport and verify its SHA-256."""
    if entry.url is None:
        raise ValueError("a local fetch needs a URL; DOI resolution is intentionally not implicit")
    payload = transport(entry.url)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != entry.sha256:
        raise FileHashMismatch(f"{entry.file_pattern}: expected {entry.sha256}, got {digest}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return destination


__all__ = ["FileHashMismatch", "ManifestEntry", "fetch", "read_manifest", "write_manifest"]
