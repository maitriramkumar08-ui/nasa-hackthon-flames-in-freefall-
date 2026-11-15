"""P4 manifest and local-reader contracts."""

import hashlib
from datetime import date

import pytest

from pyrakit.io import (
    FileHashMismatch,
    LocalCSVReader,
    ManifestEntry,
    ReaderKey,
    ReaderRegistry,
    fetch,
    read_manifest,
    write_manifest,
)


def test_manifest_round_trip_and_hash_checked_fetch(tmp_path) -> None:
    payload = b"time,value\n0,1\n"
    digest = hashlib.sha256(payload).hexdigest()
    entry = ManifestEntry(
        investigation="synthetic",
        file_pattern="trace.csv",
        version="1",
        sha256=digest,
        access_date=date(2026, 11, 15),
        url="https://example.invalid/trace.csv",
    )
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest, [entry])
    assert read_manifest(manifest) == [entry]
    destination = fetch(entry, tmp_path / "trace.csv", transport=lambda _: payload)
    assert destination.read_bytes() == payload


def test_hash_mismatch_is_refused(tmp_path) -> None:
    entry = ManifestEntry(
        investigation="synthetic", file_pattern="trace.csv", version="1",
        sha256="0" * 64, access_date=date(2026, 11, 15), url="https://example.invalid/trace.csv",
    )
    with pytest.raises(FileHashMismatch):
        fetch(entry, tmp_path / "trace.csv", transport=lambda _: b"different")


def test_registry_lookup_and_local_csv_reader(tmp_path) -> None:
    source = tmp_path / "trace.csv"
    source.write_text("time,value\n0,1\n", encoding="utf-8")
    registry = ReaderRegistry()
    reader = LocalCSVReader()
    registry.register(ReaderKey("synthetic", "*.csv", "1"), reader.read)
    selected = registry.lookup("synthetic", "trace.csv", "1")
    assert selected(source) == [{"time": "0", "value": "1"}]
    with pytest.raises(KeyError):
        registry.lookup("other", "trace.csv", "1")
