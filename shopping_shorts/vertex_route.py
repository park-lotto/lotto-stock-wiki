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

OPS = ("script_extract", "frame_script", "ai_match", "script_generate",
       # 2026-10-08(관제 159) 사장님 "내꺼 1단계부터 3단계 모두 버텍스로" — 종전엔 키풀로만 가던 호출들.
       #   vertex_ops 설정엔 안 넣는다(고객이 13시 전까지 사장님 프로젝트로 새지 않게) — 관리자·등록 회원만 탄다.
       "story", "structure", "edit_plan", "script_aux")
# script_generate = script_generate._call_json 깔때기(이야기 작가·백본·옛 생성기·판정 전부) — 2026-09-26 사장님
#   "태깅은 무료로, 대본작성과 장면매칭이 얼마나 잘되는지 해보자" → 설정 vertex_ops=script_generate,ai_match
LOCATION = "global"                 # ★us-central1은 3.6-flash 404(2026-09-25 실측) — 글로벌만
VEO_LOCATION = "us-central1"        # ★Veo는 거꾸로 global 404·us-central1 OK(2026-10-02 실측, 관제 076)
VEO_MODEL = "veo-3.1-lite-generate-001"
DEFAULT_MODEL = "gemini-3.6-flash"
INLINE_MAX_BYTES = 40 * 1024 * 1024  # 실측 32.4MB OK. 그 위는 미검증 → 키풀(파일 업로드) 경로로
SETTING_ENABLED, SETTING_OPS, SETTING_MODEL = "vertex_enabled", "vertex_ops", "vertex_model"
# ★사장님 프로젝트를 고객이 얻어 쓰는 길이 닫히는 시각(2026-10-08 사장님 "내일 13시부터는 각자 버텍스 API를
#   사용하는 걸로 / 꼭 api를 고객꺼 다 끊어 그 시간 되면", 관제 159). 이 시각부터:
#     · 관리자(사장님)      → 사장님 프로젝트, 전 op
#     · 버텍스 등록 회원    → 자기 프로젝트, 전 op(종전엔 MEMBER_OPS 둘만)
#     · 미등록 고객·주인 미상 → Vertex 안 탐(종전 무료 키풀) — 화면이 그 사실과 등록 방법을 알린다(member_notice)
#   배포 시간창(02~06시) 때문에 13시에 맞춰 배포할 수 없어 **시각을 코드가 본다**. 설정으로 옮길 수 있다
#   (vertex_owner_cutoff = ISO 시각 / "off" = 닫지 않음).
SETTING_CUTOFF = "vertex_owner_cutoff"
OWNER_CUTOFF_DEFAULT = "2026-10-08T13:00:00+09:00"
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
        for k in (SETTING_ENABLED, SETTING_OPS, SETTING_MODEL, SETTING_CUTOFF):
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
    """이 호출의 주인 — usage_meter가 정하는 값을 **읽기만** 한다(0순위-B).
    ★주인을 모르면 None(2026-10-08, 관제 159). usage_meter는 주인이 안 정해진 호출을 keyctx 기본값 0(사장님)으로
      돌려주는데, 그대로 믿으면 주인을 잃은 고객 작업이 관리자로 판정돼 사장님 유료 프로젝트를 탄다
      (실측 10-07: 프레임대본 1,190건 중 1,130건이 0번 — 예열 큐 주인은 551·352·168…). 명시된 주인만 믿는다."""
    try:
        from shopping_shorts import keyctx, usage_meter
        ctx = usage_meter.current_context()
        if ctx.get("customer_id") is None and not keyctx.owner_known():
            return None
        return usage_meter._resolve_cid(ctx)
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


