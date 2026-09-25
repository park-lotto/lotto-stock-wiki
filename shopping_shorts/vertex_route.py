# -*- coding: utf-8 -*-
"""Vertex(사장님 GCP 프로젝트) 경로 스위치 — **판단·클라이언트·모델을 여기 한 곳에서**(0순위-B).

왜(2026-09-25 사장님): AI Studio 키풀은 밤 22~05시 503(모델 용량)·429(무료 등급 분당 한도)로
대본추출 성공률이 9~24%까지 떨어진다. 서버엔 유료 Vertex 프로젝트가 이미 등록돼 있고(Veo용),
실측으로 `location="global"`에서 gemini-3.6-flash가 인라인 영상 32MB까지 15~19초에 답했다
(us-central1은 404 — 글로벌 엔드포인트만 된다). 바꾸는 당위성(결·오류율)을 사장님 계정으로
먼저 재기 위한 스위치다 — **Vertex 먼저, 실패하면 종전 키풀**이라 켜도 나빠질 길은 없다.

설정(관리자 setting):
  vertex_enabled  ""/0 끔(기본) · "admin" 관리자만 · "1" 전체 · "11,42" 고객 목록  (_setting_gate와 같은 뜻)
  vertex_ops      "" = 전부 / 콤마 목록: script_extract, frame_script, ai_match
  vertex_model    기본 gemini-3.6-flash

계측: usage_meter.wrap(auth="vertex", pool="vertex") — gemini_usage.auth·api_events.pool로 API키분과 갈린다.
"""
import sys
import time

OPS = ("script_extract", "frame_script", "ai_match", "script_generate")
# script_generate = script_generate._call_json 깔때기(이야기 작가·백본·옛 생성기·판정 전부) — 2026-09-26 사장님
#   "태깅은 무료로, 대본작성과 장면매칭이 얼마나 잘되는지 해보자" → 설정 vertex_ops=script_generate,ai_match
LOCATION = "global"                 # ★us-central1은 3.6-flash 404(2026-09-25 실측) — 글로벌만
DEFAULT_MODEL = "gemini-3.6-flash"
INLINE_MAX_BYTES = 40 * 1024 * 1024  # 실측 32.4MB OK. 그 위는 미검증 → 키풀(파일 업로드) 경로로
SETTING_ENABLED, SETTING_OPS, SETTING_MODEL = "vertex_enabled", "vertex_ops", "vertex_model"
_SETTINGS_TTL = 30.0

_settings_cache = {"t": 0.0, "vals": None}
_client_cache = {}


def _read_settings():
    """설정 3개를 한 번에(30초 캐시) — 호출부가 초당 수십 번 물어도 DB를 안 두드린다."""
    now = time.monotonic()
    if _settings_cache["vals"] is not None and now - _settings_cache["t"] < _SETTINGS_TTL:
        return _settings_cache["vals"]
    vals = {}
    try:
        from shopping_shorts import config
        from shopping_shorts.store import Store
        st = Store(config.DB_PATH)
        for k in (SETTING_ENABLED, SETTING_OPS, SETTING_MODEL):
            vals[k] = (st.get_setting(k, "") or "").strip()
    except Exception:      # noqa: BLE001 — 설정을 못 읽으면 '끔'(종전 그대로)
        vals = {}
    _settings_cache.update(t=now, vals=vals)
    return vals


def reset_cache():
    _settings_cache.update(t=0.0, vals=None)
    _client_cache.clear()


def _is_admin(cid):
    """관리자 판정은 app._is_admin 하나다. 못 부르면(워커 등) 사장님(0)만 관리자로 본다."""
    try:
        from shopping_shorts.app import _is_admin as _f
        return bool(_f(cid))
    except Exception:      # noqa: BLE001
        try:
            return int(cid) == 0
        except (TypeError, ValueError):
            return False


def gate_allows(value, cid):
    """_setting_gate(app.py)와 같은 뜻: ""/0 끔 · "1" 전체 · "admin" 관리자 · "11,42" 목록(관리자 포함)."""
    v = (value or "").strip().lower()
    if not v or v in ("0", "off", "false"):
        return False
    if v == "1":
        return True
    if v == "admin":
        return _is_admin(cid)
    allowed = {x.strip() for x in v.split(",") if x.strip()}
    return str(cid) in allowed or _is_admin(cid)


def current_cid():
    """이 호출의 주인 — usage_meter가 정하는 값을 **읽기만** 한다(0순위-B)."""
    try:
        from shopping_shorts import usage_meter
        return usage_meter._resolve_cid(usage_meter.current_context())
    except Exception:      # noqa: BLE001
        return None


def on(op, cid=None):
    """이 op를 Vertex로 보낼까. 설정이 없거나 못 읽으면 False(종전 그대로)."""
    if op not in OPS:
        return False
    vals = _read_settings()
    if not gate_allows(vals.get(SETTING_ENABLED, ""), current_cid() if cid is None else cid):
        return False
    ops = [x.strip() for x in (vals.get(SETTING_OPS) or "").split(",") if x.strip()]
    return (not ops) or (op in ops)


def model():
    return _read_settings().get(SETTING_MODEL) or DEFAULT_MODEL


def client():
    """Vertex 클라이언트(계측 래핑, 캐시). 자격증명은 GOOGLE_APPLICATION_CREDENTIALS(ADC)."""
    if "cl" not in _client_cache:
        from google import genai
        from google.genai import types
        from shopping_shorts import config, usage_meter
        cl = genai.Client(vertexai=True, project=config.GCP_PROJECT, location=LOCATION,
                          http_options=types.HttpOptions(timeout=180_000))
        _client_cache["cl"] = usage_meter.wrap(cl, auth="vertex", pool="vertex", key="vertex")
    return _client_cache["cl"]


def video_part(path):
    """영상을 **인라인 바이트**로(Vertex엔 Files API가 없다). 상한 넘으면 None → 호출부는 키풀 경로."""
    import os
    from google.genai import types
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > INLINE_MAX_BYTES:
        print("vertex_route: 영상 %.1fMB > 인라인 상한 → 키풀 경로" % (size / 1048576), file=sys.stderr)
        return None
    with open(path, "rb") as fh:
        return types.Part.from_bytes(data=fh.read(), mime_type="video/mp4")


def try_call(op, fn, what=""):
    """(시도했나, 결과). 스위치가 꺼졌으면 (False, None). 켜졌으면 fn(client, model) 1회 —
    예외·빈 결과는 stderr에 남기고 (False, None) → 호출부는 종전 키풀 경로로 이어간다."""
    if not on(op):
        return False, None
    m = model()
    t0 = time.monotonic()
    try:
        got = fn(client(), m)
    except Exception as e:      # noqa: BLE001 — Vertex 실패가 본작업을 막으면 안 된다(키풀 폴백)
        print("vertex_route.%s: %s 실패(%.1fs) → 키풀 폴백 — %r" % (
            what or op, m, time.monotonic() - t0, e), file=sys.stderr)
        return False, None
    if not got:
        print("vertex_route.%s: %s 빈 결과(%.1fs) → 키풀 폴백" % (what or op, m, time.monotonic() - t0),
              file=sys.stderr)
        return False, None
    print("vertex_route.%s: %s OK(%.1fs)" % (what or op, m, time.monotonic() - t0), file=sys.stderr)
    return True, got
