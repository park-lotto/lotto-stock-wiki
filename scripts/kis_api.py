"""한국투자증권 API — 토큰 발급 + 현재가 조회.

환경변수: KIS_APP_KEY, KIS_APP_SECRET, KIS_MODE(real/paper)
"""
import os, time, threading, json, requests
from dotenv import load_dotenv

load_dotenv()

_KEY    = os.getenv("KIS_APP_KEY", "")
_SECRET = os.getenv("KIS_APP_SECRET", "")
_MODE   = os.getenv("KIS_MODE", "real")

BASE = "https://openapi.koreainvestment.com:9443"
_TR  = "FHKST01010100"  # 주식 현재가 시세 (real/paper 동일)

_cache: dict = {}
_token_lock = threading.Lock()  # 동시 토큰 발급 방지

# 토큰 파일 캐시 — 프로세스 재시작해도 재사용 (KIS는 하루 1회 발급 권장)
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".kis_token_cache.json")


def _load_token_file():
    """파일에서 토큰 로드 (프로세스 시작 시 1회)."""
    try:
        with open(_TOKEN_FILE, "r") as f:
            d = json.load(f)
        if d.get("exp", 0) > time.time() + 60:
            _cache["tok"] = d["tok"]
            _cache["exp"] = d["exp"]
    except Exception:
        pass


def _save_token_file():
    """발급한 토큰을 파일에 저장."""
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump({"tok": _cache["tok"], "exp": _cache["exp"]}, f)
    except Exception:
        pass


_load_token_file()  # 시작 시 파일 캐시 로드


def _token() -> str:
    now = time.time()
    if _cache.get("exp", 0) > now + 60:
        return _cache["tok"]
    with _token_lock:
        if _cache.get("exp", 0) > now + 60:
            return _cache["tok"]
        r = requests.post(f"{BASE}/oauth2/tokenP", json={
            "grant_type": "client_credentials",
            "appkey": _KEY,
            "appsecret": _SECRET,
        }, timeout=10)
        r.raise_for_status()
        d = r.json()
        _cache["tok"] = d["access_token"]
        _cache["exp"] = time.time() + d.get("expires_in", 86400) - 300
        _save_token_file()  # 파일에도 저장
        return _cache["tok"]


def get_price(code: str) -> dict:
    """종목 현재가 (정규장). {code, name, price, change_rate, change}"""
    r = requests.get(
        f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {_token()}",
            "appkey": _KEY,
            "appsecret": _SECRET,
            "tr_id": _TR,
            "custtype": "P",
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6)},
        timeout=5,
    )
    r.raise_for_status()
    o = r.json().get("output", {})
    return {
        "code": code,
        "name": o.get("hts_kor_isnm", ""),
        "price": int(o.get("stck_prpr", 0) or 0),
        "change_rate": float(o.get("prdy_ctrt", 0) or 0),
        "change": int(o.get("prdy_vrss", 0) or 0),
    }




def get_prices_batch(codes: list) -> dict:
    """여러 종목 현재가 (순차). {code: {..} | None}"""
    out = {}
    for c in codes:
        try:
            out[c] = get_price(c)
        except Exception:
            out[c] = None
    return out


def get_daily_bars(code: str, n: int = 20) -> list:
    """종목 최근 n일 종가 배열 (오름차순). KIS FHKST03010100."""
    import datetime as _dt
    today = _dt.date.today().strftime("%Y%m%d")
    start = (_dt.date.today() - _dt.timedelta(days=n * 2)).strftime("%Y%m%d")
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY,
                "appsecret": _SECRET,
                "tr_id": "FHKST03010100",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": start,
                "FID_INPUT_DATE_2": today,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("output2") or []
        closes = []
        for row in reversed(rows):  # output2는 최신→과거 순이므로 역순
            try:
                v = float(str(row.get("stck_clpr", 0) or 0).replace(",", ""))
                if v > 0:
                    closes.append(v)
            except Exception:
                pass
        return closes[-n:]
    except Exception:
        return []


