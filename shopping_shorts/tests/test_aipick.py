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
    # 진짜 값만(2026-07-26): 동어반복 rank·바구니평균 배수 폐기, 참여율(댓글/팔로워)로 교체.
    assert "engagement_rank" not in out["tiles"]
    assert "comments_x_avg" not in out["tiles"]
    assert "engagement_rate" in out["tiles"]
    assert isinstance(out["candidates"], list) and len(out["candidates"]) == 2
    assert isinstance(out["pick_meta"], dict) and "title" in out["pick_meta"]


def test_build_aipick_engagement_rate_is_comments_over_followers():
    """참여율 = 댓글/팔로워*100 — 소스 자체 실측치라 다른 소스를 담고 빼도 안 흔들린다(고정값)."""
    sources = [
        {"video_id": "a", "text": "훅...결과...", "followers": 120000, "comments": 6585, "seconds": 33},
        {"video_id": "b", "text": "짧은 대본", "followers": 300, "comments": 5, "seconds": 18},
    ]
    out = build_aipick(sources, {})
    # pick='a'(재조합·참여 최고점). 6585/120000*100 = 5.48 → 5.5
    assert out["pick_id"] == "a"
    assert out["tiles"]["engagement_rate"] == 5.5
    # 소스 b만 있어도 a의 참여율은 그 소스 값 그대로 — 바구니 구성과 무관(고정).
    out_a_only = build_aipick([sources[0]], {})
    assert out_a_only["tiles"]["engagement_rate"] == 5.5


def test_build_aipick_engagement_rate_none_without_followers():
    """팔로워가 없으면 참여율은 None(거짓수치 대신 타일 숨김) — 프론트가 우아하게 폴백."""
    out = build_aipick([{"video_id": "a", "text": "x", "comments": 50}], {})
    assert out["tiles"]["engagement_rate"] is None


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


def test_build_aipick_structure_partial_approx_sec_sums_to_100(monkeypatch):
    # 회귀: 일부 비트만 approx_sec가 파싱되면(선택 필드라 Gemini가 누락 가능)
    # 파싱된 애는 dur/total, 못 된 애는 100/n로 기준이 섞여 합이 100%를 넘던 버그.
    # (2비트 2s+3s → total=5 → 40,60 + 세번째 균등33.3 = 133.3%)
    from shopping_shorts import aipick
    partial = {
        "beats": [
            {"label": "훅", "desc": "d1", "approx_sec": "0-2"},
            {"label": "문제제기", "desc": "d2", "approx_sec": "2-5"},
            {"label": "결과", "desc": "d3"},  # approx_sec 없음
        ],
        "target_seconds": 10,
        "hook_type": "", "devices": [],
    }
    monkeypatch.setattr(aipick, "analyze_structure", lambda *a, **k: partial)
    out = build_aipick([{"video_id": "a", "text": "x", "comments": 1}], {})
    segs = out["structure"]["segments"]
    assert len(segs) == 3
    total_pct = sum(s["pct"] for s in segs)
    assert abs(total_pct - 100) < 0.5
    # 하나라도 파싱 안 되면 전부 균등분배로 통일(기준 혼합 금지)
    assert all(abs(s["pct"] - 100 / 3) < 0.1 for s in segs)


def test_build_aipick_structure_full_approx_sec_distributes_by_duration(monkeypatch):
    from shopping_shorts import aipick
    full = {
        "beats": [
            {"label": "훅", "desc": "d1", "approx_sec": "0-2"},
            {"label": "문제제기", "desc": "d2", "approx_sec": "2-5"},
        ],
        "target_seconds": 5,
        "hook_type": "", "devices": [],
    }
    monkeypatch.setattr(aipick, "analyze_structure", lambda *a, **k: full)
    out = build_aipick([{"video_id": "a", "text": "x", "comments": 1}], {})
    segs = out["structure"]["segments"]
    total_pct = sum(s["pct"] for s in segs)
    assert abs(total_pct - 100) < 0.5
    # 2s/5s=40%, 3s/5s=60% — 비트 수 균등(50/50)이 아니라 실제 길이 비례여야 함
    assert abs(segs[0]["pct"] - 40) < 0.5
    assert abs(segs[1]["pct"] - 60) < 0.5
