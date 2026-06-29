"""글로벌 지표 — esignal.co.kr (실시간) + yfinance (원달러 fallback).

전일종가 스크래핑:
  scrape_all_prevclose() → esignal WTI 페이지에서 Playwright로 전 심볼 변동값 파싱.
  서버 시작 시 + 이후 1시간마다 호출. 결과는 _PW_PREVCLOSE 에 캐시.
  등락률 = (현재가 - 전일종가) / 전일종가 × 100
  fallback: open 대비 등락률
"""
import re
import time

_CACHE: dict = {}
_CACHE_TTL = 15  # 15초 캐시 (esignal IP 차단 방지 최소값)

# Playwright로 스크래핑한 전일종가 캐시
# {"kospif": 1385.9, "kospif_ngt": 1385.9, "nq": 29368.25, "oil": 69.23}
_PW_PREVCLOSE: dict = {}
_PW_PREVCLOSE_TTL = 3600  # 1시간 (전일종가는 하루 중 불변)
_PW_PREVCLOSE_TS: float = 0.0

_ESIGNAL_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://esignal.co.kr/",
}


_SCRAPE_SCRIPT = r"""
import re, json, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://esignal.co.kr/wti/", wait_until="load", timeout=20000)
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    browser.close()
pairs = re.findall(r"([\d,]+\.?\d*)\s*\(([+\-][\d,]+\.?\d*)\)", text)
sym_keys = ["kospif","kospif_ngt","spx","nq","oil","gold"]
result = {}
for i,(p,c) in enumerate(pairs[:6]):
    result[sym_keys[i]] = round(float(p.replace(",","")) - float(c.replace(",","")), 4)
print(json.dumps(result))
"""

def scrape_all_prevclose() -> dict:
    """별도 subprocess로 Playwright 실행 → 전 심볼 전일종가 파싱.
    asyncio 충돌 방지: FastAPI 이벤트 루프와 완전히 분리.
    반환: {"kospif": float, "kospif_ngt": float, "nq": float, "oil": float}
    """
    global _PW_PREVCLOSE, _PW_PREVCLOSE_TS
    now = time.time()
    if now - _PW_PREVCLOSE_TS < _PW_PREVCLOSE_TTL and _PW_PREVCLOSE:
        return _PW_PREVCLOSE

    try:
        import subprocess, sys as _sys, json as _json
        r = subprocess.run(
            [_sys.executable, "-c", _SCRAPE_SCRIPT],
            capture_output=True, text=True, timeout=35,
        )
        if r.returncode == 0 and r.stdout.strip():
            result = _json.loads(r.stdout.strip())
            if result:
                _PW_PREVCLOSE = result
                _PW_PREVCLOSE_TS = now
            return result
    except Exception:
        pass

    return _PW_PREVCLOSE  # 실패 시 기존 캐시 유지


def _calc_rate(price: float, cache_key_short: str, open_price: float) -> float:
    """전일종가 캐시 있으면 그걸로, 없으면 open 대비 등락률."""
    pc = _PW_PREVCLOSE.get(cache_key_short, 0)
    if pc > 0:
        return round((price - pc) / pc * 100, 2)
    if open_price > 0:
        return round((price - open_price) / open_price * 100, 2)
    return 0.0


def _esignal_cache(url: str, cache_key: str, sym_short: str, referer: str = "") -> dict:
    """esignal cache JSON → {price, change_rate, bars, source}."""
    import requests as _req
    now = time.time()
    if cache_key in _CACHE and now - _CACHE[cache_key]["ts"] < _CACHE_TTL:
        # 캐시된 데이터도 전일종가 업데이트 반영
        cached = _CACHE[cache_key]["data"]
        pc = _PW_PREVCLOSE.get(sym_short, 0)
        if pc > 0:
            cached = dict(cached)
            cached["change_rate"] = round((cached["price"] - pc) / pc * 100, 2)
        return cached

    hdr = dict(_ESIGNAL_HDR)
    if referer:
        hdr["Referer"] = referer

    try:
        ts_ms = int(now * 1000)
        r = _req.get(f"{url}?_={ts_ms}", headers=hdr, timeout=8)
        if r.status_code == 200:
            j = r.json()
            open_price = float(j.get("open") or 0)
            rows = j.get("data") or []
            if rows and open_price > 0:
                last = rows[-1]
                price = float(last[1])
                change_rate = _calc_rate(price, sym_short, open_price)
                bars = [float(d[1]) for d in rows[-30:]]
                data = {"price": round(price, 2), "change_rate": change_rate,
                        "bars": bars, "source": "esignal"}
                _CACHE[cache_key] = {"data": data, "ts": now}
                return data
    except Exception:
        pass

    return {"price": 0, "change_rate": 0.0, "bars": [], "source": "err"}


def _yf_price_bars(ticker: str, interval: str = "15m") -> dict:
    """yfinance fallback."""
    import yfinance as yf
    now = time.time()
    key = f"__yf_{ticker}__"
    if key in _CACHE and now - _CACHE[key]["ts"] < _CACHE_TTL:
        return _CACHE[key]["data"]
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
            for v in hist["Close"].values:
                val = float(v) if not hasattr(v, "__iter__") else float(v[0])
                if val > 0:
                    bars.append(round(val, 4))
        bars = bars[-30:]
        data = {"price": round(price, 2), "change_rate": change_rate, "bars": bars}
    except Exception:
        data = {"price": 0, "change_rate": 0.0, "bars": []}
    _CACHE[key] = {"data": data, "ts": now}
    return data


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_nasdaq_futures() -> dict:
    """나스닥100 선물 — esignal nq.js (실시간, 전일종가 대비 등락률)."""
    return _esignal_cache(
        "https://esignal.co.kr/data/cache/nq.js",
        "__esignal_nq__", "nq",
        referer="https://esignal.co.kr/nasdaq100-futures/",
    )


def get_kospi_futures() -> dict:
    """코스피200 선물(주간) — esignal kospif_day.js."""
    return _esignal_cache(
        "https://esignal.co.kr/data/cache/kospif_day.js",
        "__esignal_kospif__", "kospif",
        referer="https://esignal.co.kr/kospi200-futures/",
    )


def get_kospi_night_futures() -> dict:
    """코스피200 야간선물 — esignal kospif_ngt.js."""
    return _esignal_cache(
        "https://esignal.co.kr/data/cache/kospif_ngt.js",
        "__esignal_kospif_ngt__", "kospif_ngt",
        referer="https://esignal.co.kr/kospi200-futures/",
    )


def get_wti() -> dict:
    """WTI 원유 선물 — esignal oil.js."""
    return _esignal_cache(
        "https://esignal.co.kr/data/cache/oil.js",
        "__esignal_oil__", "oil",
        referer="https://esignal.co.kr/wti/",
    )


def get_usdkrw() -> dict:
    """원달러 환율 — yfinance USDKRW=X."""
    return _yf_price_bars("USDKRW=X", "15m")


# ── 하위 호환용 ──────────────────────────────
def get_spy() -> dict:
    return _yf_price_bars("SPY", "15m")
