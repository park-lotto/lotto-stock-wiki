"""⭐ 레퍼런스 등록 — 영상 1건 + 채널을 한 번에(2026-08-18 사장님 요청).

사장님: "인스타 보다가 좋은 영상을 발견하면 바로 레퍼런스에 반영해서 정렬을 해줄 수 있나?
영상등록 + 채널등록이 되는 걸로."

종전 두 버튼으로는 안 됐다:
  · 📥 담기      → 내 즐겨찾기로만 간다(랭킹엔 안 뜬다)
  · 📌 채널수집  → 다음 수집(09/15/21시)까지 기다려야 그 영상이 잡힌다

여기서 못박는 것:
  ① 항목을 손으로 짓지 않는다 — 수집이 쓰는 build_items를 그대로 태운다.
     손으로 만들면 속도·밀도·가속이 수집분과 달라져 한 화면에 두 잣대가 섞인다(0순위-B).
  ② 오래된 영상도 등록된다(48h 창은 자동수집용이지, 사장님이 고른 영상에 쓸 자가 아니다).
  ③ 같은 영상을 두 번 넣어도 스냅샷에 중복으로 쌓이지 않는다.
  ④ 영상 편입이 실패해도 채널 등록은 살린다(반대도 마찬가지).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t.db")
    Store(path)
    return path


def _meta(hours_ago=3, **kw):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp()
    out = {"ts": int(ts), "title": "자석 네일펜", "thumbnail": "t.jpg", "channel": "chaehome",
           "views": 569324, "likes": 4200, "comments": 7217, "followers": 342545,
           "duration": 29}
    out.update(kw)
    return out


def _adopt(db_path, url, meta):
    store = Store(db_path)
    return ap._adopt_into_ranking(store, ap._grab_platform(url), url, meta)


def test_영상이_지금_랭킹에_들어간다(db):
    item = _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta())
    assert item and item["comments"] == 7217
    items, _at = Store(db).load_last_run()
    assert [i["shortcode"] for i in items] == ["ABC123"], "스냅샷 맨 앞에 들어가야 한다"
    assert items[0].get("manual") is True, "직접 등록임을 화면이 구별할 수 있어야 한다"


def test_오래된_영상도_등록된다(db):
    """자동수집은 48시간만 보지만, 사장님이 고른 영상은 그 창으로 자르면 안 된다."""
    item = _adopt(db, "https://www.instagram.com/reel/OLD1/", _meta(hours_ago=24 * 30))
    assert item is not None, "한 달 전 영상도 등록돼야 한다"


def test_같은_영상을_두_번_넣어도_한_줄이다(db):
    _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta())
    _adopt(db, "https://www.instagram.com/reel/ABC123/", _meta(comments=9000))
    items, _at = Store(db).load_last_run()
    assert len(items) == 1 and items[0]["comments"] == 9000, "덮어쓰되 중복은 안 쌓는다"


def test_기존_수집분을_지우지_않는다(db):
    store = Store(db)
    store.save_last_run([{"shortcode": "OLD", "comments": 1}], "2026-08-18T00:00:00+00:00")
    _adopt(db, "https://www.instagram.com/reel/NEW1/", _meta())
    items, _at = store.load_last_run()
    assert [i["shortcode"] for i in items] == ["NEW1", "OLD"]


def test_시각을_못_읽으면_영상은_건너뛴다(db):
    """지표를 못 만들면 랭킹에 못 넣는다 — 조용히 빈 카드를 만드느니 안 넣는 게 낫다."""
    assert _adopt(db, "https://www.instagram.com/reel/ABC/", _meta(ts=None)) is None


def test_쓰레드_유튜브도_각_플랫폼_스냅샷에_들어간다(db):
    _adopt(db, "https://www.threads.com/@shop/post/TH1", _meta())
    _adopt(db, "https://www.youtube.com/shorts/_6v_D3MktcI", _meta())  # 실제 길이(11자)
    st = Store(db)
    assert [i["shortcode"] for i in st.load_last_run_platform("threads")[0]] == ["TH1"]
    assert [i["shortcode"] for i in st.load_last_run_platform("youtube")[0]] == ["_6v_D3MktcI"]
    assert st.load_last_run()[0] == [], "인스타 스냅샷은 건드리지 않는다"


def test_지원안하는_주소는_거절한다(db):
    with patch.object(ap, "DB_PATH", db), patch.object(ap, "_require_admin", lambda r: None):
        html = ap.api_reference_adopt(request=None, url="https://example.com/x")
    assert "지원하지 않는" in html.body.decode("utf-8")


def test_영상편입이_실패해도_채널등록은_한다(db):
    """둘을 한 트랜잭션으로 묶으면 하나가 깨질 때 둘 다 날아간다."""
    called = {}
    with patch.object(ap, "DB_PATH", db), \
         patch.object(ap, "_require_admin", lambda r: None), \
         patch.object(ap, "probe_grab_meta", lambda u, **k: _meta()), \
         patch.object(ap, "_adopt_into_ranking",
                      lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))), \
         patch.object(ap, "api_discover_add_by_url",
                      lambda req, url="", username="": called.setdefault("ch", url) or
                      ap.HTMLResponse("✅ 채널 등록 완료")):
        html = ap.api_reference_adopt(request=None, url="https://www.instagram.com/reel/ABC/")
    assert called.get("ch"), "영상이 깨져도 채널 등록은 시도해야 한다"
    assert "채널만 등록" in html.body.decode("utf-8")


# ── A안: 화면에 떠 있는 숫자를 같이 보낸다(2026-08-18) ────────────────────────────
# 서버는 인스타를 로그인 없이 읽어 조회수·팔로워가 0으로 왔다(실측: 채이홈 항목
# views 0 / followers 0 / 제목 "Video by chae2home"). 그러면 조회수당댓글·팔로워당댓글이
# 계산되지 않아 정렬에서 불리해진다. 사장님 화면엔 그 숫자가 이미 떠 있으니 함께 보낸다.
def _adopt_api(db_path, url, meta, **q):
    with patch.object(ap, "DB_PATH", db_path), \
         patch.object(ap, "_require_admin", lambda r: None), \
         patch.object(ap, "probe_grab_meta", lambda u, **k: dict(meta)), \
         patch.object(ap, "api_discover_add_by_url",
                      lambda req, url="", username="": ap.HTMLResponse("✅ 채널 등록 완료")):
        return ap.api_reference_adopt(request=None, url=url, **q)


def test_화면에서_보낸_숫자로_빈칸을_채운다(db):
    _adopt_api(db, "https://www.instagram.com/reel/ABC123/",
               _meta(views=0, followers=0, likes=0),
               views=569324, followers=342545, likes=4200)
    items, _at = Store(db).load_last_run()
    got = items[0]
    assert got["views"] == 569324 and got["followers"] == 342545, \
        "0으로 비어 있던 칸은 화면 값으로 채워야 정렬 지표가 산다"


def test_서버가_제대로_읽은_값은_덮지_않는다(db):
    """화면 글자 파싱은 근사치다 — 더 정확한 값을 밀어내면 안 된다."""
    _adopt_api(db, "https://www.instagram.com/reel/ABC123/",
               _meta(views=100000), views=7)
    items, _at = Store(db).load_last_run()
    assert items[0]["views"] == 100000
