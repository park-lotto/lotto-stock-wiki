# -*- coding: utf-8 -*-
"""실제 사진 조달 — 검색·거르기·변형·폴백. 외부 API는 부르지 않는다(주입·가짜로 대체).

사장님 2026-09-13: "유명인 기사인데 완전 딴판인 사람이 나와 이질감이 심하다.
좋은 얘기는 실물, 안 좋은 얘기는 원본 받아서 변형."
"""
import json

import pytest
from PIL import Image

from shopping_shorts.brainbulb import images, photos, spec


def _png(path, size=(400, 300), color=(120, 120, 200)):
    Image.new("RGB", size, color).save(path)


# ── 거르기 ───────────────────────────────────────────────────────────────────────
def test_news_source_filter():
    """실측: '박수홍' 검색 상위에 핀터레스트·중국 기업·대학 페이지가 섞였다."""
    assert photos.looks_like_news("모바일한경 - 한국경제")
    assert photos.looks_like_news("연합뉴스")
    assert photos.looks_like_news("OSEN")
    assert not photos.looks_like_news("Pinterest")
    assert not photos.looks_like_news("广州纺织工贸企业集团有限公司")
    assert not photos.looks_like_news("쿠팡")
    assert not photos.looks_like_news("나무위키")


def test_pick_photo_prefers_news_and_skips_small(tmp_path, monkeypatch):
    hits = [
        {"url": "http://x/pin.jpg", "source": "Pinterest", "title": "", "w": 900, "h": 600},
        {"url": "http://x/tiny.jpg", "source": "연합뉴스", "title": "", "w": 200, "h": 150},   # 너무 작다 → 건너뜀
        {"url": "http://x/news.jpg", "source": "한국경제", "title": "", "w": 800, "h": 600},
    ]
    got = []
    monkeypatch.setattr(photos, "search_images", lambda q, **k: hits)
    monkeypatch.setattr(photos, "download", lambda u, p, **k: (got.append(u), _png(p))[1] or p)
    monkeypatch.setattr(photos, "has_face", lambda p: True)
    r = photos.pick_photo("박수홍 홈쇼핑", str(tmp_path), 1, log=lambda *a: None)
    assert r and got == ["http://x/news.jpg"]          # 뉴스 먼저, 작은 건 건너뜀


def test_pick_photo_skips_faceless(tmp_path, monkeypatch):
    hits = [{"url": "http://x/logo.jpg", "source": "연합뉴스", "title": "", "w": 800, "h": 600},
            {"url": "http://x/face.jpg", "source": "한국경제", "title": "", "w": 800, "h": 600}]
    monkeypatch.setattr(photos, "search_images", lambda q, **k: hits)
    monkeypatch.setattr(photos, "download", lambda u, p, **k: (_png(p), p)[1])
    monkeypatch.setattr(photos, "has_face", lambda p: "face" in str(p) or photos._FACE_STUB.pop() if False else True)
    r = photos.pick_photo("q", str(tmp_path), 1, log=lambda *a: None)
    assert r is not None


def test_pick_photo_returns_none_without_key(tmp_path, monkeypatch):
    """키가 없으면 조용히 None — 호출부가 생성으로 폴백한다(편이 멈추면 안 된다)."""
    monkeypatch.setattr(photos, "serper_key", lambda key_file=None: "")
    assert photos.pick_photo("q", str(tmp_path), 1, log=lambda *a: None) is None


def test_search_failure_does_not_raise(tmp_path, monkeypatch):
    def boom(q, **k):
        raise RuntimeError("serper 500")
    monkeypatch.setattr(photos, "search_images", boom)
    assert photos.pick_photo("q", str(tmp_path), 1, log=lambda *a: None) is None


# ── 대본이 정하는 사진 종류 ───────────────────────────────────────────────────────
def test_make_prompts_parses_sources():
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "y", "color": "WHITE", "role": "NARR", "img": 2},
                         {"text": "z", "color": "WHITE", "role": "NARR", "img": 3}]}
    raw = json.dumps({"cast": {"1": "a man"},
                      "prompts": {"1": "scene one", "2": "scene two", "3": "scene three"},
                      "sources": {"1": {"kind": "real", "query": "박수홍 홈쇼핑"},
                                  "2": {"kind": "variant", "query": "박수홍 공항"},
                                  "3": {"kind": "gen", "query": ""}}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["sources"]["1"] == {"kind": "real", "query": "박수홍 홈쇼핑"}
    assert r["sources"]["2"]["kind"] == "variant"
    assert r["sources"]["3"]["kind"] == "gen"


def test_make_prompts_downgrades_bad_source_to_gen():
    """검색어 없는 real, 모르는 kind는 gen으로 — 판정은 한 곳(0순위-B)."""
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1},
                         {"text": "y", "color": "WHITE", "role": "NARR", "img": 2}]}
    raw = json.dumps({"cast": {}, "prompts": {"1": "a", "2": "b"},
                      "sources": {"1": {"kind": "real", "query": ""},        # 검색어 없음
                                  "2": {"kind": "무엇", "query": "뭐"}}})     # 모르는 값
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["sources"]["1"]["kind"] == "gen" and r["sources"]["2"]["kind"] == "gen"


