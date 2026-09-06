# -*- coding: utf-8 -*-
"""썸네일 보관함 — CDN URL이 만료돼도 판독할 수 있는가 (2026-09-06).

★왜 만들었나: 랭킹 카드 "살 물건 없음" 3,191건 중 2,771건(87%)이
  인스타 썸네일 만료 + 캡션 없음이었다. 근거가 0이면 어떤 프롬프트도 소용없다.
  받아올 때 남겨두면 앞으로 담는 것은 만료돼도 판독된다.
"""
import pytest

from shopping_shorts import video_analysis as VA


class _Resp:
    def __init__(self, content): self.content = content
    def raise_for_status(self): pass


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(VA, "_THUMB_DIR", str(tmp_path / "thumbs"))
    return tmp_path


def _fake_requests(monkeypatch, get):
    import types
    mod = types.SimpleNamespace(get=get)
    monkeypatch.setitem(__import__("sys").modules, "requests", mod)


def test_받아오면_보관한다(cache_dir, monkeypatch):
    _fake_requests(monkeypatch, lambda url, **kw: _Resp(b"JPEGDATA"))
    assert VA.fetch_thumb_bytes("https://cdn.example/a.jpg") == b"JPEGDATA"
    import os
    assert os.path.exists(VA._thumb_cache_path("https://cdn.example/a.jpg"))


def test_URL이_죽어도_보관본으로_답한다(cache_dir, monkeypatch):
    """★이게 이 기능의 전부다 — 이 단언이 빨개지면 87% 문제가 되돌아온다."""
    url = "https://scontent-ssn1-1.cdninstagram.com/v/expired.jpg"
    _fake_requests(monkeypatch, lambda u, **kw: _Resp(b"ORIGINAL"))
    assert VA.fetch_thumb_bytes(url) == b"ORIGINAL"          # 살아있을 때 받아둠

    def _dead(u, **kw):
        raise RuntimeError("410 Gone")                        # CDN 만료 재현
    _fake_requests(monkeypatch, _dead)
    assert VA.fetch_thumb_bytes(url) == b"ORIGINAL"          # 보관본으로 답한다


def test_보관본도_없으면_None(cache_dir, monkeypatch):
    def _dead(u, **kw):
        raise RuntimeError("410 Gone")
    _fake_requests(monkeypatch, _dead)
    assert VA.fetch_thumb_bytes("https://cdn.example/never-seen.jpg") is None


def test_빈_URL은_그대로_None(cache_dir):
    assert VA.fetch_thumb_bytes("") is None
    assert VA.fetch_thumb_bytes(None) is None


def test_너무_큰_파일은_안_담는다(cache_dir, monkeypatch):
    big = b"x" * (VA._THUMB_MAX_BYTES + 1)
    _fake_requests(monkeypatch, lambda u, **kw: _Resp(big))
    url = "https://cdn.example/huge.jpg"
    assert VA.fetch_thumb_bytes(url) == big                   # 판독은 그대로 된다
    import os
    assert not os.path.exists(VA._thumb_cache_path(url))      # 보관은 안 한다


def test_보관_실패해도_판독은_된다(cache_dir, monkeypatch):
    """디스크가 꽉 차도 화면이 죽으면 안 된다."""
    monkeypatch.setattr(VA, "_thumb_cache_write",
                        lambda u, c: (_ for _ in ()).throw(OSError("No space left")))
    _fake_requests(monkeypatch, lambda u, **kw: _Resp(b"IMG"))
    with pytest.raises(OSError):
        VA._thumb_cache_write("x", b"y")                       # 위 스텁이 실제로 던진다
    # 진짜 함수는 예외를 삼키므로 판독이 살아있다
    monkeypatch.undo()
    monkeypatch.setattr(VA, "_THUMB_DIR", "/proc/불가능한경로")
    _fake_requests(monkeypatch, lambda u, **kw: _Resp(b"IMG"))
    assert VA.fetch_thumb_bytes("https://cdn.example/b.jpg") == b"IMG"


# ── 근거 없는 카드를 "살 물건 없음"과 갈라서 알려주는가 (2026-09-06) ──────────
def test_근거없는것을_따로_알려준다(tmp_path, monkeypatch):
    """썸네일도 캡션도 없으면 모델을 부를 수 없다 — 그건 '살 물건 없음'이 아니다."""
    from shopping_shorts import product_name as PN

    called = []
    monkeypatch.setattr(PN, "_identify_shop_one",
                        lambda img, cap: called.append(1) or "무쇠 솥")
    monkeypatch.setattr(PN.video_analysis if hasattr(PN, "video_analysis") else VA,
                        "fetch_thumb_bytes", lambda u, **kw: None, raising=False)
    import shopping_shorts.video_analysis as _va
    monkeypatch.setattr(_va, "fetch_thumb_bytes", lambda u, **kw: None)

    class _Store:
        def __init__(self, *a, **kw): pass
        def shop_products_map(self, codes): return {}
        def save_shop_product(self, sc, p): pass
    monkeypatch.setattr(PN, "Store", _Store)

    blind = []
    items = [{"shortcode": "dead1", "thumbnail": "https://cdn/expired.jpg", "caption": ""}]
    out = PN.identify_shop_many(items, str(tmp_path / "x.db"), out_no_evidence=blind)

    assert blind == ["dead1"], "근거 0인 카드가 out_no_evidence에 담겨야 한다"
    assert "dead1" not in out, "판독 안 했으므로 결과에 없어야 한다"
    assert not called, "근거가 없는데 모델을 부르면 돈만 쓴다"
