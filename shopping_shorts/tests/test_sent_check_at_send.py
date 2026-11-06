"""11-06 김준용 #10406: 뒤에서 지운 결과를 받을 때 '쓰는 구간'을 그때 계획 파일로 다시 읽어, 그 사이 vmake_cuts 가 사라지자 used 0초 →
정상 전송을 '쓰지 않는 구간까지 보냄'(final)으로 편을 끝냈다. 보낸 때의 쓰는 구간(job.json used)과 견준다."""
import json

from tools.calcopy import vmake_clean as VC


def test_bg_take_returns_used_recorded_at_send(tmp_path, monkeypatch):
    d = tmp_path / VC.BG_DIR
    d.mkdir()
    used = {"a.mp4": [[8.2, 14.9], [18.6, 22.6]]}
    (d / "job.json").write_text(json.dumps({"src": str(tmp_path), "spans": {}, "rd": "", "spots": {}, "at": 1, "used": used}), encoding="utf-8")
    (d / "result.json").write_text(json.dumps({"error": "x", "calls": 1}), encoding="utf-8")
    r = VC.bg_take(tmp_path, 0)
    assert r["used_at_send"] == used


def test_sent_within_send_time_used_is_not_bad():
    used = {"a.mp4": [[8.2, 14.86], [18.6, 22.63], [24.17, 37.77], [39.2, 42.5], [46.4, 48.2], [51.28, 54.83]]}
    assert VC.sent_check({"a.mp4": 32.933}, used) == []
    assert VC.sent_check({"a.mp4": 32.933}, {}) != []        # 받는 때 계획(빈 구간)과 견주면 오판 — 이걸 피하려고 보낸 때 기록을 쓴다


def test_c_clean_take_prefers_used_at_send():
    import inspect
    from tools.calcopy.hybrid import runner_ops as R
    assert 'r.get("used_at_send")' in inspect.getsource(R.c_clean_take)
