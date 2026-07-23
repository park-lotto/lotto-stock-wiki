from shopping_shorts.aipick import build_aipick


def test_build_aipick_picks_top_and_tiles():
    sources = [
        {"video_id": "a", "text": "훅...결과...", "views": 1000, "followers": 200, "comments": 50, "seconds": 30},
        {"video_id": "b", "text": "짧은 대본", "views": 300, "followers": 300, "comments": 5, "seconds": 18},
    ]
    meta = {"a": {"comments": 50, "avg_comments": 10}, "b": {"comments": 5, "avg_comments": 10}}
    out = build_aipick(sources, meta)
    assert out["pick_id"] in ("a", "b")
    assert out["tiles"]["comments"] is not None
    assert out["tiles"]["engagement_rank"] == 1
    assert isinstance(out["candidates"], list) and len(out["candidates"]) == 2


def test_build_aipick_respects_forced():
    sources = [{"video_id": "a", "text": "x", "comments": 50}, {"video_id": "b", "text": "y", "comments": 1}]
    out = build_aipick(sources, {}, forced="b")
    assert out["pick_id"] == "b"


def test_build_aipick_structure_falls_back_empty(monkeypatch):
    from shopping_shorts import aipick
    monkeypatch.setattr(aipick, "analyze_structure", lambda *a, **k: {})
    out = build_aipick([{"video_id": "a", "text": "x", "comments": 1}], {})
    assert out["structure"] == {}   # 구조분석 실패해도 pick/tiles는 살아있음
    assert out["pick_id"] == "a"
