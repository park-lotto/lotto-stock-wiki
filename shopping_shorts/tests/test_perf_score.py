from shopping_shorts import perf_score


def test_percentile_monotonic():
    peers = [10, 100, 1000, 10000]
    assert perf_score.within_platform_percentile(10000, peers) == 1.0
    assert perf_score.within_platform_percentile(10, peers) < \
           perf_score.within_platform_percentile(1000, peers)
    assert perf_score.within_platform_percentile(None, peers) == 0.0


def test_recency_decay_half_life():
    now = "2026-07-31T00:00:00"
    d0 = perf_score.recency_decay("2026-07-31T00:00:00", now, half_life_days=30)
    d30 = perf_score.recency_decay("2026-07-01T00:00:00", now, half_life_days=30)
    assert abs(d0 - 1.0) < 1e-6
    assert abs(d30 - 0.5) < 0.02
    assert perf_score.recency_decay(None, now) == 1.0


def test_compute_perf_score_range_and_recency_penalty():
    peers = {"tiktok": [
        {"views": 10, "likes": 1, "comments": 0, "captured_at": "2026-07-31T00:00:00"},
        {"views": 10000, "likes": 900, "comments": 50, "captured_at": "2026-07-31T00:00:00"}]}
    hi_fresh = perf_score.compute_perf_score(
        {"platform": "tiktok", "views": 10000, "likes": 900, "comments": 50,
         "followers": None, "captured_at": "2026-07-31T00:00:00"}, peers, now_iso="2026-07-31T00:00:00")
    hi_old = perf_score.compute_perf_score(
        {"platform": "tiktok", "views": 10000, "likes": 900, "comments": 50,
         "followers": None, "captured_at": "2026-05-01T00:00:00"}, peers, now_iso="2026-07-31T00:00:00")
    assert 0.0 <= hi_old < hi_fresh <= 1.0
