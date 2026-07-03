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

# ── 초당 요청 속도 제한 ──────────────────────────────────────
# KIS 개인계정은 초당 약 20건 제한. 초과 시 EGW00201("초당 거래건수를 초과") 500.
# 히트맵은 수백 종목을 동시에 조회하므로 전역 게이트로 ~15건/초로 페이싱한다.
_RATE_MAX_PER_SEC = 15
_MIN_INTERVAL = 1.0 / _RATE_MAX_PER_SEC
_rate_lock = threading.Lock()
_next_slot = [0.0]


def _rate_gate():
    """호출을 전역적으로 ~15건/초로 분산. 슬롯 예약 후 락 밖에서 대기."""
    with _rate_lock:
        now = time.time()
        scheduled = max(now, _next_slot[0] + _MIN_INTERVAL)
        _next_slot[0] = scheduled
    wait = scheduled - now
    if wait > 0:
        time.sleep(wait)

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
            _cache["issued_at"] = d.get("issued_at", 0)
    except Exception:
        pass


def _save_token_file():
    """발급한 토큰을 파일에 저장 (issued_at 포함 → 같은 PC 다른 프로세스의 발급 폭주 방지)."""
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump({"tok": _cache["tok"], "exp": _cache["exp"],
                       "issued_at": _cache.get("issued_at", 0)}, f)
    except Exception:
        pass


_load_token_file()  # 시작 시 파일 캐시 로드


def _token(force: bool = False) -> str:
    """KIS 접근토큰 반환. force=True면 서버가 토큰을 무효화(EGW00123)했을 때 강제 재발급.

    여러 PC·프로세스가 같은 앱키를 공유하면 한 곳에서 새 토큰을 받는 순간
    나머지 토큰이 서버 측에서 죽는다. 로컬 exp가 미래여도 죽을 수 있으므로,
    호출이 EGW00123으로 실패하면 force=True로 다시 발급받아 복구한다.
    """
    now = time.time()
    if not force and _cache.get("exp", 0) > now + 60:
        return _cache["tok"]
    with _token_lock:
        now = time.time()
        if not force and _cache.get("exp", 0) > now + 60:
            return _cache["tok"]
        if force:
            # 같은 PC의 다른 프로세스가 방금 재발급했을 수 있으니 파일을 다시 읽는다
            _load_token_file()
            # 60초 내 발급분이면 그걸 신뢰 — KIS는 1분당 1회만 발급(초과 시 403) → 재발급 무의미
            if _cache.get("tok") and now - _cache.get("issued_at", 0) < 60:
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
        _cache["issued_at"] = time.time()
        _save_token_file()  # 파일에도 저장
        return _cache["tok"]


# 토큰 재발급이 필요한 KIS 인증 오류 코드군
#   EGW00121 = 유효하지 않은 토큰 / EGW00122 = 토큰 누락 / EGW00123 = 기간 만료 토큰
_TOKEN_ERR_CODES = {"EGW00121", "EGW00122", "EGW00123"}
_RATELIMIT_CODE = "EGW00201"   # 초당 거래건수 초과


def _resp_msg_cd(resp) -> str:
    """KIS 응답 본문의 msg_cd 추출. HTTP 500이어도 본문으로 확인. 없으면 ""."""
    try:
        return resp.json().get("msg_cd", "") or ""
    except Exception:
        return ""


def _is_expired_token(resp) -> bool:
    """KIS 응답이 토큰 무효/만료 오류인지 판별."""
    return _resp_msg_cd(resp) in _TOKEN_ERR_CODES


def _authed_get(url: str, headers: dict, params: dict, timeout: float):
    """KIS GET 공통 래퍼. headers에 authorization은 넣지 말 것(여기서 주입).

    - 전역 레이트 게이트로 ~15건/초 페이싱
    - 토큰 무효/만료(EGW0012x) → 강제 재발급 후 재시도
    - 초당 한도 초과(EGW00201) → 짧은 백오프 후 재시도(토큰 재발급 아님)
    """
    h = dict(headers)
    for attempt in range(3):
        _rate_gate()
        h["authorization"] = f"Bearer {_token()}"
        r = requests.get(url, headers=h, params=params, timeout=timeout)
        msg = _resp_msg_cd(r)
        if msg in _TOKEN_ERR_CODES:
            # 토큰 무효/만료 → 강제 재발급 후 1회 재시도. 재발급 실패 시 원응답 반환(크래시 방지).
            try:
                _rate_gate()
                h["authorization"] = f"Bearer {_token(force=True)}"
                return requests.get(url, headers=h, params=params, timeout=timeout)
            except Exception:
                return r
        if msg == _RATELIMIT_CODE and attempt < 2:
            time.sleep(0.3 * (attempt + 1))   # 0.3s, 0.6s 백오프
            continue
        return r
    return r


