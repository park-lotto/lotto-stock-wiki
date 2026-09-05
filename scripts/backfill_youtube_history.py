# -*- coding: utf-8 -*-
"""유튜브 '이번 주·이번 달' 재고 복원 — platform_snapshots → reel_history (2026-09-04).

## 왜 필요한가
사장님: "유튜브는 48시간으로만 되어있는데 이것도 이번주 터진것 이번달 명예의전당에
남게 할수있나". 막혀 있던 이유는 `reel_history`가 인스타 전용이어서였고, 그건 고쳤다
(platform 축 추가). 그런데 **과거 재고**가 없다 — 유튜브는 last_run 스냅샷만 덮어써 와서
지나간 수집분의 제목·썸네일·조회수가 남아 있지 않다.

## 있는 것 / 없는 것 (서버 실측 2026-09-04)
    platform_snapshots  platform='youtube'  329,416행 · 고유 45,387편 · 2026-07-13~09-03(60일)
    → 그런데 컬럼이 shortcode/base/delta 뿐이라 **카드를 그릴 수 없다**(제목·채널·조회수 없음).

## 그래서 이 스크립트가 하는 일
video_id를 50개씩 묶어 videos.list(part=snippet,statistics)로 메타를 받아 reel_history에
넣는다. 썸네일은 API 없이 video_id로 만든다(i.ytimg.com/vi/<id>/hqdefault.jpg).

비용: videos.list는 **호출당 1유닛**(50편 묶음). 45,387편 = 약 908유닛.
      하루 무료 10,000유닛의 9% — 돈은 들지 않는다. 그래도 다른 기능과 나눠 쓰므로
      기본은 --limit로 조금씩 돌리게 해 뒀다.

사용:
    python -m scripts.backfill_youtube_history --days 30 --limit 2000        # 맛보기
    python -m scripts.backfill_youtube_history --days 30                     # 전체
    python -m scripts.backfill_youtube_history --days 30 --dry-run           # 호출 없이 대상만
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

from shopping_shorts import config
from shopping_shorts.store import Store

_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _targets(db_path, days, limit):
    """platform_snapshots에서 유튜브 video_id를 최근 것부터. 이미 있는 건 건너뛴다."""
    with sqlite3.connect(db_path) as c:
        rows = c.execute(
            "SELECT s.shortcode, MIN(s.run_date), MAX(s.run_date) "
            "FROM platform_snapshots s "
            "LEFT JOIN reel_history h ON h.shortcode = s.shortcode "
            "WHERE s.platform = 'youtube' AND h.shortcode IS NULL "
            "  AND s.run_date >= datetime('now', ?) "
            "GROUP BY s.shortcode ORDER BY MAX(s.run_date) DESC" + (" LIMIT ?" if limit else ""),
            (f"-{int(days)} day", int(limit)) if limit else (f"-{int(days)} day",),
        ).fetchall()
    return rows


def _fetch(chunk, key):
    r = requests.get(_VIDEOS_URL, params={
        "part": "snippet,statistics", "id": ",".join(chunk), "key": key}, timeout=30)
    if r.status_code != 200:
        return None, r.status_code
    return r.json().get("items", []), 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="며칠치까지 되살릴까(기본 30)")
    ap.add_argument("--limit", type=int, default=0, help="이번에 처리할 영상 수(0=전부)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    db = a.db or str(config.DB_PATH) if hasattr(config, "DB_PATH") else a.db
    if not db:
        from shopping_shorts.app import DB_PATH
        db = str(DB_PATH)

    tgt = _targets(db, a.days, a.limit)
    print(f"대상 {len(tgt)}편 (최근 {a.days}일, reel_history에 아직 없는 것)")
    print(f"예상 호출 {(len(tgt) + 49) // 50}회 = 같은 수의 쿼터 유닛")
    if a.dry_run or not tgt:
        for sc, first, last in tgt[:10]:
            print("   ", sc, first, "~", last)
        return

    keys = list(config.YOUTUBE_API_KEYS or [])
    if not keys:
        print("유튜브 API 키가 없습니다 — config.YOUTUBE_API_KEYS")
        sys.exit(1)
    ki = 0
    store = Store(db)
    seen = {sc: (first, last) for sc, first, last in tgt}
    ids = [sc for sc, _, _ in tgt]
    got = skipped = 0

    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        items = None
        for _ in range(len(keys)):                     # 쿼터 초과면 다음 키로
            items, code = _fetch(chunk, keys[ki])
            if items is not None:
                break
            ki = (ki + 1) % len(keys)
            time.sleep(0.4)
        if items is None:
            print(f"  [{i}] 모든 키 실패 — 여기서 멈춥니다(다음에 이어서 돌리면 됩니다)")
            break

        rows = []
        for it in items:
            vid = it.get("id")
            sn = it.get("snippet") or {}
            st = it.get("statistics") or {}
            first, last = seen.get(vid, (None, None))
            rows.append({
                "shortcode": vid,
                "username": sn.get("channelId") or "",
                "name": sn.get("channelTitle") or "",
                "category": "",                       # 분류는 화면이 categorize로 다시 한다
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "caption": sn.get("title") or "",
                "views": int(st.get("viewCount") or 0),
                "comments": int(st.get("commentCount") or 0),
                "timestamp": sn.get("publishedAt") or "",
                "_first_seen": first,
            })
        got += len(rows)
        skipped += len(chunk) - len(rows)             # 삭제·비공개된 영상
        # ★직접 넣는다 — store._record_history를 쓰면 안 된다.
        #   그 함수는 first_seen·last_seen을 **같은 값**으로 넣고 끝에서
        #   "last_seen이 30일보다 오래된 행 삭제"를 돌린다 → 옛 날짜로 넣는 순간
        #   방금 넣은 행이 그 자리에서 지워진다(넣었는데 0건이 되는 조용한 실패).
        # ★first_seen은 **그때 그 수집일**, last_seen은 **지금**으로 갈라 넣는다.
        #   first_seen이 '이번 주/이번 달'의 기준이고(hits_since), last_seen은 정리 기준이다.
        nowiso = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db) as c:
            for r in rows:
                fs = r.pop("_first_seen") or nowiso
                c.execute(
                    "INSERT INTO reel_history"
                    "(shortcode, username, name, category, url, thumb, caption,"
                    " views, comments, first_seen, last_seen, upload_ts, platform) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'youtube') "
                    "ON CONFLICT(shortcode) DO UPDATE SET "
                    "  views=excluded.views, comments=excluded.comments,"
                    "  last_seen=excluded.last_seen, platform='youtube'",
                    (r["shortcode"], r["username"], r["name"], r["category"], r["url"],
                     r["thumbnail"], r["caption"], r["views"], r["comments"],
                     fs, nowiso, r["timestamp"]))
        print(f"  {i + len(chunk)}/{len(ids)} — 받은 {got} · 사라진 {skipped}")
        time.sleep(0.2)

    print(f"끝. reel_history에 유튜브 {got}편 적재(삭제·비공개 {skipped}편 제외).")


if __name__ == "__main__":
    main()
