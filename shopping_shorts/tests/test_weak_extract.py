"""추출 조용한 실패 검출 — 커버리지가 낮으면 재시도하고 표시한다(2026-07-31).

사장님: "실제 영상은 20초가 넘는데 추출할 때 실패한 거라 사용자는 알 수가 없다."
실측 job 8226822c5b09: B영상 21초가 2구간 7.4초(35%)로 나와 재료가 사실상 없었고,
화면엔 아무 표시가 없어 "왜 A로만 만들어졌지?"로만 보였다.
"""
from shopping_shorts import mix_pipeline as mp


def _r(spans):
    return {"segments": [{"seg_id": f"v-{i}", "start": a, "end": b}
                         for i, (a, b) in enumerate(spans)]}


def test_coverage_is_covered_over_duration(monkeypatch):
    monkeypatch.setattr(mp, "_video_seconds", lambda p: 20.0)
    assert mp._extract_coverage(_r([(0, 5), (5, 10)]), "x.mp4") == 0.5


def test_coverage_none_when_duration_unknown(monkeypatch):
    monkeypatch.setattr(mp, "_video_seconds", lambda p: None)
    assert mp._extract_coverage(_r([(0, 5)]), "x.mp4") is None


def test_real_failure_case_is_below_threshold(monkeypatch):
    """실측: 21초 영상이 2구간 7.4초 → 35%로 임계 아래."""
    monkeypatch.setattr(mp, "_video_seconds", lambda p: 21.0)
    cov = mp._extract_coverage(_r([(0.8, 7.4), (7.4, 8.2)]), "x.mp4")
    assert cov < mp._MIN_COVERAGE


def test_full_coverage_passes(monkeypatch):
    monkeypatch.setattr(mp, "_video_seconds", lambda p: 20.0)
    cov = mp._extract_coverage(_r([(0, 10), (10, 19)]), "x.mp4")
    assert cov >= mp._MIN_COVERAGE


def test_coverage_capped_at_one(monkeypatch):
    """구간이 겹쳐 합이 길이를 넘어도 100%를 넘기지 않는다."""
    monkeypatch.setattr(mp, "_video_seconds", lambda p: 10.0)
    assert mp._extract_coverage(_r([(0, 8), (0, 8)]), "x.mp4") == 1.0


def test_video_seconds_is_safe_on_bad_path():
    assert mp._video_seconds("존재하지않는파일.mp4") is None
