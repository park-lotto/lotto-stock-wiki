from scripts.channel_pipeline.cost_guard import estimate, can_run, reduce_scope, DAILY_CAP_USD


def test_estimate_zero_files():
    manifest = {"telegram": [], "blog": [], "report": [], "yt": []}
    cost, detail = estimate(manifest)
    assert cost < DAILY_CAP_USD
    assert "$" in detail


def test_estimate_many_files():
    manifest = {"telegram": ["f"] * 50, "blog": ["f"] * 50, "report": [], "yt": []}
    cost, detail = estimate(manifest)
    assert cost > 0
    assert "A(Gemini" in detail


def test_can_run_under_cap():
    manifest = {"telegram": ["f"] * 5, "blog": [], "report": [], "yt": []}
    ok, cost, _ = can_run(manifest)
    assert ok is True
    assert cost < DAILY_CAP_USD


def test_can_run_over_cap():
    manifest = {"telegram": ["f"] * 500, "blog": ["f"] * 500, "report": [], "yt": []}
    ok, cost, _ = can_run(manifest)
    assert ok is False
    assert cost > DAILY_CAP_USD


def test_reduce_scope():
    manifest = {"telegram": [f"f{i}" for i in range(20)], "blog": [], "report": [], "yt": []}
    reduced = reduce_scope(manifest, cap=5)
    assert len(reduced["telegram"]) == 5
    assert reduced["telegram"] == [f"f{i}" for i in range(15, 20)]
