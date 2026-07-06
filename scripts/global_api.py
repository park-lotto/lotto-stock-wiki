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

# 원달러 환율 세션 상태 (무료 FX API는 일 단위 갱신 → 세션 시초 대비 변동 누적)
_FX_STATE: dict = {"day": "", "open": 0.0, "bars": []}

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


def _resample_bars(rows: list, interval_sec: int = 300, max_bars: int = 30) -> list:
    """esignal 원본(약 6초 간격 틱)을 interval_sec 단위로 묶어 마지막 값만 채택.

    기존에는 rows[-30:]로 원본 틱을 그대로 잘라 써서 30틱×6초≈3분 구간만
    보였다(체감상 "몇분봉인지 알 수 없는" 짧은 스냅샷). 5분 버킷으로 리샘플하면
    같은 30개 포인트로 최근 최대 2시간30분 구간을 보여줄 수 있다.
    """
    if not rows:
        return []
    buckets = {}
    for row in rows:
        # kospif_day.js는 [ts, price, vol, ...] 4열, nq/kospif_ngt/oil은 [ts, price] 2열 —
        # 튜플 언패킹(for ts, price in rows)은 4열에서 ValueError로 죽어 코스피선물 차트가 빈 값이 됐었다.
        ts, price = row[0], row[1]
        bucket = int(ts) // (interval_sec * 1000)
        buckets[bucket] = float(price)
    bars = [buckets[k] for k in sorted(buckets.keys())]
    return bars[-max_bars:]


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
                # 1분봉(방향 전환 포착용, 최근 60분) / 15분봉(큰 그림, 보유 이력 전체) 둘 다 제공
                bars_1m = _resample_bars(rows, interval_sec=60, max_bars=60)
                bars_15m = _resample_bars(rows, interval_sec=900, max_bars=20)
                bars = bars_1m
                # 마지막 체결 시각(epoch ms) — 야간선물 '마감' 날짜 표시에 사용
                last_ts = 0
                try:
                    last_ts = int(last[0])
                except Exception:
                    last_ts = 0
                data = {"price": round(price, 2), "change_rate": change_rate,
                        "bars": bars, "bars_1m": bars_1m, "bars_15m": bars_15m,
                        "source": "esignal", "last_ts": last_ts}
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


def _yf_daily_bars(ticker: str, days: int = 30) -> list:
    """yfinance 일봉 종가(과거→최신) 최근 days개. 1시간 캐시(일봉은 자주 안 바뀜)."""
    now = time.time()
    key = f"__yfd_{ticker}__"
    if key in _CACHE and now - _CACHE[key]["ts"] < 3600:
        return _CACHE[key]["data"]
    bars = []
    try:
        import yfinance as yf
        hist = yf.download(ticker, period=f"{days + 15}d", interval="1d",
                           progress=False, auto_adjust=True)
        for v in hist["Close"].values:
            val = float(v) if not hasattr(v, "__iter__") else float(v[0])
            if val > 0:
                bars.append(round(val, 4))
        bars = bars[-days:]
    except Exception:
        bars = []
    _CACHE[key] = {"data": bars, "ts": now}
    return bars


def _naver_daily_bars(code: str, days: int = 30) -> list:
    """네이버 fchart 일봉 종가(과거→최신) 최근 days개. 코스피선물류 일봉 소스 없어 KODEX200 근사용."""
    now = time.time()
    key = f"__nvd_{code}__"
    if key in _CACHE and now - _CACHE[key]["ts"] < 3600:
        return _CACHE[key]["data"]
    bars = []
    try:
        import naver_api as _nv
        candles = _nv.daily_candles(code, count=days + 15)
        bars = [c["close"] for c in candles][-days:]
    except Exception:
        bars = []
    _CACHE[key] = {"data": bars, "ts": now}
    return bars


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_nasdaq_futures() -> dict:
    """나스닥100 선물 — esignal nq.js (실시간, 전일종가 대비 등락률)."""
    d = dict(_esignal_cache(
        "https://esignal.co.kr/data/cache/nq.js",
        "__esignal_nq__", "nq",
        referer="https://esignal.co.kr/nasdaq100-futures/",
    ))
    d["bars_1d"] = _yf_daily_bars("NQ=F")
    return d


def get_kospi_futures() -> dict:
    """코스피200 선물(주간) — esignal kospif_day.js."""
    d = dict(_esignal_cache(
        "https://esignal.co.kr/data/cache/kospif_day.js",
        "__esignal_kospif__", "kospif",
        referer="https://esignal.co.kr/kospi200-futures/",
    ))
    # 선물 자체 일봉 소스가 없어 KODEX200(069500, KOSPI200 추종 ETF) 일봉으로 근사
    d["bars_1d"] = _naver_daily_bars("069500")
    return d


def get_kospi_night_futures() -> dict:
    """코스피200 야간선물 — esignal kospif_ngt.js."""
    d = dict(_esignal_cache(
        "https://esignal.co.kr/data/cache/kospif_ngt.js",
        "__esignal_kospif_ngt__", "kospif_ngt",
        referer="https://esignal.co.kr/kospi200-futures/",
    ))
    d["bars_1d"] = _naver_daily_bars("069500")
    return d


def get_wti() -> dict:
    """WTI 원유 선물 — esignal oil.js."""
    return _esignal_cache(
        "https://esignal.co.kr/data/cache/oil.js",
        "__esignal_oil__", "oil",
        referer="https://esignal.co.kr/wti/",
    )


