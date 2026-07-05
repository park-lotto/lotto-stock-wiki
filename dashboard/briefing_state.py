"""장중 시황 브리핑 — 오늘의 스토리 상태 영속(재시작해도 스토리 유지)."""
import json
import os


def reset_state(date_str: str) -> dict:
    return {"date": date_str, "session_phase": None, "verdict": None,
            "narrative": "", "turning_points": [], "baseline": None,
            "surfaced_news_ids": [], "last_synth_ts": 0.0, "updated_at": ""}


def is_new_day(state: dict, date_str: str) -> bool:
    return not state or state.get("date") != date_str


def load_state(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass
