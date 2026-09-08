"""랭킹 수집이 멈춘 플랫폼(B-41, 사장님 제보 ③).
저장 위치는 settings['last_run::<platform>'] = {"items":[...],"collected_at":...}
(store.py:2594·2637), 인스타만 last_run 테이블 id=1 (store.py:491, app.py:343)."""
import json
from datetime import datetime, timezone

from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "랭킹 수집이 멈춘 플랫폼", "every": "1h",
        "source": "reference.db settings last_run::* / last_run 테이블"}
PLATFORMS = ("youtube", "tiktok", "threads", "naverclip", "pinterest", "xiaohongshu", "douyin")
MAX_AGE_H = 26


def _age_h(collected_at, now):
    dt = datetime.fromisoformat(str(collected_at).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600


def _one(platform, items, collected_at, now):
    item = f"h_ranking_fresh::{platform}"
    name = f"{META['name']} — {platform}"
    if not collected_at:
        return Sample(item, name, None, False, detail="수집 기록 없음")
    age = _age_h(collected_at, now)
    n = len(items or [])
    ok = age < MAX_AGE_H and n >= 1
    return Sample(item, name, round(age, 1), ok, detail=f"{age:.1f}시간 전 · {n}건")


def measure(ctx):
    now = ctx["now"]
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001 — 소스를 못 읽으면 '0건'이 아니라 판정 불가
        return [Sample(f"h_ranking_fresh::{p}", META["name"], None, None, detail=f"DB 읽기 실패: {e!r}")
                for p in PLATFORMS + ("instagram",)]
    out = []
    try:
        for p in PLATFORMS:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (f"last_run::{p}",)).fetchone()
            d = json.loads(row["value"]) if row and row["value"] else {}
            out.append(_one(p, d.get("items"), d.get("collected_at"), now))
        row = conn.execute("SELECT items_json, collected_at FROM last_run WHERE id=1").fetchone()
        items = json.loads(row["items_json"]) if row else []
        out.append(_one("instagram", items, row["collected_at"] if row else None, now))
    finally:
        conn.close()
    return out
