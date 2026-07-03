import json, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
PENDING_PATH = ROOT / "out" / "goal_loop" / "pending.json"

def write(entry: dict) -> None:
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")

def read():
    if not PENDING_PATH.exists():
        return None
    try:
        return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

def clear() -> None:
    try:
        os.remove(PENDING_PATH)
    except FileNotFoundError:
        pass
