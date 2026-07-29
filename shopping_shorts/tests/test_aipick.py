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


def test_build_aipick_pick_meta_matches_pick_identity():
    """pick_meta의 이름·썸네일은 '고른 그 영상'에서 나와야 한다 — 숫자(tiles)와 다른 영상이
    섞이면(프론트 HANDOFF 오정렬) '살림홈 숫자에 엉뚱한 썸네일' 카드가 된다(2026-07-26 사고)."""
    sources = [
        {"video_id": "a", "text": "훅...결과...", "followers": 120000, "comments": 6585,
         "name": "살림홈", "thumbnail": "socks.jpg"},
        {"video_id": "b", "text": "짧은", "followers": 300, "comments": 1,
         "name": "다른채널", "thumbnail": "other.jpg"},
    ]
    out = build_aipick(sources, {})
    assert out["pick_id"] == "a"
    # 숫자와 이름·썸네일이 같은 영상(a)에서 나온다
    assert out["tiles"]["comments"] == 6585
    assert out["pick_meta"]["title"] == "살림홈"
    assert out["pick_meta"]["thumbnail"] == "socks.jpg"


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


def test_build_aipick_ships_pick_text(monkeypatch):
    """★2026-07-27 사장님 제보 "대본을 확보하지 못했습니다": AI PICK 응답에 pick의 원본
    대본이 실려야 한다. 안 실으면 프론트가 도서관(/api/produce/picks)에서만 찾는데,
    AI PICK 소스가 도서관 교차를 벗어난 뒤로는 도서관에 없는 영상이 픽될 수 있어
    '이대로 만들기 시작'이 막다른 알럿으로 끝난다."""
    from shopping_shorts import aipick as _aipick
    monkeypatch.setattr(_aipick, "analyze_structure", lambda text: None)
    sources = [{"video_id": "V1", "text": "정리 꿀팁 원본 대본입니다.", "comments": 100,
                "source_url": "https://www.instagram.com/reel/V1/"}]
    d = _aipick.build_aipick(sources, {"V1": {"platform": "instagram", "comments": 100}})
    assert d["pick_id"] == "V1"
    assert d["pick_text"] == "정리 꿀팁 원본 대본입니다."


def test_build_aipick_pick_text_empty_when_no_sources():
    """소스가 없으면 pick_id=None이고 대본도 없다(프론트가 '먼저 AI PICK…'으로 막는다)."""
    from shopping_shorts import aipick as _aipick
    d = _aipick.build_aipick([], {})
    assert d["pick_id"] is None
    assert not d.get("pick_text")


def test_build_aipick_candidates_carry_structure_and_meta(monkeypatch):
    """★소스 구조 비교(A, 2026-07-29): 사장님이 3개를 나란히 보고 백본을 고르려면 candidates에
    각 소스의 이름·썸네일·(캐시된)구조가 실려야 한다. 캐시 있는 소스는 structure를 그대로,
    캐시 없는 소스는 structure=None(프론트가 '분석 전'으로 표시). 여기서 새 Gemini 호출은 없다."""
    from shopping_shorts import aipick as _aipick
    # pick 경로의 폴백 분석이 테스트를 오염시키지 않게 비활성(캐시만 검증).
    monkeypatch.setattr(_aipick, "analyze_structure", lambda *a, **k: {})
    cached = {"beats": [{"label": "훅", "approx_sec": "0-2"},
                        {"label": "결과", "approx_sec": "2-5"}],
              "target_seconds": 5, "hook_type": "권위인용", "devices": ["주변인물"]}
    sources = [
        {"video_id": "a", "text": "x", "comments": 500, "followers": 1000,
         "name": "살림홈", "thumbnail": "a.jpg", "structure": cached},
        {"video_id": "b", "text": "y", "comments": 5, "followers": 1000,
         "name": "다른채널", "thumbnail": "b.jpg"},   # 구조 캐시 없음
    ]
    out = _aipick.build_aipick(sources, {})
    cby = {c["video_id"]: c for c in out["candidates"]}
    assert set(cby) == {"a", "b"}
    # 캐시 있는 a: 이름·썸네일·구조(뷰) 다 실림
    assert cby["a"]["name"] == "살림홈" and cby["a"]["thumbnail"] == "a.jpg"
    assert cby["a"]["structure"] and cby["a"]["structure"]["hook_type"] == "권위인용"
    assert cby["a"]["structure"]["devices"] == ["주변인물"]
    assert abs(sum(s["pct"] for s in cby["a"]["structure"]["segments"]) - 100) < 0.5
    # 캐시 없는 b: structure=None(프론트 '분석 전'), 이름·썸네일은 그대로
    assert cby["b"]["structure"] is None
    assert cby["b"]["name"] == "다른채널" and cby["b"]["thumbnail"] == "b.jpg"
