from scripts.goal_loop import verify

def test_no_anomaly_normal_day():
    data = {"headline": "반도체 강세", "date": "2026-07-02"}
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": -0.8, "kosdaq": 0.5})
    assert flags == []

def test_index_crash_flags():
    data = {"headline": "폭락", "date": "2026-07-02"}
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": -3.4, "kosdaq": -2.0})
    assert any("코스피" in f for f in flags)

def test_stale_data_flags():
    data = {"headline": "x", "date": "2026-06-30"}   # 대상일과 불일치
    flags = verify.detect_anomalies(data, "2026-07-02", {"kospi": 0.1, "kosdaq": 0.1})
    assert any("공백" in f or "최신" in f for f in flags)
