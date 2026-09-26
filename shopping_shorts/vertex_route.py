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
    _member_cache.clear()


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


# ── 회원 자기 Vertex(2026-09-26 사장님 "필요한 사람은 등록하게") ─────────────────────────
# 서비스계정 JSON 하나로 텍스트(3.6)와 Veo(AI 장면생성)를 같이 쓴다 — Express 키는 일부 Gemini만 돼 Veo가 안 된다.
# 저장소는 기존 BYOK(customer_keys + keycrypt Fernet) 그대로, service="vertex_sa". 회원당 1개.
SVC = "vertex_sa"
MEMBER_OPS = ("script_generate", "ai_match")      # 등록한 회원은 이 op가 자동으로 자기 Vertex로 간다
_MEMBER_TTL = 30.0
_member_cache = {}                                 # cid → (t, info|None)


def validate_sa(text):
    """(info, 에러문구) — 붙여넣은 서비스계정 JSON 검사. 구글 호출 없이 모양만 본다."""
    import json
    raw = (text or "").strip()
    if not raw:
        return None, "서비스계정 JSON을 붙여넣어 주세요"
    if len(raw) > 20000:
        return None, "JSON이 너무 큽니다 — 서비스계정 키 파일(.json) 내용만 붙여넣어 주세요"
    try:
        info = json.loads(raw)
    except ValueError:
        return None, "JSON 형식이 아닙니다 — 내려받은 키 파일을 메모장으로 열어 전체를 복사해 주세요"
    if not isinstance(info, dict) or info.get("type") != "service_account":
        return None, "서비스계정 키가 아닙니다(type이 service_account여야 합니다)"
    for k in ("project_id", "client_email", "private_key"):
        if not str(info.get(k) or "").strip():
            return None, "키 파일에 %s가 없습니다 — 다시 내려받아 주세요" % k
    if "BEGIN PRIVATE KEY" not in info["private_key"]:
        return None, "private_key 모양이 이상합니다 — 파일 전체를 그대로 붙여넣어 주세요"
    return info, ""


def sa_label(info):
    """화면 표시용 — 프로젝트 ID + 가린 이메일. 비밀값(private_key)은 절대 싣지 않는다."""
    em = str(info.get("client_email") or "")
    name = em.split("@")[0]
    return "%s · %s…@%s" % (info.get("project_id") or "?", name[:4], (em.split("@") + [""])[1][:24])


def member_info(cid):
    """회원이 등록한 서비스계정(dict) 또는 None. 끈(off)·죽은(bad) 것은 None. 30초 캐시."""
    try:
        cid_i = int(cid)
    except (TypeError, ValueError):
        return None
    now = time.monotonic()
    hit = _member_cache.get(cid_i)
    if hit and now - hit[0] < _MEMBER_TTL:
        return hit[1]
    info = None
    try:
        import json
        from shopping_shorts import config
        from shopping_shorts.store import Store
        st = Store(config.DB_PATH)
        bad = {r["id"] for r in st.list_customer_keys(cid_i, SVC) if r.get("status") == "bad"}
        for kid, plain in st.get_customer_keys_with_id(cid_i, SVC):
            if kid in bad:
                continue
            try:
                info = json.loads(plain)
                break
            except ValueError:
                continue
    except Exception as e:      # noqa: BLE001 — 못 읽으면 '등록 안 함'(종전 경로)
        print("vertex_route: 회원 %s 자격증명 읽기 실패 — %r" % (cid, e), file=sys.stderr)
        info = None
    _member_cache[cid_i] = (now, info)
    return info


def forget_member(cid):
    """등록·삭제 직후 캐시를 비운다(30초 기다리지 않게)."""
    try:
        _member_cache.pop(int(cid), None)
    except (TypeError, ValueError):
        pass
    for k in [k for k in _client_cache if k.startswith("m:%s:" % cid)]:
        _client_cache.pop(k, None)