def get_prices_batch_parallel(codes: list, workers: int = 10) -> dict:
    """여러 종목 현재가 병렬 조회 (J마켓 = NXT 포함 통합 실시간가)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = {c: None for c in codes}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(get_price, c): c for c in codes}
        for fut in as_completed(futures):
            c = futures[fut]
            try:
                out[c] = fut.result()
            except Exception:
                out[c] = None
    return out


def get_overseas_price(symbol: str, excd: str = "NYS") -> dict:
    """해외주식/지수 현재가. excd: NYS/NAS/AMS/TSE 등
    S&P500 ETF → SYMB=SPY EXCD=NYS
    나스닥100 ETF → SYMB=QQQ EXCD=NAS
    """
    try:
        r = requests.get(
            f"{BASE}/uapi/overseas-stock/v1/quotations/price",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "HHDFS00000300",
                "custtype": "P",
            },
            params={"AUTH": "", "EXCD": excd, "SYMB": symbol},
            timeout=8,
        )
        r.raise_for_status()
        o = r.json().get("output", {}) or {}
        return {
            "code": symbol,
            "name": o.get("rsym", symbol),
            "price": float(o.get("last", 0) or 0),
            "change_rate": float(o.get("rate", 0) or 0),
            "change": float(o.get("diff", 0) or 0),
        }
    except Exception:
        return {"code": symbol, "name": symbol, "price": 0, "change_rate": 0, "change": 0}


def get_overseas_minutebar(symbol: str, excd: str = "NYS", interval: int = 15) -> list:
    """해외주식 당일 분봉 종가 배열."""
    try:
        r = requests.get(
            f"{BASE}/uapi/overseas-stock/v1/quotations/inquire-time-itemchartprice",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "HHDFS76950200",
                "custtype": "P",
            },
            params={
                "AUTH": "", "EXCD": excd, "SYMB": symbol,
                "NMIN": str(interval), "PINC": "1", "NEXT": "", "NREC": "30",
                "FILL": "", "KEYB": "",
            },
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("output2") or []
        out = []
        for row in reversed(rows):
            try:
                v = float(row.get("clos", 0) or 0)
                if v > 0:
                    out.append(v)
            except Exception:
                pass
        return out
    except Exception:
        return []


def get_night_futures_price() -> dict:
    """코스피200 야간선물 현재가.
    TR_ID: FHKIF03010100 (국내선물 현재가)
    종목코드: 101W9 → 현재 최근월물 자동 조회
    """
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-futu/v1/quotations/inquire-price",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHKIF03010100",
                "custtype": "P",
            },
            params={"FID_COND_MRKT_DIV_CODE": "N", "FID_INPUT_ISCD": "101W9"},
            timeout=8,
        )
        r.raise_for_status()
        o = r.json().get("output", {}) or {}
        return {
            "code": "101W9",
            "name": "코스피야간선물",
            "price": float(o.get("futr_prpr", 0) or 0),
            "change_rate": float(o.get("prdy_ctrt", 0) or 0),
            "change": float(o.get("prdy_vrss", 0) or 0),
        }
    except Exception:
        return {"code": "101W9", "name": "코스피야간선물", "price": 0, "change_rate": 0, "change": 0}


def get_usdkrw() -> dict:
    """원달러 환율 현재가. KIS FOREX 시도, 실패시 0."""
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHKEF00010200",
                "custtype": "P",
            },
            params={"FID_COND_MRKT_DIV_CODE": "X", "FID_INPUT_ISCD": "FX@KRW"},
            timeout=8,
        )
        r.raise_for_status()
        o = r.json().get("output", {}) or {}
        price = float(o.get("stck_prpr", 0) or o.get("ovrs_nmix_prpr", 0) or 0)
        rate  = float(o.get("prdy_ctrt", 0) or 0)
        return {"price": price, "change_rate": rate}
    except Exception:
        return {"price": 0, "change_rate": 0}


def get_crude_oil() -> dict:
    """국제유가 WTI 프록시 (USO ETF, NYSE)."""
    try:
        d = get_overseas_price("USO", "NYS")
        return {"price": d["price"], "change_rate": d["change_rate"]}
    except Exception:
        return {"price": 0, "change_rate": 0}


def get_inquiry_rank(n: int = 15) -> list:
    """실시간 거래대금 상위 종목 (조회순위 프록시).
    TR_ID: FHPST01710000 (거래대금 순위)
    """
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/volume-rank",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHPST01710000",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "", "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "", "FID_INPUT_DATE_1": "",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("output", []) or []
        result = []
        for row in rows:  # n은 호출측에서 필터 후 제한 (KIS는 50개 최대 반환)
            result.append({
                "rank":        len(result) + 1,
                "code":        row.get("mksc_shrn_iscd", ""),
                "name":        row.get("hts_kor_isnm", ""),
                "price":       int(row.get("stck_prpr", 0) or 0),
                "change_rate": float(row.get("prdy_ctrt", 0) or 0),
            })
        return result
    except Exception:
        return []


def get_us_market_stocks() -> list:
    """미국 주요 종목/ETF 현재가 리스트 (병렬)."""
    symbols = [
        ("SPY", "NYS", "S&P500"),
        ("QQQ", "NAS", "나스닥"),
        ("NVDA", "NAS", "엔비디아"),
        ("AAPL", "NAS", "애플"),
        ("TSLA", "NAS", "테슬라"),
        ("TSM",  "NYS", "TSMC"),
        ("SMH",  "NYS", "반도체ETF"),
        ("META", "NAS", "메타"),
    ]
    from concurrent.futures import ThreadPoolExecutor
    results = [None] * len(symbols)
    def fetch(idx, sym, excd, label):
        d = get_overseas_price(sym, excd)
        results[idx] = {"symbol": sym, "label": label,
                        "price": d["price"], "change_rate": d["change_rate"]}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch, i, s, e, l) for i, (s, e, l) in enumerate(symbols)]
        for f in futs:
            try: f.result()
            except Exception: pass
    return [r for r in results if r]


def get_night_futures_minutebar(interval: int = 15) -> list:
    """코스피200 야간선물 분봉."""
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-futu/v1/quotations/inquire-time-itemchartprice",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHKIF03010200",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "N",
                "FID_INPUT_ISCD": "101W9",
                "FID_INPUT_HOUR_1": "235900",
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_HOUR_CLS_CODE": str(interval),
            },
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("output2") or []
        out = []
        for row in reversed(rows):
            try:
                v = float(row.get("futr_prpr", 0) or 0)
                if v > 0:
                    out.append(v)
            except Exception:
                pass
        return out
    except Exception:
        return []


def get_minutebar(code: str, interval: int = 15) -> list:
    """종목/ETF 당일 분봉 종가 배열 (오름차순, 최대 30봉).
    interval: 1/5/10/15/30/60
    FID_INPUT_HOUR_1 = 현재 시간 → 미래 빈 봉 제외
    """
    import datetime as _dt
    now_str = _dt.datetime.now().strftime("%H%M%S")
    r = requests.get(
        f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {_token()}",
            "appkey": _KEY, "appsecret": _SECRET,
            "tr_id": "FHKST03010200",
            "custtype": "P",
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_ETC_CLS_CODE": "",
            "FID_INPUT_ISCD": code.zfill(6),
            "FID_INPUT_HOUR_1": now_str,
            "FID_PW_DATA_INCU_YN": "N",
            "FID_HOUR_CLS_CODE": str(interval),
        },
        timeout=8,
    )
    r.raise_for_status()
    rows = r.json().get("output2") or []
    today = _dt.datetime.now().strftime("%Y%m%d")
    out = []
    for row in reversed(rows):  # API는 역순 반환 → 뒤집어서 오름차순
        if row.get("stck_bsop_date", today) != today:
            continue  # 전날 데이터 제외
        if row.get("stck_cntg_hour", "090000") < "090000":
            continue  # 정규장(9시) 이전 시간외 데이터 제외
        try:
            v = float(row.get("stck_prpr", 0) or 0)
            if v > 0:
                out.append(v)
        except Exception:
            pass
    return out


def get_index_minutebar(index_code: str, interval: int = 15) -> list:
    """코스피(0001)/코스닥(1001) 지수 분봉 종가 배열 (오름차순).
    KIS 지수 분봉 API는 별도 구독 필요 → KODEX200/코스닥150 ETF 분봉으로 대체.
    추세(방향) 동일, 절대값만 다름.
    """
    # 코스피 → KODEX 200 (069500), 코스닥 → KODEX 코스닥150 (229200)
    proxy = "069500" if index_code == "0001" else "229200"
    return get_minutebar(proxy, interval)


def get_market_investor(market_div: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 투자자별 오늘 누적 순매수 (백만원).
    Returns {외인, 기관, 개인, ts}
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHKST01010900",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": market_div,
                "FID_INPUT_ISCD": "0001" if market_div == "J" else "Q001",
            },
            timeout=8,
        )
        r.raise_for_status()
        o = r.json().get("output", {}) or {}
        return {
            "외인": int(o.get("frgn_ntby_tr_pbmn", 0) or 0),
            "기관": int(o.get("orgn_ntby_tr_pbmn", 0) or 0),
            "개인": int(o.get("prsn_ntby_tr_pbmn", 0) or 0),
            "ts": ts,
        }
    except Exception:
        return {"외인": 0, "기관": 0, "개인": 0, "ts": ts}


def get_program_trade(market_div: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 프로그램매매 순매수 (백만원).
    TR_ID: FHPPG04650200
    Returns {차익, 비차익, 합계, ts}
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/program-trade-by-stock",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHPPG04650200",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": market_div,
                "FID_INPUT_ISCD": "0001" if market_div == "J" else "Q001",
                "FID_INPUT_DATE_1": "",
            },
            timeout=8,
        )
        r.raise_for_status()
        o = r.json().get("output1", {}) or {}
        arb   = int(o.get("pgtr_ntby_tr_pbmn", 0) or 0)    # 차익
        noarb = int(o.get("napr_ntby_tr_pbmn", 0) or 0)    # 비차익
        return {"차익": arb, "비차익": noarb, "합계": arb + noarb, "ts": ts}
    except Exception:
        return {"차익": 0, "비차익": 0, "합계": 0, "ts": ts}


def get_index_price(index_code: str) -> dict:
    """코스피(0001)/코스닥(1001) 지수 현재가.
    TR_ID: FHPUP02100000 (업종/지수 현재가)
    """
    r = requests.get(
        f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-index-price",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {_token()}",
            "appkey": _KEY,
            "appsecret": _SECRET,
            "tr_id": "FHPUP02100000",
            "custtype": "P",
        },
        params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": index_code},
        timeout=5,
    )
    r.raise_for_status()
    o = r.json().get("output", {})
    return {
        "code": index_code,
        "name": o.get("hts_kor_isnm", ""),
        "price": float(o.get("bstp_nmix_prpr", 0) or 0),
        "change_rate": float(o.get("bstp_nmix_prdy_ctrt", 0) or 0),
        "change": float(o.get("bstp_nmix_prdy_vrss", 0) or 0),
    }
