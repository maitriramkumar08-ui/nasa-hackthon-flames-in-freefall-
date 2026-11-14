from pathlib import Path

# tools/phase0/paths.py -> project root is three levels up
ROOT = Path(__file__).resolve().parents[2]

SOURCES_CSV = ROOT / "sources" / "sources.csv"
DECISIONS_JSON = ROOT / "config" / "decisions.json"
