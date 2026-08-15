"""종목별 공매도 — 일별 추이에서 '지금 몰리는 중인가'만 뽑는다.

## 왜 pykrx가 아니라 KIS인가 (2026-08-15 실측)

핸드오프에는 "`pykrx` 기설치라 최단"이라고 적혀 있었지만 **사실이 아니었다**:

    로컬  py -m pip show pykrx  → WARNING: Package(s) not found
    서버  venv/bin/python -c "import pykrx" → ModuleNotFoundError

어디에도 없고 `requirements.txt`에도 없다. 새로 깔면 라이브 배포에 의존성이 하나
늘고, 서버가 KRX를 직접 때리는 경로가 또 생긴다(이미 KIS라는 정식 경로가 있는데).

**KIS가 공매도를 그대로 준다** — `FHPST04830000`(국내주식 공매도 일별추이).
실측(현대차 005380, 2026-07-01~08-15): `rt_cd=0`, `output2` **32행**.
그래서 의존성 추가 없이 이미 인증·레이트게이트가 도는 `kis_api`를 그대로 쓴다.

## 응답 필드 (실측한 것만 쓴다)

| 필드 | 뜻 |
|---|---|
| `ssts_cntg_qty` | 그날 공매도 체결 수량 |
| `ssts_vol_rlim` | 그날 거래량 중 공매도 비중(%) ← **핵심 지표** |
| `ssts_tr_pbmn` | 그날 공매도 거래대금(원) |
| `acml_ssts_cntg_qty` | 기간 누적 공매도 수량 |
| `stck_clpr` / `prdy_ctrt` | 종가 / 전일대비율 |

⚠️ **이건 '공매도 잔고'가 아니라 '일별 공매도 체결'이다.** 잔고(대차잔고)는 KRX가
2영업일 늦게 공시하는 별도 통계고 이 API에 없다. 화면에도 그렇게 적는다 —
없는 것을 있는 것처럼 이름 붙이면 신뢰가 무너진다(차트 C층을 안 만든 것과 같은 이유).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import kis_api

_WON_TO_EOK = 1 / 100_000_000.0

# 공매도 비중이 이 % 이상이면 화면에서 '높음'으로 부른다.
# 실측 현대차 평균 6~10% 대라 시장 통념(10%)을 기준으로 잡았다.
_HEAVY_RATIO = 10.0


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_short_daily(code: str, days: int = 45) -> list[dict]:
    """일별 공매도 원본(최신→과거). 실패하면 예외를 올린다."""
    to = datetime.now()
    frm = to - timedelta(days=max(7, days))
    r = kis_api._authed_get(
        f"{kis_api.BASE}/uapi/domestic-stock/v1/quotations/daily-short-sale",
        headers={
            "content-type": "application/json; charset=utf-8",
            "appkey": kis_api._KEY,
            "appsecret": kis_api._SECRET,
            "tr_id": "FHPST04830000",
            "custtype": "P",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code.zfill(6),
            "FID_INPUT_DATE_1": frm.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": to.strftime("%Y%m%d"),
        },
        timeout=10,
    )
    r.raise_for_status()
    d = r.json()
    if str(d.get("rt_cd")) != "0":
        raise RuntimeError(d.get("msg1") or "KIS 오류")
    return d.get("output2") or []


def short_summary(code: str, days: int = 45) -> dict:
    """{date_from, date_to, days, ratio_last, ratio_avg, ratio_avg20, trend,
        heavy, series[], amt_eok_5, note}

    series[] = 오래된→최신 `{date, ratio, qty, amt_eok, close}` (스파크라인용).
    실패해도 화면 전체가 죽지 않게 `{error}` 만 담아 돌려준다(stock_flow와 같은 규약).
    """
    try:
        out = fetch_short_daily(code, days)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "series": []}

    if not out:
        return {"error": "no data", "series": []}

    # 원본은 최신이 앞 → 화면·계산은 시간순이 편하다
    rows = list(reversed(out))
    series = []
    for o in rows:
        d = o.get("stck_bsop_date") or ""
        series.append({
            "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d,
            "ratio": round(_num(o.get("ssts_vol_rlim")), 2),
            "qty": int(_num(o.get("ssts_cntg_qty"))),
            "amt_eok": round(_num(o.get("ssts_tr_pbmn")) * _WON_TO_EOK),
            "close": int(_num(o.get("stck_clpr"))),
        })

    ratios = [s["ratio"] for s in series]
    last = ratios[-1] if ratios else 0.0
    avg = sum(ratios) / len(ratios) if ratios else 0.0
    r5 = ratios[-5:]
    r20 = ratios[-20:]
    avg5 = sum(r5) / len(r5) if r5 else 0.0
    avg20 = sum(r20) / len(r20) if r20 else 0.0

    # 추세 판정은 **5일 평균 vs 20일 평균**으로 한다.
    # 하루치만 보면 그날 수급 한 방에 흔들려 매번 말이 바뀐다.
    if avg20 and avg5 >= avg20 * 1.3:
        trend = "늘는 중"
    elif avg20 and avg5 <= avg20 * 0.7:
        trend = "주는 중"
    else:
        trend = "비슷"

    return {
        "date_from": series[0]["date"] if series else "",
        "date_to": series[-1]["date"] if series else "",
        "days": len(series),
        "ratio_last": round(last, 2),
        "ratio_avg": round(avg, 2),
        "ratio_avg5": round(avg5, 2),
        "ratio_avg20": round(avg20, 2),
        "trend": trend,
        "heavy": last >= _HEAVY_RATIO,
        "amt_eok_5": sum(s["amt_eok"] for s in series[-5:]),
        "series": series,
        # 이름을 정확히 적는다 — 잔고가 아니라 체결이다
        "note": "공매도 잔고(대차잔고)가 아니라 일별 공매도 체결 비중입니다",
    }
