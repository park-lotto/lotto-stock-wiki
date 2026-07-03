"""브리핑 피드 일별 저장소 — output/flow_history.json과 같은 원자적 append 패턴.
리셋은 자정이 아니라 '날짜가 바뀐 뒤 첫 호출 시점'에 일어난다(_flow_day 규칙과 동일)."""
import json
import os
from datetime import datetime

_MAX_ITEMS = 200


def load_briefing(path: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            data.setdefault("insight", None)
            return data
    except Exception:
        pass
    return {"date": today, "items": [], "insight": None}


def append_briefing_item(path: str, item: dict) -> dict:
    data = load_briefing(path)
    data["items"] = [item] + data["items"]
    data["items"] = data["items"][:_MAX_ITEMS]
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass
    return data


def set_insight(path: str, insight_obj: dict) -> dict:
    """items는 그대로 두고 insight 필드만 갱신. append_briefing_item과 같은
    원자적 쓰기 패턴(tmp→os.replace)."""
    data = load_briefing(path)
    data["insight"] = insight_obj
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass
    return data
