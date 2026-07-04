"""이벤트 원자 → D-정렬 투영 + 위키 보드."""
import json
import sys
from datetime import date as _date
from pathlib import Path

from pipeline.atoms.db import get_conn


def _dday(today: str, event_date: str) -> int:
    y1, m1, d1 = (int(x) for x in today.split("-"))
    y2, m2, d2 = (int(x) for x in event_date.split("-"))
    return (_date(y2, m2, d2) - _date(y1, m1, d1)).days


def select_future_events(today: str, watchlist=None, sector=None) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM atoms WHERE event_type='event' AND is_active=1 "
        "AND event_date IS NOT NULL AND event_date >= ? ORDER BY event_date ASC",
        (today,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["structured_fields"] = json.loads(d["structured_fields"]) if d.get("structured_fields") else {}
        except (json.JSONDecodeError, TypeError):
            d["structured_fields"] = {}
        d["dday"] = _dday(today, d["event_date"])
        affected = d["structured_fields"].get("affected_stocks", [])
        if watchlist and not (set(watchlist) & set(affected)):
            continue
        if sector and d.get("sector") != sector:
            continue
        out.append(d)
    return out


_CONF_LABEL = {1: "● 확정", 2: "◐ 높음", 3: "○ 관측", 4: "· 추정"}


def _esc(s) -> str:
    """마크다운 표 셀 안전화: 파이프·개행 이스케이프."""
    return str(s).replace("|", "\\|").replace("\n", " ")


def build_calendar_board(today: str, out_dir: str) -> str:
    events = select_future_events(today)
    lines = [
        f"# 📅 이벤트 캘린더 — {today} 기준",
        "",
        "| 날짜 | D | 종목/섹터 | 이벤트 | 종류 | 확정도 |",
        "|---|---|---|---|---|---|",
    ]
    for e in events:
        sf = e["structured_fields"]
        conf = _CONF_LABEL.get(sf.get("confidence", 4), "· 추정")
        lines.append(
            f"| {e['event_date']} | D-{e['dday']} | {_esc(e['asset'])} | "
            f"{_esc(e['content'])} | {_esc(sf.get('event_kind', ''))} | {conf} |"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "캘린더_index.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    from datetime import datetime
    today = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent.parent / "wiki" / "이벤트캘린더"
    p = build_calendar_board(today, str(out_dir))
    print(f"보드 생성: {p}")
