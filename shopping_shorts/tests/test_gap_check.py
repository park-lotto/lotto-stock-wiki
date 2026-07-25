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