def owner_cutoff():
    """사장님 프로젝트 공유가 끝나는 시각(aware datetime) 또는 None(닫지 않음). 못 읽으면 기본값."""
    from datetime import datetime
    raw = (_read_settings().get(SETTING_CUTOFF) or "").strip() or OWNER_CUTOFF_DEFAULT
    if raw.lower() in ("off", "0", "none"):
        return None
    for cand in (raw, OWNER_CUTOFF_DEFAULT):
        try:
            dt = datetime.fromisoformat(cand)
            if dt.tzinfo is None:                      # 시간대 없는 값은 KST로 본다(사장님이 말한 시각)
                from datetime import timedelta, timezone
                dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
            return dt
        except ValueError:
            print("vertex_route: %s=%r 를 시각으로 못 읽음 → 기본값" % (SETTING_CUTOFF, cand), file=sys.stderr)
    return None


def cutoff_passed(now=None):
    """지금이 차단 시각 이후인가. now는 테스트 주입용(aware datetime)."""
    from datetime import datetime, timezone
    dt = owner_cutoff()
    if dt is None:
        return False
    return (now or datetime.now(timezone.utc)) >= dt


def plan(cid=None, now=None):
    """이 계정의 1~3단계 AI가 **누구 것으로** 도는가 — 판정은 여기 한 곳(0순위-B). on()·화면 안내가 같이 읽는다.
      "member" 자기 Vertex(등록 회원) · "owner" 사장님 프로젝트(관리자) ·
      "shared" 사장님 프로젝트를 설정된 op만 얻어 씀(차단 시각 전 고객) · "free" 무료 키풀만."""
    cid = current_cid() if cid is None else cid
    if cid is not None and member_info(cid):
        return "member"
    val = _read_settings().get(SETTING_ENABLED, "")
    if cid is None:
        # 주인 미상 — 관리자로 치지 않는다. 차단 시각 전엔 종전대로(전체 스위치 "1"일 때만), 이후엔 끊는다.
        return "shared" if (val.strip() == "1" and not cutoff_passed(now)) else "free"
    if not gate_allows(val, cid):
        return "free"
    if _is_admin(cid):
        return "owner"
    return "free" if cutoff_passed(now) else "shared"


def on(op, cid=None, now=None):
    """이 op를 Vertex로 보낼까 — plan() 한 곳의 판정을 op에 적용한다. 설정을 못 읽으면 False(종전 그대로).
      member: 차단 시각 전엔 MEMBER_OPS만, 이후엔 전 op(자기 비용) · owner: 전 op ·
      shared: vertex_ops 목록만 · free: 안 탄다."""
    if op not in OPS:
        return False
    cid = current_cid() if cid is None else cid
    p = plan(cid, now=now)
    if p == "member":
        # 관리자가 자기 서비스계정을 등록해 둔 경우(실측: 사장님 0번 = 서버와 같은 프로젝트)도 "내꺼 전부"가 지켜지게.
        return op in MEMBER_OPS or cutoff_passed(now) or _is_admin(cid)
    if p == "owner":
        return True
    if p == "shared":
        ops = [x.strip() for x in (_read_settings().get(SETTING_OPS) or "").split(",") if x.strip()]
        return (not ops) or (op in ops)
    return False


MANUAL_URL = "/api_manual.html#vertex"


def notice_body(cid=None, now=None):
    """미등록 안내의 본문(2026-10-08 사장님, 관제 159) — "무료 제미나이 API는 분석이 끊기고 오래 걸릴 수 있다"와
    전환 시각을 알린다. 문구는 여기 한 곳: 하루 1회 팝업·1단계 분석 카드·3단계 시작 안내가 같이 읽는다."""
    dt = owner_cutoff()
    if dt is None or cutoff_passed(now):
        return ("지금 무료 제미나이 API로 진행 중이에요. 무료 API는 사용자가 몰리면 영상 분석이 중간에 끊기고 "
                "시간이 오래 걸릴 수 있어요. 구글 버텍스 API를 등록하면 영상 분석·대본·장면 매칭이 끊김 없이 "
                "빠르게 돌아갑니다.")
    when = "%d월 %d일 %d시" % (dt.month, dt.day, dt.hour)
    return ("지금 영상 분석은 무료 제미나이 API로 돌고 있어, 사용자가 몰리면 분석이 중간에 끊기고 시간이 오래 "
            "걸릴 수 있어요. %s부터는 각자 등록한 구글 버텍스 API로 진행되고, 등록하지 않으면 대본·장면 매칭까지 "
            "전부 무료 제미나이 API로 돌아갑니다(끊김·지연 가능). 미리 등록해 두세요." % when)


