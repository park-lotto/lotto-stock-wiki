"""
channel_pipeline/trust_tracker.py — 채널 신뢰도 CRUD
"""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
TRUST_FILE = ROOT / "pipeline" / "channel_trust.json"

GRADE_THRESHOLDS = [
    ("S",  0.85, 20),
    ("A+", 0.80, 15),
    ("A-", 0.75, 15),
    ("B+", 0.70, 10),
    ("B-", 0.60, 10),
    ("C",  0.50,  5),
    ("D",  0.00,  0),
]


def _compute_grade(correct: int, total: int) -> str:
    if total == 0:
        return "신규"
    acc = correct / total
    for grade, min_acc, min_calls in GRADE_THRESHOLDS:
        if acc >= min_acc and total >= min_calls:
            return grade
    return "D"


def load() -> dict:
    if not TRUST_FILE.exists():
        return {"version": "1.0", "last_updated": "", "channels": {}}
    return json.loads(TRUST_FILE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    TRUST_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    TRUST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_or_create(trust: dict, channel_source: str, platform: str = "unknown") -> dict:
    ch = trust.setdefault("channels", {})
    if channel_source not in ch:
        ch[channel_source] = {
            "display_name": channel_source,
            "platform": platform,
            "speciality": [],
            "grade": "신규",
            "stats": {"total_calls": 0, "correct": 0, "incorrect": 0,
                      "pending": 0, "accuracy_rate": 0.0},
            "by_category": {},
            "by_sector": {},
            "calls": [],
        }
    return ch[channel_source]


def apply_deltas(trust: dict, deltas: list[dict]) -> dict:
    """Agent B가 생성한 trust_delta 반영 (pending 처리)"""
    for delta in deltas:
        src = delta.get("channel_source", "")
        d = delta.get("delta", 0)
        ch = get_or_create(trust, src)
        if d > 0:
            ch["stats"]["pending"] = ch["stats"].get("pending", 0) + 1
        # 실제 correct/incorrect는 mark_verified에서 확정
    save(trust)
    return trust


def mark_verified(channel_source: str, decision_id: str,
                  correct: bool, sector: str | None = None) -> None:
    """검증 완료 후 correct/incorrect 확정"""
    trust = load()
    ch = get_or_create(trust, channel_source)
    stats = ch["stats"]

    # pending → 확정
    stats["pending"] = max(0, stats.get("pending", 0) - 1)
    if correct:
        stats["correct"] = stats.get("correct", 0) + 1
    else:
        stats["incorrect"] = stats.get("incorrect", 0) + 1

    total = stats.get("correct", 0) + stats.get("incorrect", 0)
    stats["total_calls"] = total
    stats["accuracy_rate"] = round(stats["correct"] / total, 3) if total else 0.0
    ch["grade"] = _compute_grade(stats["correct"], total)

    # 섹터별 추적
    if sector:
        by_sec = ch.setdefault("by_sector", {})
        sec_stat = by_sec.setdefault(sector, {"correct": 0, "incorrect": 0})
        if correct:
            sec_stat["correct"] += 1
        else:
            sec_stat["incorrect"] += 1

    # 콜 기록 업데이트
    for call in ch.get("calls", []):
        if call.get("id") == decision_id:
            call["status"] = "verified"
            call["resolution_date"] = datetime.now().strftime("%Y-%m-%d")
            call["verdict"] = "correct" if correct else "incorrect"
            break

    save(trust)


def add_call(channel_source: str, call_record: dict) -> None:
    """새 콜 추가"""
    trust = load()
    ch = get_or_create(trust, channel_source)
    ch["calls"].append(call_record)
    ch["stats"]["pending"] = ch["stats"].get("pending", 0) + 1
    save(trust)


def get_summary() -> list[dict]:
    """신뢰도 순 정렬 목록"""
    trust = load()
    rows = []
    for src, ch in trust.get("channels", {}).items():
        stats = ch.get("stats", {})
        rows.append({
            "channel": src,
            "grade": ch.get("grade", "신규"),
            "accuracy": stats.get("accuracy_rate", 0),
            "correct": stats.get("correct", 0),
            "incorrect": stats.get("incorrect", 0),
            "pending": stats.get("pending", 0),
        })
    return sorted(rows, key=lambda x: x["accuracy"], reverse=True)


def get_accuracy(channel_source: str) -> float:
    trust = load()
    ch = trust.get("channels", {}).get(channel_source, {})
    return ch.get("stats", {}).get("accuracy_rate", 0.0)
