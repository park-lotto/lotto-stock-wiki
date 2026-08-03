import shopping_shorts.gap_check as gc


def test_no_korean_results_means_takeable(monkeypatch):
    monkeypatch.setattr(gc.youtube_search, "search",
                        lambda q, max_results=10: [{"title": "amazing woodworking skills"},
                                                   {"title": "satisfying video compilation"}])
    assert gc.gap_badge("mesmerising woodworking") == "🔥선점가능"


def test_korean_result_means_already_imported(monkeypatch):
    monkeypatch.setattr(gc.youtube_search, "search",
                        lambda q, max_results=10: [{"title": "해외 목공 반응 모음"},
                                                   {"title": "amazing woodworking"}])
    assert gc.gap_badge("mesmerising woodworking") == "이미유입"


def test_search_failure_is_unknown(monkeypatch):
    def boom(q, max_results=10):
        raise RuntimeError("quota exhausted")
    monkeypatch.setattr(gc.youtube_search, "search", boom)
    assert gc.gap_badge("anything") == "미확인"


def test_empty_title_is_unknown():
    assert gc.gap_badge("") == "미확인"
    assert gc.gap_badge(None) == "미확인"


def test_gap_badge_translates_cn(monkeypatch):
    from shopping_shorts import gap_check, youtube_search, video_analysis
    monkeypatch.setattr(video_analysis, "translate_keyword", lambda k, **kw: "주방 꿀템")
    seen = {}
    def fake_search(q, max_results=10):
        seen["q"] = q
        return [{"title": "한국어 재편집본"}]
    monkeypatch.setattr(youtube_search, "search", fake_search)
    assert gap_check.gap_badge("厨房神器", translate=True) == "이미유입"
    assert seen["q"] == "주방 꿀템"


def test_gap_badge_degrades_when_translation_not_korean(monkeypatch):
    from shopping_shorts import gap_check, video_analysis
    monkeypatch.setattr(video_analysis, "translate_keyword", lambda k, **kw: "厨房神器")  # 방향반대
    assert gap_check.gap_badge("厨房神器", translate=True) == "미확인"
