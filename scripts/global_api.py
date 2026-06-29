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


_ESIGNAL_CACHE_KEY = "__esignal_kospif__"

def get_kospi_futures() -> dict:
    """코스피200 선물 현재가 — esignal.co.kr REST 폴링.
    https://esignal.co.kr/data/cache/kospif_day.js
    data: [[timestamp_ms, price, volume, change_from_open], ...]
    주간(09:00~15:30) + 야간 모두 포함.
    fallback: ^KS11 (yfinance)
    """
    import requests as _req
    now = time.time()
    if _ESIGNAL_CACHE_KEY in _CACHE and now - _CACHE[_ESIGNAL_CACHE_KEY]["ts"] < _CACHE_TTL:
        return _CACHE[_ESIGNAL_CACHE_KEY]["data"]

    try:
        ts = int(now * 1000)
        r = _req.get(
            f"https://esignal.co.kr/data/cache/kospif_day.js?_={ts}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://esignal.co.kr/kospi200-futures/",
            },
            timeout=8,
        )
        if r.status_code == 200:
            j = r.json()
            open_price = float(j.get("open") or 0)
            rows = j.get("data") or []
            if rows and open_price > 0:
                last = rows[-1]
                price = float(last[1])
                change_rate = round((price - open_price) / open_price * 100, 2)
                bars = [float(d[1]) for d in rows[-30:]]
                data = {"price": round(price, 2), "change_rate": change_rate,
                        "bars": bars, "source": "esignal"}
                _CACHE[_ESIGNAL_CACHE_KEY] = {"data": data, "ts": now}
                return data
    except Exception:
        pass

    # fallback: ^KS11 (장 중만)
    d = _yf_price_bars("^KS11", "15m")
    return {**d, "source": "^KS11"}