def model():
    return _read_settings().get(SETTING_MODEL) or DEFAULT_MODEL


def _member_client(cid, info, location=LOCATION):
    import hashlib
    fp = hashlib.sha256(str(info.get("private_key_id") or info.get("client_email")).encode()).hexdigest()[:10]
    ck = "m:%s:%s:%s" % (cid, fp, location)
    if ck not in _client_cache:
        from google import genai
        from google.genai import types
        from google.oauth2 import service_account
        from shopping_shorts import usage_meter
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        cl = genai.Client(vertexai=True, project=info["project_id"], location=location, credentials=creds,
                          http_options=types.HttpOptions(timeout=180_000))
        _client_cache[ck] = usage_meter.wrap(cl, auth="vertex", pool="vertex-member", key="member:%s" % cid)
    return _client_cache[ck]


def client(cid=None, location=LOCATION):
    """Vertex 클라이언트(계측 래핑, 캐시). ★회원이 자기 서비스계정을 등록했으면 **그 프로젝트**(회원 비용),
    아니면 사장님 프로젝트(GOOGLE_APPLICATION_CREDENTIALS). 판단은 여기 한 곳(0순위-B)."""
    cid = current_cid() if cid is None else cid
    info = member_info(cid)
    if info:
        return _member_client(cid, info, location)
    ck = "cl" if location == LOCATION else "cl:%s" % location
    if ck not in _client_cache:
        from google import genai
        from google.genai import types
        from shopping_shorts import config, usage_meter
        cl = genai.Client(vertexai=True, project=config.GCP_PROJECT, location=location,
                          http_options=types.HttpOptions(timeout=180_000))
        _client_cache[ck] = usage_meter.wrap(cl, auth="vertex", pool="vertex", key="vertex")
    return _client_cache[ck]


def is_member(cid=None):
    return bool(member_info(current_cid() if cid is None else cid))


VEO_NEEDS_MEMBER = "AI 장면 생성은 구글 버텍스 API를 등록해야 쓸 수 있어요 — 마이페이지 › 🔑 내 키 등록에서 등록해 주세요"


def veo_client(cid):
    """Veo(AI 장면생성)용 Vertex 클라이언트 — ★영상 생성은 텍스트보다 10~50배 비싸다.
    회원 자격증명이 있으면 **그 프로젝트**, 사장님(관리자)이면 사장님 프로젝트, 그 외는 None
    (사장님 크레딧으로 회원 영상을 대신 만들지 않는다 — 2026-09-26 사장님 확정 설계)."""
    info = member_info(cid)
    if info:
        return _member_client(cid, info, VEO_LOCATION)
    if _is_admin(cid):
        return client(cid, VEO_LOCATION)
    return None


VERTEX_NOTICE = "AI 기능을 쓰려면 내 구글 Vertex 키 등록이 필요해요"
VERTEX_NOTICE_URL = "/settings#vertexCard"      # 마이페이지 설정 › 내 구글 Vertex 연결 카드(settings.html #vertexCard)


def needs_notice(cid):
    """Vertex 미등록 안내를 띄울 회원인가 — 판정 한 곳(하루 1회 팝업·3단계 시작 안내가 같이 쓴다).
    관리자(사장님 프로젝트를 씀)는 제외, 자기 서비스계정(member_info)이 있으면 제외."""
    if _is_admin(cid):
        return False
    return not member_info(cid)      # plan()의 member·owner 와 같은 두 조건 — 설정이 꺼져도 안내는 띄운다


