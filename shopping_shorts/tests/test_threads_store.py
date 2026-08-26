"""쓰레드 저장은 인스타 표(channel_archive·reel_history)와 섞지 않는다.

★섞으면 안 되는 실측 근거: hits_since는 platform 인자를 받으면서 SQL에서 쓰지 않는다
  (store.py:2187). 지금 섞으면 인스타 랭킹에 쓰레드가 조용히 흘러든다.
"""
from shopping_shorts.store import Store

_POST = {
    "code": "DcIknZjEQVW", "username": "petppuri", "caption": "나 지금까지 헛고생함",
    "tail_caption": "링크", "coupang_url": "https://link.coupang.com/a/x",
    "media_kind": "video", "video_url": "https://cdn/v.mp4", "thumb": "https://cdn/t.jpg",
    "likes": 9, "comments": 1, "reposts": 2, "shares": 0, "views": 0,
    "posted_at": "2026-08-17T05:00:00+00:00", "quality": 7, "source": "account",
}


def test_넣고_읽는다(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.threads_upsert(_POST) is True
    rows = s.threads_list()
    assert len(rows) == 1
    assert rows[0]["code"] == "DcIknZjEQVW"
    assert rows[0]["coupang_url"] == "https://link.coupang.com/a/x"
    assert rows[0]["quality"] == 7


def test_같은_코드는_갱신된다(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.threads_upsert(_POST)
    assert s.threads_upsert(dict(_POST, likes=100)) is False
    rows = s.threads_list()
    assert len(rows) == 1
    assert rows[0]["likes"] == 100


def test_품질순으로_나온다(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.threads_upsert(dict(_POST, code="LOW", quality=1))
    s.threads_upsert(dict(_POST, code="HIGH", quality=9))
    assert [r["code"] for r in s.threads_list()][0] == "HIGH"


def test_최소품질로_거를_수_있다(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.threads_upsert(dict(_POST, code="LOW", quality=1))
    s.threads_upsert(dict(_POST, code="HIGH", quality=9))
    assert [r["code"] for r in s.threads_list(min_quality=5)] == ["HIGH"]


def test_인스타_표는_건드리지_않는다(tmp_path):
    # 쓰레드를 넣어도 인스타 경로엔 한 건도 안 생겨야 한다.
    s = Store(str(tmp_path / "t.db"))
    s.threads_upsert(_POST)
    assert s.hits_since(30, min_comments=0) == []
