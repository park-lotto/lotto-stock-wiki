"""한국투자증권 API — 토큰 발급 + 현재가 조회.

환경변수: KIS_APP_KEY, KIS_APP_SECRET, KIS_MODE(real/paper)
"""
import os, time, requests
from dotenv import load_dotenv

load_dotenv()

_KEY    = os.getenv("KIS_APP_KEY", "")
_SECRET = os.getenv("KIS_APP_SECRET", "")
_MODE   = os.getenv("KIS_MODE", "real")

BASE = "https://openapi.koreainvestment.com:9443"
_TR  = "FHKST01010100"  # 주식 현재가 시세 (real/paper 동일)

_cache: dict = {}


def _token() -> str:
    now = time.time()
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
    _cache["exp"] = now + d.get("expires_in", 86400) - 300
    return _cache["tok"]


def get_price(code: str) -> dict:
    """종목 현재가. {code, name, price, change_rate, change}"""
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


def get_prices_batch_parallel(codes: list, workers: int = 10) -> dict:
    """여러 종목 현재가 (병렬). {code: {..} | None}"""
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
