import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import osc_live as ol


def test_compute_osc_from_series_basic():
    ser = [10, -5, 20, -3, 15, 8, -2, 12, 30, -10, 5, 18, 22, -4, 9]
    r = ol.compute_osc_from_series(ser, market_cap_eok=1000.0)
    assert r["osc"] is not None
    assert len(r["series"]) == len(ser)
    assert isinstance(r["trend"], str) and r["trend"]


def test_compute_osc_empty_or_no_cap():
    assert ol.compute_osc_from_series([], 1000)["osc"] is None
    assert ol.compute_osc_from_series([1, 2, 3], 0)["osc"] is None


def test_group_from_osc():
    assert ol.group_from_osc(0.01, "↑ 재진입") == "매수우위"
    assert ol.group_from_osc(-0.01, "↑ 재진입") == "반등시도"
    assert ol.group_from_osc(-0.01, "↓ 빈집심화") == "빈집(매도우위)"
    assert ol.group_from_osc(None, "") is None


def test_live_osc_entry_shape_from_injected(monkeypatch):
    # 실호출 대신 계산부만 검증: fetch를 스텁
    monkeypatch.setattr(ol, "fetch_supply_series", lambda code, n=40: [5, -3, 10, 2, -8, 15, 4, -1, 9, 20, -5, 3, 11, 7])
    monkeypatch.setattr(ol, "fetch_market_cap_eok", lambda code: 500.0)
    e = ol.live_osc_entry("001270", name="부국증권")
    assert e["name"] == "부국증권"
    assert e["osc"]["live"] is True
    assert e["osc"]["pct"] is None          # 엑셀 %ile과 혼동 방지
    assert e["osc"]["osc"] is not None
    assert e["osc"]["group"] in ("매수우위", "반등시도", "빈집(매도우위)")
