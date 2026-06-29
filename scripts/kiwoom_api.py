"""키움 REST API 래퍼 — 지수 분봉 + 투자자 순매수.

환경변수: KIWOOM_APP_KEY, KIWOOM_APP_SECRET
베이스URL: https://api.kiwoom.com
"""
import os, time, json, threading, requests
from dotenv import load_dotenv

load_dotenv()

_KEY    = os.getenv("KIWOOM_APP_KEY", "")
_SECRET = os.getenv("KIWOOM_APP_SECRET", "")
BASE    = "https://api.kiwoom.com"

_cache: dict = {}
_lock = threading.Lock()
_TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".kiwoom_token_cache.json")


def _load_token_file():
    try:
        with open(_TOKEN_FILE) as f:
            d = json.load(f)
        if d.get("exp", 0) > time.time() + 60:
            _cache["tok"] = d["tok"]
            _cache["exp"] = d["exp"]
    except Exception:
        pass


def _save_token_file():
    try:
        with open(_TOKEN_FILE, "w") as f:
            json.dump({"tok": _cache["tok"], "exp": _cache["exp"]}, f)
    except Exception:
        pass


_load_token_file()


def _token() -> str:
    now = time.time()
    if _cache.get("exp", 0) > now + 60:
        return _cache["tok"]
    with _lock:
        if _cache.get("exp", 0) > now + 60:
            return _cache["tok"]
        r = requests.post(
            f"{BASE}/oauth2/token",
            headers={"Content-Type": "application/json;charset=UTF-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": _KEY,
                "secretkey": _SECRET,
            },
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        _cache["tok"] = d["token"]
        _cache["exp"] = time.time() + int(d.get("expires_in", 86400)) - 300
        _save_token_file()
        return _cache["tok"]


def _hdrs(extra: dict = None) -> dict:
    h = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {_token()}",
        "appkey": _KEY,
    }
    if extra:
        h.update(extra)
    return h


