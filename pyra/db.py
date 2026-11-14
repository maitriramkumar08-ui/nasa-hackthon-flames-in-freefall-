import sqlite3
from pathlib import Path

from . import paths


def connect(db_path):
    """Open an existing database. Rows come back like dicts: row["acronym"]."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create(db_path):
    """Start a new, empty database (deletes the old file). Use ":memory:" in tests."""
    if str(db_path) != ":memory:":
        Path(db_path).unlink(missing_ok=True)
    conn = connect(db_path)
    conn.executescript(paths.SCHEMA_SQL.read_text(encoding="utf-8"))
    return conn
