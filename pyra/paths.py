from pathlib import Path

# pyra/paths.py -> the project root is two levels up
ROOT = Path(__file__).resolve().parents[1]

SCHEMA_SQL = ROOT / "pyra" / "schema.sql"

FACTSHEETS = ROOT / "data" / "factsheets"
DRAFTS = FACTSHEETS / "drafts"        # straight out of Prompt 1, not checked yet
VERIFIED = FACTSHEETS / "verified"    # passed Prompt 12 and a second person: these get loaded
SAMPLES = ROOT / "data" / "samples"   # DUMMY data for trying things out and for tests

DATABASE = ROOT / "data" / "pyra.db"
DUMMY_DATABASE = ROOT / "data" / "dummy.db"