def get_index_minutebar(index_code: str = "0001", interval: int = 15) -> list:
    """코스피(0001)/코스닥(1001) 지수 분봉 종가 배열 (오름차순).
    API ID: ka20005 — 업종분봉조회요청
    inds_cd: 001=코스피종합, 101=코스닥종합
    """
    inds_cd = "001" if index_code == "0001" else "101"
    try:
        r = requests.post(
            f"{BASE}/api/dostk/chart",
            headers={**_hdrs(), "api-id": "ka20005", "cont-yn": "N", "next-key": ""},
            json={"inds_cd": inds_cd, "tic_scope": str(interval)},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("inds_min_pole_qry", []) or []
        out = []
        for row in reversed(rows):
            try:
                v = float(str(row.get("cur_prc", 0) or 0).replace(",", "").lstrip("-"))
                if v > 0:
                    out.append(v)
            except Exception:
                pass
        return out[-30:]
    except Exception:
        return []


def get_program_trade_series(market: str = "J") -> list:
    """코스피(J)/코스닥(Q) 프로그램매매 시간대별 배열 (ka90005, 최근→과거 순).
    반환: [{"t":"090500","차익":100,"비차익":-200,"합계":-100}, ...]
    """
    mrkt_tp = "P00101" if market == "J" else "P10102"
    import datetime as _dt
    date = _dt.datetime.now().strftime("%Y%m%d")

    def _parse(v):
        s = str(v).replace(",", "").replace(" ", "")
        if s.startswith("--"):
            return -int(float(s[2:]))
        s = s.lstrip("+")
        try: return int(float(s))
        except: return 0

    try:
        r = requests.post(
            f"{BASE}/api/dostk/mrkcond",
            headers={**_hdrs(), "api-id": "ka90005", "cont-yn": "N", "next-key": ""},
            json={"date": date, "amt_qty_tp": "1", "mrkt_tp": mrkt_tp,
                  "min_tic_tp": "1", "stex_tp": "1"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("prm_trde_trnsn", []) or []
        out = []
        for row in reversed(rows):  # 오래된→최신 정렬
            t = str(row.get("cntr_tm", ""))
            arb   = _parse(row.get("dfrt_trde_netprps", 0))
            noarb = _parse(row.get("ndiffpro_trde_netprps", 0))
            out.append({"t": t, "차익": arb, "비차익": noarb, "합계": arb + noarb})
        return out
    except Exception:
        return []


def get_program_trade(market: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 프로그램매매 순매수 (백만원).
    API ID: ka90005 — 프로그램매매추이(시간대별)
    mrkt_tp: P00101=코스피, P10102=코스닥
    응답: prm_trde_trnsn[0](가장 최근) → dfrt_trde_netprps / ndiffpro_trde_netprps
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    mrkt_tp = "P00101" if market == "J" else "P10102"
    date = _dt.datetime.now().strftime("%Y%m%d")

    def _parse(v):
        s = str(v).replace(",", "").replace(" ", "")
        if s.startswith("--"):
            return -int(float(s[2:]))
        s = s.lstrip("+")
        try: return int(float(s))
        except: return 0

    try:
        r = requests.post(
            f"{BASE}/api/dostk/mrkcond",
            headers={**_hdrs(), "api-id": "ka90005", "cont-yn": "N", "next-key": ""},
            json={"date": date, "amt_qty_tp": "1", "mrkt_tp": mrkt_tp,
                  "min_tic_tp": "1", "stex_tp": "1"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("prm_trde_trnsn", []) or []
        if not rows:
            return {"차익": 0, "비차익": 0, "합계": 0, "ts": ts}
        latest = rows[0]
        arb   = _parse(latest.get("dfrt_trde_netprps", 0))
        noarb = _parse(latest.get("ndiffpro_trde_netprps", 0))
        return {"차익": arb, "비차익": noarb, "합계": arb + noarb, "ts": ts}
    except Exception:
        return {"차익": 0, "비차익": 0, "합계": 0, "ts": ts}


def get_market_investor(market: str = "J") -> dict:
    """코스피(J)/코스닥(Q) 투자자별 당일 누적 순매수.
    API ID: ka10051 — 업종별투자자순매수요청
    mrkt_tp: 0=코스피, 1=코스닥
    응답: inds_netprps 리스트에서 inds_cd=001(코스피)/101(코스닥) 행 추출
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    mrkt_tp = "0" if market == "J" else "1"
    target_cd = "001" if market == "J" else "101"
    try:
        r = requests.post(
            f"{BASE}/api/dostk/sect",
            headers={**_hdrs(), "api-id": "ka10051", "cont-yn": "N", "next-key": ""},
            json={"mrkt_tp": mrkt_tp, "amt_qty_tp": "0", "stex_tp": "3"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("inds_netprps", []) or []

        def _int(v):
            try: return int(float(str(v).replace(",", "")))
            except: return 0

        # 업종별 리스트에서 종합지수 행(001/101) 찾기
        for row in rows:
            if row.get("inds_cd", "") == target_cd:
                return {
                    "외인": _int(row.get("frgnr_netprps", 0)),
                    "기관": _int(row.get("orgn_netprps", 0)),
                    "개인": _int(row.get("ind_netprps", 0)),
                    "ts": ts,
                }
        # 없으면 전체 합산
        외인 = sum(_int(r.get("frgnr_netprps", 0)) for r in rows)
        기관 = sum(_int(r.get("orgn_netprps", 0)) for r in rows)
        개인 = sum(_int(r.get("ind_netprps", 0)) for r in rows)
        return {"외인": 외인, "기관": 기관, "개인": 개인, "ts": ts}
    except Exception:
        return {"외인": 0, "기관": 0, "개인": 0, "ts": ts}


def get_trade_rank(n: int = 30) -> list:
    """거래대금 상위 종목 순위 (ka10032).
    mrkt_tp: 2=전체(코스피+코스닥)
    반환: [{"rank", "code", "name", "price", "change_rate"}, ...]
    """
    def _val(v, is_rate=False):
        s = str(v or "0").strip().replace(",", "")
        try:
            f = float(s)
        except Exception:
            f = 0.0
        return round(f, 2) if is_rate else int(f)

    try:
        r = requests.post(
            f"{BASE}/api/dostk/rkinfo",
            headers={**_hdrs(), "api-id": "ka10032", "cont-yn": "N", "next-key": ""},
            json={"mrkt_tp": "2", "trde_tp": "0", "stex_tp": "1", "mang_stk_incls": "0"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("trde_prica_upper") or []
        result = []
        for row in rows[:n]:
            result.append({
                "rank":        int(row.get("now_rank") or len(result) + 1),
                "code":        str(row.get("stk_cd", "")).zfill(6),
                "name":        row.get("stk_nm", ""),
                "price":       _val(row.get("cur_prc", 0)),
                "change_rate": _val(row.get("flu_rt", 0), is_rate=True),
            })
        return result
    except Exception:
        return []
