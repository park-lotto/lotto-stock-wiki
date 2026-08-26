# -*- coding: utf-8 -*-
"""조회수는 **두 테이블에 나뉘어** 있다 — 한 곳만 보면 절반이 빈다 (2026-08-20).

실측(서버 DB):
    reel_history       인스타 6,364/6,367건   (shortcode 키)
    source_enrichment  유튜브 1,394/1,410건   (url 키)

사장님 지시 "팔로워 댓글 조회수 썸네일에" — 화면에 띄우려면 이 값이 있어야 한다.
예전엔 호출부가 `views: None`을 하드코딩해 DB에 수천 건이 있어도 영영 안 떴다.
"""
import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def st(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    with s._conn() as c:
        c.execute("INSERT OR REPLACE INTO reel_history(shortcode,url,views,comments)"
                  " VALUES('IG1','https://instagram.com/p/IG1',152000,830)")
        c.execute("INSERT OR REPLACE INTO reel_history(shortcode,url,views)"
                  " VALUES('IG0','https://instagram.com/p/IG0',NULL)")
        c.execute("INSERT OR REPLACE INTO source_enrichment(url,platform,views)"
                  " VALUES('https://youtube.com/watch?v=YT1','youtube',1047000)")
    return s


def test_인스타는_shortcode로_찾는다(st):
    assert st.latest_views(["IG1"], []) == {"IG1": 152000}


def test_유튜브는_URL로_찾는다(st):
    u = "https://youtube.com/watch?v=YT1"
    assert st.latest_views([], [u]) == {u: 1047000}


def test_두_곳을_한_번에_본다(st):
    """★한 곳만 보면 유튜브나 인스타 한쪽이 통째로 빈다."""
    u = "https://youtube.com/watch?v=YT1"
    out = st.latest_views(["IG1"], [u])
    assert out["IG1"] == 152000 and out[u] == 1047000


def test_값이_없으면_키를_안_담는다(st):
    """호출부가 폴백할 수 있어야 한다(latest_comments와 같은 규약)."""
    out = st.latest_views(["IG0", "없는코드"], ["https://없는.url"])
    assert out == {}


def test_빈_입력에도_안_죽는다(st):
    assert st.latest_views([], []) == {}
    assert st.latest_views(None, None) == {}
