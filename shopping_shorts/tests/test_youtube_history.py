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


def test_유튜브는_조회수로_거른다(tmp_path):
    """★2026-09-04 사장님 "유튭은 댓글이 필요없어, 조회수 기반이야".

    플랫폼마다 '터진 것'의 잣대가 다르다 — 실측 댓글 중앙값이 인스타 60 / 유튜브 **1**이라
    유튜브에 댓글 문턱(500/1000)을 쓰면 이번 주 48편·이번 달 27편밖에 안 남아 빈 화면이 된다.
    """
    from datetime import datetime, timezone
    s = Store(tmp_path / "t.db")
    now = datetime.now(timezone.utc).isoformat()
    s.save_last_run_platform("youtube", [
        {"shortcode": "big", "username": "c1", "name": "채널", "category": "",
         "url": "u", "thumbnail": "t", "caption": "천재가 만든 제품의 정체",
         "views": 300000, "comments": 3},          # 조회수 크고 댓글 거의 없음 = 유튜브의 '터진 것'
        {"shortcode": "mid", "username": "c2", "name": "채널", "category": "",
         "url": "u", "thumbnail": "t", "caption": "살림팁", "views": 50000, "comments": 900},
    ], now)

    by_views = [r["shortcode"] for r in
                s.hits_since(7, min_comments=0, platform="youtube", min_views=100000)]
    assert by_views == ["big"], "조회수 문턱이 안 걸린다 — 유튜브 기간탭이 엉뚱해진다"

    by_comments = [r["shortcode"] for r in
                   s.hits_since(7, min_comments=500, platform="youtube")]
    assert by_comments == ["mid"], "댓글 기준은 종전대로여야 한다(인스타가 이걸 쓴다)"

    # 정렬도 조회수 — 댓글 많은 것이 위로 오면 안 된다
    both = [r["shortcode"] for r in
            s.hits_since(7, min_comments=0, platform="youtube", min_views=1000)]
    assert both == ["big", "mid"], f"조회수순이 아니다: {both}"
