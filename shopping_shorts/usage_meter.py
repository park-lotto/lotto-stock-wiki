"""Gemini 토큰 사용량 계측 — 호출부를 안 고치고 클라이언트를 감싸서 잰다.

왜 래퍼인가:
  `generate_content(` 호출부가 34곳(2026-08-16 실측)이라 거기마다 usage_metadata를
  찍으면 34벌이 되고, 새 호출부가 생길 때마다 반드시 빠뜨린다(CLAUDE.md 0순위-B).
  클라이언트를 만드는 곳은 6곳뿐이고 전부 `_client_for_key()` 계열이라, 거기서
  한 번 감싸면 34곳이 자동으로 잡힌다.

무엇을 재는가:
  resp.usage_metadata의 prompt_token_count / candidates_token_count.
  모델별 단가를 곱해 원화까지 계산해 `gemini_usage` 테이블에 1행씩 쌓는다.

⚠️ 계측이 본작업을 죽이면 안 된다 — 이 모듈의 모든 실패는 삼키고 원래 응답을 그대로
   돌려준다. 단, 삼킨 것은 로그로 남긴다(침묵 except가 SQL 오류를 먹어 라이브에서
   0건이 된 2026-08-10 사고 재발 방지).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# ── 단가 (USD / 1M tokens) ────────────────────────────────────────────────
# 출처: https://ai.google.dev/pricing (2026-08-16 확인)
# ⚠️ 구글이 단가를 바꾸면 여기만 고치면 된다. 다른 곳에 적지 마라.
_PRICING = {
    "gemini-3.1-flash-lite": {"in": 0.25, "out": 1.50},
    "gemini-3.5-flash":      {"in": 0.50, "out": 3.00},
    "gemini-3-flash":        {"in": 0.50, "out": 3.00},
}
_DEFAULT_PRICE = {"in": 0.50, "out": 3.00}   # 모르는 모델은 비싼 쪽으로 잡는다

USD_KRW = float(os.environ.get("USAGE_USD_KRW", "1400"))

_DB_PATH = Path(__file__).parent / "data" / "reference.db"
_init_lock = threading.Lock()
_initialized = False


def _price_for(model: str) -> dict:
    """모델명 → 단가. 접두사 매칭이라 '-preview' 같은 꼬리표가 붙어도 잡힌다."""
    m = (model or "").strip()
    if m in _PRICING:
        return _PRICING[m]
    for known, p in _PRICING.items():
        if m.startswith(known):
            return p
    return _DEFAULT_PRICE


def _ensure_schema(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gemini_usage (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            day           TEXT    NOT NULL,
            op            TEXT,              -- 기능 이름 (대본/태깅/SEO…)
            job_id        TEXT,              -- 영상 1편 묶음 (제작소 job)
            customer_id   TEXT,              -- 사용자별 누적용
            model         TEXT    NOT NULL,
            in_tokens     INTEGER NOT NULL DEFAULT 0,
            out_tokens    INTEGER NOT NULL DEFAULT 0,
            krw           REAL    NOT NULL DEFAULT 0,
            auth          TEXT               -- 'apikey' | 'vertex'
        )""")
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_gu_day ON gemini_usage(day)",
        "CREATE INDEX IF NOT EXISTS ix_gu_job ON gemini_usage(job_id)",
        "CREATE INDEX IF NOT EXISTS ix_gu_cust ON gemini_usage(customer_id, day)",
        "CREATE INDEX IF NOT EXISTS ix_gu_op ON gemini_usage(op, day)",
    ):
        conn.execute(stmt)
    conn.commit()


def _connect():
    global _initialized
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    if not _initialized:
        with _init_lock:
            if not _initialized:
                _ensure_schema(conn)
                _initialized = True
    return conn


# ── 호출 문맥 (누가 부른 콜인지) ───────────────────────────────────────────
# op/job_id/customer_id를 인자로 넘기려면 34곳을 다 고쳐야 한다. 스레드로컬에
# 담아두면 호출부는 그대로 두고 파이프라인 진입점에서만 한 번 세팅하면 된다.
_ctx = threading.local()


