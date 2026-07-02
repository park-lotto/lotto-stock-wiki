"""네이버 증권 스크래퍼 — 인기 검색 종목."""
import re
import time
import requests

_CACHE: dict = {}
_CACHE_TTL = 120  # 2분

_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def minute_candles(code: str, tf_min: int = 5, count: int = 3000) -> list:
    """네이버 fchart 분봉(다일치, 1분 종가) → tf_min OHLC 리샘플.
    fchart는 여러 날치 1분봉을 주지만 종가만(OHLC null) → 버킷 내 1분 종가들로 OHLC 근사
    (open=첫종가, high=최대, low=최소, close=마지막종가). 시각적으로 실제 캔들과 거의 동일.
    반환(과거→최신): [{"time"(epoch초·KST-as-UTC), open, high, low, close, value}]
    """
    import calendar
    try:
        url = (f"https://fchart.stock.naver.com/sise.nhn?symbol={code}"
               f"&timeframe=minute&count={count}&requestType=0")
        r = requests.get(url, headers={"User-Agent": _HDR["User-Agent"]}, timeout=12)
        r.encoding = "euc-kr"
        items = re.findall(r'data="([^"]+)"', r.text)
    except Exception:
        return []
    tf = tf_min if tf_min and tf_min > 0 else 5
    buckets = {}
    for it in items:
        p = it.split("|")
        if len(p) < 6 or len(p[0]) < 12:
            continue
        try:
            close = float(p[4])
        except Exception:
            continue
        if close <= 0:
            continue
        try:
            vol = int(float(p[5]))
        except Exception:
            vol = 0
        dt = p[0]
        Y, Mo, D = int(dt[:4]), int(dt[4:6]), int(dt[6:8])
        hh, mm = int(dt[8:10]), int(dt[10:12])
        bmm = (mm // tf) * tf
        key = (Y, Mo, D, hh, bmm)
        b = buckets.get(key)
        if b is None:
            buckets[key] = {"open": close, "high": close, "low": close, "close": close, "value": vol}
        else:
            b["high"] = max(b["high"], close)
            b["low"] = min(b["low"], close)
            b["close"] = close
            b["value"] += vol
    out = []
    for key in sorted(buckets):
        Y, Mo, D, hh, bmm = key
        epoch = calendar.timegm((Y, Mo, D, hh, bmm, 0, 0, 0, 0))
        b = buckets[key]
        out.append({"time": epoch, "open": b["open"], "high": b["high"],
                    "low": b["low"], "close": b["close"], "value": b["value"]})
    return out


def get_popular_stocks(n: int = 10) -> list:
    """네이버 금융 메인 '인기 검색 종목' 상위 n개.
    반환: [{"rank":1,"code":"005930","name":"삼성전자","price":70000,"change_rate":-1.5}, ...]
    """
    now = time.time()
    key = "__naver_popular__"
    if key in _CACHE and now - _CACHE[key]["ts"] < _CACHE_TTL:
        return _CACHE[key]["data"][:n]

    try:
        r = requests.get("https://finance.naver.com/", headers=_HDR, timeout=8)
        r.raise_for_status()
        html = r.content.decode("euc-kr", errors="replace")

        # aside_popular 섹션 추출
        m = re.search(r'class="aside_area aside_popular"(.*?)(?=</div>\s*<div class="aside_area)', html, re.DOTALL)
        if not m:
            return []
        section = m.group(1)

        # 각 행 파싱: code, name, price, change
        rows = re.findall(
            r'href="/item/main\.naver\?code=(\d{6})"[^>]*>\s*([^<]+)</a>'
            r'.*?<td>([\d,]+)</td>'
            r'.*?<span[^>]*>\s*([\d,.]+)\s*</span>',
            section, re.DOTALL
        )

        # 등락 방향 추출 (up/down 클래스)
        signs = re.findall(r'<tr class="(up|down|same)">', section)

        result = []
        for i, row in enumerate(rows[:n]):
            code, name, price_str, change_str = row
            price = int(price_str.replace(",", ""))
            try:
                change = float(change_str.replace(",", ""))
            except Exception:
                change = 0.0
            sign = signs[i] if i < len(signs) else "same"
            if sign == "down":
                change = -change

            # 등락률 계산 (네이버가 변동폭만 줌 → prev_close로 역산)
            prev = price - change if sign != "same" else price
            change_rate = round(change / prev * 100, 2) if prev else 0.0
            if sign == "down":
                change_rate = -abs(change_rate)

            result.append({
                "rank": i + 1,
                "code": code,
                "name": name.strip(),
                "price": price,
                "change_rate": change_rate,
            })

        _CACHE[key] = {"data": result, "ts": now}
        return result[:n]
    except Exception:
        return []
