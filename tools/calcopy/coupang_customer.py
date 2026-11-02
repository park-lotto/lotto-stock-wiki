# -*- coding: utf-8 -*-
"""회원 PC 쿠팡 검색(사장님 10-21: 회원 본인 파트너스 키 — 없는 사람만 본인 PC 크롬). 서버 정보 없음(설치본 묶음에 들어간다).
판단 주인: 검색 = shopping_shorts.coupang_partners.search_products(서비스와 같은 함수) · 크롬 길 = hybrid/customer.coupang_chrome."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _classify(st: int, d: dict) -> tuple[str, str]:
    """쿠팡 응답 한 건 → (state, reason). 쿠팡이 키를 거부했다고 말한 때만 'bad' — 나머지 실패는 키가 살았을 수 있어 'unknown'(11-02 회원 제보).
    401·403 묶음·한도·서버·회선 갈래는 coupang_partners._outcome 을 그대로 쓰고, 여기서는 그 안을 더 가른다."""
    if st == 200 and str(d.get("rCode", "")) == "0":     # coupang_partners.probe_key 와 같은 통과 기준(_outcome 의 'ok' 는 rCode 없는 응답도 통과시킨다)
        return "ok", "ok"
    from shopping_shorts import coupang_partners as cp
    oc = cp._outcome(st, d)
    if oc == "auth_dead":                                # 본문이 JSON 이 아닌 403 = 게이트웨이 앞에서 막힘(회선·방화벽) — _call 이 {'error': 'HTTP 403'} 로 준다
        return ("unknown", "blocked") if d == {"error": "HTTP 403"} else ("bad", "key_rejected")
    if oc == "network":
        err = str(d.get("error") or "").lower()
        return "unknown", "net_ssl" if "ssl" in err or "certificate" in err else "net_timeout" if "timed out" in err or "timeout" in err else "net_failed"
    return "unknown", {"rpm": "rate_limited", "server": "server_error"}.get(oc, "probe_refused")


def key_check(tries: int = 2, gap: float = 2.0) -> dict:
    """회원 파트너스 키 상태 — 판단 주인(runner_ops.coupang_key_state·search 가 부른다). 무과금 딥링크(확인용 상품은 coupang_partners._PROBE_URL).
    → {state, reason, http} · state: ok / none(키 없음) / bad(쿠팡이 키 거부) / unknown(일시 실패·판정 불가 — 키는 그대로 먼저 쓴다).
    reason·http 만 남긴다 — 키 값·쿠팡 응답 글은 로그에 쓰지 않는다."""
    ak, sk = os.environ.get("COUPANG_ACCESS_KEY", ""), os.environ.get("COUPANG_SECRET_KEY", "")
    if not (ak and sk):
        return {"state": "none", "reason": "no_key", "http": None}
    r = {"state": "unknown", "reason": "check_error", "http": None}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from shopping_shorts import coupang_partners as cp
        for k in range(tries):
            st, d = cp._call("POST", f"{cp._API_BASE}/v1/deeplink", ak, sk, {"coupangUrls": [cp._PROBE_URL]})
            state, reason = _classify(st, d if isinstance(d, dict) else {})
            r = {"state": state, "reason": reason, "http": st or None}
            if state != "unknown":                       # 통과·거부는 다시 불러도 같다 — 잠깐의 끊김만 한 번 더
                break
            if k + 1 < tries:
                time.sleep(gap)
    except Exception as e:  # noqa: BLE001 — 확인이 깨져도 제작 시작을 막지 않는다(경보는 아래 한 줄)
        r = {"state": "unknown", "reason": "check_error", "http": None}
        print(f"[coupang] 키 확인 오류 {type(e).__name__}", file=sys.stderr, flush=True)
    if r["state"] != "ok":
        print(f"[coupang] 키 확인 state={r['state']} reason={r['reason']} http={r['http']}", file=sys.stderr, flush=True)
    return r


def search(queries: list[str]) -> dict:
    ak, sk = os.environ.get("COUPANG_ACCESS_KEY", ""), os.environ.get("COUPANG_SECRET_KEY", "")
    if os.environ.get("CALCOPY_DEV_COUPANG_SERVER") == "1" and not (ak and sk):
        # 개발 PC 시험 전용 — 이 PC 회선은 쿠팡이 막는다(10-21 실측 '사용권한이 제한된 페이지') → '키 있는 회원' 길을 서버 관리자 키로 흉내.
        #   coupang_api_search(서버 SSH)는 설치본에 없다 — 회원 PC 에서는 ImportError 로 이 줄이 돌 수 없다
        try:
            from tools.calcopy import coupang_api_search as srv
        except ImportError as e:   # 설치 묶음엔 없다(10-26 run4 — 시험 하네스가 이 스위치를 켠 채 묶음을 돌림) → 회원 길로(경보 한 줄)
            print(f"[coupang] 개발 서버 검색 없음({e}) — 회원 키·크롬 길로", file=sys.stderr, flush=True)
            srv = None
    if os.environ.get("CALCOPY_DEV_COUPANG_SERVER") == "1" and not (ak and sk) and srv is not None:
        os.environ.pop("CALCOPY_CUSTOMER_MODE", None)
        try:
            return srv.search(queries)
        finally:
            os.environ["CALCOPY_CUSTOMER_MODE"] = "1"
    if not (ak and sk):
        return {q: {"ok": False, "need": "chrome", "notice": "회원 파트너스 키 없음 — 크롬 검색", "items": []} for q in queries}
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shopping_shorts import coupang_partners as cp
    got = {q: cp.search_products(q, limit=10, access_key=ak, secret_key=sk) for q in queries}
    if queries and not any((v or {}).get("ok") for v in got.values()):      # 키가 죽었거나 막혔다 — 빈손으로 끝내지 않고 크롬 길로(사장님 11-02 "키 있으면 우선")
        why = key_check(tries=1)                          # 왜 실패했나 사유 코드 — 딥링크가 통과하면 키는 살아 있고 검색 쪽 사정이다
        reason = "search_only" if why["state"] == "ok" else why["reason"]
        print(f"[coupang] 키 검색 전부 실패 reason={reason} — 크롬 검색으로", file=sys.stderr, flush=True)
        return {q: {"ok": False, "need": "chrome", "notice": "파트너스 키 검색 실패 — 크롬 검색", "reason": reason, "items": []} for q in queries}
    return got
