from shopping_shorts import seo_probe


def _items(n, views, subs):
    return [{"title": f"t{i}", "views": views, "subs": subs} for i in range(n)]


def test_judge_blue():
    """수요 있고(조회수 높음) 작은 채널도 상위권 → 뚫린다."""
    assert seo_probe.judge(320_000, 0.4, 20) == "blue"


def test_judge_red():
    """수요는 있으나 대형 채널이 독식 → 레드오션."""
    assert seo_probe.judge(1_800_000, 0.05, 20) == "red"


def test_judge_dead():
    """조회수가 낮으면 소형채널 비율과 무관하게 수요 없음."""
    assert seo_probe.judge(3_000, 0.9, 20) == "dead"


def test_judge_unknown_small_sample():
    """샘플이 모자라면 판정하지 않는다 — 거짓 근거를 만들지 않는다."""
    assert seo_probe.judge(320_000, 0.4, 2) == "unknown"


def test_judge_boundary_views_floor():
    """문턱 정확히 = 통과(>=). off-by-one 방지."""
    assert seo_probe.judge(100_000, 0.4, 20) == "blue"
    assert seo_probe.judge(99_999, 0.4, 20) == "dead"


def test_judge_boundary_small_ratio():
    assert seo_probe.judge(320_000, 0.3, 20) == "blue"
    assert seo_probe.judge(320_000, 0.29, 20) == "red"


def test_summarize_median_and_ratio():
    items = [{"title": "a", "views": 100, "subs": 500},
             {"title": "b", "views": 300, "subs": 50_000},
             {"title": "c", "views": 200, "subs": 900}]
    got = seo_probe.summarize(items)
    assert got["views_median"] == 200          # 중앙값(평균 아님 — 이상치에 안 흔들리게)
    assert got["small_ratio"] == 2 / 3         # subs < 10,000 인 게 2개
    assert got["sample_n"] == 3


def test_summarize_top_titles_by_views():
    """top_titles는 조회수 상위 3개 — 사장님이 눈으로 검증할 실물."""
    items = [{"title": "low", "views": 1, "subs": 1},
             {"title": "high", "views": 999, "subs": 1},
             {"title": "mid", "views": 50, "subs": 1},
             {"title": "x", "views": 2, "subs": 1}]
    got = seo_probe.summarize(items)
    assert got["top_titles"] == ["high", "mid", "x"]


def test_summarize_empty_is_unknown():
    got = seo_probe.summarize([])
    assert got["verdict"] == "unknown"
    assert got["sample_n"] == 0


def test_summarize_missing_subs_counts_as_large():
    """구독자를 못 받아온 채널을 '작다'고 치면 블루오션이 과대평가된다 → 크다고 친다."""
    items = _items(5, 500_000, 0)
    for it in items:
        it.pop("subs")
    got = seo_probe.summarize(items)
    assert got["small_ratio"] == 0.0
    assert got["verdict"] == "red"
