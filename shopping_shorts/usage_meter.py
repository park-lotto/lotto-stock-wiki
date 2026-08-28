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


# ── op(어떤 기능이 태운 비용인가) 자동 판별 ────────────────────────────────
# ★왜 자동인가: Gemini를 부르는 곳이 25개 모듈에 흩어져 있다(2026-08-29 grep 실측).
#   거기마다 track(op=...)를 적으면 25벌이 되고, 새 모듈이 생길 때마다 반드시
#   빠뜨린다(0순위-B). 호출 스택에서 **모듈 이름**을 읽어 여기 표 하나로 옮긴다.
#   표에 없는 모듈은 모듈명 그대로 남는다 — '(미지정)'으로 뭉뚱그리지 않는다.
_OP_BY_MODULE = {
    "script_generate": "대본생성",
    "script_extract": "대본추출",
    "bank_assemble": "대본조립",
    "pattern_bank": "패턴은행",
    "edit_plan": "장면배치",
    "similarity": "장면매칭",
    "video_analysis": "영상분석",
    "archive_tagger": "태깅",
    "tag_qa_frames": "태깅검수",
    "seo_generate": "SEO",
    "thumb_title": "썸네일문구",
    "comment_gen": "댓글생성",
    "ai_categorize": "카테고리",
    "coupang_query": "쿠팡검색",
    "product_identify": "제품식별",
    "product_name": "제품이름",
    "product_facts": "제품정보",
    "insta_facts": "인스타분석",
    "sul_facts": "썰추출",
    "frame_script": "프레임대본",
    "structure_analyze": "구조분석",
    "element_stats": "요소통계",
    "longform_shorts": "롱폼분할",
    "mix_pipeline": "제작",
}


def _op_from_stack():
    """호출 스택을 거슬러 올라가 '어느 기능이 부른 콜인가'를 알아낸다.

    usage_meter 자신과 SDK 래퍼 프레임은 건너뛴다. 못 찾으면 None(=옛 동작 그대로).
    ⚠️ 계측이 본작업을 죽이면 안 되므로 실패는 전부 삼킨다.
    """
    try:
        import inspect
        for fr in inspect.stack()[1:12]:
            mod = Path(fr.filename).stem
            if mod in ("usage_meter", "key_vault", "keyroute", "keyctx"):
                continue
            if mod in _OP_BY_MODULE:
                return _OP_BY_MODULE[mod]
            # shopping_shorts 안의 모듈이면 이름 그대로 남긴다(표에 없어도 '미지정'보단 낫다)
            if "shopping_shorts" in fr.filename.replace("\\", "/"):
                return mod
    except Exception:                  # noqa: BLE001
        pass
    return None


def _resolve_cid(ctx: dict):
    """이 콜의 주인(customer_id)을 정하는 **유일한 곳**.

    ★왜 폴백이 필요한가 (2026-08-29 서버 실측)
      `track(customer_id=...)`를 넘기는 곳은 `mix_pipeline.run_mix_job` 하나뿐이라,
      라이브 28,314건 중 **27,079건(96%, 86,580원)이 customer_id NULL**이었다.
      대본·렌즈·태깅·썸네일 등 나머지 경로가 전부 '누가 썼는지 모르는 비용'으로
      쌓여, 고객별 원가를 낼 수 없었다(하루 12,000원 중 식별 462원).

    ★왜 keyctx인가
      "지금 작업이 누구 것인가"는 이미 keyctx가 알고 있다 — HTTP 요청은 미들웨어
      `_auth_guard`가, 워커는 `_owned_job` 데코레이터가 채운다. 같은 판단을 여기서
      다시 만들면 두 벌이 되어 언젠가 어긋난다(0순위-B). **읽기만 한다.**

    우선순위: track(customer_id=) 명시값 > keyctx 주인 > None.
      - 명시값이 이기는 이유: 워커가 job 주인을 아는 경우가 더 정확하다.
      - **0(사장님)은 기록한다.** 회사 부담분도 원가라 빼면 합이 안 맞는다.
      - keyctx를 못 읽으면(임포트 실패 등) None — 계측이 본작업을 죽이면 안 된다.
    """
    cid = ctx.get("customer_id")
    if cid is not None:
        return cid
    try:
        from shopping_shorts import keyctx
        return keyctx.owner_cid()
    except Exception:                  # noqa: BLE001 — 계측이 본작업을 죽이면 안 된다
        return None


def record(model: str, in_tokens: int, out_tokens: int, auth: str = "apikey", **over) -> float:
    """1콜 기록 → 원화 비용 반환. 실패해도 예외를 올리지 않는다."""
    price = _price_for(model)
    usd = (in_tokens / 1e6) * price["in"] + (out_tokens / 1e6) * price["out"]
    krw = usd * USD_KRW
    ctx = current_context()
    ctx.update({k: v for k, v in over.items() if v is not None})
    # ★컬럼은 TEXT인데 넘어오는 값은 int라 섞여 저장된다. 조회할 때 '57'과 57이
    #   서로 안 잡히므로 **쓰는 순간 문자열로 통일**한다(조회부에 CAST를 흩뿌리지 않는다).
    cid = _resolve_cid(ctx)
    ctx["customer_id"] = None if cid is None else str(cid)
    # op도 같은 이유로 96%가 비어 있었다 — track(op=)로 명시한 게 있으면 그게 이기고,
    # 없으면 호출 스택에서 유도한다(0순위-B: 판단은 _op_from_stack 한 곳).
    if not ctx.get("op"):
        ctx["op"] = _op_from_stack()
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
