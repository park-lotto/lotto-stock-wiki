import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

import server  # noqa: E402


def _bars(n, start_hhmm=900):
    out = []
    t = start_hhmm
    for _ in range(n):
        out.append({"t": f"{t:04d}00", "price": 100.0})
        t += 15
        if t % 100 >= 60:
            t += 40
    return out


def _make_result(n_bars, price=100.0):
    return {
        "0001": {"label": "코스피", "price": price, "bars": _bars(n_bars)},
        "1001": {"label": "코스닥", "price": price, "bars": _bars(n_bars)},
    }


def test_serve_mf_does_not_apply_bar_guard_across_day_boundary(monkeypatch):
    """전날 27봉 스냅샷이 남아있어도, 그 스냅샷이 '오늘' 것이 아니면
    새로 받아온 오늘의(적은) 봉수를 어제 것으로 덮어쓰면 안 된다."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    monkeypatch.setattr(server, "_last_good_mf",
                         {"result": _make_result(27), "date": yesterday})

    today_fresh = _make_result(2)
    resp = server._serve_mf(today_fresh)
    body = resp.body.decode("utf-8") if hasattr(resp, "body") else None
    import json
    payload = json.loads(body) if body else today_fresh

    assert len(payload["0001"]["bars"]) == 2, (
        "오늘 갓 받아온 2개봉이 전날 스냅샷(27개)으로 덮어써지면 안 됨")
    assert len(payload["1001"]["bars"]) == 2


def test_serve_mf_still_applies_bar_guard_within_same_day(monkeypatch):
    """같은 날 안에서 봉수가 급감하면(페이지네이션 순간실패 등) 기존 방어 로직대로
    직전 정상 스냅샷을 유지해야 한다 — 이번 수정이 원래 목적을 깨면 안 됨."""
    today = datetime.now().strftime("%Y%m%d")
    monkeypatch.setattr(server, "_last_good_mf",
                         {"result": _make_result(20), "date": today})

    degraded = _make_result(2)
    resp = server._serve_mf(degraded)
    body = resp.body.decode("utf-8") if hasattr(resp, "body") else None
    import json
    payload = json.loads(body) if body else degraded

    assert len(payload["0001"]["bars"]) == 20, (
        "같은 날 안의 순간적 봉수 급감은 여전히 직전 정상값으로 방어돼야 함")
