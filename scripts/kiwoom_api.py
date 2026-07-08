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
    """코스피(J)/코스닥(Q) 투자자별 당일 누적 순매수 + 기관 세부(금투/보험/투신/사모/은행/연기금등/기타).
    API ID: ka10051 — 업종별투자자순매수요청
    mrkt_tp: 0=코스피, 1=코스닥
    응답: inds_netprps 리스트에서 inds_cd=001(코스피)/101(코스닥) 행 추출
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    mrkt_tp = "0" if market == "J" else "1"
    target_cd = "001" if market == "J" else "101"  # 장내 종합지수 코드 (stex_tp=1)

    def _int(v):
        try: return int(float(str(v).replace(",", "")))
        except: return 0

    # 기관 세부 항목 필드 매핑 (ka10051 raw row → 한글 키)
    _SUB = {
        "금투": "sc_netprps", "보험": "insrnc_netprps", "투신": "invtrt_netprps",
        "은행": "bank_netprps", "연기금": "jnsinkm_netprps", "기타금융": "endw_netprps",
        "기타법인": "etc_corp_netprps", "국가": "natn_netprps", "사모": "samo_fund_netprps",
    }
    _ZERO_SUB = {k: 0 for k in _SUB}
    try:
        r = requests.post(
            f"{BASE}/api/dostk/sect",
            headers={**_hdrs(), "api-id": "ka10051", "cont-yn": "N", "next-key": ""},
            json={"mrkt_tp": mrkt_tp, "amt_qty_tp": "0", "stex_tp": "1"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("inds_netprps", []) or []

        # 업종별 리스트에서 종합지수 행(001/101) 찾기
        for row in rows:
            if row.get("inds_cd", "") == target_cd:
                return {
                    "외인": _int(row.get("frgnr_netprps", 0)),
                    "기관": _int(row.get("orgn_netprps", 0)),
                    "개인": _int(row.get("ind_netprps", 0)),
                    **{k: _int(row.get(f, 0)) for k, f in _SUB.items()},
                    "ts": ts,
                }
        # 없으면 전체 합산
        외인 = sum(_int(r.get("frgnr_netprps", 0)) for r in rows)
        기관 = sum(_int(r.get("orgn_netprps", 0)) for r in rows)
        개인 = sum(_int(r.get("ind_netprps", 0)) for r in rows)
        sub = {k: sum(_int(r.get(f, 0)) for r in rows) for k, f in _SUB.items()}
        return {"외인": 외인, "기관": 기관, "개인": 개인, **sub, "ts": ts}
    except Exception:
        return {"외인": 0, "기관": 0, "개인": 0, **_ZERO_SUB, "ts": ts}


def get_volume_rank(n: int = 30) -> list:
    """당일 거래량 상위 종목 (ka10030) — '실시간 조회순위' 대용."""
    def _val(v, is_rate=False):
        s = str(v or "0").strip().replace(",", "")
        try:
            f = float(s)
        except Exception:
            f = 0.0
        return round(f, 2) if is_rate else abs(int(f))  # price는 부호 제거 (키움 응답에 +/- 포함)

    try:
        r = requests.post(
            f"{BASE}/api/dostk/rkinfo",
            headers={**_hdrs(), "api-id": "ka10030", "cont-yn": "N", "next-key": ""},
            json={
                "mrkt_tp": "2", "stex_tp": "1", "mang_stk_incls": "0",
                "sort_tp": "1", "crd_tp": "0", "trde_qty_tp": "0",
                "pric_tp": "0", "trde_prica_tp": "0", "mrkt_open_tp": "0",
            },
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get("tdy_trde_qty_upper") or []
        result = []
        for i, row in enumerate(rows[:n]):
            result.append({
                "rank":        i + 1,
                "code":        str(row.get("stk_cd", "")).zfill(6),
                "name":        row.get("stk_nm", ""),
                "price":       _val(row.get("cur_prc", 0)),
                "change_rate": _val(row.get("flu_rt", 0), is_rate=True),
            })
        return result
    except Exception:
        return []


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
        return round(f, 2) if is_rate else abs(int(f))  # price는 부호 제거

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


def _pamt(v) -> int:
    """키움 금액 문자열 파싱 → 정수(백만원). '--7767'(이중부호)·'+88548'·콤마 처리."""
    s = str(v).replace(",", "").replace(" ", "")
    if not s or s in ("-", "+"):
        return 0
    neg = False
    if s.startswith("--"):
        neg, s = True, s[2:]
    elif s.startswith("-"):
        neg, s = True, s[1:]
    else:
        s = s.lstrip("+")
    try:
        n = int(float(s))
    except Exception:
        return 0
    return -n if neg else n


def _pricenum(v) -> float:
    """가격 문자열 → 양수 float (키움 '+338000'/'-321000'의 부호는 등락 표시일 뿐, 가격은 양수)."""
    s = str(v).replace(",", "").strip().lstrip("+")
    if s.startswith("-"):
        s = s[1:]
    try:
        return float(s)
    except Exception:
        return 0.0


# tf → (api-id, 응답 list key, 종류)  /  종류 day=dt 기반, min=cntr_tm 기반
_CANDLE_TR = {
    "D": ("ka10081", "stk_dt_pole_chart_qry", "day"),    # 일봉
    "W": ("ka10082", "stk_stk_pole_chart_qry", "day"),   # 주봉
    "M": ("ka10083", "stk_mth_pole_chart_qry", "day"),   # 월봉
}


def get_stock_candles(code: str, tf: str = "D", n: int = 800) -> list:
    """종목 캔들(OHLCV). tf='D'일/'W'주/'M'월(ka10081/82/83) / '5'·'30'·'60'분봉(ka10080).

    반환(과거→최신): [{"time","open","high","low","close","value"(거래량)}]
      - 일/주/월봉 time = "YYYY-MM-DD"
      - 분봉 time = epoch초 (KST 벽시계를 UTC로 취급 → 차트 축에 KST 시각 표시)
    단일 요청 반환량: 일600·5분900·주300·월240 → 충분한 과거 표시.
    """
    import datetime as _dt
    out = []
    try:
        if tf in _CANDLE_TR:
            api_id, key, _ = _CANDLE_TR[tf]
            today = _dt.datetime.now().strftime("%Y%m%d")
            r = requests.post(
                f"{BASE}/api/dostk/chart",
                headers={**_hdrs(), "api-id": api_id, "cont-yn": "N", "next-key": ""},
                json={"stk_cd": code, "base_dt": today, "upd_stkpc_tp": "1"},
                timeout=12,
            )
            r.raise_for_status()
            rows = r.json().get(key, []) or []
            for row in rows:
                dt = str(row.get("dt", ""))
                if len(dt) != 8:
                    continue
                out.append({
                    "time": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                    "open": _pricenum(row.get("open_pric")), "high": _pricenum(row.get("high_pric")),
                    "low": _pricenum(row.get("low_pric")), "close": _pricenum(row.get("cur_prc")),
                    "value": int(_pricenum(row.get("trde_qty"))),
                })
        else:
            import calendar
            tic = tf if tf in ("1", "3", "5", "10", "15", "30", "60") else "5"
            r = requests.post(
                f"{BASE}/api/dostk/chart",
                headers={**_hdrs(), "api-id": "ka10080", "cont-yn": "N", "next-key": ""},
                json={"stk_cd": code, "tic_scope": tic, "upd_stkpc_tp": "1"},
                timeout=12,
            )
            r.raise_for_status()
            rows = r.json().get("stk_min_pole_chart_qry", []) or []
            for row in rows:
                t = str(row.get("cntr_tm", ""))
                if len(t) < 12:
                    continue
                epoch = calendar.timegm((int(t[:4]), int(t[4:6]), int(t[6:8]),
                                         int(t[8:10]), int(t[10:12]), 0, 0, 0, 0))
                out.append({
                    "time": epoch,
                    "open": _pricenum(row.get("open_pric")), "high": _pricenum(row.get("high_pric")),
                    "low": _pricenum(row.get("low_pric")), "close": _pricenum(row.get("cur_prc")),
                    "value": int(_pricenum(row.get("trde_qty"))),
                })
        out.reverse()  # 최신→과거 → 과거→최신 (lightweight-charts는 오름차순 필요)
        # 시간 중복/역행 제거 (차트 라이브러리 오류 방지)
        clean, last = [], None
        for c in out:
            if last is not None and c["time"] <= last:
                continue
            clean.append(c); last = c["time"]
        return clean[-n:]
    except Exception:
        return []


def get_stock_supply(code: str) -> dict:
    """종목별 잠정수급 — 외인/기관/개인(ka10059) + 프로그램 순매수(ka90013).

    단위: 백만원 (시장 투자자 수급과 동일, fmtAuk로 억 환산).
    반환: {"외인","기관","개인","프로그램","ts"} — 실패 항목은 0.
    """
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%H:%M")
    today = _dt.datetime.now().strftime("%Y%m%d")
    out = {"외인": 0, "기관": 0, "개인": 0, "프로그램": 0, "ts": ts}

    # ① 외인/기관/개인 — ka10059 종목별투자자기관별요청 (금액, 최신일=rows[0])
    try:
        r = requests.post(
            f"{BASE}/api/dostk/stkinfo",
            headers={**_hdrs(), "api-id": "ka10059", "cont-yn": "N", "next-key": ""},
            json={"dt": today, "stk_cd": code, "amt_qty_tp": "1",
                  "trde_tp": "0", "unit_tp": "1000"},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("stk_invsr_orgn", []) or []
        if rows:
            row = rows[0]
            out["외인"] = _pamt(row.get("frgnr_invsr", 0))
            out["기관"] = _pamt(row.get("orgn", 0))
            gae = _pamt(row.get("ind_invsr", 0))
            # ka10059가 개인(ind_invsr)을 0으로 주는 경우 → 순매수 합=0 원리로 도출
            #   개인 = -(외인 + 기관계 + 기타법인 + 내외국인)
            if gae == 0:
                gae = -(out["외인"] + out["기관"]
                        + _pamt(row.get("etc_corp", 0)) + _pamt(row.get("natfor", 0)))
            out["개인"] = gae
    except Exception:
        pass

    # ② 프로그램 순매수 — ka90013 종목별일별프로그램매매추이요청 (최신일=rows[0])
    try:
        r = requests.post(
            f"{BASE}/api/dostk/mrkcond",
            headers={**_hdrs(), "api-id": "ka90013", "cont-yn": "N", "next-key": ""},
            json={"stk_cd": code, "date": today, "amt_qty_tp": "1",
                  "mrkt_tp": "P00101", "min_tic_tp": "1", "stex_tp": "1"},
            timeout=8,
        )
        r.raise_for_status()
        rows = r.json().get("stk_daly_prm_trde_trnsn", []) or []
        if rows:
            out["프로그램"] = _pamt(rows[0].get("prm_netprps_amt", 0))
    except Exception:
        pass

    return out