def veo_allowed(cid):
    """(허용, 막을 때 문구) — 화면 버튼·API·워커가 같은 판정을 쓴다(0순위-B)."""
    if member_info(cid) or _is_admin(cid):
        return True, ""
    return False, VEO_NEEDS_MEMBER


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
        if not (r.text or "").strip():
            return False, "확인 실패 — 응답이 비었습니다"
    except Exception as e:      # noqa: BLE001
        # ★구글 원문을 남긴다(2026-10-01 관제 053) — 번역문만 남기면 "역할 추가"가 결제 미연결인지 반영 대기인지 못 가른다.
        #   키 내용은 예외 문자열에 안 들어온다(요청 본문 아님). 앞 300자만.
        print("[vertex_verify] project=%s 구글원문: %s" % (info.get("project_id"), str(e)[:300].replace("\n", " ")),
              file=sys.stderr)
        return False, _explain(e, model_name)
    # Veo 권한 확인 — 영상은 만들지 않고(과금 방지) 모델 조회만 한다. 조회가 막혀도 대본은 되므로 등록은 받는다.
    try:
        vcl = genai.Client(vertexai=True, project=info["project_id"], location=VEO_LOCATION, credentials=creds,
                           http_options=types.HttpOptions(timeout=60_000))
        vcl.models.get(model=VEO_MODEL)
        return True, "확인 완료 — 대본·장면매칭과 AI 장면생성을 이 계정으로 씁니다"
    except Exception as e:      # noqa: BLE001
        return True, ("확인 완료(대본·장면매칭) — AI 장면생성 모델 조회는 실패했습니다: %s"
                      % _explain(e, VEO_MODEL))


def _explain(e, model_name=None):
    """구글 오류 → 회원이 할 일 한 줄. 판정은 여기 한 곳(등록 확인·Veo 조회가 같이 쓴다)."""
    m = str(e)
    if "SERVICE_DISABLED" in m or "has not been used" in m or "is disabled" in m:
        return "Vertex AI API가 꺼져 있습니다 — 구글 클라우드 콘솔에서 'Vertex AI API 사용'을 눌러 주세요"
    # ★결제 미연결도 HTTP 403이다 — 403 검사보다 먼저 가른다(2026-10-01 관제 053: 회원 153이 역할을 맞게 넣고도
    #   "역할 추가"만 보고 막혔다. 구글 원문: "This API method requires billing to be enabled" / reason BILLING_DISABLED).
    if "BILLING" in m.upper():
        return ("결제 계정이 연결돼 있지 않습니다 — 구글 콘솔 「결제」에서 이 프로젝트에 결제 계정을 연결해 주세요"
                "(무료 체험 $300 시작). 안내서 💳 단계")
    if "PERMISSION_DENIED" in m or "403" in m:
        return ("권한이 없습니다 — 서비스계정 역할에 'Agent Platform 사용자(옛 이름 Vertex AI 사용자)'가 있는지 확인하고, "
                "방금 넣었다면 5분 뒤 다시 눌러 주세요. 역할이 맞는데도 그대로면 「결제」에 결제 계정이 연결됐는지 보세요")
    if "invalid_grant" in m or "401" in m:
        return "키가 폐기됐거나 잘못됐습니다 — 새 키를 내려받아 주세요"
    if "404" in m:
        return "모델을 찾지 못했습니다(%s) — 관리자에게 알려 주세요" % (model_name or DEFAULT_MODEL)
    return "확인 실패 — %s" % m[:160]


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


def try_json(op, prompt, schema, what=""):
    """(시도했나, dict) — "프롬프트+스키마 → JSON" 꼴 호출의 Vertex 우선 경로(2026-10-08, 관제 159).
    스토리·구조분석·대본 보조·장면배치처럼 자기 키풀 루프만 있던 호출부가 맨 앞에서 한 줄로 부른다.
    꺼졌거나 실패·빈 결과면 (False, None) → 호출부는 종전 키풀 그대로(try_call과 같은 약속)."""
    def _fn(cl, m):
        import json
        from google.genai import types
        resp = cl.models.generate_content(
            model=m, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema))
        got = json.loads(resp.text)
        return got if isinstance(got, dict) else None
    return try_call(op, _fn, what=what or op)


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
