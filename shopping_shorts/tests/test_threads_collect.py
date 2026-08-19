"""수집기 조립 — 브라우저는 가짜로 세우고 '파서→묶기→점수→저장' 배선만 본다."""
from shopping_shorts import threads_playwright as tp
from shopping_shorts.store import Store

_NODES = [
    {"code": "A", "caption": {"text": "가" * 50}, "like_count": 9,
     "video_versions": [{"url": "https://cdn/v.mp4", "width": 720}],
     "image_versions2": {"candidates": [{"url": "https://cdn/t.jpg", "width": 640}]},
     "taken_at": 1786900000},
    {"code": "B", "caption": {"text": "링크 link.coupang.com/a/x"},
     "like_count": 1, "taken_at": 1786900060},
]


def test_이어진_글이_접히고_품질이_붙어_저장된다(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "_fetch_profile_nodes", lambda *a, **k: _NODES)
    s = Store(str(tmp_path / "t.db"))
    out = tp.collect_account("petppuri", s)
    assert out == {"posts": 1, "new": 1}          # 2건이 1건으로 접힌다
    rows = s.threads_list()
    assert rows[0]["code"] == "A"
    assert rows[0]["coupang_url"] == "https://link.coupang.com/a/x"
    assert rows[0]["quality"] == 7                # 영상3 + 쿠팡2 + 캡션2
    assert rows[0]["source"] == "account"


def test_두번_돌려도_한_건이다(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "_fetch_profile_nodes", lambda *a, **k: _NODES)
    s = Store(str(tmp_path / "t.db"))
    tp.collect_account("petppuri", s)
    out = tp.collect_account("petppuri", s)
    assert out == {"posts": 1, "new": 0}
    assert len(s.threads_list()) == 1


def test_노드가_0건이면_조용히_0을_돌려준다(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "_fetch_profile_nodes", lambda *a, **k: [])
    s = Store(str(tmp_path / "t.db"))
    assert tp.collect_account("x", s) == {"posts": 0, "new": 0}


def test_네트워크가_실패해도_예외없이_0을_돌려준다(tmp_path, monkeypatch):
    """fetch_html이 실패(빈 문자열)해도 collect_account는 예외 없이 계속 돈다."""
    monkeypatch.setattr(tp, "fetch_html", lambda *a, **k: "")
    s = Store(str(tmp_path / "t.db"))
    assert tp.collect_account("x", s) == {"posts": 0, "new": 0}