def get_price(code: str) -> dict:
    """종목 현재가 (KRX+NXT 통합 UN → 장외 NXT 시세도 반영). {code, name, price, change_rate, change}"""
    r = _authed_get(
        f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-price",
        headers={
            "content-type": "application/json; charset=utf-8",
            "appkey": _KEY,
            "appsecret": _SECRET,
            "tr_id": _TR,
            "custtype": "P",
        },
        params={"FID_COND_MRKT_DIV_CODE": "UN", "FID_INPUT_ISCD": code.zfill(6)},
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
        r = _authed_get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers={
                "Content-Type": "application/json; charset=utf-8",
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


def get_daily_ohlc(code: str, tf: str = "D", n: int = 500) -> list:
    """일/주/월 OHLCV 캔들 (KIS FHKST03010100, 키움 부재 서버 폴백용).
    tf=D/W/M. 반환(과거→최신): [{"time":"YYYY-MM-DD", open, high, low, close, value}]
    KIS 일봉차트 API는 1콜 ~100봉 → 과거로 페이지네이션해 n봉까지 수집.
    """
    import datetime as _dt
    period = tf if tf in ("D", "W", "M") else "D"
    code = code.zfill(6)
    win = {"D": 150, "W": 900, "M": 4000}.get(period, 150)  # 1콜당 창(≈100봉)

    def _f(row, k):
        try:
            return float(str(row.get(k, 0) or 0).replace(",", ""))
        except Exception:
            return 0.0

    def _batch(date2: str) -> list:
        d1 = (_dt.datetime.strptime(date2, "%Y%m%d").date() - _dt.timedelta(days=win)).strftime("%Y%m%d")
        try:
            r = _authed_get(
                f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                headers={"Content-Type": "application/json; charset=utf-8",
                         "appkey": _KEY, "appsecret": _SECRET,
                         "tr_id": "FHKST03010100", "custtype": "P"},
                params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                        "FID_INPUT_DATE_1": d1, "FID_INPUT_DATE_2": date2,
                        "FID_PERIOD_DIV_CODE": period, "FID_ORG_ADJ_PRC": "0"},
                timeout=10,
            )
            r.raise_for_status()
            return r.json().get("output2") or []
        except Exception:
            return []

    seen, acc = set(), {}
    date2 = _dt.date.today().strftime("%Y%m%d")
    for _ in range(8):
        rows = _batch(date2)
        if not rows:
            break
        oldest = None
        for row in rows:
            d = str(row.get("stck_bsop_date", ""))
            if len(d) != 8 or d in seen:
                continue
            seen.add(d)
            c = _f(row, "stck_clpr")
            if c <= 0:
                continue
            acc[d] = {"time": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                      "open": _f(row, "stck_oprc") or c, "high": _f(row, "stck_hgpr") or c,
                      "low": _f(row, "stck_lwpr") or c, "close": c,
                      "value": int(_f(row, "acml_vol"))}
            if oldest is None or d < oldest:
                oldest = d
        if len(acc) >= n or not oldest:
            break
        date2 = (_dt.datetime.strptime(oldest, "%Y%m%d").date() - _dt.timedelta(days=1)).strftime("%Y%m%d")
    out = [acc[d] for d in sorted(acc)]
    return out[-n:]


_MULTI_TR = "FHKST11300006"  # 관심종목(멀티종목) 시세조회 — 1콜당 최대 30종목


def get_prices_multi(codes: list, workers: int = 6) -> dict:
    """여러 종목 현재가를 KIS 멀티시세 API로 일괄 조회 (1콜당 30종목).

    개별 get_price(583콜)는 초당 한도 때문에 ~30초 걸리지만,
    멀티 API는 583종목도 ~20콜이라 ~2초. 이게 근본 해결.
    반환: {code: {"code","name","price","change_rate","change"}}  (없으면 None)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = {c: None for c in codes}
    code_map = {c.zfill(6): c for c in codes}        # 6자리 → 원본 코드
    chunks = [codes[i:i + 30] for i in range(0, len(codes), 30)]

    def fetch_chunk(chunk):
        params = {}
        for i, c in enumerate(chunk, 1):
            params[f"FID_COND_MRKT_DIV_CODE_{i}"] = "UN"   # KRX+NXT 통합 (장외 NXT 시세 반영)
            params[f"FID_INPUT_ISCD_{i}"] = c.zfill(6)
        r = _authed_get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/intstock-multprice",
            headers={"content-type": "application/json; charset=utf-8",
                     "appkey": _KEY, "appsecret": _SECRET,
                     "tr_id": _MULTI_TR, "custtype": "P"},
            params=params, timeout=8)
        r.raise_for_status()
        res = {}
        for row in (r.json().get("output") or []):
            code6 = row.get("inter_shrn_iscd", "")
            if not code6:
                continue
            try:    price = int(float(row.get("inter2_prpr", 0) or 0))
            except Exception: price = 0
            try:    rate = float(row.get("prdy_ctrt", 0) or 0)
            except Exception: rate = 0.0
            try:    chg = int(float(row.get("inter2_prdy_vrss", 0) or 0))
            except Exception: chg = 0
            res[code_map.get(code6, code6)] = {
                "code": code6, "name": row.get("inter_kor_isnm", ""),
                "price": price, "change_rate": rate, "change": chg}
        return res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_chunk, ch) for ch in chunks]
        for fut in as_completed(futs):
            try:
                for k, v in fut.result().items():
                    out[k] = v
            except Exception:
                pass
    return out


def get_prices_batch_parallel(codes: list, workers: int = 6) -> dict:
    """여러 종목 현재가 일괄 조회. KIS 멀티시세 API 사용(근본적으로 빠름)."""
    return get_prices_multi(codes, workers=workers)


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


def get_minutebar(code: str, interval: int = 15, with_time: bool = False) -> list:
    """종목/ETF 당일 분봉 종가 배열 (오름차순, 최대 30봉).
    interval: 1/5/10/15/30/60
    FID_INPUT_HOUR_1 = 현재 시간 → 미래 빈 봉 제외
    with_time=True면 [{"t":"HHMMSS","price":...}] 형태로 실제 체결시각 포함 반환
    (KIS가 요청 interval을 그대로 안 지키고 봉 개수가 들쭉날쭉할 때가 있어,
     프론트에서 09:00 기준 등간격으로 추정하면 시간축이 틀어짐 — 실제 시각 사용 권장)
    """
    import datetime as _dt
    now_str = _dt.datetime.now().strftime("%H%M%S")
    if now_str > "153000":
        now_str = "153000"   # 장 종료 후엔 15:30 마감 기준 봉 조회 (시간외 단일가 꼬리 방지)
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
        _ch = row.get("stck_cntg_hour", "090000")
        if _ch < "090000":
            continue  # 정규장(9시) 이전 시간외 데이터 제외
        if _ch > "153000":
            continue  # 장 종료(15:30) 이후 동시호가·시간외 단일가 제외 → 종가 모양 유지
        try:
            v = float(row.get("stck_prpr", 0) or 0)
            if v > 0:
                out.append({"t": _ch, "price": v} if with_time else v)
        except Exception:
            pass
    return out


def _minutebar_page(code: str, end_hhmmss: str, mdiv: str = "J") -> list:
    """분봉 1페이지(최근 30개, end_hhmmss 이전으로) 원시 rows 반환. mdiv='UN'이면 KRX+NXT 통합."""
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
            "FID_COND_MRKT_DIV_CODE": mdiv,
            "FID_ETC_CLS_CODE": "",
            "FID_INPUT_ISCD": code.zfill(6),
            "FID_INPUT_HOUR_1": end_hhmmss,
            "FID_PW_DATA_INCU_YN": "N",
            "FID_HOUR_CLS_CODE": "1",
        },
        timeout=8,
    )
    r.raise_for_status()
    return r.json().get("output2") or []


def get_intraday_series(code: str, resample_min: int = 15, max_pages: int = 15) -> list:
    """당일 09:00~현재 분봉 시계열을 페이지네이션으로 전부 수집 후 resample_min 간격으로 리샘플.
    KIS 분봉 API는 1콜당 30개(1분봉)만 주므로, 가장 오래된 시각으로 되짚어가며 09:00까지 수집한다.
    반환: [{"t":"HHMMSS","price":...}] (오름차순, 각 버킷의 마지막=종가).
    """
    import datetime as _dt
    now_str = _dt.datetime.now().strftime("%H%M%S")
    if now_str > "153000":
        now_str = "153000"
    collected = {}   # "HHMMSS" -> price (중복 제거)
    cursor = now_str
    prev_oldest = None
    for _ in range(max_pages):
        try:
            rows = _minutebar_page(code, cursor)
        except Exception:
            break
        if not rows:
            break
        oldest = None
        for row in rows:
            ch = row.get("stck_cntg_hour", "")
            if not ch or ch < "090000" or ch > "153000":
                continue
            try:
                v = float(row.get("stck_prpr", 0) or 0)
                if v > 0:
                    collected[ch] = v
            except Exception:
                pass
            if oldest is None or ch < oldest:
                oldest = ch
        # 09:00 도달했거나 더 이상 안 내려가면 종료 (무한루프 방지)
        if oldest is None or oldest <= "090000" or oldest == prev_oldest:
            break
        prev_oldest = oldest
        cursor = oldest
    # 오름차순 정렬 후 resample_min 버킷으로 리샘플 (버킷 마지막 체결가=종가)
    buckets = {}
    for ch in sorted(collected):
        mins = int(ch[:2]) * 60 + int(ch[2:4])
        bucket = (mins // resample_min) * resample_min
        buckets[bucket] = collected[ch]
    out = []
    for b in sorted(buckets):
        out.append({"t": f"{b // 60:02d}{b % 60:02d}00", "price": buckets[b]})
    return out


def get_minute_bars_ohlc(code: str, tf: str = "5", mdiv: str = "UN", max_pages: int = 16) -> list:
    """분봉 OHLCV (mdiv='UN' → KRX+NXT 통합 → 장외 NXT 시간외 봉 포함).
    KIS 분봉 API는 1콜당 30개(1분봉)만 주고 tf 간격도 안 지킴 → 09:00까지 페이지네이션으로
    1분봉 전부 수집한 뒤 tf분(5/10/15/30/60)으로 OHLC 리샘플. 그래서 분봉 개수가 하루치로 충분.
    반환(과거→최신): [{"time"(epoch초·KST-as-UTC), open, high, low, close, value}]
    """
    import datetime as _dt, calendar
    now = _dt.datetime.now()
    today = now.strftime("%Y%m%d")
    try:
        tf_min = int(tf) if str(tf).isdigit() and int(tf) > 0 else 5
    except Exception:
        tf_min = 5

    def _f(row, k):
        try:
            return float(str(row.get(k, 0) or 0).replace(",", ""))
        except Exception:
            return 0.0

    # ── 1분봉 페이지네이션 수집 (now → 09:00) ──
    raw = {}   # "HHMM" -> {o,h,l,c,v}
    cursor = now.strftime("%H%M%S")
    prev_oldest = None
    for _ in range(max_pages):
        try:
            rows = _minutebar_page(code, cursor, mdiv=mdiv)
        except Exception:
            break
        if not rows:
            break
        oldest = None
        for row in rows:
            if row.get("stck_bsop_date", today) != today:
                continue
            t = str(row.get("stck_cntg_hour", ""))
            if len(t) < 6:
                continue
            c = _f(row, "stck_prpr")
            if c <= 0:
                continue
            raw[t[:4]] = {"o": _f(row, "stck_oprc") or c, "h": _f(row, "stck_hgpr") or c,
                          "l": _f(row, "stck_lwpr") or c, "c": c, "v": int(_f(row, "cntg_vol"))}
            if oldest is None or t < oldest:
                oldest = t
        if oldest is None or oldest[:4] <= "0900" or oldest == prev_oldest:
            break
        prev_oldest = oldest
        cursor = oldest

    # ── 1분봉 → tf분 OHLC 리샘플 ──
    buckets = {}
    for hm in sorted(raw):
        mins = int(hm[:2]) * 60 + int(hm[2:4])
        bk = (mins // tf_min) * tf_min
        b = raw[hm]
        if bk not in buckets:
            buckets[bk] = {"open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "value": b["v"]}
        else:
            agg = buckets[bk]
            agg["high"] = max(agg["high"], b["h"])
            agg["low"] = min(agg["low"], b["l"])
            agg["close"] = b["c"]
            agg["value"] += b["v"]
    out = []
    for bk in sorted(buckets):
        epoch = calendar.timegm((int(today[:4]), int(today[4:6]), int(today[6:8]),
                                 bk // 60, bk % 60, 0, 0, 0, 0))
        agg = buckets[bk]
        out.append({"time": epoch, "open": agg["open"], "high": agg["high"],
                    "low": agg["low"], "close": agg["close"], "value": agg["value"]})
    return out


def get_index_minutebar(index_code: str, interval: int = 15) -> list:
    """코스피(0001)/코스닥(1001) 지수 분봉 [{"t":"HHMMSS","price":...}] (오늘 09:00~현재, 15분 리샘플).
    KIS 지수 분봉 API는 별도 구독 필요 → KODEX200/코스닥150 ETF 분봉으로 대체.
    1순위=네이버 fchart 단일호출(오늘치 안정적). KIS 페이지네이션(15콜)은 중간 순간실패로
    최근 3개만 오는 일이 잦아 그래프가 짧아졌다 복구됐다 하던 문제 → 단일호출로 근본 차단.
    """
    # 코스피 → KODEX 200 (069500), 코스닥 → KODEX 코스닥150 (229200)
    proxy = "069500" if index_code == "0001" else "229200"
    try:
        import naver_api as _nv, time as _t, datetime as _dt
        allc = _nv.minute_candles(proxy, interval, count=500)  # fchart 단일호출(오늘+며칠)
        today = _dt.datetime.now().strftime("%Y%m%d")
        out = []
        for x in allc:
            g = _t.gmtime(x["time"])   # epoch=KST벽시계-as-UTC로 생성됨 → gmtime이 KST 복원
            if f"{g.tm_year}{g.tm_mon:02d}{g.tm_mday:02d}" == today:
                out.append({"t": f"{g.tm_hour:02d}{g.tm_min:02d}00", "price": x["close"]})
        if len(out) >= 2:
            return out
    except Exception:
        pass
    # 폴백: KIS 페이지네이션
    return get_intraday_series(proxy, resample_min=interval)


def get_market_investor(market_div: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 투자자별 오늘 누적 순매수 (백만원).
    TR_ID: FHPTJ04040000 (시장별 투자자매매동향-일별). output[0]=오늘.
    (구버전 FHKST01010900은 종목전용 TR이라 지수코드 입력시 빈값만 나오던 버그 수정)
    Returns {외인, 기관, 개인, ts}
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    iscd = "0001" if market_div == "J" else "1001"
    iscd1 = "KSP" if market_div == "J" else "KSQ"
    today = _dt.datetime.now().strftime("%Y%m%d")
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHPTJ04040000",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": iscd,
                "FID_INPUT_DATE_1": today,
                "FID_INPUT_ISCD_1": iscd1,
                "FID_INPUT_DATE_2": today,
                "FID_INPUT_ISCD_2": iscd,
            },
            timeout=8,
        )
        r.raise_for_status()
        out = r.json().get("output", []) or []
        o = out[0] if out else {}
        return {
            "외인": int(float(o.get("frgn_ntby_tr_pbmn", 0) or 0)),
            "기관": int(float(o.get("orgn_ntby_tr_pbmn", 0) or 0)),
            "개인": int(float(o.get("prsn_ntby_tr_pbmn", 0) or 0)),
            "ts": ts,
        }
    except Exception:
        return {"외인": 0, "기관": 0, "개인": 0, "ts": ts}


def get_program_trade(market_div: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 프로그램매매 순매수 (백만원).
    TR_ID: FHPPG04600101 (프로그램매매 종합현황-시간, 최근 30분 시계열). output[0]=최신.
    (구버전 FHPPG04650200은 종목전용 TR이라 지수코드 입력시 빈값만 나오던 버그 수정)
    Returns {차익, 비차익, 합계, ts}
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    mkt = "K" if market_div == "J" else "Q"
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/comp-program-trade-today",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHPPG04600101",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_MRKT_CLS_CODE": mkt,
                "FID_SCTN_CLS_CODE": "",
                "FID_INPUT_ISCD": "",
                "FID_COND_MRKT_DIV_CODE1": "",
                "FID_INPUT_HOUR_1": "",
            },
            timeout=8,
        )
        r.raise_for_status()
        out = r.json().get("output", []) or []
        o = out[0] if out else {}
        arb   = int(float(o.get("arbt_smtn_ntby_tr_pbmn", 0) or 0))    # 차익
        noarb = int(float(o.get("nabt_smtn_ntby_tr_pbmn", 0) or 0))    # 비차익
        return {"차익": arb, "비차익": noarb, "합계": arb + noarb, "ts": ts}
    except Exception:
        return {"차익": 0, "비차익": 0, "합계": 0, "ts": ts}


def get_program_trade_series(market_div: str = "J") -> list:
    """코스피(J)/코스닥(Q) 프로그램매매 최근 30분 시계열 (한 번 호출로 즉시 그래프용 데이터 확보).
    TR_ID: FHPPG04600101 (comp-program-trade-today). API가 최신순으로 주므로 오래된순으로 뒤집어 반환.
    Returns [{"t":"094300","차익":...,"비차익":...,"합계":...}, ...] (과거→최신 순)
    """
    mkt = "K" if market_div == "J" else "Q"
    try:
        r = requests.get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/comp-program-trade-today",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {_token()}",
                "appkey": _KEY, "appsecret": _SECRET,
                "tr_id": "FHPPG04600101",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_MRKT_CLS_CODE": mkt,
                "FID_SCTN_CLS_CODE": "",
                "FID_INPUT_ISCD": "",
                "FID_COND_MRKT_DIV_CODE1": "",
                "FID_INPUT_HOUR_1": "",
            },
            timeout=8,
        )
        r.raise_for_status()
        out = r.json().get("output", []) or []
        result = []
        for o in reversed(out):
            arb   = int(float(o.get("arbt_smtn_ntby_tr_pbmn", 0) or 0))
            noarb = int(float(o.get("nabt_smtn_ntby_tr_pbmn", 0) or 0))
            result.append({"t": o.get("bsop_hour", ""), "차익": arb, "비차익": noarb, "합계": arb + noarb})
        return result
    except Exception:
        return []


def get_stock_supply(code: str) -> dict:
    """종목별 잠정수급(외인/기관/개인 순매수대금 + 프로그램 순매수대금).
    kiwoom_api.get_stock_supply와 동일 반환 형태 — 서버에 키움 키 미등록이라
    kiwoom 실패 시 이걸로 폴백(2026-07-03).
    TR_ID: FHKST01010900(종목 투자자매매동향) + FHPPG04650200(종목 프로그램매매,
    market_investor/program_trade가 쓰는 시장전용 TR과는 다른 종목전용 TR). output[0]=오늘.
    Returns {"외인","기관","개인","프로그램","ts"} — 실패 항목은 0.
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    today = _dt.datetime.now().strftime("%Y%m%d")
    out = {"외인": 0, "기관": 0, "개인": 0, "프로그램": 0, "ts": ts}

    try:
        r = _authed_get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-investor",
            headers={"content-type": "application/json; charset=utf-8",
                     "appkey": _KEY, "appsecret": _SECRET,
                     "tr_id": "FHKST01010900", "custtype": "P"},
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6)},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("output", []) or []
        if rows:
            o = rows[0]
            out["외인"] = int(float(o.get("frgn_ntby_tr_pbmn", 0) or 0))
            out["기관"] = int(float(o.get("orgn_ntby_tr_pbmn", 0) or 0))
            out["개인"] = int(float(o.get("prsn_ntby_tr_pbmn", 0) or 0))
    except Exception:
        pass

    try:
        r = _authed_get(
            f"{BASE}/uapi/domestic-stock/v1/quotations/program-trade-by-stock",
            headers={"content-type": "application/json; charset=utf-8",
                     "appkey": _KEY, "appsecret": _SECRET,
                     "tr_id": "FHPPG04650200", "custtype": "P"},
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code.zfill(6),
                    "FID_INPUT_DATE_1": today},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("output", []) or []
        if rows:
            # 이 TR의 pbmn은 원단위 그대로 옴(투자자매매동향 TR은 이미 백만원 단위) → 환산
            out["프로그램"] = int(float(rows[0].get("whol_smtn_ntby_tr_pbmn", 0) or 0) / 1_000_000)
    except Exception:
        pass

    return out


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