def get_usdkrw() -> dict:
    """원달러 환율 — 네이버 marketindex(하나은행 고시, 인트라데이 갱신) 우선.

    기존 open.er-api.com은 '일 단위' 갱신이라 종일 값이 고정(1553.24/0.00%)됐음.
    네이버는 하루에도 여러 번 고시가 갱신돼 실시간에 가깝고, 전일종가 대비 등락률을 직접 제공.
    폴 때마다 값을 bars에 누적(장중 스텝 라인). 실패 시 무료 FX API로 폴백.
    """
    import requests as _req, datetime as _dt
    now = time.time()
    key = "__usdkrw__"
    if key in _CACHE and now - _CACHE[key]["ts"] < _CACHE_TTL:
        return _CACHE[key]["data"]

    rate = 0.0
    change_rate = 0.0
    source = ""
    # 1순위: 네이버 하나은행 고시 (인트라데이 갱신)
    try:
        j = _req.get("https://api.stock.naver.com/marketindex/exchange/FX_USDKRW/prices"
                     "?page=1&pageSize=3&category=exchange",
                     headers={"User-Agent": "Mozilla/5.0",
                              "Referer": "https://m.stock.naver.com/"}, timeout=8).json()
        rows = j if isinstance(j, list) else (j.get("result") or [])
        if rows:
            r0 = rows[0]
            rate = float(str(r0.get("closePrice", "0")).replace(",", "") or 0)
            fr = float(str(r0.get("fluctuationsRatio", "0")).replace(",", "") or 0)
            nm = (r0.get("fluctuationsType") or {}).get("name", "")
            change_rate = round(-fr if nm == "FALLING" else fr, 2)
            source = "naver"
    except Exception:
        pass

    # 2순위: 무료 FX API (일 단위) — 네이버 실패 시
    if rate <= 0:
        for url in ("https://open.er-api.com/v6/latest/USD",
                    "https://api.exchangerate-api.com/v4/latest/USD"):
            try:
                j = _req.get(url, timeout=8).json()
                rate = float((j.get("rates") or {}).get("KRW") or 0)
                if rate > 0:
                    source = "er-api"
                    break
            except Exception:
                pass
        if rate > 0:
            today0 = _dt.date.today().isoformat()
            if _FX_STATE["day"] != today0 or _FX_STATE["open"] <= 0:
                _FX_STATE.update({"day": today0, "open": rate, "bars": []})
            change_rate = round((rate - _FX_STATE["open"]) / _FX_STATE["open"] * 100, 2)

    if rate <= 0:
        return {"price": 0, "change_rate": 0.0, "bars": [], "source": "err"}

    # bars 누적 (장중 스텝 라인). 날짜 바뀌면 리셋.
    today = _dt.date.today().isoformat()
    if _FX_STATE["day"] != today:
        _FX_STATE.update({"day": today, "open": rate, "bars": []})
    _FX_STATE["bars"].append(round(rate, 2))
    _FX_STATE["bars"] = _FX_STATE["bars"][-30:]

    data = {"price": round(rate, 2), "change_rate": change_rate,
            "bars": list(_FX_STATE["bars"]), "source": source}
    _CACHE[key] = {"data": data, "ts": now}
    return data


# ── 하위 호환용 ──────────────────────────────
def get_spy() -> dict:
    return _yf_price_bars("SPY", "15m")


# ── 나스닥 프리마켓 개별종목·섹터 (저녁 야간선물 브리핑용) ──
_NASDAQ_WATCHLIST = {
    "반도체/AI": ["NVDA", "AMD", "AVGO", "MU"],
    "빅테크":    ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "전기차":    ["TSLA", "RIVN"],
    "바이오":    ["MRNA", "REGN"],
}
_NASDAQ_MOVERS_CACHE: dict = {"data": None, "ts": 0.0}
_NASDAQ_MOVERS_TTL = 300  # 5분 (18~20시 저녁 구간에만 호출되므로 부담 적음)


def get_nasdaq_premarket_movers() -> dict:
    """나스닥 프리마켓 개별종목 등락률(yfinance) + 섹터별 평균으로 강한 섹터 분류.
    프리마켓 세션 밖(preMarketChangePercent 없음)이면 정규장 등락률로 폴백.
    반환: {"stocks": [{"ticker","name","sector","rate"}...], "sectors": [{"sector","avg_rate"}...]}"""
    now = time.time()
    if _NASDAQ_MOVERS_CACHE["data"] and now - _NASDAQ_MOVERS_CACHE["ts"] < _NASDAQ_MOVERS_TTL:
        return _NASDAQ_MOVERS_CACHE["data"]

    import yfinance as yf
    all_tickers = [tk for tks in _NASDAQ_WATCHLIST.values() for tk in tks]
    stocks = []
    try:
        tks = yf.Tickers(" ".join(all_tickers))
        for sector, tickers in _NASDAQ_WATCHLIST.items():
            for tk in tickers:
                try:
                    info = tks.tickers[tk].info
                    rate = info.get("preMarketChangePercent")
                    if rate is None:
                        rate = info.get("regularMarketChangePercent") or 0.0
                    stocks.append({"ticker": tk, "name": info.get("shortName") or tk,
                                    "sector": sector, "rate": round(float(rate), 2)})
                except Exception:
                    continue
    except Exception:
        pass

    sector_rates: dict = {}
    for s in stocks:
        sector_rates.setdefault(s["sector"], []).append(s["rate"])
    sectors = [{"sector": k, "avg_rate": round(sum(v) / len(v), 2)}
               for k, v in sector_rates.items() if v]
    sectors.sort(key=lambda x: x["avg_rate"], reverse=True)
    stocks.sort(key=lambda x: x["rate"], reverse=True)

    data = {"stocks": stocks, "sectors": sectors}
    _NASDAQ_MOVERS_CACHE.update({"data": data, "ts": now})
    return data
