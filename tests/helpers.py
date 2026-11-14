import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


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
