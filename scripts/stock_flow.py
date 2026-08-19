"""종목별 수급 — 주체를 갈라서 5일·20일 누적으로 준다.

## 왜 새로 만들었나 (2026-08-15 실측)

`osc_live.fetch_supply_series()`는 같은 KIS 응답(`FHKST01010900`)을 읽으면서
**외국인+기관을 더해버린다**. 빈집 오실레이터 공식이 합산값을 쓰기 때문인데,
그 바람에 "누가 사고 누가 파나"가 화면에서 사라졌다.

실제로 현대차(005380)에서 갈라 보니 판단이 뒤집혔다:
    외국인 20일 +1,761억  /  기관 20일 -1,090억
합산은 +671억이라 "수급 들어온다"로 보이지만, 국내 기관은 20일 내내 팔고 있었다.

응답 원본에는 개인/외국인/기관이 **이미 따로** 들어 있다(`prsn_/frgn_/orgn_`).
더하지 않고 그대로 보존하기만 하면 된다.

⚠️ 종목 단위로 KIS가 주는 주체는 **개인·외국인·기관 3분류뿐**이다.
   사모·투신·연기금 세부는 이 API에 없다(원본 필드 전수 확인). 시장 전체는
   키움 `ka10051`로 세부가 나오지만 종목별은 경로가 없다.
"""
from __future__ import annotations

import kis_api

# 단위: KIS는 순매수 대금을 백만원으로 준다 → 억원으로 바꿔 화면에 그대로 쓴다
_MILLION_TO_EOK = 1 / 100.0

_SUBJECTS = (
    ("frgn_ntby_tr_pbmn", "외국인"),
    ("orgn_ntby_tr_pbmn", "기관"),
    ("prsn_ntby_tr_pbmn", "개인"),
)


def fetch_investor_daily(code: str) -> list[dict]:
    """일별 투자자 순매수(최신→과거). 실패하면 빈 리스트."""
    r = kis_api._authed_get(
        f"{kis_api.BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
        headers={
            "content-type": "application/json; charset=utf-8",
            "appkey": kis_api._KEY,
            "appsecret": kis_api._SECRET,
            "tr_id": "FHKST01010900",
            "custtype": "P",
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6)},
        timeout=8,
    )
    r.raise_for_status()
    return r.json().get("output", []) or []


def _num(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def flow_summary(code: str, windows=(5, 20)) -> dict:
    """{date_from, date_to, close, change, rows:[{name, w5, w20, daily5[]}], days}

    rows[].w5/w20 = 억원 누적. daily5 = 최근 5거래일 일별(오래된→최신).
    """
    try:
        out = fetch_investor_daily(code)
    except Exception as e:  # 네트워크·키 문제로 화면 전체가 죽지 않게 한다
        return {"error": f"{type(e).__name__}: {e}", "rows": [], "days": 0}

    if not out:
        return {"error": "no data", "rows": [], "days": 0}

    rows = []
    for key, name in _SUBJECTS:
        item = {"name": name}
        for w in windows:
            item[f"w{w}"] = round(sum(_num(o.get(key)) for o in out[:w]) * _MILLION_TO_EOK)
        item["daily5"] = [
            round(_num(o.get(key)) * _MILLION_TO_EOK) for o in reversed(out[:5])
        ]
        rows.append(item)

    last = out[0]
    oldest_idx = min(max(windows) - 1, len(out) - 1)
    return {
        "date_to": last.get("stck_bsop_date", ""),
        "date_from": out[oldest_idx].get("stck_bsop_date", ""),
        "close": _num(last.get("stck_clpr")),
        "change": _num(last.get("prdy_vrss")),
        "rows": rows,
        "days": len(out),
    }
