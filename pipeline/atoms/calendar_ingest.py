"""섹터 캘린더 JSON → 이벤트 원자 적재."""
import hashlib
import json
import re
import sys
from pathlib import Path

from pipeline.atoms.db import insert_atom, init_db

FOREIGN_ENTITIES = {
    "마이크론", "인텔", "TSMC", "엔비디아", "AMD", "애플",
    "마이크론테크놀로지", "브로드컴", "퀄컴",
}
POLICY_KINDS = {"정책", "FOMC", "금통위", "수출지표", "MSCI", "경제지표"}
_KIND_MAP = {
    "실적발표": "실적발표", "IR": "IR", "정책": "정책", "전시": "전시", "수주": "수주",
    "FOMC": "정책", "금통위": "정책", "수출지표": "정책", "MSCI": "정책", "경제지표": "정책",
}


def _map_kind(ev_type: str) -> str:
    return _KIND_MAP.get(ev_type, "트리거")


def _entity_scope(company, ev_type: str) -> str:
    if ev_type in POLICY_KINDS:
        return "policy"
    if company and company in FOREIGN_ENTITIES:
        return "foreign"
    return "domestic"


def _confidence(confirmed: bool, mention_count: int, has_date: bool) -> int:
    if not has_date:
        return 4
    if confirmed:
        return 1
    if mention_count >= 2:
        return 2
    return 3


def _evid(event_date: str, event: str, company) -> str:
    raw = f"{event_date}|{event}|{company or ''}"
    norm = re.sub(r"\s+", "", raw)
    return "cal_" + hashlib.md5(norm.encode()).hexdigest()[:12]


def event_to_atom(ev: dict, sector: str, gen_date: str) -> dict:
    company = ev.get("company")
    event = ev.get("event", "")
    event_date = ev.get("date")
    ev_type = ev.get("type", "기타")
    confirmed = bool(ev.get("confirmed", False))
    importance = ev.get("importance", "")
    has_date = bool(event_date)
    kind = _map_kind(ev_type)
    scope = _entity_scope(company, ev_type)
    conf = _confidence(confirmed, 1, has_date)
    affected = [company] if company else []
    return {
        "id": _evid(event_date, event, company),
        "date": gen_date,
        "source_type": "calendar",
        "source_name": "sector_calendar",
        "source_trust": "A" if confirmed else "C",
        "raw_file": None,
        "relations": [],
        "layer": "L5",
        "sector": sector,
        "asset": company or sector,
        "asset_level": "stock" if company else "sector",
        "signal": "catalyst",
        "event_type": "event",
        "magnitude": "major" if "HIGH" in importance else "minor",
        "content_type": "fact",
        "strength_score": 3 if "HIGH" in importance else 1,
        "validity_type": "date",
        "validity_until": event_date,
        "is_active": 1,
        "content": f"{event} — {ev.get('desc', '')}".strip(" —"),
        "event_date": event_date,
        "structured_fields": {
            "event_date": event_date,
            "event_kind": kind,
            "entity": company or sector,
            "entity_scope": scope,
            "event_form": "point",
            "affected_stocks": affected,
            "confidence": conf,
            "confirmed": confirmed,
        },
    }


def ingest_calendar_file(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    gen_date = data.get("generated_at", "")[:10] or "1970-01-01"
    count = 0
    for ev in data.get("macro", []):
        insert_atom(event_to_atom(ev, sector="매크로", gen_date=gen_date))
        count += 1
    for sector, evs in data.get("sectors", {}).items():
        for ev in evs:
            insert_atom(event_to_atom(ev, sector=sector, gen_date=gen_date))
            count += 1
    return count


if __name__ == "__main__":
    init_db()
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        cal_dir = Path(__file__).parent.parent.parent / "raw" / "캘린더"
        files = sorted(cal_dir.glob("*_섹터캘린더.json"))
        if not files:
            print("섹터캘린더.json 없음 — 먼저 fetch_sector_calendar.py 실행")
            sys.exit(1)
        target = str(files[-1])
    n = ingest_calendar_file(target)
    print(f"적재 완료: {n}건 ← {target}")
