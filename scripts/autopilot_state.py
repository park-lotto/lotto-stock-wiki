"""미해결 이상 항목 영속 추적 — 해결될 때까지 날짜와 무관하게 누적, 스로틀은 진단
호출에만 적용(보고는 매일 빠짐없이 포함)."""
import json
import os
from datetime import datetime

_META_KEYS = {"_daily_stats"}


def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def bump_daily_stat(state, today_str, key):
    stats = state.get("_daily_stats")
    if not stats or stats.get("date") != today_str:
        stats = {"date": today_str}
    stats[key] = stats.get(key, 0) + 1
    state["_daily_stats"] = stats
    return state


def get_daily_stats(state, today_str):
    stats = state.get("_daily_stats") or {}
    if stats.get("date") != today_str:
        return {"detected": 0, "auto_fixed": 0, "escalated": 0}
    return {"detected": stats.get("detected", 0), "auto_fixed": stats.get("auto_fixed", 0),
            "escalated": stats.get("escalated", 0)}


def touch_anomaly(state, channel, today_str):
    """이상 감지된 채널의 최근 관측일 갱신(없으면 신규 등록, 신규일 때만 '감지' 통계 증가)."""
    entry = state.get(channel)
    if entry is None:
        entry = {"first_detected": today_str, "diagnosed_dates": [], "latest_outcome": None}
        bump_daily_stat(state, today_str, "detected")
    entry["last_seen"] = today_str
    state[channel] = entry
    return state


def should_diagnose(state, channel, today_str):
    entry = state.get(channel)
    if entry is None:
        return True
    return today_str not in entry.get("diagnosed_dates", [])


def mark_diagnosed(state, channel, today_str, outcome):
    """outcome: 'auto_fixed' | 'escalated'. auto_fixed면 추적목록에서 제거(다음 슬럿부턴 정상 취급)."""
    entry = state[channel]
    entry.setdefault("diagnosed_dates", []).append(today_str)
    entry["latest_outcome"] = outcome
    bump_daily_stat(state, today_str, outcome)
    if outcome == "auto_fixed":
        del state[channel]
    else:
        state[channel] = entry
    return state


def resolve_if_healed(state, channel, today_str):
    """이전에 추적중이던 채널이 이번엔 정상으로 관측되면 제거하고 해소 정보 반환."""
    entry = state.pop(channel, None)
    if entry is None:
        return None
    return {"channel": channel, "first_detected": entry["first_detected"],
            "days_open": days_open(entry, today_str)}


def days_open(entry, today_str):
    first = datetime.strptime(entry["first_detected"], "%Y-%m-%d")
    today = datetime.strptime(today_str, "%Y-%m-%d")
    return (today - first).days + 1


def open_escalations(state):
    return {k: v for k, v in state.items()
            if k not in _META_KEYS and v.get("latest_outcome") == "escalated"}
