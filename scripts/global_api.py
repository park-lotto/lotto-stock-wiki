"""글로벌 지표 — yfinance 기반 (SPY / WTI / 원달러 / 코스피선물)."""
import time
import yfinance as yf

_CACHE: dict = {}
_CACHE_TTL = 180  # 3분 캐시


def _yf_price_bars(ticker: str, interval: str = "15m") -> dict:
    """ticker → {price, change_rate, bars(오름차순 최대 30)}."""
    now = time.time()
    if ticker in _CACHE and now - _CACHE[ticker]["ts"] < _CACHE_TTL:
        return _CACHE[ticker]["data"]

    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = float(fi.last_price or 0)
        prev  = float(fi.previous_close or price or 1)
        change_rate = round((price - prev) / prev * 100, 2) if prev else 0.0

        hist = yf.download(ticker, period="1d", interval=interval,
                           progress=False, auto_adjust=True)
        bars = []
        if len(hist) > 0:
            close_col = hist["Close"]
            for v in close_col.values:
                val = float(v) if not hasattr(v, "__iter__") else float(v[0])
                if val > 0:
                    bars.append(round(val, 4))
        bars = bars[-30:]

        data = {"price": round(price, 2), "change_rate": change_rate, "bars": bars}
    except Exception:
        data = {"price": 0, "change_rate": 0.0, "bars": []}

    _CACHE[ticker] = {"data": data, "ts": now}
    return data


def get_spy() -> dict:
    """SPY ETF 현재가 + 등락률 + 15분봉."""
    return _yf_price_bars("SPY", "15m")


def get_wti() -> dict:
    """WTI 원유 선물 현재가 + 등락률."""
    d = _yf_price_bars("CL=F", "15m")
    return {"price": d["price"], "change_rate": d["change_rate"], "bars": d["bars"]}


def get_usdkrw() -> dict:
    """원달러 환율 현재가 + 등락률."""
    d = _yf_price_bars("USDKRW=X", "15m")
    return {"price": d["price"], "change_rate": d["change_rate"], "bars": d["bars"]}


def get_kospi_futures() -> dict:
    """코스피200 선물 현재가.
    KIS 주간선물(FHKIF03010100) 시도 → 실패 시 yfinance^KS11 fallback.
    """
    import os, sys, requests as _req
    try:
        # KIS API로 주간선물 근월물 조회
        sys.path.insert(0, os.path.dirname(__file__))
        import kis_api as _kis
        tok = _kis._token()
        for code in ("101W6C0", "101W6B0", "101V6C0", "101V6B0",
                     "101W6C", "101W6B", "101V9", "101V6"):
            r = _req.get(
                "https://openapi.koreainvestment.com:9443"
                "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                headers={"content-type": "application/json;charset=UTF-8",
                         "authorization": f"Bearer {tok}",
                         "appkey": _kis._KEY, "appsecret": _kis._SECRET,
                         "tr_id": "FHKIF03010100", "custtype": "P"},
                params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code},
                timeout=5)
            d = r.json().get("output", {})
            price = float(d.get("stck_prpr", 0) or 0)
            if price > 0:
                prev  = float(d.get("stck_sdpr", price) or price)
                change_rate = round((price - prev) / prev * 100, 2) if prev else 0.0
                return {"price": round(price, 2), "change_rate": change_rate,
                        "bars": [], "code": code}
    except Exception:
        pass

    # fallback: ^KS11 (KOSPI 지수 근사)
    d = _yf_price_bars("^KS11", "15m")
    return {**d, "code": "^KS11"}
