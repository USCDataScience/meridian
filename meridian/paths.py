from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "meridian.sqlite"
CONCEPTS_PATH = ROOT / "concepts.yaml"
WEB_DIST = ROOT / "web" / "dist"


def ensure_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
