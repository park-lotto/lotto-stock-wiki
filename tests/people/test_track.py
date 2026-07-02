from pipeline.people import track


def _sel(date, hit, matched, missed, cands):
    return {
        "date": date,
        "thresholds": {"mode": "his"},
        "validation": {"hit_rate": hit, "mentioned_count": len(matched) + len(missed),
                       "matched": matched, "missed": missed},
        "candidates": [{"name": n} for n in cands],
    }


def test_record_from_selection():
    r = track._record_from_selection(_sel("2026-07-02", 0.25, ["A", "B"], ["C"], ["A", "B", "X"]))
    assert r["date"] == "2026-07-02"
    assert r["hit_rate"] == 0.25
    assert r["matched"] == ["A", "B"]
    assert r["candidates"] == ["A", "B", "X"]


def test_save_and_history_roundtrip(tmp_path):
    track.save_record("테스트", track._record_from_selection(_sel("2026-07-01", 0.2, ["A"], ["B"], ["A"])), base_dir=tmp_path)
    track.save_record("테스트", track._record_from_selection(_sel("2026-07-02", 0.3, ["A", "C"], [], ["A", "C"])), base_dir=tmp_path)
    h = track.history("테스트", base_dir=tmp_path)
    assert [r["date"] for r in h] == ["2026-07-01", "2026-07-02"]   # 날짜순
    assert h[-1]["hit_rate"] == 0.3


def test_history_empty(tmp_path):
    assert track.history("없음", base_dir=tmp_path) == []


def test_trend_summary(tmp_path):
    for d, hit in [("2026-07-01", 0.2), ("2026-07-02", 0.4)]:
        track.save_record("t", track._record_from_selection(_sel(d, hit, ["A"], [], ["A"])), base_dir=tmp_path)
    t = track.trend("t", base_dir=tmp_path)
    assert t["days"] == 2
    assert t["latest"] == 0.4
    assert t["avg"] == 0.3
