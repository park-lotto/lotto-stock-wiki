"""osc_live.py — 수급 오실레이터 실시간 계산(엑셀 독립, KIS 직접).

배경: 서버 지표(수급빈집 osc)는 엑셀 export(taerini_stock.json) 커버 종목만 나오고,
히트맵에 커스텀 등록한 종목(예: 부국증권)은 "미수록"이 됐다. 이 모듈은 KIS의 일별
외인·기관 순매수(FHKST01010900, 30일)로 calc_oscillator와 동일 공식의 osc를 그 자리에서
계산해, 엑셀에 없어도 등록된 아무 종목이나 지표가 나오게 한다.

공식(calc_oscillator 재사용): osc = MACD(EMA12-EMA26) - Signal(EMA9) of [(기관+외인)/시총].
순수 계산부(compute_osc_from_series)는 주입 데이터로 테스트 가능. fetch_*만 KIS 실호출.
"""
import sys
import pathlib

_SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kis_api  # noqa: E402
import calc_oscillator as _co  # noqa: E402  (calc_osc, trend_str, ema_series 재사용)


def fetch_supply_series(code: str, n: int = 40) -> list:
    """KIS 일별 외인+기관 순매수 시계열(오래된→최신). 값 없는 날(당일 미체결)은 제외."""
    r = kis_api._authed_get(
        f"{kis_api.BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
        headers={"content-type": "application/json; charset=utf-8",
                 "appkey": kis_api._KEY, "appsecret": kis_api._SECRET,
                 "tr_id": "FHKST01010900", "custtype": "P"},
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6)},
        timeout=8,
    )
    r.raise_for_status()
    rows = r.json().get("output", []) or []
    out = []
    for o in rows:  # rows[0]=최신
        f = o.get("frgn_ntby_tr_pbmn")
        g = o.get("orgn_ntby_tr_pbmn")
        if f in (None, "") and g in (None, ""):
            continue  # 당일 미체결 등 빈 행
        out.append(int(float(f or 0)) + int(float(g or 0)))
    return list(reversed(out[:n]))  # 오래된→최신


def fetch_market_cap_eok(code: str) -> float:
    """시가총액(억원). 실패 시 0."""
    try:
        r = kis_api._authed_get(
            f"{kis_api.BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers={"content-type": "application/json; charset=utf-8",
                     "appkey": kis_api._KEY, "appsecret": kis_api._SECRET,
                     "tr_id": "FHKST01010100", "custtype": "P"},
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6)},
            timeout=8,
        )
        r.raise_for_status()
        return float((r.json().get("output") or {}).get("hts_avls") or 0)
    except Exception:
        return 0.0


def compute_osc_from_series(net_series: list, market_cap_eok: float) -> dict:
    """(기관+외인) 시계열 + 시총 → osc(calc_oscillator 공식). 순수 함수.
    반환 {osc, series, trend} — series 없거나 시총 0이면 osc=None."""
    if not net_series or not market_cap_eok:
        return {"osc": None, "series": [], "trend": ""}
    signal = [v / market_cap_eok for v in net_series]
    r = _co.calc_osc(signal)
    return {"osc": r["latest"], "series": r["series"], "trend": _co.trend_str(r["series"])}


def group_from_osc(osc, trend: str) -> str | None:
    """osc 부호·트렌드로 방향 라벨(엑셀 %ile과 다른 실시간 등급)."""
    if osc is None:
        return None
    if osc > 0:
        return "매수우위"
    if "재진입" in (trend or ""):
        return "반등시도"
    return "빈집(매도우위)"


def live_osc(code: str) -> dict:
    """한 종목의 실시간 osc(impure 엔트리)."""
    return compute_osc_from_series(fetch_supply_series(code), fetch_market_cap_eok(code))


def live_osc_entry(code: str, name: str = None) -> dict | None:
    """taerini_stock 'stock'과 호환되는 실시간 osc 엔트리. 계산 불가면 None.
    엑셀 %ile과 다른 실시간 지표이므로 osc.live=True, pct=None(오해 방지)."""
    r = live_osc(code)
    if r.get("osc") is None:
        return None
    return {
        "name": name,
        "osc": {
            "group": group_from_osc(r["osc"], r["trend"]),
            "osc": r["osc"], "pct": None, "trend": r["trend"],
            "series": r["series"], "live": True,
        },
    }