class track:
    """with usage_meter.track(op="대본", job_id=..., customer_id=...): 로 감싼다.

    중첩되면 안쪽이 이긴다(대본 안에서 번역을 부르면 번역으로 찍힌다).
    """

    def __init__(self, op=None, job_id=None, customer_id=None):
        self._new = {"op": op, "job_id": job_id, "customer_id": customer_id}
        self._prev = None

    def __enter__(self):
        self._prev = getattr(_ctx, "cur", None)
        merged = dict(self._prev or {})
        merged.update({k: v for k, v in self._new.items() if v is not None})
        _ctx.cur = merged
        return self

    def __exit__(self, *exc):
        _ctx.cur = self._prev
        return False


def current_context() -> dict:
    return dict(getattr(_ctx, "cur", None) or {})


def record(model: str, in_tokens: int, out_tokens: int, auth: str = "apikey", **over) -> float:
    """1콜 기록 → 원화 비용 반환. 실패해도 예외를 올리지 않는다."""
    price = _price_for(model)
    usd = (in_tokens / 1e6) * price["in"] + (out_tokens / 1e6) * price["out"]
    krw = usd * USD_KRW
    ctx = current_context()
    ctx.update({k: v for k, v in over.items() if v is not None})
    now = datetime.now(timezone.utc)
    try:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO gemini_usage(ts,day,op,job_id,customer_id,model,"
                "in_tokens,out_tokens,krw,auth) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now.isoformat(), now.strftime("%Y-%m-%d"), ctx.get("op"),
                 ctx.get("job_id"), ctx.get("customer_id"), model,
                 int(in_tokens), int(out_tokens), krw, auth))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:            # noqa: BLE001 — 계측이 본작업을 죽이면 안 된다
        log.warning("usage_meter: 기록 실패(무시하고 진행) %s", e)
    return krw


# ── 클라이언트 래퍼 ───────────────────────────────────────────────────────
class _MeteredModels:
    """client.models 를 감싸 generate_content 응답에서 토큰을 뽑아 기록한다."""

    def __init__(self, inner, auth):
        self._inner = inner
        self._auth = auth

    def generate_content(self, *a, **kw):
        resp = self._inner.generate_content(*a, **kw)
        try:
            um = getattr(resp, "usage_metadata", None)
            if um is not None:
                model = kw.get("model") or (a[0] if a else "") or ""
                # 필드명이 SDK 버전마다 다를 수 있어 방어적으로 읽는다
                pt = getattr(um, "prompt_token_count", 0) or 0
                ct = (getattr(um, "candidates_token_count", 0) or 0)
                # thinking 토큰은 출력으로 과금된다
                ct += (getattr(um, "thoughts_token_count", 0) or 0)
                record(str(model), pt, ct, auth=self._auth)
        except Exception as e:         # noqa: BLE001
            log.warning("usage_meter: 응답 파싱 실패(무시) %s", e)
        return resp

    def __getattr__(self, name):       # count_tokens 등은 그대로 통과
        return getattr(self._inner, name)


class MeteredClient:
    """genai.Client 를 감싼다. .models 만 가로채고 나머지(files 등)는 그대로."""

    def __init__(self, inner, auth="apikey"):
        self._inner = inner
        self._auth = auth
        self._models = None

    @property
    def models(self):
        if self._models is None:
            self._models = _MeteredModels(self._inner.models, self._auth)
        return self._models

    def __getattr__(self, name):
        return getattr(self._inner, name)


def wrap(client, auth="apikey"):
    """이미 감싼 것은 두 번 감싸지 않는다(중복 기록 방지)."""
    if client is None or isinstance(client, MeteredClient):
        return client
    if os.environ.get("USAGE_METER", "1") != "1":
        return client
    return MeteredClient(client, auth=auth)
