"""쓰레드 랭킹 배선 — 수집기(threads_posts)를 레퍼런스 랭킹 카드로 잇는 층.

사장님 결정(2026-08-17): 지표는 **댓글 기준**, 창은 **48시간** — 인스타와 동일하게 본다.
그래서 참여합산식 build_overseas_items가 아니라 인스타와 같은 build_items를 쓴다.

★필드 이름이 어긋난다(실측): threads_posts는 posted_at·code·thumb·caption인데
  build_items가 읽는 건 timestamp·shortcode·displayUrl·caption이다. 특히
  timestamp가 없으면 ranking.build_items가 그 항목을 **통째로 건너뛴다**(ranking.py:47)
  → 조용히 0건이 된다. 그 매핑을 여기서 못박는다.
"""
from datetime import datetime, timedelta, timezone

from shopping_shorts import service
from shopping_shorts.store import Store


def _row(code="A", hours_ago=1, comments=10, likes=5, views=100):
    """threads_posts에 들어가는 모양 그대로(=store.threads_upsert가 받는 dict)."""
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "code": code, "username": "petppuri", "caption": "가" * 30,
        "tail_caption": "", "coupang_url": "https://link.coupang.com/a/x",
        "media_kind": "video", "video_url": "https://cdn/v.mp4",
        "thumb": "https://cdn/t.jpg", "likes": likes, "comments": comments,
        "reposts": 2, "shares": 1, "views": views,
        "posted_at": ts.isoformat(), "quality": 7, "source": "account",
    }


def _seeded_store(tmp_path, rows):
    s = Store(str(tmp_path / "t.db"))
    s.add_seed("threads", "account", "petppuri")
    for r in rows:
        s.threads_upsert(r)
    return s


def test_수집한_게시물이_댓글기준_카드로_나온다(tmp_path, monkeypatch):
    s = _seeded_store(tmp_path, [_row(comments=10, hours_ago=2)])
    monkeypatch.setattr(service, "Store", lambda *a, **k: s)
    monkeypatch.setattr(service.threads_playwright, "collect_account",
                        lambda u, st, **k: {"posts": 0, "new": 0})

    items = service._collect_threads()

    assert len(items) == 1
    it = items[0]
    assert it["shortcode"] == "A"
    assert it["username"] == "petppuri"
    assert it["comments"] == 10
    assert it["thumbnail"] == "https://cdn/t.jpg"
    # 댓글 ÷ 경과시간 = 인스타와 같은 식(참여합산이 아니다).
    # age_hours는 표시용으로 반올림되므로(ranking.py) speed와 정확히 나눠떨어지지
    # 않는다 — 값이 아니라 '무엇으로 나눴나'를 본다. 참여합산이면 (10+5+2+1)/2h=9로
    # 튀므로 댓글기준 5 근처인지로 갈린다.
    assert abs(it["speed"] - 10 / 2) < 0.01
    # 카드가 새 탭으로 열 주소 — 실제 쓰레드 게시물 주소여야 한다
    assert it["url"] == "https://www.threads.com/@petppuri/post/A"


def test_48시간_넘은_건_빠진다(tmp_path, monkeypatch):
    s = _seeded_store(tmp_path, [_row(code="OLD", hours_ago=100),
                                 _row(code="NEW", hours_ago=3)])
    monkeypatch.setattr(service, "Store", lambda *a, **k: s)
    monkeypatch.setattr(service.threads_playwright, "collect_account",
                        lambda u, st, **k: {"posts": 0, "new": 0})

    items = service._collect_threads()

    assert [i["shortcode"] for i in items] == ["NEW"]


def test_등록된_계정이_없으면_수집을_안_돈다(tmp_path, monkeypatch):
    """시드가 비면 네트워크를 아예 건드리지 않는다(빈 목록만 돌려준다)."""
    s = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(service, "Store", lambda *a, **k: s)
    called = []
    monkeypatch.setattr(service.threads_playwright, "collect_account",
                        lambda u, st, **k: called.append(u))

    assert service._collect_threads() == []
    assert called == []


def test_한_계정이_실패해도_나머지는_수집한다(tmp_path, monkeypatch):
    """계정 하나가 터져도 통째로 0건이 되면 안 된다(수집은 계정 단위로 격리)."""
    s = _seeded_store(tmp_path, [_row(code="A", hours_ago=1)])
    s.add_seed("threads", "account", "boom")
    monkeypatch.setattr(service, "Store", lambda *a, **k: s)

    def _collect(u, st, **k):
        if u == "boom":
            raise RuntimeError("차단됨")
        return {"posts": 1, "new": 1}
    monkeypatch.setattr(service.threads_playwright, "collect_account", _collect)

    items = service._collect_threads()

    assert [i["shortcode"] for i in items] == ["A"]


def test_collect가_threads로_분기한다(tmp_path, monkeypatch):
    """service.collect(platform='threads')가 빈 목록으로 떨어지지 않는다.

    ★service.py의 `if platform != "instagram": return []`는 유료 Apify 경로로
      새는 걸 막는 방어벽이라 없애면 안 된다 — 그 위에 분기가 얹혔는지 본다.
    """
    monkeypatch.setattr(service, "_collect_threads", lambda: [{"shortcode": "Z"}])
    assert service.collect(platform="threads") == [{"shortcode": "Z"}]