def test_make_prompts_without_sources_field_defaults_to_gen():
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1}]}
    raw = json.dumps({"cast": {}, "prompts": {"1": "a"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert r["sources"]["1"]["kind"] == "gen"


# ── 조달 순서 ─────────────────────────────────────────────────────────────────────
def test_generate_all_uses_photo_for_real_and_skips_imagegen(tmp_path, monkeypatch):
    called = []
    src = tmp_path / "found.jpg"; _png(src, color=(10, 200, 10))
    monkeypatch.setattr(photos, "pick_photo", lambda q, wd, slot, **k: {"path": str(src), "source": "한국경제"})
    out = images.generate_all({"1": "prompt"}, str(tmp_path), lambda p, o: called.append(p),
                              sources={"1": {"kind": "real", "query": "박수홍"}}, log=lambda *a: None)
    assert not called                                    # 생성 API를 안 불렀다
    assert Image.open(out["1"]).size == (400, 300)       # 검색 사진이 그대로 들어갔다
    assert json.load(open(out["1"] + ".json", encoding="utf-8"))["kind"] == "real"


def test_generate_all_variant_calls_edit_model(tmp_path, monkeypatch):
    src = tmp_path / "found.jpg"; _png(src)
    seen = {}
    monkeypatch.setattr(photos, "pick_photo", lambda q, wd, slot, **k: {"path": str(src), "source": "연합뉴스"})
    def fake_variant(s, o, prompt, **k):
        seen["prompt"] = prompt; _png(o); return o
    monkeypatch.setattr(photos, "variant", fake_variant)
    out = images.generate_all({"1": "prompt"}, str(tmp_path), lambda p, o: pytest.fail("생성을 부르면 안 된다"),
                              sources={"1": {"kind": "variant", "query": "박수홍"}}, log=lambda *a: None)
    assert seen["prompt"] == spec.VARIANT_PROMPT
    assert json.load(open(out["1"] + ".json", encoding="utf-8"))["kind"] == "variant"


def test_generate_all_falls_back_to_gen_when_no_photo(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(photos, "pick_photo", lambda q, wd, slot, **k: None)   # 못 찾음
    out = images.generate_all({"1": "prompt"}, str(tmp_path),
                              lambda p, o: (called.append(p), _png(o))[1],
                              sources={"1": {"kind": "real", "query": "없는사람"}}, log=lambda *a: None)
    assert called == ["prompt"]                                                 # 생성으로 폴백
    assert json.load(open(out["1"] + ".json", encoding="utf-8"))["kind"] == "gen"


def test_generate_all_reuse_keys_on_kind_change(tmp_path, monkeypatch):
    """종류가 바뀌면 해시가 달라져 다시 만든다 — real→variant로 바꿨는데 옛 사진이 남으면 안 된다."""
    src = tmp_path / "f.jpg"; _png(src)
    monkeypatch.setattr(photos, "pick_photo", lambda q, wd, slot, **k: {"path": str(src), "source": "연합뉴스"})
    monkeypatch.setattr(photos, "variant", lambda s, o, p, **k: (_png(o), o)[1])
    images.generate_all({"1": "p"}, str(tmp_path), lambda a, b: None,
                        sources={"1": {"kind": "real", "query": "q"}}, log=lambda *a: None)
    first = json.load(open(str(tmp_path / "img" / "01.png.json"), encoding="utf-8"))
    images.generate_all({"1": "p"}, str(tmp_path), lambda a, b: None,
                        sources={"1": {"kind": "variant", "query": "q"}}, log=lambda *a: None)
    second = json.load(open(str(tmp_path / "img" / "01.png.json"), encoding="utf-8"))
    assert first["hash"] != second["hash"] and second["kind"] == "variant"
