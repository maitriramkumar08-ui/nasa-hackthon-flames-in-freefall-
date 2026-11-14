import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))   # phase0 lives in tools/
sys.path.insert(0, str(ROOT))             # pyra lives at the project root


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
    """A fresh copy of one of the DUMMY sample sheets, safe to change in a test."""
    return json.loads((ROOT / "data" / "samples" / name).read_text(encoding="utf-8"))
