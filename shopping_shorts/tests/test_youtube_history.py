# -*- coding: utf-8 -*-
"""유튜브도 '이번 주·이번 달'에 남는다 (2026-09-04 사장님).

제보: "유튜브는 48시간으로만 되어있는데 이것도 이번주 터진것 이번달 명예의전당에 남게 할수있나"

막혀 있던 뿌리 두 개:
1. `reel_history`가 **인스타 전용**이었다(platform 컬럼 자체가 없었다).
   유튜브 수집(save_last_run_platform)은 last_run 스냅샷만 덮어써서 지난 것이 안 남았다.
2. `api_reference`가 platform != 'instagram'이면 **빈 목록**을 돌려줬다.

여기서 못 박는 것 — 전부 조용히 깨지는 실패다:
- 유튜브 수집이 히스토리에 남는가 (안 남으면 기간탭이 영영 빈다)
- 플랫폼이 **섞이지 않는가** (인스타 탭에 유튜브가 뜨면 더 나쁘다)
- first_seen 기준으로 기간이 걸리는가
"""
from datetime import datetime, timedelta, timezone

from shopping_shorts.store import Store


def _items():
    return [
        {"shortcode": "yt_hit", "username": "ch1", "name": "채널1", "category": "제품정체형",
         "url": "https://youtube.com/watch?v=yt_hit", "thumbnail": "t",
         "caption": "천재가 만든 제품의 정체", "views": 100000, "comments": 1500},
        {"shortcode": "yt_low", "username": "ch2", "name": "채널2", "category": "홈템",
         "url": "u", "thumbnail": "t", "caption": "그냥 살림팁", "views": 500, "comments": 10},
    ]


def test_유튜브_수집이_히스토리에_남는다(tmp_path):
    s = Store(tmp_path / "t.db")
    now = datetime.now(timezone.utc).isoformat()
    s.save_last_run_platform("youtube", _items(), now)
    got = [r["shortcode"] for r in s.hits_since(7, min_comments=500, platform="youtube")]
    assert got == ["yt_hit"], "유튜브 수집이 reel_history에 안 남았다 → 기간탭이 영영 빈다"


def test_플랫폼이_섞이지_않는다(tmp_path):
    s = Store(tmp_path / "t.db")
    now = datetime.now(timezone.utc).isoformat()
    s.save_last_run_platform("youtube", _items(), now)
    assert s.hits_since(7, min_comments=500, platform="instagram") == [], \
        "인스타 탭에 유튜브가 섞였다"


def test_기간은_first_seen으로_걸린다(tmp_path):
    """★백필이 옛 수집일을 first_seen에 넣는 이유 — 안 그러면 '이번 주'가 오늘로 몰린다."""
    import sqlite3
    db = tmp_path / "t.db"
    s = Store(db)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO reel_history(shortcode,username,name,category,url,thumb,caption,"
            "views,comments,first_seen,last_seen,upload_ts,platform) "
            "VALUES('old1','ch','채널','','u','t','천재의 정체',9999,1500,?,?,'','youtube')",
            (old, now))
    assert [r["shortcode"] for r in s.hits_since(7, min_comments=500, platform="youtube")] == []
    assert [r["shortcode"] for r in s.hits_since(30, min_comments=500, platform="youtube")] == ["old1"]