def on(op, cid=None):
    """이 op를 Vertex로 보낼까. ①회원이 자기 Vertex를 등록했으면 MEMBER_OPS는 자동 ON(자기 비용)
    ②아니면 사장님 프로젝트 스위치(vertex_enabled·vertex_ops). 설정을 못 읽으면 False(종전 그대로)."""
    if op not in OPS:
        return False
    cid = current_cid() if cid is None else cid
    if op in MEMBER_OPS and member_info(cid):
        return True
    vals = _read_settings()
    if not gate_allows(vals.get(SETTING_ENABLED, ""), cid):
        return False
    ops = [x.strip() for x in (vals.get(SETTING_OPS) or "").split(",") if x.strip()]
    return (not ops) or (op in ops)


def model():
    return _read_settings().get(SETTING_MODEL) or DEFAULT_MODEL


def _member_client(cid, info):
    import hashlib
    fp = hashlib.sha256(str(info.get("private_key_id") or info.get("client_email")).encode()).hexdigest()[:10]
    ck = "m:%s:%s" % (cid, fp)
    if ck not in _client_cache:
        from google import genai
        from google.genai import types
        from google.oauth2 import service_account
        from shopping_shorts import usage_meter
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        cl = genai.Client(vertexai=True, project=info["project_id"], location=LOCATION, credentials=creds,
                          http_options=types.HttpOptions(timeout=180_000))
        _client_cache[ck] = usage_meter.wrap(cl, auth="vertex", pool="vertex-member", key="member:%s" % cid)
    return _client_cache[ck]


def client(cid=None):
    """Vertex 클라이언트(계측 래핑, 캐시). ★회원이 자기 서비스계정을 등록했으면 **그 프로젝트**(회원 비용),
    아니면 사장님 프로젝트(GOOGLE_APPLICATION_CREDENTIALS). 판단은 여기 한 곳(0순위-B)."""
    cid = current_cid() if cid is None else cid
    info = member_info(cid)
    if info:
        return _member_client(cid, info)
    if "cl" not in _client_cache:
        from google import genai
        from google.genai import types
        from shopping_shorts import config, usage_meter
        cl = genai.Client(vertexai=True, project=config.GCP_PROJECT, location=LOCATION,
                          http_options=types.HttpOptions(timeout=180_000))
        _client_cache["cl"] = usage_meter.wrap(cl, auth="vertex", pool="vertex", key="vertex")
    return _client_cache["cl"]


def is_member(cid=None):
    return bool(member_info(current_cid() if cid is None else cid))


def verify_sa(info, model_name=None):
    """등록 전 실제 호출 1회 — (ok, 사람이 읽을 문구). 구글 오류를 원인별로 옮긴다."""
    from google import genai
    from google.genai import types
    from google.oauth2 import service_account
    try:
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        cl = genai.Client(vertexai=True, project=info["project_id"], location=LOCATION, credentials=creds,
                          http_options=types.HttpOptions(timeout=60_000))
        r = cl.models.generate_content(model=model_name or DEFAULT_MODEL, contents="한 단어로: 하늘 색?")
        return bool((r.text or "").strip()), "확인 완료 — 이 계정으로 대본·장면매칭이 돌아갑니다"
    except Exception as e:      # noqa: BLE001
        m = str(e)
        if "SERVICE_DISABLED" in m or "has not been used" in m or "is disabled" in m:
            return False, "Vertex AI API가 꺼져 있습니다 — 구글 클라우드 콘솔에서 'Vertex AI API 사용'을 눌러 주세요"
        if "PERMISSION_DENIED" in m or "403" in m:
            return False, "권한이 없습니다 — 서비스계정 역할에 'Vertex AI 사용자(Vertex AI User)'를 추가해 주세요"
        if "BILLING" in m.upper() or "billing" in m:
            return False, "결제 계정이 연결돼 있지 않습니다 — 무료 체험($300)을 시작하거나 결제를 연결해 주세요"
        if "invalid_grant" in m or "401" in m:
            return False, "키가 폐기됐거나 잘못됐습니다 — 새 키를 내려받아 주세요"
        if "404" in m:
            return False, "모델을 찾지 못했습니다(%s) — 관리자에게 알려 주세요" % (model_name or DEFAULT_MODEL)
        return False, "확인 실패 — %s" % m[:160]


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
    cid = current_cid()
    if not on(op, cid=cid):
        return False, None
    m = model()
    t0 = time.monotonic()
    try:
        got = fn(client(cid), m)
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
