from pathlib import Path

# pyra/paths.py -> the project root is two levels up
ROOT = Path(__file__).resolve().parents[1]

SCHEMA_SQL = ROOT / "pyra" / "schema.sql"

FACTSHEETS = ROOT / "data" / "factsheets"
DRAFTS = FACTSHEETS / "drafts"        # straight out of Prompt 1, not checked yet
VERIFIED = FACTSHEETS / "verified"    # passed Prompt 12 and a second person: these get loaded

DATABASE = ROOT / "data" / "pyra.db"


def load_env(path=ROOT / ".env"):
    """KEY=value lines from .env into os.environ, without overriding what is already set."""
    import os
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
