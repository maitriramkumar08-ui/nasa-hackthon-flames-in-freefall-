import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Test-only sheets and eval docs, every one marked NOT REAL DATA. The app never loads them.
FIXTURES = ROOT / "tests" / "fixtures"
SAMPLES = FIXTURES / "samples"
sys.path.insert(0, str(ROOT / "tools"))   # phase0 lives in tools/
sys.path.insert(0, str(ROOT))             # pyra lives at the project root
# Tests never call a real model, even when .env holds a GROQ_API_KEY.
os.environ["PYRA_AGENTS_OFFLINE"] = "1"


class TempFiles:
    """Mixin: self.write(name, text) drops a file into a throwaway folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def write(self, name, text):
        path = self.folder / name
        path.write_text(text, encoding="utf-8")
        return path


def dummy_sheet(name="dummy_a1.json"):
    """A fresh copy of one of the test sample sheets, safe to change in a test."""
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def sample_conn():
    """An in-memory database built from the test sample sheets."""
    from pyra import db
    from pyra.loader import load_folder
    conn = db.create(":memory:")
    load_folder(conn, SAMPLES)
    return conn


def sample_corpus():
    from pyra import evidence
    return evidence.load(sample_conn())
