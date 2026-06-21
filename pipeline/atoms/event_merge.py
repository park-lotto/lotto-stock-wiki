"""채널간 이벤트 병합 (비파괴) — 같은 이벤트면 mention_count/mention_channels만 UPDATE."""
import sys
import json
import argparse
from datetime import datetime

from .db import get_conn, init_db, migrate_db
from .telegram_questionnaire import _event_key

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def merge_events(date: str) -> int:
    """해당 날짜의 이벤트성 원자(event_type IN event/macro)를 _event_key로 그룹핑.
    2개 이상 서로 다른 source_name이 같은 이벤트를 말하면 그 그룹 원자들에
    mention_count=채널수, mention_channels=채널목록 UPDATE. 반환=업데이트된 원자 수."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, source_name, content FROM atoms "
        "WHERE date=? AND event_type IN ('event','macro') AND is_active=1",
        (date,),
    ).fetchall()
    groups = {}  # event_key -> {"ids": [...], "sources": set()}
    for id_, src, content in rows:
        if not content:
            continue
        k = _event_key(content)
        g = groups.setdefault(k, {"ids": [], "sources": set()})
        g["ids"].append(id_)
        if src:
            g["sources"].add(src)
    updated = 0
    for g in groups.values():
        if len(g["sources"]) >= 2:  # 서로 다른 채널 2개 이상 = 교차
            chans = sorted(g["sources"])
            payload = json.dumps(chans, ensure_ascii=False)
            for id_ in g["ids"]:
                conn.execute(
                    "UPDATE atoms SET mention_count=?, mention_channels=? WHERE id=?",
                    (len(chans), payload, id_),
                )
                updated += 1
    conn.commit()
    conn.close()
    return updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()
    init_db(); migrate_db()
    n = merge_events(args.date)
    print(f"[이벤트병합] {args.date}: {n}개 원자에 교차언급 표시")


if __name__ == "__main__":
    main()
