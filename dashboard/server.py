"""
딸깍 대시보드 — 로컬 내부 도구
버튼 하나로 이미 생성된 자동화 산출물을 한 화면에 모아 보여준다.

실행:  python dashboard/server.py
접속:  http://localhost:8090
"""
import os, sys, json, glob, re, shutil, subprocess, uuid, time, threading
from collections import deque
from datetime import datetime, timedelta
import requests

# 프로젝트 루트를 sys.path에 추가 (python dashboard/server.py 로 실행 시 pipeline import 가능하게)
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from pipeline.atoms import key_vault
from pipeline.atoms import strength_net as _strength_net

# ── 인사이트 허브: pipeline.atoms.doc_summary 지연 import ──────
try:
    from pipeline.atoms.doc_summary import (
        get_or_build_summary, _collect_atoms, _load_summary,
        _row_to_summary_dict, ensure_table as _ds_ensure_table,
        _get_conn as _ds_get_conn, _source_type_to_category,
    )
    _DS_AVAIL = True
except Exception:
    _DS_AVAIL = False

sys.stdout.reconfigure(encoding="utf-8")

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, RedirectResponse, PlainTextResponse
    from starlette.concurrency import run_in_threadpool
    import uvicorn
except ImportError:
    print("의존성 설치 필요:  pip install fastapi uvicorn")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

# 노트북별 수집 자료(md) 메모리 캐시 — Claude 직접 대화 컨텍스트로 사용
_NB_BUNDLES = {}
# 노트북별 디자인 레퍼런스(업로드 이미지에서 추출한 스타일 텍스트)
_NB_DESIGN = {}

# 만든 브리핑(노트북) 영속 레지스트리 — 이전 자료 끌어오기/교차검색용
_REGISTRY_PATH = os.path.join(ROOT, "out", "insights_notebook", "registry.json")


def _load_nb_registry():
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_nb_registry(reg):
    try:
        os.makedirs(os.path.dirname(_REGISTRY_PATH), exist_ok=True)
        with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(reg[:100], f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _nb_registry_add(entry):
    reg = [e for e in _load_nb_registry() if e.get("id") != entry.get("id")]
    reg.insert(0, entry)   # 최신이 앞
    _save_nb_registry(reg)


# 스탁브레인 스튜디오 — 사용자 커스텀 프롬프트 버튼 (추가/삭제/수정 가능)
_STUDIO_PRESETS_PATH = os.path.join(HERE, "studio_presets.json")
_DEFAULT_STUDIO_PRESETS = [
    {"id": "paper", "icon": "📰", "label": "한장요약(주린이)", "prompt": "한 장으로 핵심만, 주식 초보(주린이)도 이해하게 쉬운 비유와 큰 숫자 위주로"},
    {"id": "invest", "icon": "💹", "label": "투자관점", "prompt": "투자 관점에서 핵심 포인트·기회·리스크를 중심으로"},
    {"id": "data", "icon": "📊", "label": "데이터강조", "prompt": "수치·비교·비율을 강조해 데이터 중심으로"},
    {"id": "top5", "icon": "🎯", "label": "핵심5개", "prompt": "가장 중요한 5가지만 추려 간결하게"},
    {"id": "easy", "icon": "🗣️", "label": "쉽게설명", "prompt": "전문용어 없이 쉽게, 비유를 들어서 설명"},
    {"id": "stock", "icon": "📈", "label": "종목중심", "prompt": "언급된 종목별로 정리하고 종목명·목표가를 강조"},
]


def _load_studio_presets():
    try:
        with open(_STUDIO_PRESETS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        _save_studio_presets(_DEFAULT_STUDIO_PRESETS)
        return list(_DEFAULT_STUDIO_PRESETS)


def _save_studio_presets(presets):
    try:
        with open(_STUDIO_PRESETS_PATH, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _env_key(name):
    """환경변수 우선, 없으면 .env에서 읽기."""
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        with open(os.path.join(ROOT, ".env"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _gemini_interactive_keys():
    """대화형(리서치·이미지·비전) Gemini 키 — key_vault 'general' 그룹."""
    return key_vault.get_keys("general")


def _summary_keys():
    """뉴스요약용 키 풀 — 전 그룹(general/ingest/embed/briefing) 라이브 키 총동원(cross-group).
    소진 표시된 키는 건너뛰고, 4그룹 전부 소진일 때만 전체 키로 최후 시도.
    (이전엔 general+ingest 9개만 써서 그 두 그룹이 마르면 embed/briefing 놀아도 요약이 죽었음)"""
    live = key_vault.get_live_keys_cascade("general")  # 전 그룹 라이브, general 먼저
    if live:
        return live
    seen, out = set(), []
    for g in ("general", "ingest", "embed", "briefing"):
        for k in key_vault.get_keys(g):
            if k and k not in seen:
                seen.add(k)
                out.append(k)
    return out


def _briefing_keys():
    """실시간 시장 브리핑 종합 전용 키 풀 — key_vault 'briefing' 그룹, 없으면 요약 풀로 폴백."""
    dedicated = key_vault.get_keys("briefing")
    return dedicated or _summary_keys()


# 텍스트 생성 모델 폴백: 프리뷰(최고품질) → 안정모델. 프리뷰가 503 과부하일 때 안정모델로 자동 전환.
# 모델 폴백: 쿼터 살아있는 순. lite는 아톰화용 쿼터가 별도라 마지막 생존 보루.
# (2026-07-06: gemini-2.5-flash 무료쿼터 소진돼도 preview/lite로 요약이 살아남게)
GEMINI_TEXT_MODELS = ["gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-2.5-flash"]


import concurrent.futures as _cf
_GEMINI_EXEC = _cf.ThreadPoolExecutor(max_workers=4)  # generate_content가 응답없이 멈춰도 호출 스레드는 안 묶임


def _gemini_text(prompt, keys=None, models=None, timeout=45):
    """텍스트 생성 공용 호출 — 모델 폴백 + 키 로테이션 + 503 백오프.
    generate_content 자체엔 SDK 타임아웃이 없어(네트워크 hang 시 무한대기) 별도 스레드로 던지고
    timeout초 안에 안 끝나면 포기 — 안 그러면 이 함수를 부르는 단일 백그라운드 루프
    (_poll_briefing: 시장상황 타임라인·순환매감지 등)가 통째로 멈춘다(2026-07-08 사건).
    반환: {"ok":True,"analysis":str,"model":str} | {"error":str}"""
    try:
        from google import genai
    except Exception as e:
        return {"error": f"google-genai 없음: {str(e)[:120]}"}
    keys = keys or _gemini_interactive_keys()
    if not keys:
        return {"error": ".env에 GEMINI_API_KEY 없음"}
    models = models or GEMINI_TEXT_MODELS
    last = ""
    for model in models:
        for k in keys:
            client = key_vault.get_client_for_key(k)  # key_vault 캐시 재사용, 매 호출 새 클라이언트 생성 안 함
            try:
                fut = _GEMINI_EXEC.submit(client.models.generate_content, model=model, contents=prompt)
                resp = fut.result(timeout=timeout)
                txt = (resp.text or "").strip()
                if txt:
                    return {"ok": True, "analysis": txt, "model": model}
                last = "빈 응답"
                continue   # 다음 키
            except _cf.TimeoutError:
                last = f"응답시간초과({timeout}s)"
                continue   # 다음 키 (버려진 워커는 executor에 남지만 호출 스레드는 진행)
            except Exception as e:
                last = str(e)
                if any(s in last for s in ("503", "UNAVAILABLE", "overloaded")):
                    break   # 503은 모델 전체 과부하 → 키 순회 중단, 곧장 다음 모델로 폴백
                # 429(키 쿼터 소진)·기타 오류 → 다음 키 시도
    # 사용자에게는 원본 API 에러(JSON 뭉치)를 그대로 보여주지 않고 짧은 안내문으로 변환
    if "429" in last or "RESOURCE_EXHAUSTED" in last:
        friendly = "오늘 AI 요약 무료 쿼터를 다 써서 잠시 쉬어갑니다(자동 복구)"
    elif any(s in last for s in ("503", "UNAVAILABLE", "overloaded")):
        friendly = "AI 서버가 잠시 붐빕니다. 잠시 후 다시 시도해주세요"
    elif last == "빈 응답":
        friendly = "AI가 빈 응답을 반환했습니다"
    else:
        friendly = "AI 요약을 만들지 못했습니다"
    return {"error": friendly}


SIGNAL_DIR = os.path.join(ROOT, "output", "signal")
OUT_DIR = os.path.join(ROOT, "out")
AGENTS_DIR = os.path.join(HERE, "agents")
ASSETS_DIR = os.path.join(HERE, "assets")
ATOMS_DIR = os.path.join(ROOT, "pipeline", "atoms")

# 크롤링 소스 레지스트리 (카테고리 → 파일·스키마)
#  telegram: { 이름: {type, sector, trust} } / 그 외: { 이름·키워드: trust }
SOURCE_REGISTRIES = {
    "telegram": {"file": "telegram_channels.json", "label": "텔레그램", "rich": True},
    "youtube":  {"file": "youtube_registry.json",  "label": "유튜브",   "rich": False},
    "blog":     {"file": "blog_registry.json",     "label": "블로그",   "rich": False},
    "news":     {"file": "news_registry.json",     "label": "뉴스키워드", "rich": False},
}
STUDIO_DIR = os.path.join(ROOT, "out", "studio")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from nlm_bridge import (
    _nlm_exe, _run_nlm, _friendly_nlm_err, _build_notebook_bundle,
    _valid_period, _tokenize_query, _nb_cat_of, _CAT_LABEL,
    _nb_period_min, _nb_fetch_rows, _nb_scope_label, _nlm_relogin_locked,
    create_notebook, add_source_file, add_source_urls, notebook_query as nlm_notebook_query,
    create_report as nlm_create_report,
    _BRAND_DESIGN, start_manual_login, manual_login_status,
)
try:
    from studio_pipeline import generate_briefing, generate_picks  # noqa: E402
except (ImportError, SystemExit):
    generate_briefing = None  # type: ignore
    generate_picks = None  # type: ignore

sys.path.insert(0, os.path.join(ROOT, "scripts", "yt_agents"))
try:
    from hot_clips import find_hot_clips  # noqa: E402
except (ImportError, SystemExit):
    find_hot_clips = None  # type: ignore

try:
    from plan_stage import run_plan_stage  # noqa: E402
except (ImportError, SystemExit):
    run_plan_stage = None  # type: ignore

try:
    import hot_clips as _hotclips  # noqa: E402  (find_and_rank/classify)
    import clip_teardown as _teardown  # noqa: E402  (teardown/mix)
except (ImportError, SystemExit):
    _hotclips = None  # type: ignore
    _teardown = None  # type: ignore

# quote_extractor는 독립 블록 — 이웃(clip_teardown 등)이 없어도(main엔 없음) 살아있게
try:
    import quote_extractor as _qe  # noqa: E402  (extract_stream/parse_video_id)
except (ImportError, SystemExit):
    _qe = None  # type: ignore

try:
    import global_api  # noqa: E402
except (ImportError, Exception):
    global_api = None  # type: ignore

try:
    import kis_ws  # noqa: E402
    kis_ws.start()  # 백그라운드 WebSocket 시작
except (ImportError, Exception):
    kis_ws = None  # type: ignore

try:
    from sector_heatmap import build_heatmap, parse_etf_bar, build_heatmap_tab, TAB_GROUPS, WATCH_FILE  # noqa: E402
except (ImportError, Exception):
    build_heatmap = None        # type: ignore
    parse_etf_bar = None        # type: ignore
    build_heatmap_tab = None    # type: ignore
    TAB_GROUPS = []             # type: ignore
    WATCH_FILE = None           # type: ignore

# claude CLI 위치 (PATH 우선, 없으면 알려진 경로)
CLAUDE_BIN = shutil.which("claude") or r"C:\Users\TheRose\.local\bin\claude.exe"
AGENT_TIMEOUT = 240  # 초

app = FastAPI(title="딸깍 대시보드")


@app.get("/api/insights/studio_presets")
def api_studio_presets_list():
    return JSONResponse(content={"presets": _load_studio_presets()})


@app.post("/api/insights/studio_presets/add")
async def api_studio_presets_add(req: Request):
    b = await req.json()
    icon = (b.get("icon") or "✨").strip()[:4] or "✨"
    label = (b.get("label") or "").strip()[:20]
    prompt_text = (b.get("prompt") or "").strip()
    if not label or not prompt_text:
        return JSONResponse(content={"ok": False, "error": "제목/프롬프트 필요"}, status_code=400)
    presets = _load_studio_presets()
    presets.append({"id": "custom_" + uuid.uuid4().hex[:10], "icon": icon, "label": label, "prompt": prompt_text})
    _save_studio_presets(presets)
    return JSONResponse(content={"ok": True, "presets": presets})


@app.post("/api/insights/studio_presets/update")
async def api_studio_presets_update(req: Request):
    b = await req.json()
    pid = (b.get("id") or "").strip()
    presets = _load_studio_presets()
    found = False
    for p in presets:
        if p.get("id") == pid:
            if b.get("icon"):
                p["icon"] = b["icon"].strip()[:4]
            if b.get("label"):
                p["label"] = b["label"].strip()[:20]
            if b.get("prompt"):
                p["prompt"] = b["prompt"].strip()
            found = True
            break
    if not found:
        return JSONResponse(content={"ok": False, "error": "항목 없음"}, status_code=404)
    _save_studio_presets(presets)
    return JSONResponse(content={"ok": True, "presets": presets})


@app.post("/api/insights/studio_presets/delete")
async def api_studio_presets_delete(req: Request):
    b = await req.json()
    pid = (b.get("id") or "").strip()
    presets = [p for p in _load_studio_presets() if p.get("id") != pid]
    _save_studio_presets(presets)
    return JSONResponse(content={"ok": True, "presets": presets})


# ── 로그인 게이트 v2 (2026-08-06) — 사용자 계정제(구글 OAuth) + 관리자 ──
# 숏템메이커(shopping_shorts/app.py) 인증 모델 이식:
#   · HMAC 서명 세션쿠키 "uid:expiry:sig" (기존 단일 공유토큰 → 사용자별)
#   · 구글 OAuth 가입/로그인 → users 테이블(SQLite). 일반 사용자는 /market·/insights만.
#   · 기존 DASH_USER/DASH_PASS 로그인은 uid 0(관리자)로 하위호환.
import hmac as _hmac, hashlib as _hashlib, sqlite3 as _sqlite3, secrets as _secrets
import urllib.parse as _urlparse
from datetime import timezone as _tzutc

DASH_USER = os.environ.get("DASH_USER", "admin")
DASH_PASS = os.environ.get("DASH_PASS", "")        # 비어있고 OAuth도 미설정이면 인증 OFF(로컬 개발)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8090/auth/google/callback")
_ADMIN_EMAILS = {"parklotto12@gmail.com"}


def _load_dash_secret() -> str:
    """세션쿠키 HMAC 키. env 최우선, 없으면 db/.session_secret에 랜덤 생성해 영속화.
    ★소스에 기본값을 박지 않는다 — 예전 하드코딩 기본값("stockbrain-local-secret")은
    env 한 줄만 빠뜨리면 누구나 쿠키를 위조할 수 있는 구멍이었다."""
    env = os.environ.get("DASH_SECRET", "").strip()
    if env:
        return env
    path = os.path.join(ROOT, "db", ".session_secret")
    try:
        with open(path, encoding="utf-8") as f:
            existing = f.read().strip()
        if existing:
            return existing
    except OSError:
        pass
    generated = _secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(generated)
    except OSError:
        pass  # 영속화 실패해도 이번 프로세스는 랜덤키로 뜬다(재기동 시 재로그인될 뿐).
    return generated


DASH_SECRET = _load_dash_secret()
_AUTH_ON = bool(DASH_PASS) or bool(GOOGLE_CLIENT_ID)
if not _AUTH_ON:
    print("⚠️ [보안] DASH_PASS·GOOGLE_CLIENT_ID 모두 미설정 → 인증 OFF(전원 관리자). "
          "외부 공개 배포라면 반드시 설정하세요.", file=sys.stderr)

_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일
_AUTH_ALLOW = ("/login", "/api/login", "/logout", "/favicon.ico", "/healthz",
               "/api/push_market_flow",       # 외부 푸시(자체 검증) — 쿠키 없이 옴
               "/auth/google/login", "/auth/google/callback")

# ── users 저장소 (SQLite) ──
_USERS_DB = os.path.join(ROOT, "db", "users.db")


def _users_conn():
    os.makedirs(os.path.dirname(_USERS_DB), exist_ok=True)
    conn = _sqlite3.connect(_USERS_DB, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        google_sub TEXT UNIQUE,
        email TEXT,
        admin INTEGER DEFAULT 0,
        approved INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        created TEXT)""")
    # 기존 DB 마이그레이션(컬럼 없으면 추가) — 승인제(2026-08-06): Gemini API 비용 보호
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    for c in ("approved", "blocked"):
        if c not in cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {c} INTEGER DEFAULT 0")
    return conn


def _get_or_create_google_user(sub: str, email):
    with _users_conn() as conn:
        row = conn.execute("SELECT id, email FROM users WHERE google_sub=?", (sub,)).fetchone()
        if row:
            if email and email != row[1]:
                conn.execute("UPDATE users SET email=? WHERE id=?", (email, row[0]))
            return row[0], False
        cur = conn.execute("INSERT INTO users(google_sub, email, created) VALUES(?,?,?)",
                           (sub, email, datetime.now(_tzutc.utc).isoformat()))
        return cur.lastrowid, True


def _get_user(uid: int):
    try:
        with _users_conn() as conn:
            row = conn.execute("SELECT id, email, admin, approved, blocked FROM users WHERE id=?",
                               (uid,)).fetchone()
        return ({"id": row[0], "email": row[1] or "", "admin": bool(row[2]),
                 "approved": bool(row[3]), "blocked": bool(row[4])} if row else None)
    except Exception:
        return None


def _is_admin(uid) -> bool:
    if uid == 0:            # legacy DASH_USER/DASH_PASS 로그인
        return True
    u = _get_user(uid)
    if not u:
        return False
    return u["admin"] or u["email"].lower() in _ADMIN_EMAILS


# ── 세션 쿠키 (uid:expiry:sig) ──
def _sign_session(uid: int, expiry: int) -> str:
    payload = f"{uid}:{expiry}"
    sig = _hmac.new(DASH_SECRET.encode(), payload.encode(), _hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_session(cookie: str):
    """쿠키 → uid(int) 또는 None(위조·만료·형식오류)."""
    if not cookie:
        return None
    try:
        uid_s, exp_s, sig = cookie.split(":")
        expiry = int(exp_s)
    except ValueError:
        return None
    if datetime.now(_tzutc.utc).timestamp() > expiry:
        return None
    expected = _hmac.new(DASH_SECRET.encode(), f"{uid_s}:{exp_s}".encode(), _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(sig, expected):
        return None
    try:
        return int(uid_s)
    except ValueError:
        return None


def _set_session_cookie(response, uid: int):
    expiry = int(datetime.now(_tzutc.utc).timestamp()) + _COOKIE_MAX_AGE
    response.set_cookie("dash_auth", _sign_session(uid, expiry),
                        max_age=_COOKIE_MAX_AGE, httponly=True, samesite="lax")


# ── 일반 사용자 접근범위: 홈(/home) + 히트맵(/market) + 인사이트(/insights)만 ──
_USER_PAGES = ("/home", "/market", "/insights")
_USER_EXACT_ALLOW = {"/api/me", "/topbar.js"}   # 상단바·내정보(모든 로그인 사용자)
_USER_API_PREFIX = (
    "/api/insights/", "/api/catalysts",
    # market.html이 쓰는 API들
    "/api/news_feed", "/api/heatmap_tab", "/api/stock_supply_batch", "/api/sector_detail",
    "/api/sector_summary", "/api/etf_bar", "/api/market_briefing", "/api/market_flow",
    "/api/sector_custom", "/api/sector_names", "/api/sector_stocks", "/api/stock_search",
    "/api/watchlist", "/api/stock_summary", "/api/taerini_stock", "/api/taerini_consensus",
    "/api/stock_candles", "/api/briefing/pending",
)
# 운영자 전용(외부 사용자 차단): 노트북LM 세션·위키/유튜브 반출·프리셋 편집·브리핑 발행
_USER_DENY_PREFIX = (
    "/api/insights/nlm_", "/api/insights/to_wiki", "/api/insights/to_youtube",
    "/api/insights/studio_presets", "/api/briefing/publish_pending",
)
# 공유 상태를 바꾸는 엔드포인트는 GET만 허용(외부 사용자가 관리자 데이터를 못 바꾸게)
_USER_GET_ONLY_PREFIX = ("/api/sector_custom", "/api/watchlist", "/api/insights/history_save",
                         "/api/insights/notebook_forget")


def _user_allowed(path: str, method: str) -> bool:
    if path in _USER_PAGES or path == "/logout" or path in _USER_EXACT_ALLOW:
        return True
    if any(path.startswith(p) for p in _USER_DENY_PREFIX):
        return False
    if any(path.startswith(p) for p in _USER_GET_ONLY_PREFIX) and method != "GET":
        return False
    return any(path.startswith(p) for p in _USER_API_PREFIX)


_LOGIN_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>STOCK BRAIN 로그인</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif}
.box{background:#16161c;border:1px solid #2a2a30;border-radius:14px;padding:32px 28px;width:300px}
h1{color:#d4af37;font-size:18px;margin:0 0 18px;text-align:center;letter-spacing:1px}
input{width:100%;box-sizing:border-box;margin:6px 0;padding:11px 12px;background:#0e0e12;
border:1px solid #333;border-radius:8px;color:#eee;font-size:14px}
button{width:100%;margin-top:12px;padding:11px;background:#d4af37;color:#111;border:0;
border-radius:8px;font-weight:700;font-size:14px;cursor:pointer}
a.gbtn{display:block;text-align:center;margin-bottom:14px;padding:12px;background:#fff;color:#1a1a1a;
border-radius:8px;font-weight:700;font-size:14px;text-decoration:none}
.or{color:#555;font-size:11px;text-align:center;margin:4px 0 8px}
.err{color:#e74c3c;font-size:12px;text-align:center;margin-top:10px;min-height:14px}
details{margin-top:6px}summary{color:#666;font-size:12px;cursor:pointer;text-align:center}</style></head>
<body><div class=box>
<h1>⚡ STOCK BRAIN</h1>
__GOOGLE__
<details><summary>관리자 로그인</summary>
<form method=post action=/api/login>
<input name=user placeholder=아이디 autocomplete=username>
<input name=pass type=password placeholder=비밀번호 autocomplete=current-password>
<button>로그인</button></form></details>
<div class=err>__ERR__</div></div></body></html>"""

_GOOGLE_BTN = '<a class=gbtn href="/auth/google/login">구글로 시작하기</a>'


@app.get("/login", response_class=HTMLResponse)
def _login_page(e: str = ""):
    g = _GOOGLE_BTN if GOOGLE_CLIENT_ID else '<div class=or>구글 로그인 미설정</div>'
    return _LOGIN_HTML.replace("__GOOGLE__", g).replace("__ERR__", e or "")


@app.post("/api/login")
async def _api_login(req: Request):
    body = (await req.body()).decode("utf-8", "ignore")
    form = _urlparse.parse_qs(body)
    u = (form.get("user") or [""])[0]
    p = (form.get("pass") or [""])[0]
    if DASH_PASS and u == DASH_USER and p == DASH_PASS:
        r = RedirectResponse("/home", status_code=303)
        _set_session_cookie(r, 0)
        return r
    return RedirectResponse("/login?e=" + _urlparse.quote("아이디 또는 비밀번호가 틀렸습니다"), status_code=303)


@app.get("/logout")
def _logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("dash_auth")
    return r


# ── 구글 OAuth (숏템메이커와 동일 플로우: state 쿠키 → code → userinfo) ──
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _google_fetch_identity(code):
    """code → {sub, email} 또는 None."""
    tok = requests.post(_GOOGLE_TOKEN_URL, data={
        "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"}, timeout=10)
    if tok.status_code != 200:
        return None
    access = tok.json().get("access_token")
    if not access:
        return None
    ui = requests.get(_GOOGLE_USERINFO_URL, headers={"Authorization": "Bearer " + access}, timeout=10)
    if ui.status_code != 200:
        return None
    d = ui.json()
    if not d.get("sub"):
        return None
    email = d.get("email") if d.get("email_verified") is True else None
    return {"sub": d["sub"], "email": email}


@app.get("/auth/google/login")
def _google_login():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return HTMLResponse("<h3 style='font-family:sans-serif'>구글 로그인이 아직 설정되지 않았어요.</h3>",
                            status_code=503)
    state = _secrets.token_urlsafe(24)
    q = _urlparse.urlencode({
        "client_id": GOOGLE_CLIENT_ID, "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code", "scope": "openid email profile",
        "state": state, "access_type": "online", "prompt": "select_account"})
    r = RedirectResponse(_GOOGLE_AUTH_URL + "?" + q, status_code=303)
    r.set_cookie("g_state", state, max_age=600, httponly=True, samesite="lax")
    return r


@app.get("/auth/google/callback")
def _google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/login?e=" + _urlparse.quote("구글 로그인이 취소됐어요"), status_code=303)
    cookie_state = request.cookies.get("g_state")
    try:
        state_ok = bool(cookie_state) and _hmac.compare_digest(cookie_state, state)
    except (TypeError, ValueError):
        state_ok = False       # 비-ASCII state 주입 등 → fail-closed
    if not state_ok:
        return RedirectResponse("/login?e=" + _urlparse.quote("보안 검증 실패 — 다시 시도해주세요"), status_code=303)
    try:
        ident = _google_fetch_identity(code)
    except Exception:
        ident = None
    if not ident:
        return RedirectResponse("/login?e=" + _urlparse.quote("구글 인증에 실패했어요"), status_code=303)
    uid, _created = _get_or_create_google_user(ident["sub"], ident.get("email"))
    if _created and not _is_admin(uid):     # 새 가입 → 사장님 텔레그램 쪽지(승인 대기 알림)
        try:
            _weather_tg(f"📥 STOCK BRAIN 새 가입: {ident.get('email') or '(이메일 비공개)'}\n"
                        f"승인 대기중입니다 → https://stockbrain1.duckdns.org/admin")
        except Exception:
            pass
    r = RedirectResponse("/home", status_code=303)
    _set_session_cookie(r, uid)
    r.delete_cookie("g_state")
    return r


@app.get("/healthz")
def _healthz():
    return {"ok": True}


# ── 승인제 (2026-08-06) — Gemini API 비용 보호: 가입해도 관리자 승인 전엔 사용 불가 ──
_PENDING_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>승인 대기중 · STOCK BRAIN</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif;color:#eee}
.box{background:#16161c;border:1px solid #2a2a30;border-radius:14px;padding:36px 32px;width:320px;text-align:center}
h1{color:#d4af37;font-size:17px;margin:0 0 14px}p{color:#9aa;font-size:13px;line-height:1.7;margin:0 0 18px}
a{color:#667;font-size:12px}</style></head>
<body><div class=box><h1>__TITLE__</h1><p>__MSG__</p><a href=/logout>로그아웃</a></div></body></html>"""


def _pending_response(user, path: str):
    """미승인·차단 사용자 응답. API는 403 JSON, 페이지는 안내 화면."""
    blocked = bool(user.get("blocked"))
    if path.startswith("/api/"):
        return JSONResponse({"error": "blocked" if blocked else "pending_approval"}, status_code=403)
    if blocked:
        html = _PENDING_HTML.replace("__TITLE__", "이용이 제한된 계정입니다") \
                            .replace("__MSG__", "관리자에게 문의해주세요.")
    else:
        html = _PENDING_HTML.replace("__TITLE__", "가입 승인 대기중입니다 ⏳") \
                            .replace("__MSG__", "관리자가 승인하면 바로 이용할 수 있어요.<br>승인 후 새로고침해주세요.")
    return HTMLResponse(html, status_code=403)


# ── 회원 관리 (/admin — 관리자 전용) ──
_ADMIN_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>회원 관리 · STOCK BRAIN</title>
<style>body{margin:0;background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif;color:#eee;padding:28px}
h1{color:#d4af37;font-size:19px;margin:0 0 4px}.sub{color:#778;font-size:12px;margin-bottom:20px}
table{border-collapse:collapse;width:100%;max-width:860px}th,td{padding:9px 12px;font-size:13px;text-align:left;
border-bottom:1px solid #23232a}th{color:#889;font-weight:600;font-size:12px}
.b{border:0;border-radius:7px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;margin-right:6px}
.ok{background:#1f6f43;color:#dff5e7}.no{background:#333;color:#bbb}.ban{background:#6f1f1f;color:#f5dfdf}
.tag{font-size:11px;border-radius:6px;padding:2px 8px;font-weight:700}
.t-wait{background:#4a3b12;color:#ffd863}.t-ok{background:#143c26;color:#6fe0a0}.t-ban{background:#3c1414;color:#e06f6f}
.t-adm{background:#1c2740;color:#8fb4ff}a{color:#667;font-size:12px}</style></head>
<body><h1>회원 관리</h1><div class=sub>승인해야 이용 가능(Gemini API 비용 보호) · <a href=/>홈</a></div>
<table><thead><tr><th>이메일</th><th>가입일</th><th>상태</th><th>작업</th></tr></thead>
<tbody id=rows></tbody></table>
<script>
async function load(){
  const r=await fetch('/api/admin/users');const d=await r.json();
  document.getElementById('rows').innerHTML=(d.users||[]).map(u=>{
    const st=u.admin?'<span class="tag t-adm">관리자</span>'
      :u.blocked?'<span class="tag t-ban">차단됨</span>'
      :u.approved?'<span class="tag t-ok">승인됨</span>':'<span class="tag t-wait">승인 대기</span>';
    const btns=u.admin?'':(
      (u.approved?'<button class="b no" onclick="upd('+u.id+',{approved:0})">승인 해제</button>'
                 :'<button class="b ok" onclick="upd('+u.id+',{approved:1})">승인</button>')+
      (u.blocked ?'<button class="b no" onclick="upd('+u.id+',{blocked:0})">차단 해제</button>'
                 :'<button class="b ban" onclick="upd('+u.id+',{blocked:1})">차단</button>'));
    return '<tr><td>'+(u.email||'(이메일 비공개)')+'</td><td>'+(u.created||'').slice(0,10)+
           '</td><td>'+st+'</td><td>'+btns+'</td></tr>';
  }).join('')||'<tr><td colspan=4 style="color:#667">아직 가입자가 없습니다</td></tr>';
}
async function upd(id,patch){
  await fetch('/api/admin/user_update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(Object.assign({id:id},patch))});load();
}
load();
</script></body></html>"""


@app.get("/admin", response_class=HTMLResponse)
def _admin_page():
    return _ADMIN_HTML   # 접근 제어는 미들웨어(_user_allowed에 없음 → 관리자만 통과)


# ── 사용자 홈(/home) — 블랙 첫화면: 히트맵·인사이트 두 개만, 관리자면 관리 버튼 추가 ──
_HOME_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>STOCK BRAIN</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#000;color:#eee;
font-family:system-ui,'Noto Sans KR',sans-serif;display:flex;flex-direction:column}
main{flex:1;display:flex;align-items:center;justify-content:center;padding:24px}
.wrap{width:100%;max-width:760px}
h1{color:#d4af37;font-size:22px;letter-spacing:2px;text-align:center;margin:0 0 34px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:560px){.cards{grid-template-columns:1fr}}
a.card{display:block;background:#0e0e12;border:1px solid #23232a;border-radius:18px;
padding:34px 26px;text-decoration:none;color:#eee;transition:.15s;text-align:center}
a.card:hover{border-color:#d4af37;transform:translateY(-2px)}
.ico{font-size:34px;margin-bottom:12px}.t{font-size:17px;font-weight:800;margin-bottom:6px}
.d{font-size:12.5px;color:#889;line-height:1.6}</style></head>
<body><div id=topbar></div><script src=/topbar.js></script>
<main><div class=wrap><h1>⚡ STOCK BRAIN</h1>
<div class=cards>
<a class=card href=/market><div class=ico>🔥</div><div class=t>섹터 히트맵</div>
<div class=d>업종·테마별 자금 흐름을<br>한눈에</div></a>
<a class=card href=/insights><div class=ico>🧠</div><div class=t>인사이트</div>
<div class=d>리포트·뉴스 요약과<br>시장 브리핑</div></a>
</div></div></main></body></html>"""


@app.get("/home", response_class=HTMLResponse)
def _home_page():
    return _HOME_HTML


@app.get("/api/me")
def _api_me(request: Request):
    uid = _verify_session(request.cookies.get("dash_auth", ""))
    if uid is None:
        if not _AUTH_ON:
            return {"ok": True, "admin": True, "email": "(로컬)"}
        return JSONResponse({"ok": False}, status_code=401)
    u = _get_user(uid) or {}
    return {"ok": True, "admin": _is_admin(uid), "email": u.get("email", "관리자" if uid == 0 else "")}


# 공용 상단바 — 사용자: 히트맵·인사이트만 / 관리자: +관리자·회원관리 버튼 (market·insights·home에 주입)
_TOPBAR_JS = """(function(){
fetch('/api/me').then(function(r){return r.ok?r.json():null}).then(function(me){
  if(!me||!me.ok)return;
  var bar=document.createElement('div');
  bar.id='sb-topbar';
  var s=document.createElement('style');
  s.textContent='#sb-topbar{position:fixed;top:0;left:0;right:0;z-index:99999;height:46px;'+
   'background:#000;border-bottom:1px solid #1e1e24;display:flex;align-items:center;gap:6px;'+
   'padding:0 14px;font-family:system-ui,"Noto Sans KR",sans-serif}'+
   '#sb-topbar .lg{color:#d4af37;font-weight:800;font-size:14px;letter-spacing:1px;'+
   'text-decoration:none;margin-right:14px}'+
   '#sb-topbar a.nv{color:#aab;font-size:13px;font-weight:700;text-decoration:none;'+
   'padding:6px 12px;border-radius:8px}'+
   '#sb-topbar a.nv:hover,#sb-topbar a.nv.on{background:#16161c;color:#fff}'+
   '#sb-topbar .sp{flex:1}'+
   '#sb-topbar a.ad{color:#8fb4ff;font-size:12px;font-weight:700;text-decoration:none;'+
   'border:1px solid #2a3a5a;border-radius:8px;padding:5px 11px;margin-left:6px}'+
   '#sb-topbar a.out{color:#667;font-size:12px;text-decoration:none;margin-left:10px}'+
   'body{padding-top:46px!important}';
  document.head.appendChild(s);
  var p=location.pathname;
  var h='<a class=lg href=/home>⚡ STOCK BRAIN</a>'+
    '<a class="nv'+(p=='/market'?' on':'')+'" href=/market>🔥 히트맵</a>'+
    '<a class="nv'+(p=='/insights'?' on':'')+'" href=/insights>🧠 인사이트</a>'+
    '<span class=sp></span>';
  if(me.admin){h+='<a class=ad href=/>⚙ 관리자 페이지</a><a class=ad href=/admin>👥 회원관리</a>';}
  h+='<a class=out href=/logout>로그아웃</a>';
  bar.innerHTML=h;
  document.body.prepend(bar);
});
})();"""


@app.get("/topbar.js")
def _topbar_js():
    return PlainTextResponse(_TOPBAR_JS, media_type="application/javascript")


@app.get("/api/admin/users")
def _api_admin_users():
    with _users_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, admin, approved, blocked, created FROM users ORDER BY id DESC").fetchall()
    return {"users": [{"id": r[0], "email": r[1], "admin": bool(r[2]),
                       "approved": bool(r[3]), "blocked": bool(r[4]), "created": r[5]} for r in rows]}


@app.post("/api/admin/user_update")
async def _api_admin_user_update(req: Request):
    b = await req.json()
    uid = int(b.get("id", 0))
    sets, vals = [], []
    for k in ("approved", "blocked"):
        if k in b:
            sets.append(f"{k}=?"); vals.append(1 if b[k] else 0)
    if not uid or not sets:
        return JSONResponse({"ok": False, "error": "id/필드 없음"}, status_code=400)
    with _users_conn() as conn:
        if conn.execute("SELECT admin FROM users WHERE id=?", (uid,)).fetchone() == (1,):
            return JSONResponse({"ok": False, "error": "관리자는 변경 불가"}, status_code=400)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals + [uid])
    return {"ok": True}


@app.middleware("http")
async def _auth_guard(request: Request, call_next):
    if not _AUTH_ON:
        response = await call_next(request)
        _no_store(request, response)
        return response
    path = request.url.path
    if path in _AUTH_ALLOW or path.startswith("/static"):
        return await call_next(request)
    uid = _verify_session(request.cookies.get("dash_auth", ""))
    if uid is None:
        if path.startswith("/api/"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return RedirectResponse("/login")
    if not _is_admin(uid):
        user = _get_user(uid)
        if user is None:               # 세션은 유효한데 계정이 삭제됨 → 재로그인
            r = RedirectResponse("/login")
            r.delete_cookie("dash_auth")
            return r
        if user["blocked"] or not user["approved"]:   # 승인제: 승인 전·차단이면 전부 차단
            if path == "/logout":
                return await call_next(request)
            return _pending_response(user, path)
        if not _user_allowed(path, request.method):
            if path.startswith("/api/"):
                return JSONResponse({"error": "forbidden"}, status_code=403)
            return RedirectResponse("/home")   # 일반 사용자는 관리 대시보드 대신 블랙 홈으로
    response = await call_next(request)
    _no_store(request, response)
    return response


def _no_store(request: Request, response):
    """API·HTML 응답 브라우저 캐싱 방지 — 새로고침해도 옛날 데이터 뜨는 문제 재발 방지 (2026-07-02)."""
    path = request.url.path
    if path.startswith("/static"):
        return
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"

# ── 부팅 시 데이터소스 가용성 점검 (재발 방지: 조용히 0값만 나오던 문제 재현 시 즉시 로그로 드러나게) ──
def _check_datasource_availability():
    import sys as _sys
    _sd = os.path.join(ROOT, "scripts")
    if _sd not in _sys.path:
        _sys.path.insert(0, _sd)
    try:
        import kiwoom_api as _kw
        _kw._token()
        print("[boot] kiwoom_api: OK (서버에 키움 키 등록됨)", flush=True)
    except Exception as e:
        print("=" * 70, flush=True)
        print("[boot][WARN] kiwoom_api 인증 실패.", flush=True)
        print(f"  사유: {e}", flush=True)
        print("  키움 앱키는 특정 IP만 '지정단말기'로 허용한다(키움 개발자센터 IP 등록 페이지).", flush=True)
        print("  2026-07-06 서버 IP(3.39.179.148)를 등록해서 정상화한 적 있음 — 이 경고가 다시", flush=True)
        print("  뜨면 등록이 풀렸거나 서버 IP가 바뀐 것. market_flow의 J/Q_investor·prog·", flush=True)
        print("  prog_series·get_stock_supply가 전부 kiwoom_api라 이 경고 뜨는 동안은 0으로 샌다.", flush=True)
        print("  → 위 endpoint를 만지거나 새 기능을 kiwoom_api로 연결할 때는 반드시 서버에서", flush=True)
        print("    실데이터 응답을 확인할 것. 종목분봉(get_stock_candles)은 이미 KIS 폴백 있음.", flush=True)
        print("=" * 70, flush=True)

_check_datasource_availability()


# ── 투자자/프로그램 시계열 누적 (장 중 15분 폴링) ──────────────────
_FLOW: dict = {
    "J": {"investor": deque(maxlen=400), "program": deque(maxlen=400)},  # 1분×400 ≈ 장중 09:00~15:30 풀커버
    "Q": {"investor": deque(maxlen=400), "program": deque(maxlen=400)},
}

from briefing_detect import detect_alerts as _briefing_detect_alerts
from briefing_store import load_briefing as _briefing_load, append_briefing_item as _briefing_append
from briefing_collect import recent_news_headlines as _briefing_news, recent_market_atoms as _briefing_atoms
from briefing_synth import build_briefing_prompt as _briefing_build_prompt, parse_briefing_response as _briefing_parse
from briefing_detect import compute_index_shape as _compute_index_shape
from briefing_collect import pick_notable_movers as _pick_notable_movers, recent_atoms_for_stock as _recent_atoms_for_stock, recent_topick_mentions as _recent_topick_mentions
from briefing_synth import build_insight_prompt as _build_insight_prompt, parse_insight_response as _parse_insight_response
from briefing_store import set_insight as _briefing_set_insight

BRIEFING_PATH = os.path.join(ROOT, "output", "market_briefing.json")
ATOMS_DB_PATH = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
_briefing_last_metrics = {"data": None}   # 직전 폴링의 market_flow 스냅샷 (임계치 비교 기준선)
_briefing_last_ai_call = {"ts": 0.0}      # 마지막 Gemini 호출 시각 (쿨다운용)
_insight_last_run = {"ts": 0.0}   # 마지막 인사이트 갱신 시각(15분 독립 타이머)

_flow_day = {"date": None}  # 마지막으로 데이터를 쌓은 거래일 (자정 넘어 서버가 계속 떠있어도 매일 09:00에 새로 시작하도록)
_FLOW_PERSIST = os.path.join(ROOT, "output", "flow_history.json")

def _save_flow():
    """투자자·프로그램 누적 이력을 디스크에 저장 (서버 재시작해도 09:00부터의 데이터 보존).
    KIS엔 투자자매매동향 시계열 단건조회 API가 없어 폴링 누적이 유일한 방법이라, 재시작 손실을 막으려면 영속화 필수."""
    try:
        os.makedirs(os.path.dirname(_FLOW_PERSIST), exist_ok=True)
        data = {"date": _flow_day["date"], "flow": {
            mkt: {"investor": list(_FLOW[mkt]["investor"]), "program": list(_FLOW[mkt]["program"])}
            for mkt in ("J", "Q")}}
        tmp = _FLOW_PERSIST + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, _FLOW_PERSIST)   # 원자적 교체 (쓰다 죽어도 기존 파일 안 깨짐)
    except Exception:
        pass

def _load_flow():
    """저장된 이력이 '오늘' 것이면 복원 (서버 재시작 후에도 그래프가 09:00부터 이어짐)."""
    try:
        with open(_FLOW_PERSIST, encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") != today:
            return   # 다른 날 데이터 → 무시 (매일 새로 시작)
        for mkt in ("J", "Q"):
            for snap in (data.get("flow", {}).get(mkt, {}).get("investor") or []):
                _FLOW[mkt]["investor"].append(snap)
            for snap in (data.get("flow", {}).get(mkt, {}).get("program") or []):
                _FLOW[mkt]["program"].append(snap)
        _flow_day["date"] = today
    except Exception:
        pass

_load_flow()   # 부팅 시 오늘자 이력 복원 (재시작 후 그래프 이어짐)

def _poll_flow():
    """장 중(09:00~16:00) 1분마다 투자자·프로그램 순매수 스냅샷 수집.
    서버 시작 즉시 첫 수집 (initial=True), 이후 1분 간격. 매 수집마다 디스크에 영속화.
    매일 09:00 첫 수집 시 전날 데이터를 지워 항상 '오늘 09:00부터'로 시작한다
    (서버 재시작 없이 자정을 넘겨도 그래프가 어제 데이터와 섞이지 않게).
    """
    initial = True
    while True:
        try:
            now = datetime.now()
            _mins = now.hour * 60 + now.minute
            today_str = now.strftime("%Y-%m-%d")
            if _mins >= 540 and _flow_day["date"] != today_str:
                for mkt in ("J", "Q"):
                    _FLOW[mkt]["investor"].clear()
                    _FLOW[mkt]["program"].clear()
                _flow_day["date"] = today_str
            # 09:00~15:35만 수집 → 이후엔 동결(15:30 종가 모양 유지). 저녁엔 마지막값 그대로 표시.
            if initial or (540 <= _mins <= 935):
                import kis_api as _kis
                for mkt in ("J", "Q"):
                    try:
                        iv = _kis.get_market_investor(mkt)
                        if iv.get("외인") or iv.get("기관") or iv.get("개인"):  # all-zero=조회실패 → 스킵(스파이크 방지)
                            _FLOW[mkt]["investor"].append(iv)
                    except Exception:
                        pass
                    try:
                        pg = _kis.get_program_trade(mkt)
                        if pg.get("차익") or pg.get("비차익") or pg.get("합계"):  # all-zero=조회실패 → 스킵
                            _FLOW[mkt]["program"].append(pg)
                    except Exception:
                        pass
                initial = False
                _save_flow()   # 매 수집마다 영속화 → 재시작해도 이력 유지
        except Exception:
            pass
        time.sleep(60)  # 1분 (투자자매매동향은 KIS에 시계열 단건조회 API가 없어 폴링으로만 누적 가능)

_poll_thread = threading.Thread(target=_poll_flow, daemon=True)
_poll_thread.start()


# ── 데이터 로더 ───────────────────────────────────────────

def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _file_mtime(path):
    if not os.path.exists(path):
        return None
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")


def load_morning():
    """장 시작 전 데이터: 신호 스냅샷 + 백테스트 + 미국증시 브리핑"""
    snap_path = os.path.join(SIGNAL_DIR, "signal_snapshot.json")
    bt_path = os.path.join(SIGNAL_DIR, "backtest_summary.json")

    snapshot = _load_json(snap_path) or {}
    backtest = _load_json(bt_path) or {}

    # 종목 9점표 — score 내림차순 상위 40개만
    stage3 = snapshot.get("stage3", {})
    stocks = sorted(stage3.get("stocks", []), key=lambda s: s.get("score", 0), reverse=True)
    top_stocks = stocks[:40]

    # 최신 미국증시 브리핑 마크다운
    briefing_files = sorted(glob.glob(os.path.join(OUT_DIR, "briefing_*_미국증시.md")), reverse=True)
    briefing_md, briefing_name, briefing_date = "", "", ""
    if briefing_files:
        path = briefing_files[0]
        briefing_name = os.path.basename(path)
        m = re.search(r"briefing_(\d{8})_", briefing_name)
        if m:
            d = m.group(1)
            briefing_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        with open(path, encoding="utf-8") as f:
            briefing_md = f.read()

    return {
        "snapshot_date": snapshot.get("date", ""),
        "snapshot_mtime": _file_mtime(snap_path),
        "stage1": snapshot.get("stage1", {}),
        "stage2": snapshot.get("stage2", {}),
        "top_stocks": top_stocks,
        "stock_total": len(stocks),
        "backtest": backtest,
        "briefing_md": briefing_md,
        "briefing_name": briefing_name,
        "briefing_date": briefing_date,
    }


# ── 라우트 ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/net", response_class=HTMLResponse)
def net_page():
    """촘촘한 그물 대시보드 — 미귀속 강세 랭킹 + 촘촘함 지표 + 원인추적."""
    with open(os.path.join(HERE, "net.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/api/morning")
def api_morning():
    return JSONResponse(content=load_morning())


@app.get("/api/intraday")
def api_intraday():
    return JSONResponse(content={"status": "준비중", "message": "2단계: 한투 API 연결 예정"})


@app.get("/api/close")
def api_close():
    return JSONResponse(content={"status": "준비중", "message": "3단계: 마감 정리 예정"})


@app.get("/assets/{fname}")
def asset(fname: str):
    """캐릭터 그림 등 정적 파일 제공. 없으면 404 → 프론트는 이모지로 대체."""
    p = os.path.normpath(os.path.join(ASSETS_DIR, fname))
    if p.startswith(ASSETS_DIR) and os.path.exists(p):
        return FileResponse(p)
    return JSONResponse(content={"error": "not found"}, status_code=404)


# ── 크롤링 소스 관리 ───────────────────────────────────────

def _registry_path(cat):
    reg = SOURCE_REGISTRIES.get(cat)
    if not reg:
        return None
    return os.path.join(ATOMS_DIR, reg["file"])


def _load_registry(cat):
    p = _registry_path(cat)
    if p and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_registry(cat, data):
    p = _registry_path(cat)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/sources", response_class=HTMLResponse)
def sources_page():
    with open(os.path.join(HERE, "sources.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/api/sources")
def api_sources_list():
    out = {}
    for cat, reg in SOURCE_REGISTRIES.items():
        out[cat] = {"label": reg["label"], "rich": reg["rich"],
                    "items": _load_registry(cat)}
    return JSONResponse(content=out)


# ── 🧠 브레인 (채널 사고 복제) ─────────────────────────────
PEOPLE_JSON = os.path.join(ROOT, "pipeline", "people", "people.json")


@app.get("/brain", response_class=HTMLResponse)
def brain_page():
    with open(os.path.join(HERE, "brain.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/api/brain/people")
def api_brain_people():
    from pipeline.people.brain_view import list_people
    return JSONResponse(content=list_people())


@app.post("/api/brain/people/add")
async def api_brain_add(request: Request):
    b = await request.json()
    name = (b.get("name") or "").strip()
    sources = [s.strip() for s in (b.get("sources") or []) if s.strip()]
    trust = (b.get("trust") or "B").strip() or "B"
    if not name or not sources:
        return JSONResponse(content={"ok": False, "error": "이름과 source_name 필요"}, status_code=400)
    with open(PEOPLE_JSON, encoding="utf-8") as f:
        reg = json.load(f)
    if name in reg:
        return JSONResponse(content={"ok": False, "error": "이미 존재하는 채널"}, status_code=400)
    reg[name] = {
        "display": name, "sources": sources, "trust": trust,
        "brain_page": f"wiki/people/{name}.md",
    }
    with open(PEOPLE_JSON, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    return JSONResponse(content={"ok": True, "name": name})


@app.get("/api/brain/{person}/materials")
def api_brain_materials(person: str, q: str = None):
    """3. 섹터·종목 재료 꺼내쓰기 — q로 종목/섹터 검색."""
    from pipeline.people.brain_view import materials
    return JSONResponse(content=materials(person, query=q, days=180, limit=80))


@app.get("/api/brain/{person}/trend")
def api_brain_trend(person: str):
    """퍼널 적중률 추세 (자동 수렴 확인)."""
    from pipeline.people.track import trend
    return JSONResponse(content=trend(person))


@app.get("/api/brain/{person}/routine_today")
def api_brain_routine_today(person: str):
    """오늘의 루틴 재구성 — 정적 루틴을 오늘 데이터로 채움."""
    from pipeline.people.brain_view import routine_today
    r = routine_today(person)
    if r is None:
        return JSONResponse(content={"available": False})
    return JSONResponse(content={"available": True, **r})


@app.get("/api/brain/{person}/ask")
def api_brain_ask(person: str, q: str = ""):
    """질의 엔진: '이 종목 태린이라면 어떻게 볼까?'"""
    from pipeline.people.persona import stock_verdict
    if not q.strip():
        return JSONResponse(content={"error": "종목명을 입력하세요"}, status_code=400)
    return JSONResponse(content=stock_verdict(person, q.strip()))


@app.get("/api/brain/{person}/market_verdict")
def api_brain_market_verdict(person: str):
    """질의 엔진: '지금 시장 비중 높일까/낮출까?'"""
    from pipeline.people.persona import market_verdict
    return JSONResponse(content=market_verdict(person))


@app.get("/api/brain/{person}/selection")
def api_brain_selection(person: str):
    """복사: 그의 규칙으로 오늘의 종목선정 재현."""
    from pipeline.people.brain_view import today_selection
    try:
        return JSONResponse(content=today_selection(person))
    except KeyError:
        return JSONResponse(content={"error": "unknown person"}, status_code=404)


@app.get("/api/brain/{person}")
def api_brain_person(person: str):
    from pipeline.people.brain_view import person_view
    try:
        return JSONResponse(content=person_view(person))
    except KeyError:
        return JSONResponse(content={"error": "unknown person"}, status_code=404)


def _normalize_source(cat, raw):
    """입력이 링크면 카테고리에 맞는 키로 변환 + 링크 보존. 이름이면 그대로.
    반환 (key, url)."""
    raw = (raw or "").strip()
    is_url = raw.startswith(("http://", "https://", "t.me/", "www.")) or "/" in raw and "." in raw
    if not is_url:
        return raw, ""
    url = raw if raw.startswith("http") else "https://" + raw
    if cat == "blog":
        m = re.search(r"(?:rss\.)?blog\.naver\.com/([A-Za-z0-9_\-]+)", raw) \
            or re.search(r"/([A-Za-z0-9_\-]+)\.xml", raw)
        if m:
            return m.group(1), f"https://blog.naver.com/{m.group(1)}"
    elif cat == "telegram":
        m = re.search(r"t\.me/([A-Za-z0-9_+]+)", raw)
        if m:
            return m.group(1), f"https://t.me/{m.group(1)}"
    elif cat == "youtube":
        m = re.search(r"youtube\.com/@([A-Za-z0-9_.\-]+)", raw) \
            or re.search(r"youtube\.com/(?:channel|c|user)/([A-Za-z0-9_\-]+)", raw)
        if m:
            return m.group(1), url
    # 일반: 마지막 경로조각을 키로
    seg = raw.split("?")[0].rstrip("/").split("/")[-1]
    return (seg or raw), url


# 서버(크롤러) 자동 등록용
SSH_KEY = r"C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem"
# IP는 바뀔 수 있다(2026-08-05 인스타 scraping_warning 회피로 교체) —
# 서버 주소는 SERVER_HOST 하나로만 바꾼다.
SSH_HOST = os.getenv("SERVER_HOST", "ubuntu@3.39.179.148")
REMOTE_ADD = "python3 /home/ubuntu/kmong/crawling_bot/add_source.py"


# 크롤봇 스크립트(대시보드와 같은 서버에 존재). 있으면 SSH 없이 직접 실행.
LOCAL_ADD = "/home/ubuntu/kmong/crawling_bot/add_source.py"
LOCAL_DEL = "/home/ubuntu/kmong/crawling_bot/del_source.py"


def _crawlbot_cmd(local_script, remote_cmd):
    """서버(리눅스)면 로컬 직접 실행, 로컬 PC면 SSH.
    크롤봇이 대시보드와 같은 머신에 있어 SSH가 불필요·불가(Windows 키경로)라 매번 실패하던 문제 해결."""
    if os.path.exists(local_script):
        return ["python3", local_script]
    return ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=20", SSH_HOST, remote_cmd]


def server_register(cat, name, url):
    """서버 config.yaml에 소스 자동 등록 (add_source.py 호출). best-effort."""
    payload = json.dumps({"category": cat, "name": name, "url": url})
    cmd = _crawlbot_cmd(LOCAL_ADD, REMOTE_ADD)
    try:
        r = subprocess.run(cmd, input=payload.encode("utf-8"),
                           capture_output=True, timeout=35)
        out = (r.stdout or b"").decode("utf-8", "replace").strip()
        try:
            return json.loads(out.splitlines()[-1])
        except Exception:
            err = out or (r.stderr or b"").decode("utf-8", "replace")
            return {"ok": False, "error": err[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/sources/add")
async def api_sources_add(req: Request):
    b = await req.json()
    cat = b.get("category")
    raw = (b.get("name") or "").strip()
    if cat not in SOURCE_REGISTRIES or not raw:
        return JSONResponse(content={"ok": False, "error": "카테고리/이름 누락"})
    key, url = _normalize_source(cat, raw)
    if not key:
        return JSONResponse(content={"ok": False, "error": "이름/링크 해석 실패"})
    d = _load_registry(cat)
    trust = b.get("trust") or "B"
    if SOURCE_REGISTRIES[cat]["rich"]:  # telegram
        val = {"type": (b.get("type") or "general"),
               "sector": (b.get("sector") or "").strip(),
               "trust": trust}
        if url:
            val["url"] = url
        d[key] = val
    else:
        d[key] = {"trust": trust, "url": url} if url else trust
    _save_registry(cat, d)
    # 서버 크롤러에도 자동 등록 (뉴스는 url 불필요, 그 외는 url 있을 때만)
    server = None
    if cat == "news" or url:
        server = await run_in_threadpool(server_register, cat, key, url)
    return JSONResponse(content={"ok": True, "count": len(d), "key": key,
                                 "url": url, "server": server})


def server_unregister(cat, name, url):
    """서버 config.yaml 에서 소스 제거 (del_source.py). best-effort."""
    payload = json.dumps({"category": cat, "name": name, "url": url})
    cmd = _crawlbot_cmd(LOCAL_DEL, "python3 /home/ubuntu/kmong/crawling_bot/del_source.py")
    try:
        r = subprocess.run(cmd, input=payload.encode("utf-8"),
                           capture_output=True, timeout=35)
        out = (r.stdout or b"").decode("utf-8", "replace").strip()
        try:
            return json.loads(out.splitlines()[-1])
        except Exception:
            return {"ok": False, "error": out[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/sources/delete")
async def api_sources_delete(req: Request):
    b = await req.json()
    cat = b.get("category")
    name = b.get("name")
    if cat not in SOURCE_REGISTRIES:
        return JSONResponse(content={"ok": False, "error": "카테고리 오류"})
    d = _load_registry(cat)
    if name not in d:
        return JSONResponse(content={"ok": False, "error": "항목 없음"})
    v = d.get(name)
    url = v.get("url", "") if isinstance(v, dict) else ""
    del d[name]
    _save_registry(cat, d)
    server = await run_in_threadpool(server_unregister, cat, name, url)
    return JSONResponse(content={"ok": True, "count": len(d), "server": server})


@app.post("/api/sources/rename")
async def api_sources_rename(req: Request):
    b = await req.json()
    cat = b.get("category")
    old_name = b.get("old_name", "").strip()
    new_name = b.get("new_name", "").strip()
    new_url  = b.get("url", "").strip()
    if cat not in SOURCE_REGISTRIES:
        return JSONResponse(content={"ok": False, "error": "카테고리 오류"})
    if not old_name or not new_name:
        return JSONResponse(content={"ok": False, "error": "이름 없음"})
    d = _load_registry(cat)
    if old_name not in d:
        return JSONResponse(content={"ok": False, "error": "항목 없음"})
    if new_name in d and new_name != old_name:
        return JSONResponse(content={"ok": False, "error": "이미 존재하는 이름"})
    # 기존 값 보존하면서 키 교체
    v = d.pop(old_name)
    if isinstance(v, str):
        v = {"trust": v}
    if new_url:
        v["url"] = new_url
    elif "url" in v and not new_url:
        pass  # 빈 문자열이면 기존 URL 유지
    d[new_name] = v
    _save_registry(cat, d)
    # 서버 크롤러에도 새 이름/URL 반영 (add_source.py가 upsert)
    server = None
    final_url = v.get("url", "") if isinstance(v, dict) else ""
    if cat == "news" or final_url:
        server = await run_in_threadpool(server_register, cat, new_name, final_url)
    return JSONResponse(content={"ok": True, "server": server})


CRAWL_DIR = "/home/ubuntu/kmong/crawling_bot"


def server_crawl(cat, only):
    """서버에서 해당 카테고리/채널 크롤을 백그라운드로 시작 (즉시 반환)."""
    import shlex
    only = only or ""
    remote = ("cd " + CRAWL_DIR + " && nohup python3 crawl_run.py "
              + shlex.quote(cat) + " " + shlex.quote(only)
              + " >> logs/manual_crawl.log 2>&1 </dev/null &")
    # 서버(리눅스)면 직접 실행, 로컬 PC면 SSH
    if os.path.exists(os.path.join(CRAWL_DIR, "crawl_run.py")):
        cmd = ["bash", "-c", remote]
    else:
        cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
               "-o", "ConnectTimeout=20", SSH_HOST, remote]
    try:
        subprocess.run(cmd, capture_output=True, timeout=25)
        return {"ok": True, "started": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/crawl/run")
async def api_crawl_run(req: Request):
    b = {}
    try:
        b = await req.json()
    except Exception:
        pass
    cat = b.get("category")
    only = (b.get("only") or "").strip()
    if cat not in ("telegram", "youtube", "blog", "news", "market"):
        return JSONResponse(content={"ok": False, "error": "카테고리 오류"})
    return JSONResponse(content=await run_in_threadpool(server_crawl, cat, only))


# ── 골-루프: 대기 브리핑(이상징후 에스컬레이션) 조회·수동 발행 ──
@app.get("/api/briefing/pending")
def api_briefing_pending():
    """이상징후로 대기 중인 아침 브리핑 메타(날짜·사유). 없으면 빈 객체."""
    try:
        from scripts.goal_loop import pending as _gl_pending
        p = _gl_pending.read() or {}
    except Exception:
        p = {}
    return JSONResponse(content={"date": p.get("date"), "reasons": p.get("reasons", [])} if p else {})


@app.post("/api/briefing/publish_pending")
async def api_briefing_publish():
    """대기 브리핑을 채널로 수동 발행."""
    from scripts.goal_loop import publish as _gl_publish
    return JSONResponse(content=await run_in_threadpool(_gl_publish.publish_pending))


# 실제 크롤링 폴더 (소스 자동 감지용)
CRAWL_DIR = r"C:\Users\TheRose\crawling_bot_data"


def scan_actual_sources():
    """크롤링 폴더를 훑어 실제 들어오는 소스를 카테고리별로 집계 {소스: 글수}."""
    res = {"telegram": {}, "news": {}, "blog": {}, "youtube": {}}
    if not os.path.isdir(CRAWL_DIR):
        return res

    def bump(cat, name):
        name = name.strip()
        if name:
            res[cat][name] = res[cat].get(name, 0) + 1

    for d in os.listdir(CRAWL_DIR):
        if not re.match(r"\d{4}-\d{2}-\d{2}$", d):
            continue
        base = os.path.join(CRAWL_DIR, d)
        # 텔레그램: 날짜_채널.md
        for f in glob.glob(os.path.join(base, "telegram", "*.md")):
            m = re.match(r"\d{4}-\d{2}-\d{2}_(.+)", os.path.basename(f)[:-3])
            if m:
                bump("telegram", m.group(1))
        # 뉴스: [묶음]키워드_kw
        for f in glob.glob(os.path.join(base, "news", "*.md")):
            m = re.search(r"\[묶음\](.+?)_kw", os.path.basename(f))
            if m:
                bump("news", m.group(1))
        # 블로그: 파일 내부 naver blog id
        for f in glob.glob(os.path.join(base, "blog", "*.md")):
            try:
                t = open(f, encoding="utf-8", errors="replace").read(800)
            except Exception:
                continue
            m = re.search(r"blog\.naver\.com/([A-Za-z0-9_]+)/", t)
            if m:
                bump("blog", m.group(1))
        # 유튜브: 파일 내부 **채널** 필드
        for f in glob.glob(os.path.join(base, "youtube", "*.md")):
            try:
                t = open(f, encoding="utf-8", errors="replace").read(400)
            except Exception:
                continue
            m = re.search(r"\*\*채널\*\*\s*[:：]\s*(.+)", t)
            if m:
                bump("youtube", m.group(1))
    return res


@app.post("/api/sources/sync")
def api_sources_sync():
    """실제 크롤링 소스 중 등록 안 된 것을 자동 등록(신뢰도 B). 추가된 목록 반환."""
    actual = scan_actual_sources()
    report = {}
    for cat, items in actual.items():
        d = _load_registry(cat)
        added = []
        for name in items:
            if name not in d:
                d[name] = {"type": "general", "sector": "", "trust": "B"} \
                    if SOURCE_REGISTRIES[cat]["rich"] else "B"
                added.append(name)
        if added:
            _save_registry(cat, d)
        report[cat] = {"added": added, "actual": len(items), "registered": len(d)}
    return JSONResponse(content={"ok": True, "report": report})


# ── 크롤 결과 수동 받아오기 (서버 → 로컬, 증분) ──────────────
CLIENT_DIR = r"C:\Users\TheRose\crawling_bot_client"
CLIENT_CFG = os.path.join(CLIENT_DIR, "client_config.json")
CLIENT_STATE = os.path.join(CLIENT_DIR, "client_state.json")


def _crawl_last_sync():
    try:
        with open(CLIENT_STATE, encoding="utf-8") as f:
            return json.load(f).get("last_sync")
    except Exception:
        return None


def pull_crawl() -> dict:
    """서버에서 last_sync 이후 새 파일만 다운로드 (client.py sync_once 로직 복제, stdlib)."""
    import urllib.request as _u, urllib.parse as _up
    try:
        with open(CLIENT_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        return {"ok": False, "error": f"client_config 읽기 실패: {e}"}
    try:
        with open(CLIENT_STATE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {"last_sync": None}

    base, key, save = cfg["server_url"], cfg["api_key"], cfg["save_path"]
    since = state.get("last_sync")

    def _get(url, timeout):
        return _u.urlopen(_u.Request(url, headers={"x-api-key": key}), timeout=timeout)

    url = base + "/files" + (f"?since={_up.quote(since)}" if since else "")
    try:
        files = json.loads(_get(url, 15).read().decode("utf-8")).get("files", [])
    except Exception as e:
        return {"ok": False, "error": f"서버 연결 실패: {e}", "last_sync": since}

    downloaded = 0
    for fi in files:
        try:
            path = fi["path"]
            sp = os.path.join(save, path.replace("/", os.sep))
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            if os.path.exists(sp):
                sm = fi.get("modified", "")
                lm = datetime.fromtimestamp(os.path.getmtime(sp)).isoformat()
                if sm and sm <= lm:
                    continue
            data = _get(base + "/download/" + _up.quote(path), 30).read()
            if sp.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                with open(sp, "wb") as f:
                    f.write(data)
            else:
                with open(sp, "w", encoding="utf-8") as f:
                    f.write(data.decode("utf-8", "replace"))
            downloaded += 1
        except Exception:
            continue

    state["last_sync"] = datetime.now().isoformat()
    try:
        with open(CLIENT_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass
    return {"ok": True, "downloaded": downloaded, "last_sync": state["last_sync"]}


@app.get("/api/crawl/status")
def api_crawl_status():
    return JSONResponse(content={"last_sync": _crawl_last_sync()})


@app.post("/api/crawl/pull")
async def api_crawl_pull():
    return JSONResponse(content=await run_in_threadpool(pull_crawl))


# ── 에이전트 (claude CLI 헤드리스) ─────────────────────────

def run_agent(role: str, request_text: str) -> dict:
    """역할 .md를 지침으로 claude -p 를 프로젝트 루트에서 실행, 결과 텍스트 반환."""
    role_path = os.path.join(AGENTS_DIR, role + ".md")
    if not os.path.exists(role_path):
        return {"ok": False, "error": f"역할 파일 없음: {role}.md"}
    if not (CLAUDE_BIN and os.path.exists(CLAUDE_BIN)):
        return {"ok": False, "error": f"claude 실행파일을 찾을 수 없음: {CLAUDE_BIN}"}

    with open(role_path, encoding="utf-8") as f:
        role_prompt = f.read()

    prompt = role_prompt + "\n\n---\n## 지금 처리할 요청\n" + request_text
    cmd = [CLAUDE_BIN, "-p", prompt, "--permission-mode", "bypassPermissions"]
    started = datetime.now()
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True,
            encoding="utf-8", errors="replace", timeout=AGENT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"시간 초과 ({AGENT_TIMEOUT}초). 요청을 더 좁혀보세요."}
    except Exception as e:
        return {"ok": False, "error": f"실행 오류: {e}"}

    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        return {"ok": False, "error": (proc.stderr or "알 수 없는 오류").strip()[:800]}

    elapsed = round((datetime.now() - started).total_seconds(), 1)
    return {"ok": True, "result": out, "elapsed": elapsed,
            "ran_at": started.strftime("%Y-%m-%d %H:%M")}


@app.post("/api/agent")
async def api_agent(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    role = body.get("role", "시황부장")
    request_text = body.get("request") or "오늘 자 시황 브리핑 초안을 작성해줘."
    result = await run_in_threadpool(run_agent, role, request_text)
    return JSONResponse(content=result)


def run_chat(role: str, message: str, session_id: str | None) -> dict:
    """멀티턴 대화. 첫 턴이면 역할지침+세션생성, 이후엔 --resume 으로 기억 이어감."""
    if not (CLAUDE_BIN and os.path.exists(CLAUDE_BIN)):
        return {"ok": False, "error": f"claude 실행파일을 찾을 수 없음: {CLAUDE_BIN}"}

    if session_id:
        # 기존 대화 이어가기 (역할은 이미 세션 안에 있음)
        prompt = message
        cmd = [CLAUDE_BIN, "-p", prompt, "--resume", session_id,
               "--permission-mode", "bypassPermissions"]
    else:
        # 첫 턴: 새 세션 + 역할지침 주입
        role_path = os.path.join(AGENTS_DIR, role + ".md")
        if not os.path.exists(role_path):
            return {"ok": False, "error": f"역할 파일 없음: {role}.md"}
        with open(role_path, encoding="utf-8") as f:
            role_prompt = f.read()
        session_id = str(uuid.uuid4())
        prompt = role_prompt + "\n\n---\n## 사용자 메시지\n" + message
        cmd = [CLAUDE_BIN, "-p", prompt, "--session-id", session_id,
               "--permission-mode", "bypassPermissions"]

    started = datetime.now()
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, capture_output=True,
            encoding="utf-8", errors="replace", timeout=AGENT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"시간 초과 ({AGENT_TIMEOUT}초).", "session_id": session_id}
    except Exception as e:
        return {"ok": False, "error": f"실행 오류: {e}", "session_id": session_id}

    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        return {"ok": False, "error": (proc.stderr or "알 수 없는 오류").strip()[:800],
                "session_id": session_id}

    elapsed = round((datetime.now() - started).total_seconds(), 1)
    return {"ok": True, "reply": out, "session_id": session_id, "elapsed": elapsed}


@app.post("/api/chat")
async def api_chat(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    role = body.get("role", "시황부장")
    message = (body.get("message") or "").strip()
    session_id = body.get("session_id") or None
    if not message:
        return JSONResponse(content={"ok": False, "error": "메시지가 비어 있음"})
    result = await run_in_threadpool(run_chat, role, message, session_id)
    return JSONResponse(content=result)


# ── 섹터 히트맵 ───────────────────────────────────────────
@app.get("/market", response_class=HTMLResponse)
def market_page():
    p = os.path.join(HERE, "market.html")
    if not os.path.exists(p):
        return "<h1>market.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    # 폰 캐시로 옛 버전 남는 것 방지 (매번 최신 서빙)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


_last_good_etf: dict = {"data": None, "ts": 0.0}   # ETF바 마지막 정상 응답(KIS 순간실패 시 유지)
_ETF_PERSIST = os.path.join(ROOT, "output", "etf_bar_last_good.json")

def _save_etf_persist():
    """ETF바 마지막 정상 데이터를 디스크에 저장. 장마감·주말처럼 KIS가 응답 안 하는 동안
    서비스가 재시작되면 인메모리 _last_good_etf가 비어 폴백조차 못 하는 문제 방지."""
    try:
        os.makedirs(os.path.dirname(_ETF_PERSIST), exist_ok=True)
        tmp = _ETF_PERSIST + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"data": _last_good_etf["data"], "ts": _last_good_etf["ts"]}, f, ensure_ascii=False)
        os.replace(tmp, _ETF_PERSIST)
    except Exception:
        pass

def _load_etf_persist():
    """부팅 시 디스크에 저장된 마지막 정상 ETF 데이터 복원 (날짜 무관 — 어제/금요일 것이라도 복원해서
    KIS 완전불통 상황에도 '마지막으로 알려진 값'을 바로 보여줄 수 있게 함)."""
    try:
        with open(_ETF_PERSIST, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("data"):
            _last_good_etf["data"] = data["data"]
            _last_good_etf["ts"] = data.get("ts", 0.0)
    except Exception:
        pass

_load_etf_persist()   # 부팅 시 복원 (재시작·KIS 불통 겹쳐도 직전 값 유지)

_etf_kis_down = {"ts": 0.0}      # 마지막으로 KIS 라이브 조회가 전멸(전종목 price=0)한 시각
_ETF_DOWN_COOLDOWN = 60           # 이 시간 안엔 재시도 없이 바로 last-good 서빙 (요청마다 수십초 대기 방지)

def _kis_reachable(timeout=2.5) -> bool:
    """KIS 서버 포트에 빠르게(수 초 내) 붙는지만 확인하는 저비용 프로브.
    2026-07-04 KIS 서버 완전장애 때 개별 시세/분봉 콜(8초 타임아웃 × 19개 ETF)이 누적되어
    /api/etf_bar 응답이 2분+ 걸리던 문제 발견 — 라이브 시도 전에 먼저 이걸로 죽었는지 확인하고,
    죽었으면 바로 폴백으로 넘어가 응답을 즉시 준다."""
    import socket
    try:
        with socket.create_connection(("openapi.koreainvestment.com", 9443), timeout=timeout):
            return True
    except Exception:
        return False

def _etf_static_fallback(etfs: list) -> list:
    """최후 폴백(3순위): 로컬 감시종목 엑셀(parse_etf_bar의 ohlc)에 이미 들어있는 종가.
    이 엑셀은 수동/일별 갱신이라 며칠씩 밀려있을 수 있음(2026-07-04 KIS 장애 때 실제로 7/1치였음) —
    네이버 폴백(_etf_naver_fallback)이 실패한 개별 종목에 대해서만 최후 수단으로 쓴다."""
    out = []
    for e in etfs:
        ohlc = e.get("ohlc") or []
        close = ohlc[-1] if ohlc else 0
        out.append({**e, "price": int(close), "change_rate": 0.0, "bars": []})
    return out

def _watch_file_asof_ts() -> float:
    """감시종목 엑셀(WATCH_FILE)의 수정시각 — 정적 폴백(_etf_static_fallback)이 '몇 일자 종가'인지
    프론트에 표시하기 위한 근거 시각. 파일이 없으면 현재시각으로 대체(라벨 생략보단 나음)."""
    try:
        return os.path.getmtime(WATCH_FILE)
    except Exception:
        return time.time()

def _naver_last_session(code: str, tf_min: int = 15, count: int = 120):
    """naver_api.last_session 얇은 래퍼(기존 호출부 이름 유지용) — 실제 구현은
    scripts/naver_api.py에 있어 히트맵(sector_heatmap.build_heatmap)과도 공유한다."""
    import naver_api
    return naver_api.last_session(code, tf_min=tf_min, count=count)

def _naver_sessions_batch(codes: list, workers: int = 8) -> dict:
    """naver_api.last_session_batch 얇은 래퍼(기존 호출부 이름 유지용)."""
    import naver_api
    return naver_api.last_session_batch(codes, workers=workers)

def _etf_naver_fallback(etfs: list):
    """ETF바용 래퍼: last-good 캐시도 없을 때 네이버로 등락률·스파크라인 재구성.
    개별 종목 실패 시에만 그 종목을 엑셀 종가로 메꾼다. 반환: (etfs, asof_epoch)."""
    got = _naver_sessions_batch([e["code"] for e in etfs])
    out, max_ts = [], 0
    for e in etfs:
        r = got.get(e["code"])
        if r:
            out.append({**e, "price": r["price"], "change_rate": r["change_rate"], "bars": r["bars"]})
            max_ts = max(max_ts, r["asof"])
        else:
            ohlc = e.get("ohlc") or []
            close = ohlc[-1] if ohlc else 0
            out.append({**e, "price": int(close), "change_rate": 0.0, "bars": []})
    return out, (max_ts or _watch_file_asof_ts())

def _etf_fallback_response(etfs: list) -> JSONResponse:
    """last-good 캐시도 없을 때 쓰는 공용 폴백: 네이버(신선, 1순위) 시도 후 실패하면 로컬 엑셀(최후)."""
    try:
        data, asof = _etf_naver_fallback(etfs)
        return JSONResponse(content=data,
                             headers={"X-Etf-Stale": "1", "X-Etf-Static": "1", "X-Etf-Asof": str(asof)})
    except Exception:
        return JSONResponse(content=_etf_static_fallback(etfs),
                             headers={"X-Etf-Stale": "1", "X-Etf-Static": "1", "X-Etf-Asof": str(_watch_file_asof_ts())})

@app.get("/api/etf_bar")
def api_etf_bar():
    if parse_etf_bar is None:
        return JSONResponse(content={"error": "parse_etf_bar 없음"}, status_code=503)
    try:
        # 프리워밍 캐시 hit → 즉시 반환
        cached = _prewarm_cache.get("etf_bar")
        if cached and time.time() - cached["ts"] < _PREWARM_TTL:
            return JSONResponse(content=cached["data"])

        etfs = parse_etf_bar()   # 로컬 엑셀 파싱(네트워크 불필요) — 폴백용 종가도 여기 이미 들어있음

        # 최근에 KIS 라이브 조회가 전멸했거나(쿨다운) 지금 붙지도 않으면(프로브) —
        # 매 요청마다 8초×종목수 만큼 기다리지 않고 바로 폴백.
        recently_down = time.time() - _etf_kis_down["ts"] < _ETF_DOWN_COOLDOWN
        if recently_down or not _kis_reachable():
            _etf_kis_down["ts"] = time.time()
            if _last_good_etf["data"]:
                return JSONResponse(content=_last_good_etf["data"],
                                     headers={"X-Etf-Stale": "1", "X-Etf-Asof": str(_last_good_etf["ts"])})
            return _etf_fallback_response(etfs)

        import kis_api
        from concurrent.futures import ThreadPoolExecutor, as_completed
        codes = [e["code"] for e in etfs]

        # 현재가 + 15분봉 병렬 조회
        prices   = kis_api.get_prices_batch_parallel(codes)
        bars_map = {c: [] for c in codes}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = {ex.submit(kis_api.get_minutebar, c, 1): c for c in codes}
            for fut in as_completed(futs):
                c = futs[fut]
                try:
                    bars_map[c] = fut.result()
                except Exception:
                    bars_map[c] = []

        for e in etfs:
            p = prices.get(e["code"]) or {}
            e["change_rate"] = float(p.get("change_rate", 0) or 0)
            e["price"]       = int(p.get("price", 0) or 0)
            e["bars"]        = bars_map.get(e["code"], [])
        # 정상(가격 있는 ETF 존재)일 때만 캐시·last-good 갱신, 열화면 직전 정상 서빙(그래프 유지)
        if any((e.get("price") or 0) > 0 for e in etfs):
            _prewarm_cache["etf_bar"] = {"data": etfs, "ts": time.time()}
            _last_good_etf["data"] = etfs
            _last_good_etf["ts"] = time.time()
            _save_etf_persist()
            return JSONResponse(content=etfs)
        _etf_kis_down["ts"] = time.time()
        if _last_good_etf["data"]:
            return JSONResponse(content=_last_good_etf["data"],
                                 headers={"X-Etf-Stale": "1", "X-Etf-Asof": str(_last_good_etf["ts"])})
        return _etf_fallback_response(etfs)
    except Exception as e:
        _etf_kis_down["ts"] = time.time()
        if _last_good_etf["data"]:
            return JSONResponse(content=_last_good_etf["data"],
                                 headers={"X-Etf-Stale": "1", "X-Etf-Asof": str(_last_good_etf["ts"])})
        try:
            return _etf_fallback_response(parse_etf_bar())
        except Exception:
            return JSONResponse(content={"error": str(e)}, status_code=500)


_sv_cache: dict = {"data": None, "ts": 0.0}
_SV_TTL = 600   # 10분

def _fetch_etf_constituents(code: str) -> list:
    """네이버 모바일 API로 ETF 상위10 편입종목 파싱. 일시적 타임아웃 대비 1회 재시도."""
    import urllib.request
    url = f"https://m.stock.naver.com/api/stock/{code}/etfAnalysis"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_err = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                d = json.load(resp)
            return d.get("etfTop10MajorConstituentAssets") or []
        except Exception as e:
            last_err = e
    raise last_err


def _compute_sector_vacuum(top: int = 5) -> dict:
    """강한 ETF섹터 상위 → 편입종목 → 빈집(osc pct) 정렬. (순수 계산, 캐시 없음)"""
    etfs = None
    cached = _prewarm_cache.get("etf_bar")
    if cached and cached.get("data"):
        etfs = cached["data"]
    if not etfs and parse_etf_bar is not None:
        try:
            import kis_api
            etfs = parse_etf_bar()
            prices = kis_api.get_prices_batch_parallel([e["code"] for e in etfs])
            for e in etfs:
                p = prices.get(e["code"]) or {}
                e["change_rate"] = float(p.get("change_rate", 0) or 0)
        except Exception:
            etfs = etfs or []

    tk = {}
    try:
        with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
            tk = json.load(f).get("stocks") or {}
    except Exception:
        pass

    top_etfs = sorted([e for e in (etfs or []) if e.get("change_rate") is not None],
                      key=lambda x: x.get("change_rate", 0), reverse=True)[:max(1, min(top, 8))]

    from concurrent.futures import ThreadPoolExecutor
    def _build(e):
        try:
            cons = _fetch_etf_constituents(e["code"])
        except Exception:
            cons = []
        stocks = []
        for c in cons:
            cc = str(c.get("itemCode") or "").zfill(6)
            o = (tk.get(cc) or {}).get("osc") or {}
            stocks.append({"code": cc, "name": c.get("itemName"), "weight": c.get("etfWeight"),
                           "pct": o.get("pct"), "group": o.get("group")})
        stocks.sort(key=lambda s: s["pct"] if s["pct"] is not None else 999)
        return {"etf": e.get("name"), "code": e.get("code"),
                "rate": round(float(e.get("change_rate", 0) or 0), 2), "stocks": stocks}

    result = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(_build, top_etfs):
            result.append(r)
    result.sort(key=lambda x: x["rate"], reverse=True)
    return {"sectors": result, "ts": time.time()}


@app.get("/api/sector_vacuum")
def api_sector_vacuum(top: int = 5):
    """오늘 강한 ETF섹터 상위 → 각 ETF 실제 편입종목 → 수급빈집(osc) 우선정렬."""
    now = time.time()
    if _sv_cache["data"] and now - _sv_cache["ts"] < _SV_TTL:
        return JSONResponse(content=_sv_cache["data"])
    out = _compute_sector_vacuum(top)
    _sv_cache["data"] = out
    _sv_cache["ts"] = now
    return JSONResponse(content=out)


# ── 오늘의 빈집 포착 (자동 콜아웃) + 성과 추적 ──────────────────────
CALLOUT_DIR = os.path.join(ROOT, "pipeline", "callouts")

def _callout_score(rate, pct, chg) -> float:
    vac     = max(0.0, 100.0 - (pct if pct is not None else 100.0))  # 빈집 깊이
    strong  = max(0.0, rate or 0.0)                                  # 섹터 강도
    not_run = max(0.0, 5.0 - max(0.0, chg or 0.0))                   # 아직 안 오름
    return round(vac * 1.0 + strong * 3.0 + not_run * 2.0, 1)

def _generate_callout(top_sectors: int = 5, n: int = 3) -> dict:
    """강한섹터×빈집 통합 랭킹 Top n → 기준가 기록 → 당일 파일 동결."""
    sv = _compute_sector_vacuum(top_sectors)
    codes = [st["code"] for s in sv["sectors"] for st in s["stocks"] if st.get("code")]
    prices = {}
    try:
        import kis_api
        prices = kis_api.get_prices_multi(list(dict.fromkeys(codes)))
    except Exception:
        pass
    best = {}
    for s in sv["sectors"]:
        for st in s["stocks"]:
            cc = st.get("code")
            if not cc or st.get("pct") is None:
                continue
            pr  = prices.get(cc) or {}
            chg = float(pr.get("change_rate") or 0)
            sc  = _callout_score(s["rate"], st["pct"], chg)
            cand = {"code": cc, "name": st.get("name"), "sector": s["etf"],
                    "sector_rate": s["rate"], "pct": st["pct"], "group": st.get("group"),
                    "entry": int(pr.get("price") or 0), "change_at_gen": round(chg, 2),
                    "score": sc,
                    "reason": f"{s['etf']} 강세 · {st.get('group') or '빈집'} {st['pct']}%"}
            if cc not in best or sc > best[cc]["score"]:
                best[cc] = cand
    picks = sorted(best.values(), key=lambda x: x["score"], reverse=True)[:n]
    date = datetime.now().strftime("%Y-%m-%d")
    out = {"date": date, "generated_ts": time.time(), "picks": picks}
    try:
        os.makedirs(CALLOUT_DIR, exist_ok=True)
        with open(os.path.join(CALLOUT_DIR, f"{date}.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return out

@app.get("/api/callout")
def api_callout(refresh: int = 0):
    """오늘의 빈집 포착 Top3 — 그날 최초 요청 시 생성·동결, 이후 동일값."""
    date = datetime.now().strftime("%Y-%m-%d")
    p = os.path.join(CALLOUT_DIR, f"{date}.json")
    if not refresh and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return JSONResponse(content=json.load(f))
        except Exception:
            pass
    return JSONResponse(content=_generate_callout())

@app.get("/api/callout_history")
def api_callout_history(days: int = 10):
    """과거 콜아웃 + 현재가 기준 수익률·적중률."""
    import glob
    files = sorted(glob.glob(os.path.join(CALLOUT_DIR, "*.json")), reverse=True)[:max(1, days)]
    loaded, codes = [], set()
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
            loaded.append(d)
            for pk in d.get("picks", []):
                if pk.get("code"):
                    codes.add(pk["code"])
        except Exception:
            pass
    prices = {}
    try:
        import kis_api
        prices = kis_api.get_prices_multi(list(codes))
    except Exception:
        pass
    items = []
    for d in loaded:
        picks = []
        for pk in d.get("picks", []):
            cur   = int((prices.get(pk["code"]) or {}).get("price") or 0)
            entry = pk.get("entry") or 0
            ret   = round((cur - entry) / entry * 100, 2) if entry and cur else None
            picks.append({**pk, "cur": cur, "ret": ret})
        rets = [p["ret"] for p in picks if p["ret"] is not None]
        items.append({"date": d.get("date"), "picks": picks,
                      "avg_ret": round(sum(rets) / len(rets), 2) if rets else None,
                      "hit": round(sum(1 for r in rets if r > 0) / len(rets) * 100) if rets else None})
    return JSONResponse(content={"items": items})


# ── 뉴스 매칭 (백그라운드 스레드, 토큰0) ────────────────────────────
_NEWS_FEED = {"data": None, "ts": 0.0}
NEWS_FEED_PATH = os.path.join(ROOT, "pipeline", "news_feed.json")

def _refresh_news(top_sectors: int = 8, per_stock: int = 3):
    """상위 섹터 → 섹터 테마뉴스 + 종목뉴스 매칭 → 메모리·파일 저장."""
    try:
        import sys as _sys
        _sd = os.path.join(ROOT, "scripts")
        if _sd not in _sys.path:
            _sys.path.insert(0, _sd)
        import news_feed as nf
        import telegram_news_filter as tnf
        kw = nf.load_keywords()
        with open(os.path.join(ROOT, "pipeline", "atoms", "telegram_channels.json"),
                  encoding="utf-8") as f:
            tg_channels = json.load(f)
        with open(os.path.join(ROOT, "pipeline", "atoms", "stock_sector_map.json"),
                  encoding="utf-8") as f:
            stock_names = tnf.clean_stock_names(json.load(f))
        tg_by_sector, tg_by_stock = tnf.load_today_news_relay(
            os.path.join(ROOT, "raw", "telegram"), tg_channels, stock_names, kw)
        sv = _compute_sector_vacuum(top_sectors)
        out_sectors = []
        for s in sv.get("sectors", []):
            stocks = []
            for st in (s.get("stocks") or [])[:per_stock]:
                stock_news = nf.stock_news(st.get("code"), name=st.get("name"), top=2)
                stock_news = stock_news + tg_by_stock.get(st.get("name"), [])
                stocks.append({"code": st.get("code"), "name": st.get("name"),
                               "pct": st.get("pct"), "group": st.get("group"),
                               "news": stock_news})
            sector_news = nf.sector_news(s.get("code"), kw, top=3)
            sector_label = (kw.get(s.get("code")) or {}).get("sector")
            sector_news = sector_news + tg_by_sector.get(sector_label, [])
            out_sectors.append({"etf": s.get("etf"), "code": s.get("code"),
                                "rate": s.get("rate"), "sector": sector_label,
                                "news": sector_news,
                                "stocks": stocks})
        data = {"sectors": out_sectors, "ts": time.time()}
        _NEWS_FEED["data"] = data
        _NEWS_FEED["ts"] = time.time()
        try:
            with open(NEWS_FEED_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[_refresh_news] 파일저장 실패: {e}", flush=True)
    except Exception as e:
        import traceback
        print(f"[_refresh_news] 실패: {e}", flush=True)
        traceback.print_exc()

#  2026-07-08: ADR·상장 등 매크로/이벤트성 재료 키워드 보강(하이닉스 ADR 상장 뉴스가
#  누락되던 문제) — 관심종목 매칭(_match_stock)은 그대로 유지해 잡주는 계속 걸러진다.
_STRONG_RE   = re.compile(r"속보|특징주|급등|급락|수주|계약|부지|증설|투자|사상\s*최대|최대\s*실적|자사주|증자|신고가|목표주가|흑자|적자|인수|합병|매각|공급"
                           r"|ADR|상장|IPO|스팩|관세|환율|금리|기준금리|연준|FOMC|국채|유가|반덤핑|수출규제|무역분쟁"
                           r"|콜옵션|풋옵션|서킷브레이커|사이드카|블록딜|공매도")
# 거버넌스·인사 등 투자무관 뉴스 제외(예: "KB금융 차기 회장 숏리스트 확정")
_EXCLUDE_RE  = re.compile(r"회장|대표이사|사외이사|주주총회|주총|숏리스트|연임|임원|인사|이사회|사임|선임|취임|배당락|주식담보|스톡옵션")
# 알맹이 없는 클릭베이트/단순호명 제외 (예: "특징주 종목: 삼성전자(005930)", "…무슨 회사 길래?")
_LOWINFO_RE  = re.compile(r"무슨\s*회사|어떤\s*회사|길래|왜\s*(오르|급등|뛰|내리|빠)|특징주\s*종목\s*[:：]|이\s*종목은|눈길")
# '재료성' 판단 — 관심종목 매칭이 없을 때 이 키워드라도 있어야 노출
_MATERIAL_RE = re.compile(r"수주|계약|부지|증설|투자|실적|급등|급락|목표주가|자사주|증자|신고가|흑자|적자|인수|합병|매각|공급|사상\s*최대"
                           r"|ADR|상장|IPO|관세|환율|금리|연준|FOMC|국채|유가|수출규제")
# 전쟁·지정학 등 종목 무관 매크로 이벤트 — 관심종목 매칭 없이도 노출(시장상황 타임라인용, _weather_tick news 보강)
_MACRO_RE    = re.compile(r"전쟁|침공|공습|미사일|휴전|정전협정|계엄|쿠데타|지정학|제재|봉쇄|해협|유가\s*급등|유가\s*급락"
                           r"|연준|FOMC|기준금리|금리\s*(인상|인하)|국채\s*금리|관세\s*(폭탄|전쟁)|환율\s*급등|환율\s*급락")

def _news_norm(t: str) -> str:
    return re.sub(r"[^가-힣0-9a-zA-Z]", "", t or "")[:36]

def _match_stock(t: str, stocks_set) -> str:
    """제목에서 관심종목명을 찾되, 더 긴 단어의 일부(예: '이닉스'⊂'하이닉스')는 제외.
    앞뒤가 한글이면 다른 단어의 일부로 보고 버리고, 'AI'·'SK' 같은 2자 영문 오탐도 제외. 가장 긴 매칭 선호."""
    def _kr(c): return "가" <= c <= "힣"
    best = ""
    for s in stocks_set:
        if not s or len(s) < 2 or (len(s) <= 2 and s.isascii()):
            continue
        idx = t.find(s)
        if idx < 0:
            continue
        before = t[idx - 1] if idx > 0 else ""
        after = t[idx + len(s)] if idx + len(s) < len(t) else ""
        if _kr(before) or _kr(after):
            continue
        if len(s) > len(best):
            best = s
    return best

def _news_bigrams(s: str) -> set:
    t = re.sub(r"\s+", "", s or "")
    return {t[i:i+2] for i in range(len(t) - 1)}

def _news_sim(a: str, b: str) -> float:
    A, B = _news_bigrams(a), _news_bigrams(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    return inter / (len(A) + len(B) - inter)

def _surface_strong_news():
    """뉴스피드의 '강한' 원문 뉴스를 원문+출처+섹터+종목 카드로 타임라인에 직접 추가.
    Gemini 요약이 5개만 순서대로 받아 중요뉴스(광주 반도체 클러스터 등)를 통째로 놓치던 문제 보완.
    - 관심종목(stock_sector_map) 언급 or 재료성 키워드만 노출, 거버넌스·인사 뉴스는 제외
    - 여러 채널이 동시에 쏟아낸 뉴스(클러스터 크기)를 중요도로 봐 상위는 important=맨앞 고정+뱃지"""
    try:
        data = _NEWS_FEED.get("data")
        if not data:
            return
        today = datetime.now().strftime("%m/%d")
        smap, stocks_set = {}, set()
        try:
            import telegram_news_filter as _tnf
            with open(os.path.join(ROOT, "pipeline", "atoms", "stock_sector_map.json"),
                      encoding="utf-8") as f:
                smap = json.load(f)
            stocks_set = _tnf.clean_stock_names(smap)
        except Exception:
            pass
        # 매칭 대상 = 전체맵(1405종목, 잡주 포함) 대신 '내 관심종목(watchlist)'으로 좁힘.
        # → 히트맵에 없는 소형주(동구바이오·지니너스 등) 뉴스 제외, 리가켐 등 추적종목은 유지.
        focus_stocks = set()
        try:
            import sector_heatmap as _sh
            for _sec in _sh.parse_watchlist(999):
                for _s in (_sec.get("stocks") or []):
                    if _s.get("name"):
                        focus_stocks.add(_s["name"])
        except Exception:
            pass
        if not focus_stocks:
            focus_stocks = stocks_set   # 폴백
        # 종목명→오늘 등락률(%) 맵 — 많이 오른 종목의 뉴스가 그날 섹터를 끌어올린 '진짜 재료'
        pct_map = {}
        for sec in (data.get("sectors") or []):
            for st in (sec.get("stocks") or []):
                nm = st.get("name")
                if nm:
                    try: pct_map[nm] = float(st.get("pct") or 0)
                    except Exception: pass
        cands = []
        for sec in (data.get("sectors") or []):
            sector = sec.get("sector") or "시장"
            rows = list(sec.get("news") or [])
            for st in (sec.get("stocks") or []):
                rows += st.get("news") or []
            for n in rows:
                t = (n.get("title") or "").strip()
                d = (n.get("date") or "")
                if not t or not d.startswith(today):
                    continue
                if not _STRONG_RE.search(t) or _EXCLUDE_RE.search(t) or _LOWINFO_RE.search(t):
                    continue
                stock = _match_stock(t, focus_stocks)
                if not stock:   # 내 관심종목(watchlist) 매칭된 뉴스만 — 잡주/정책일반 제외
                    continue
                cands.append({"t": t, "d": d, "src": n.get("src") or n.get("source") or "뉴스",
                              "sector": (smap.get(stock) or sector), "stock": stock,
                              "pct": pct_map.get(stock, 0.0)})
        # 유사한 것끼리 클러스터 → 대표 1개 + 크기(=여러 채널 동시보도=중요도)
        clusters = []
        for c in cands:
            # 문장 유사 or 같은 종목(같은 이벤트일 가능성 큼)이면 한 클러스터로 병합 → 중복 카드 방지
            cl = next((x for x in clusters
                       if _news_sim(x["items"][0]["t"], c["t"]) >= 0.30
                       or (c["stock"] and c["stock"] == x["items"][0]["stock"])), None)
            (cl["items"].append(c) if cl else clusters.append({"items": [c]}))
        reps = []
        for cl in clusters:
            it = cl["items"][0]; size = len(cl["items"])
            base = 3 if "속보" in it["t"] else 2 if "특징주" in it["t"] else 1
            gain = max((x.get("pct", 0) for x in cl["items"]), default=0)   # 오늘 상승기여
            gain_bonus = 5 if gain >= 8 else 3 if gain >= 4 else 1 if gain >= 2 else 0
            reps.append({**it, "score": base + size + (2 if it["stock"] else 0) + gain_bonus,
                         "cluster": size, "pct": round(gain, 1)})
        reps.sort(key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(reps):
            # 상위 + (다채널 보도 or 큰 상승) → '중요' 맨앞 고정
            # 기준 강화(2026-07-08): 상위3→2, 점수5→7 — '중요' 과다노출 완화. 더 줄이려면 이 두 값만 조정.
            r["important"] = (i < 2 and r["score"] >= 7)
        stored = _briefing_load(BRIEFING_PATH)
        seen = {_news_norm(x.get("headline", "")) for x in (stored.get("items") or [])}
        new = [r for r in reps if _news_norm(r["t"]) not in seen]
        new.sort(key=lambda x: x["d"])
        for r in new[-20:]:
            _briefing_append(BRIEFING_PATH, {
                "ts": (r["d"].split(" ")[-1][:5] if " " in r["d"] else datetime.now().strftime("%H:%M")),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "severity": "red", "headline": r["t"], "body": "",
                "sector": r["sector"], "stock": r["stock"], "source": r["src"],
                "pct": r.get("pct", 0),
                "important": bool(r.get("important")), "kind": "raw_news"})
    except Exception:
        pass

def _news_loop():
    while True:
        _refresh_news()
        _surface_strong_news()   # 강한 원문 뉴스 직접 노출
        time.sleep(1200)   # 20분 간격

threading.Thread(target=_news_loop, daemon=True).start()

@app.get("/api/news_feed")
def api_news_feed():
    if _NEWS_FEED["data"]:
        return JSONResponse(content=_NEWS_FEED["data"])
    try:
        with open(NEWS_FEED_PATH, encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))
    except Exception:
        return JSONResponse(content={"sectors": [], "ts": 0})


_sd2_cache: dict = {}   # {key: {"data":..., "ts":...}}

@app.get("/api/sector_detail")
def api_sector_detail(etf: str = "", codes: str = "", title: str = ""):
    """섹터 상세: 섹터뉴스 + 종목별(빈집 osc + 종목뉴스). etf=ETF코드 / codes=종목코드목록(콤마)."""
    key = f"etf:{etf}" if etf else f"codes:{codes}"
    now = time.time()
    c = _sd2_cache.get(key)
    if c and now - c["ts"] < 300:
        return JSONResponse(content=c["data"])
    import sys as _sys
    _sd = os.path.join(ROOT, "scripts")
    if _sd not in _sys.path:
        _sys.path.insert(0, _sd)
    import news_feed as nf
    tk = {}
    try:
        with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
            tk = json.load(f).get("stocks") or {}
    except Exception:
        pass
    sector_news, metas = [], []
    cons_failed = False
    if etf:
        ec = etf.zfill(6) if etf.isdigit() else etf
        try:
            cons = _fetch_etf_constituents(ec)
        except Exception:
            cons, cons_failed = [], True   # 일시적 실패 — 아래에서 캐시하지 않음(다음 클릭 때 재시도)
        for co in cons:
            metas.append((str(co.get("itemCode") or "").zfill(6), co.get("itemName")))
        for s in (_NEWS_FEED.get("data") or {}).get("sectors", []):
            if str(s.get("code")) == ec:
                sector_news = s.get("news", []); break
        if not sector_news:
            sector_news = nf.sector_news(ec, top=3)
    else:
        for cc in [x.strip().zfill(6) for x in codes.split(",") if x.strip()][:12]:
            metas.append((cc, (tk.get(cc) or {}).get("name")))

    from concurrent.futures import ThreadPoolExecutor
    def _build(m):
        cc, nm = m
        o = (tk.get(cc) or {}).get("osc") or {}
        resolved_name = nm or (tk.get(cc) or {}).get("name") or cc
        chg = None
        import kis_api
        for _attempt in range(2):   # KIS API 일시적 500 대응 1회 재시도(5분 캐시라 실패시 오래 굳음)
            try:
                chg = kis_api.get_price(cc).get("change_rate")
                break
            except Exception:
                if _attempt == 0:
                    time.sleep(0.5)
        return {"code": cc, "name": resolved_name,
                "pct": o.get("pct"), "group": o.get("group"), "chg": chg,
                "news": nf.stock_news(cc, name=resolved_name, top=2)}
    with ThreadPoolExecutor(max_workers=6) as ex:
        stocks = list(ex.map(_build, metas))
    stocks.sort(key=lambda s: s["pct"] if s["pct"] is not None else 999)
    if not sector_news:
        # 섹터 테마뉴스가 없으면 편입종목 개별뉴스로 대체(빈 화면 방지)
        for s in stocks:
            for n in (s.get("news") or []):
                sector_news.append({"title": f"[{s['name']}] {n['title']}", "date": n.get("date", ""),
                                     "url": n.get("url", ""), "score": 0})
                if len(sector_news) >= 2:
                    break
            if len(sector_news) >= 2:
                break
    out = {"title": title or etf, "sector_news": sector_news, "stocks": stocks}
    if not (cons_failed and not stocks):   # 종목 조회 자체가 실패한 경우만 캐시 스킵
        _sd2_cache[key] = {"data": out, "ts": now}
    return JSONResponse(content=out)


_sector_summary_cache: dict = {}   # {key: {"data":..., "ts":...}}

@app.get("/api/sector_summary")
def api_sector_summary(etf: str = "", codes: str = "", title: str = ""):
    return JSONResponse(content=_gen_sector_summary(etf, codes, title))

def _gen_sector_summary(etf: str = "", codes: str = "", title: str = "") -> dict:
    """섹터 뉴스 헤드라인(오늘자만) → Gemini로 '오늘 이 섹터 왜 움직이나' 요약.
    헤드라인 내용이 실제로 바뀌었을 때만 Gemini 재호출(쿼터 절약 + 사실상 실시간).
    엔드포인트+백그라운드 프리워밍 공용."""
    key = f"etf:{etf}" if etf else f"codes:{codes}"
    now = time.time()
    c = _sector_summary_cache.get(key)
    import sys as _sys
    _sd = os.path.join(ROOT, "scripts")
    if _sd not in _sys.path:
        _sys.path.insert(0, _sd)
    import news_feed as nf

    # ⚠️ 오늘 날짜 뉴스만 요약(어제 호재로 요약했는데 오늘 폭락장이면 오류) — 날짜 "MM/DD" 매칭
    today_md = datetime.now().strftime("%m/%d")
    def _is_today(dstr):
        return str(dstr or "").strip().startswith(today_md)

    # 1) 섹터 테마뉴스
    headlines = []
    if etf:
        ec = etf.zfill(6) if etf.isdigit() else etf
        # 캐시된 뉴스피드 먼저, 없으면 라이브
        snews = []
        for s in (_NEWS_FEED.get("data") or {}).get("sectors", []):
            if str(s.get("code")) == ec:
                snews = s.get("news", []); break
        if not snews:
            snews = nf.sector_news(ec, top=8)
        for n in snews:
            if _is_today(n.get("date")):
                headlines.append(f"- [{n.get('date','')}] {n.get('title','')}")
        # 2) 상위 편입종목 종목뉴스(신선·큐레이션)
        try:
            cons = _fetch_etf_constituents(ec)
        except Exception:
            cons = []
        from concurrent.futures import ThreadPoolExecutor
        metas = [(str(co.get("itemCode") or "").zfill(6), co.get("itemName")) for co in cons[:6]]
        def _sn(m):
            cc, nm = m
            return [(nm, n.get("title", ""), n.get("date", "")) for n in nf.stock_news(cc, name=nm, top=3)]
        with ThreadPoolExecutor(max_workers=6) as ex:
            for group in ex.map(_sn, metas):
                for nm, t, dt in group:
                    if _is_today(dt):
                        headlines.append(f"- [{nm} {dt}] {t}")
    else:
        _code2name = {str(_cc).zfill(6): _nm for _nm, _cc in _krx_codes().items()}
        for cc in [x.strip().zfill(6) for x in codes.split(",") if x.strip()][:6]:
            for n in nf.stock_news(cc, name=_code2name.get(cc, ""), top=3):
                if _is_today(n.get("date")):
                    headlines.append(f"- {n.get('title','')}")

    # 중복 제거
    seen, uniq = set(), []
    for h in headlines:
        if h in seen:
            continue
        seen.add(h); uniq.append(h)
    if len(uniq) < 2:
        # 오늘 뉴스가 거의 없으면 억지 요약 안 함(어제 것으로 오도 방지)
        return {"summary": "", "error": "오늘 새 뉴스가 적어 요약을 건너뜁니다."}

    # 헤드라인 내용이 지난번과 동일하면 Gemini 호출 없이 캐시 그대로 반환
    hkey = _hashlib.md5("\n".join(sorted(uniq)).encode("utf-8")).hexdigest()
    if c and c.get("hkey") == hkey:
        return c["data"]

    sector = title or etf or "이 섹터"
    prompt = (
        f"너는 주식 대시보드의 시장 인사이트 애널리스트다. 아래는 '{sector}' 섹터의 **오늘({today_md}) 뉴스 헤드라인만** 모은 것이다.\n"
        f"대시보드 사용자가 이 위젯만 보고 '여러 정보를 한 번에 얻었다'고 느끼도록 정리하라.\n"
        f"오직 아래 오늘자 헤드라인 사실만 반영하라(과거 호재로 낙관 금지).\n\n"
        f"[오늘 뉴스 헤드라인]\n" + "\n".join(uniq[:16]) + "\n\n"
        "[출력 형식 · 마크다운, 짧게]\n"
        "**🔑 한 줄**: 이 섹터가 지금 왜 주목받는지 한 문장 (구체적·흥미롭게)\n"
        "**📌 핵심 이슈**\n"
        "- 이슈 2~3개, 각 한 줄. 종목명·수치·계약/실적 등 구체 팩트 포함\n"
        "**👀 관전 포인트**: 투자자가 뭘 봐야 하는지 한 줄\n\n"
        "규칙: 헤드라인에 있는 사실만 사용. 양면론·'관망하라' 금지. 과장·추천 금지. "
        "존댓말로 간결하게. 인사말·자기소개·채널/영상 언급 절대 금지 — 바로 **🔑 한 줄**부터 시작."
    )
    # 쿼터 여유: 키 6개 총동원 + 무료쿼터 넉넉한 gemini-2.5-flash 우선(프리뷰는 폴백)
    res = _gemini_text(prompt, keys=_summary_keys(),
                       models=["gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-2.5-flash"])
    out = {"summary": res.get("analysis", ""), "model": res.get("model", ""),
           "error": res.get("error", ""), "sources": len(uniq)}
    if out["summary"]:
        _sector_summary_cache[key] = {"data": out, "ts": now, "hkey": hkey}
    return out


_stock_summary_cache: dict = {}


@app.get("/api/stock_summary")
def api_stock_summary(code: str = "", name: str = ""):
    return JSONResponse(content=_gen_stock_summary(code, name))


def _gen_stock_summary(code: str = "", name: str = "") -> dict:
    """종목 뉴스(네이버 증권 큐레이션) + Gemini 요약. 차트 우측 패널용.
    헤드라인이 바뀌거나 등락률이 크게 움직였을 때만 Gemini 재호출(쿼터 절약 + 사실상 실시간).
    요약 실패해도 뉴스 리스트는 항상 반환."""
    code = (code or "").strip().zfill(6)
    if not code.strip("0"):
        return {"news": [], "summary": "", "error": "코드 없음"}
    now = time.time()
    c = _stock_summary_cache.get(code)
    import sys as _sys
    _sd = os.path.join(ROOT, "scripts")
    if _sd not in _sys.path:
        _sys.path.insert(0, _sd)
    import news_feed as nf
    try:
        news = nf.stock_news(code, name=name, top=12)   # 여유있게 받아 필터
    except Exception:
        news = []
    if not news:
        return {"news": [], "summary": "", "error": "관련 뉴스가 없습니다."}

    # nf.stock_news가 이제 종목명으로 네이버 검색 → 노이즈컷+약칭포함 관련성필터+호재랭킹까지
    # 마친 결과라 여기서 다시 거르지 않는다.
    news = news[:8]

    nm = name or code
    headlines = [f"- [{n.get('date','')}] {n.get('title','')}" for n in news]

    # 등락률 2%p 단위 버켓 — 헤드라인이 그대로여도 주가가 크게 움직였으면 요약을 다시 만든다
    # (뉴스가 "6% 급등"이라 써놓고 실제론 9%까지 간 채 방치되는 것 방지)
    rate_bucket = None
    try:
        import kis_api
        rate = (kis_api.get_price(code) or {}).get("change_rate")
        if rate is not None:
            rate_bucket = round(float(rate) / 2) * 2
    except Exception:
        pass

    # 헤드라인+등락률 버켓이 지난번과 동일하면 Gemini 호출 없이 캐시 그대로 반환
    hkey = _hashlib.md5(
        ("\n".join(sorted(headlines)) + f"|rate:{rate_bucket}").encode("utf-8")).hexdigest()
    if c and c.get("hkey") == hkey:
        return c["data"]

    prompt = (
        f"너는 주식 대시보드의 애널리스트다. 아래는 '{nm}' 종목의 최근 뉴스 헤드라인이다.\n"
        f"대시보드 사용자가 이 종목의 현재 상황을 빠르게 파악하도록 정리하라. 아래 헤드라인 사실만 사용.\n\n"
        f"[최근 뉴스 헤드라인]\n" + "\n".join(headlines[:12]) + "\n\n"
        "[출력 형식 · 마크다운, 짧게]\n"
        "**🔑 한 줄**: 이 종목이 지금 왜 주목받는지 한 문장 (구체적)\n"
        "**📌 핵심 이슈**\n- 이슈 2~3개, 각 한 줄. 수치·계약·실적 등 구체 팩트 포함\n"
        "**👀 관전 포인트**: 투자자가 뭘 봐야 하는지 한 줄\n\n"
        "규칙: 헤드라인 사실만 사용. 양면론·'관망하라' 금지. 과장·추천 금지. "
        "존댓말로 간결하게. 인사말·자기소개·채널/영상 언급 절대 금지 — 바로 **🔑 한 줄**부터 시작."
    )
    res = _gemini_text(prompt, keys=_summary_keys(),
                       models=["gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-2.5-flash"])
    out = {"news": news, "summary": res.get("analysis", ""),
           "model": res.get("model", ""), "error": res.get("error", ""),
           "sources": len(news)}
    if out["summary"]:
        _stock_summary_cache[code] = {"data": out, "ts": now, "hkey": hkey}
    return out


def _summary_prewarm():
    """장중 ETF 섹터 요약을 백그라운드로 미리 생성해 캐시 → 사용자가 클릭하면 즉시 표시.
    _gen_sector_summary는 15분 캐시라 대부분 즉시 반환, 만료분만 Gemini 재생성."""
    time.sleep(20)   # 서버 기동 후 다른 프리워밍과 겹치지 않게 약간 대기
    while True:
        try:
            nowdt = datetime.now()
            mins = nowdt.hour * 60 + nowdt.minute
            if 540 <= mins <= 960:   # 09:00~16:00 장중만
                try:
                    from sector_heatmap import parse_etf_bar as _peb
                    etfs = _peb() or []
                except Exception:
                    etfs = []
                for e in etfs:
                    try:
                        r = _gen_sector_summary(etf=e.get("code", ""), title=e.get("name", ""))
                        # 429(쿼터소진) 뜨면 이번 사이클 중단 — 계속 때리면 쿼터 더 막힘
                        if r and "429" in str(r.get("error", "")):
                            time.sleep(120)
                            break
                    except Exception:
                        pass
                    time.sleep(12)   # Gemini 부하 분산(캐시 hit이면 즉시 지나감). 30분 캐시라 대부분 hit
            time.sleep(300)          # 사이클 간 5분(쿼터 절약)
        except Exception:
            time.sleep(300)

threading.Thread(target=_summary_prewarm, daemon=True).start()


_etfcon_cache: dict = {}   # {code: {"data":..., "ts":...}}

@app.get("/api/etf_constituents")
def api_etf_constituents(code: str = ""):
    """단일 ETF 실제 편입종목 + 수급빈집(osc) — 상단 ETF칩 클릭 펼침용."""
    code = (code or "").strip().zfill(6) if (code or "").strip().isdigit() else (code or "").strip()
    if not code:
        return JSONResponse(content={"stocks": []})
    now = time.time()
    c = _etfcon_cache.get(code)
    if c and now - c["ts"] < 600:
        return JSONResponse(content=c["data"])
    try:
        cons = _fetch_etf_constituents(code)
    except Exception as e:
        return JSONResponse(content={"code": code, "stocks": [], "error": str(e)})
    tk = {}
    try:
        with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
            tk = json.load(f).get("stocks") or {}
    except Exception:
        pass
    stocks = []
    for it in cons:
        cc = str(it.get("itemCode") or "").zfill(6)
        o = (tk.get(cc) or {}).get("osc") or {}
        stocks.append({"code": cc, "name": it.get("itemName"), "weight": it.get("etfWeight"),
                       "pct": o.get("pct"), "group": o.get("group")})
    stocks.sort(key=lambda s: s["pct"] if s["pct"] is not None else 999)   # 빈집 우선
    out = {"code": code, "stocks": stocks}
    _etfcon_cache[code] = {"data": out, "ts": now}
    return JSONResponse(content=out)


@app.get("/api/debug_flow")
def api_debug_flow():
    """각 KIS API 직접 호출 진단 (서버 캐시 토큰 사용 — reload 없음)."""
    import kis_api, kiwoom_api as _kw, traceback
    results = {}
    for name, fn, args in [
        ("J_bars",    kis_api.get_index_minutebar, ("0001", 15)),
        ("Q_bars",    kis_api.get_index_minutebar, ("1001", 15)),
        ("J_investor",_kw.get_market_investor, ("J",)),
        ("J_prog",    _kw.get_program_trade, ("J",)),
        ("J_price",   kis_api.get_index_price, ("0001",)),
        ("RANK_VOL",  _kw.get_volume_rank, ()),
        ("RANK_AMT",  _kw.get_trade_rank, ()),
    ]:
        try:
            v = fn(*args)
            results[name] = {"ok": True, "val": str(v)[:300]}
        except Exception:
            results[name] = {"ok": False, "err": traceback.format_exc()[-200:]}
    return JSONResponse(content=results)


def _enrich_rank_prices(done: dict) -> None:
    """순위 목록(인기검색=네이버 / 거래대금=키움)의 가격·등락률을 KIS 시세로 통일.

    네이버·키움·KIS가 제각각이라 같은 종목이 목록마다 다르게 보이는 문제 해결.
    순위(어떤 종목인지)는 원본 유지, 가격만 히트맵과 같은 KIS 소스로 덮어쓴다.
    fetch 단계에서 1회만 호출(캐시됨) → 요청마다 재조회 안 함.
    """
    try:
        import kis_api
        pop = done.get("RANK_POP") or []
        amt = done.get("RANK_AMT") or []
        codes = list({s["code"] for s in (pop + amt) if s.get("code")})
        if not codes:
            return
        prices = kis_api.get_prices_batch_parallel(codes)
        for lst in (pop, amt):
            for s in lst:
                p = prices.get(s.get("code")) or {}
                if p.get("price"):
                    s["price"] = p["price"]
                    s["change_rate"] = p.get("change_rate", s.get("change_rate", 0))
    except Exception:
        pass


def _build_market_flow_result(done: dict) -> dict:
    """done dict → market_flow 응답 dict 변환."""
    result = {}
    for mkt, code, label in [("J", "0001", "코스피"), ("Q", "1001", "코스닥")]:
        price_d  = done.get(f"{mkt}_price") or {}
        # WebSocket 실시간값 있으면 REST보다 우선 사용
        if kis_ws:
            ws_live = kis_ws.get(code)
            if ws_live:
                price_d = {"price": ws_live["price"], "change_rate": ws_live["change_rate"]}
        investor = done.get(f"{mkt}_investor") or {"외인": 0, "기관": 0, "개인": 0, "ts": ""}
        prog     = done.get(f"{mkt}_prog") or {"차익": 0, "비차익": 0, "합계": 0, "ts": ""}
        # 장 종료 후 키움이 0을 반환하면 마지막 장중 스냅샷(≈15:30 종가) 유지 → 저녁(~20시)까지 표시
        if not (investor.get("외인") or investor.get("기관") or investor.get("개인")):
            for snap in reversed(list(_FLOW[mkt]["investor"])):
                if snap.get("외인") or snap.get("기관") or snap.get("개인"):
                    investor = snap; break
        if not (prog.get("차익") or prog.get("비차익") or prog.get("합계")):
            for snap in reversed(list(_FLOW[mkt]["program"])):
                if snap.get("차익") or snap.get("비차익") or snap.get("합계"):
                    prog = snap; break
        # 실패해서 all-zero로 찍힌 스냅샷은 스파이크 유발 → 서빙 시 제거
        inv_hist = [s for s in _FLOW[mkt]["investor"]
                    if (s.get("외인") or s.get("기관") or s.get("개인"))]
        prog_hist = [s for s in _FLOW[mkt]["program"]
                     if (s.get("차익") or s.get("비차익") or s.get("합계"))]
        result[code] = {
            "label":            label,
            "price":            price_d.get("price", 0),
            "change_rate":      price_d.get("change_rate", 0),
            "bars":             done.get(f"{mkt}_bars") or [],
            "bars_15m":         done.get(f"{mkt}_bars") or [],
            "bars_1m":          done.get(f"{mkt}_bars_1m") or [],
            "bars_1d":          done.get(f"{mkt}_bars_1d") or [],
            "investor_now":     investor,
            "investor_history": inv_hist,
            "program_now":      prog,
            "program_history":  prog_hist,
            "program_series":   done.get(f"{mkt}_prog_series") or [],
        }
    nq   = done.get("NQ")       or {"price": 0, "change_rate": 0, "bars": []}
    ksf  = done.get("KSF")      or {"price": 0, "change_rate": 0, "bars": []}
    ksfn = done.get("KSFN")     or {"price": 0, "change_rate": 0, "bars": []}
    fx   = done.get("USDKRW")   or {"price": 0, "change_rate": 0, "bars": []}
    oil  = done.get("WTI")      or {"price": 0, "change_rate": 0, "bars": []}
    # 야간선물 마지막 체결 시각(esignal) 보존 — WS 덮어쓰기 전에 확보
    ksfn_last_ts = ksfn.get("last_ts", 0)
    import datetime as _dt2
    _now2 = _dt2.datetime.now()
    _mins = _now2.hour * 60 + _now2.minute
    _today_md = f"{_now2.month}/{_now2.day}"
    # 코스피200 선물(주간) 09:00~15:45 → 그 외 시간은 '마감'
    ksf_closed = not (540 <= _mins < 945)
    # 야간선물(미니) 18:00~익일 05:00 → 그 외(주간 포함)는 '마감'
    ksfn_closed = not (_now2.hour >= 18 or _now2.hour < 5)
    # 야간선물 마감 날짜 = 마지막 체결일
    ksfn_md = _today_md
    if ksfn_last_ts:
        try:
            _d = _dt2.datetime.fromtimestamp(ksfn_last_ts / 1000); ksfn_md = f"{_d.month}/{_d.day}"
        except Exception:
            pass
    # 야간선물 WebSocket 실시간값 우선 사용 (개장 중일 때만 의미 있음)
    if kis_ws:
        ws_ksfn = kis_ws.get("101W9")
        if ws_ksfn:
            ksfn = {"price": ws_ksfn["price"], "change_rate": ws_ksfn["change_rate"],
                    "bars": ksfn.get("bars") or [], "bars_1m": ksfn.get("bars_1m") or [],
                    "bars_15m": ksfn.get("bars_15m") or [], "bars_1d": ksfn.get("bars_1d") or [],
                    "last_ts": ksfn_last_ts}
    result["global"] = {
        "label": "글로벌 지표",
        "items": [
            {"name": "나스닥선물(NQ)",  "price": nq["price"],   "change_rate": nq["change_rate"],   "bars": nq.get("bars") or [],
             "bars_1m": nq.get("bars_1m") or [], "bars_15m": nq.get("bars_15m") or [], "bars_1d": nq.get("bars_1d") or []},
            {"name": "코스피선물",      "price": ksf["price"],  "change_rate": ksf["change_rate"],  "bars": ksf.get("bars") or [],
             "bars_1m": ksf.get("bars_1m") or [], "bars_15m": ksf.get("bars_15m") or [], "bars_1d": ksf.get("bars_1d") or [],
             "closed": ksf_closed, "night": False, "cdate": _today_md},
            {"name": "코스피야간선물",  "price": ksfn["price"], "change_rate": ksfn["change_rate"], "bars": ksfn.get("bars") or [],
             "bars_1m": ksfn.get("bars_1m") or [], "bars_15m": ksfn.get("bars_15m") or [], "bars_1d": ksfn.get("bars_1d") or [],
             "closed": ksfn_closed, "night": True, "cdate": ksfn_md, "last_ts": ksfn_last_ts},
            {"name": "원달러환율",      "price": fx["price"],   "change_rate": fx["change_rate"],   "bars": fx.get("bars") or []},
            {"name": "국제유가(WTI)",   "price": oil["price"],  "change_rate": oil["change_rate"],  "bars": oil.get("bars") or [],
             "bars_1m": oil.get("bars_1m") or [], "bars_15m": oil.get("bars_15m") or []},
        ]
    }
    pop_stocks = done.get("RANK_POP") or []
    amt_stocks = done.get("RANK_AMT") or []
    # 결정론적 일관성: 두 목록에 동시에 있는 종목은 항상 같은 가격 표시.
    # (인기검색=네이버/거래대금=키움이라 enrichment 타이밍에 따라 어긋날 수 있어 매 응답마다 강제 보정.
    #  거래대금=키움 실시간을 기준값으로 사용)
    canon = {s["code"]: s for s in amt_stocks if s.get("code") and s.get("price")}
    for s in pop_stocks:
        c = s.get("code")
        if c in canon:
            s["price"] = canon[c]["price"]
            s["change_rate"] = canon[c].get("change_rate", s.get("change_rate", 0))
    result["rank_popular"] = {"label": "실시간 인기검색", "stocks": pop_stocks}
    result["rank_amt"] = {"label": "거래대금 상위",   "stocks": amt_stocks}
    return result


# ── 로컬(키움 보유 PC)이 보낸 market_flow 수신·서빙 (서버는 키움 없음) ──
_pushed_flow = {"data": None, "ts": 0.0}
PUSH_TOKEN = os.environ.get("PUSH_TOKEN", "")

@app.post("/api/push_market_flow")
async def _push_market_flow(req: Request):
    if not PUSH_TOKEN or req.headers.get("x-push-token") != PUSH_TOKEN:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        _pushed_flow["data"] = await req.json()
        _pushed_flow["ts"] = time.time()
        return {"ok": True, "ts": _pushed_flow["ts"]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ── 마지막 정상 응답 유지(last-good): KIS 순간 실패로 그래프가 사라졌다 복구되는 현상 방지 ──
_last_good_mf: dict = {"result": None, "date": None}

def _mf_is_good(result: dict) -> bool:
    """코스피·코스닥 둘 다 15분봉 bars + 현재가가 있어야 '정상'."""
    for code in ("0001", "1001"):
        m = result.get(code) or {}
        if not (m.get("bars") and (m.get("price") or 0) > 0):
            return False
    return True

def _serve_mf(result: dict):
    """정상이면 last-good 갱신 후 서빙, 열화면 직전 정상 결과 서빙(그래프 유지)."""
    today = datetime.now().strftime("%Y%m%d")
    if _mf_is_good(result):
        prev = _last_good_mf["result"]
        # bars 급감 방어: 같은 날 안에서 새 15분봉이 직전의 절반 미만이면(페이지네이션
        # 순간실패 등) 직전 bars 유지. prev가 오늘 것이 아니면(장 시작 직후라 오늘 봉수가
        # 아직 적을 뿐인 경우) 어제 스냅샷과 비교하는 게 의미 없으므로 건너뛴다 — 안 그러면
        # 매일 09:00~13:15경까지 어제 마감 스냅샷이 오늘 데이터를 계속 덮어써 버린다.
        if prev and _last_good_mf.get("date") == today:
            for c in ("0001", "1001"):
                nb = len((result.get(c) or {}).get("bars") or [])
                pb = len((prev.get(c) or {}).get("bars") or [])
                if pb >= 6 and nb < pb // 2 and result.get(c):
                    result[c]["bars"] = prev[c]["bars"]
        _last_good_mf["result"] = result
        _last_good_mf["date"] = today
        return JSONResponse(content=result)
    if _last_good_mf["result"]:
        # 열화분에서도 실시간성 있는 순위/글로벌은 갱신본으로 덮어써 최신 유지
        merged = dict(_last_good_mf["result"])
        for k in ("global", "rank_popular", "rank_amt"):
            if result.get(k):
                merged[k] = result[k]
        return JSONResponse(content=merged)
    return JSONResponse(content=result)


@app.get("/api/market_flow")
def api_market_flow():
    """코스피/코스닥/미국선물(SPY)/코스피야간선물 지수 15분봉 + 투자자/프로그램 시계열."""
    # 릴레이 서버(키움 없음): 로컬이 보낸 데이터를 우선 서빙 (장 마감 후엔 마지막 전송분 유지)
    if os.environ.get("SERVE_PUSHED") and _pushed_flow["data"]:
        return JSONResponse(content=_pushed_flow["data"])
    try:
        import kis_api, kiwoom_api, naver_api
        from concurrent.futures import ThreadPoolExecutor

        # 프리워밍 캐시 hit → 즉시 반환 (수십 ms)
        cached = _prewarm_cache.get("market_flow")
        if cached and time.time() - cached["ts"] < _PREWARM_TTL:
            return _serve_mf(_build_market_flow_result(cached["data"]))

        # 전일종가 캐시 비어있으면 먼저 채움 (서버 시작 직후 레이스컨디션 방지)
        if global_api and not global_api._PW_PREVCLOSE:
            try:
                global_api.scrape_all_prevclose()
            except Exception:
                pass

        # 캐시 미스 → 직접 fetch (분봉·투자자·프로그램매매=KIS로 통일, 키움 서버키 미등록)
        with ThreadPoolExecutor(max_workers=22) as ex:
            tasks = {
                "J_bars":     ex.submit(kis_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kis_api.get_index_minutebar, "1001", 15),
                "J_bars_1m":  ex.submit(kis_api.get_index_minutebar, "0001", 1),
                "Q_bars_1m":  ex.submit(kis_api.get_index_minutebar, "1001", 1),
                "J_bars_1d":  ex.submit(kis_api.get_index_daily_bars, "0001", 30),
                "Q_bars_1d":  ex.submit(kis_api.get_index_daily_bars, "1001", 30),
                "J_price":    ex.submit(kis_api.get_index_price, "0001"),
                "Q_price":    ex.submit(kis_api.get_index_price, "1001"),
                "J_investor": ex.submit(kiwoom_api.get_market_investor, "J"),
                "Q_investor": ex.submit(kiwoom_api.get_market_investor, "Q"),
                "J_prog":         ex.submit(kiwoom_api.get_program_trade, "J"),
                "Q_prog":         ex.submit(kiwoom_api.get_program_trade, "Q"),
                "J_prog_series":  ex.submit(kiwoom_api.get_program_trade_series, "J"),
                "Q_prog_series":  ex.submit(kiwoom_api.get_program_trade_series, "Q"),
                "NQ":         ex.submit(global_api.get_nasdaq_futures) if global_api else None,
                "KSF":        ex.submit(global_api.get_kospi_futures) if global_api else None,
                "KSFN":       ex.submit(global_api.get_kospi_night_futures) if global_api else None,
                "USDKRW":     ex.submit(global_api.get_usdkrw) if global_api else None,
                "WTI":        ex.submit(global_api.get_wti) if global_api else None,
                "RANK_POP":   ex.submit(naver_api.get_popular_stocks, 30),
                "RANK_AMT":   ex.submit(kis_api.get_inquiry_rank, 30),
            }
            done = {}
            for k, f in tasks.items():
                try: done[k] = f.result(timeout=15)
                except Exception: done[k] = None
        _enrich_rank_prices(done)  # 순위 목록 가격을 KIS 시세로 통일
        result = _build_market_flow_result(done)
        # 정상일 때만 캐시 저장(열화 캐시 오염 방지) — bars+가격 있어야 정상
        if _mf_is_good(result):
            _prewarm_cache["market_flow"] = {"data": done, "ts": time.time()}
        return _serve_mf(result)   # 열화면 직전 정상 그래프 유지
    except Exception as e:
        # 예외 시에도 직전 정상 그래프 유지 (그래프 사라짐 방지)
        if _last_good_mf["result"]:
            return JSONResponse(content=_last_good_mf["result"])
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── 히트맵 캐시 (탭 전환 속도 개선) ──────────────────────────
_heatmap_cache: dict = {}           # {key: {"data": ..., "ts": float}}
_heatmap_building: set = set()      # 현재 빌드 중인 key 집합
_heatmap_lock = threading.Lock()
_HEATMAP_TTL = 180                  # 3분 캐시


def _heatmap_merge_keep(key: str, data: dict) -> dict:
    """새 빌드에서 빠진 섹터가 직전 캐시에 있으면 이어붙여 '섹터 사라짐(테마 등 간헐 누락)' 방지.
    섹터 집합은 원래 고정이므로, 일시적으로 일부가 빠져도 이전 데이터로 채워 항상 전부 표시."""
    try:
        if not (data and data.get("sectors")):
            return data
        prev = (_heatmap_cache.get(key) or {}).get("data")
        if prev and prev.get("sectors"):
            new_names = {s.get("name") for s in data["sectors"]}
            # 사용자가 숨긴 섹터(hidden_sectors)는 되살리지 않음 — 큐레이션 존중
            try:
                from sector_heatmap import _load_sector_custom as _lsc
                _hidden = set(_lsc().get("hidden_sectors", []))
            except Exception:
                _hidden = set()
            for ps in prev["sectors"]:
                if ps.get("name") not in new_names and ps.get("name") not in _hidden:
                    data["sectors"].append(ps)
            data["sectors"].sort(key=lambda x: x.get("avg_rate", 0) or 0, reverse=True)
    except Exception:
        pass
    return data


def _heatmap_cached(key: str, fn):
    """캐시 hit이면 즉시 반환, miss면 fn() 호출 후 캐시 저장. 빈 결과면 이전 캐시 유지."""
    now = time.time()
    entry = _heatmap_cache.get(key)
    if entry and now - entry["ts"] < _HEATMAP_TTL:
        return entry["data"]
    data = fn()
    if data and data.get("sectors"):
        data = _heatmap_merge_keep(key, data)
        _heatmap_cache[key] = {"data": data, "ts": now}
        return data
    return entry["data"] if entry else data   # 빌드 실패/빈 결과 → 직전 캐시 유지


def _heatmap_build_bg(key: str, fn):
    """캐시 없을 때 백그라운드 스레드로 빌드. 중복 실행 방지."""
    with _heatmap_lock:
        if key in _heatmap_building:
            return
        _heatmap_building.add(key)

    def _run():
        try:
            data = fn()
            if data and data.get("sectors"):   # 빈 빌드는 캐시 오염 방지(직전 캐시 유지)
                data = _heatmap_merge_keep(key, data)
                _heatmap_cache[key] = {"data": data, "ts": time.time()}
        except Exception:
            pass
        finally:
            with _heatmap_lock:
                _heatmap_building.discard(key)

    threading.Thread(target=_run, daemon=True).start()


@app.get("/api/heatmap_tab")
def api_heatmap_tab(id: str = "semi"):
    if build_heatmap_tab is None:
        return JSONResponse(content={"error": "build_heatmap_tab 없음"}, status_code=503)
    key = f"tab:{id}"
    entry = _heatmap_cache.get(key)
    if entry and time.time() - entry["ts"] < _HEATMAP_TTL:
        return JSONResponse(content=entry["data"])
    _heatmap_build_bg(key, lambda: build_heatmap_tab(id))
    return JSONResponse(content={"loading": True, "retry_after": 5, "sectors": [],
                                 "updated_at": "데이터 준비 중…"})


@app.get("/api/heatmap_tab/refresh")
def api_heatmap_tab_refresh(id: str = "semi"):
    """캐시 무효화 후 강제 재조회."""
    _heatmap_cache.pop(f"tab:{id}", None)
    return api_heatmap_tab(id)


@app.get("/api/heatmap_tabs_meta")
def api_heatmap_tabs_meta():
    return JSONResponse(content=TAB_GROUPS)


@app.get("/api/heatmap")
def api_heatmap(mode: str = "regular"):
    """mode=nxt — 정규장 마감가(15:30) 대비 등락률로 재계산한 NXT 애프터아워 전용 뷰."""
    if build_heatmap is None:
        return JSONResponse(content={"error": "sector_heatmap 로드 실패"}, status_code=503)
    key = "all_nxt" if mode == "nxt" else "all"
    # 캐시 hit → 즉시 반환
    entry = _heatmap_cache.get(key)
    if entry and time.time() - entry["ts"] < _HEATMAP_TTL:
        return JSONResponse(content=entry["data"])
    # 캐시 miss → 백그라운드 빌드 시작 후 "준비 중" 즉시 응답
    _heatmap_build_bg(key, (lambda: build_heatmap(mode="nxt")) if mode == "nxt" else build_heatmap)
    return JSONResponse(content={"loading": True, "retry_after": 5, "sectors": [],
                                 "updated_at": "데이터 준비 중…"})


@app.get("/api/heatmap/refresh")
def api_heatmap_refresh(mode: str = "regular"):
    """캐시 무효화 후 강제 재조회."""
    key = "all_nxt" if mode == "nxt" else "all"
    _heatmap_cache.pop(key, None)
    return api_heatmap(mode=mode)


@app.get("/api/net/unattributed")
def api_net_unattributed(top_n: int = 5, days: int = 3, min_rate: float = 3.0,
                         min_graph_strength: int = 3):
    """미귀속 강세 스캔: 이유 못 찾은 강세를 최상단에 고정한 랭킹 + 촘촘함 지표.
    min_graph_strength: 그래프-연계 귀속 시 관련원자 강도 임계(↑=엄격, 과잉귀속 방지)."""
    try:
        return JSONResponse(content=_strength_net.scan_heatmap(
            top_n=top_n, days=days, min_rate=min_rate, min_graph_strength=min_graph_strength))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=503)


@app.get("/api/net/hunt")
def api_net_hunt(name: str, days: int = 3):
    """원인추적 캐스케이드: 미귀속 종목의 원인을 소스 신뢰등급 순으로 계단식 수색(공시→뉴스→텔레→종토방→LLM추론)."""
    try:
        from pipeline.atoms import cause_hunt
        return JSONResponse(content=cause_hunt.hunt_with_llm(name, days=days))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=503)


# ── 섹터 커스텀 편집 ──────────────────────────────────────
SECTOR_CUSTOM_PATH = os.path.join(ROOT, "pipeline", "sector_custom.json")
SECTOR_SNAP_DIR    = os.path.join(ROOT, "pipeline", "sector_custom_snapshots")
KRX_CODES_PATH     = os.path.join(ATOMS_DIR, "krx_codes.json")
TAERINI_STOCK_PATH = os.path.join(ROOT, "pipeline", "taerini_stock.json")
TAERINI_CONSENSUS_PATH = os.path.join(ROOT, "pipeline", "taerini_consensus.json")


def _snapshot_sector_custom(label="auto", keep=60):
    """편집 저장 직전 현재 sector_custom.json을 타임스탬프 백업. 최근 keep개만 유지."""
    try:
        if not os.path.exists(SECTOR_CUSTOM_PATH):
            return None
        os.makedirs(SECTOR_SNAP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(SECTOR_SNAP_DIR, f"sc_{ts}_{label}.json")
        if not os.path.exists(dst):
            shutil.copy2(SECTOR_CUSTOM_PATH, dst)
        snaps = sorted(glob.glob(os.path.join(SECTOR_SNAP_DIR, "sc_*.json")))
        for old in snaps[:-keep]:
            try:
                os.remove(old)
            except Exception:
                pass
        return os.path.basename(dst)
    except Exception:
        return None


def _snap_summary(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {"hidden": len(d.get("hidden_sectors", [])),
                "rename": len(d.get("sector_rename", {})),
                "extra": len(d.get("extra_stocks", {})),
                "removed": len(d.get("removed_stocks", {}))}
    except Exception:
        return {}


@app.get("/api/sector_custom")
def api_sector_custom_get():
    if os.path.exists(SECTOR_CUSTOM_PATH):
        try:
            with open(SECTOR_CUSTOM_PATH, encoding="utf-8") as f:
                return JSONResponse(content=json.load(f))
        except Exception:
            pass
    return JSONResponse(content={"custom_tiles": [], "extra_stocks": {}, "removed_stocks": {}, "hidden_sectors": []})


@app.post("/api/sector_custom")
async def api_sector_custom_post(req: Request):
    data = await req.json()
    _snapshot_sector_custom("auto")   # 덮어쓰기 전 이전 상태 자동 백업(중간마다)
    with open(SECTOR_CUSTOM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _heatmap_cache.clear()   # 모든 캐시 무효화
    return JSONResponse(content={"ok": True})


@app.get("/api/sector_custom/snapshots")
def api_sector_custom_snapshots():
    """스냅샷 목록(최신순): [{file, ts, label, 요약}]."""
    out = []
    for p in sorted(glob.glob(os.path.join(SECTOR_SNAP_DIR, "sc_*.json")), reverse=True):
        fn = os.path.basename(p)
        parts = fn[3:-5].split("_")   # sc_YYYYMMDD_HHMMSS_label
        ts = (parts[0] + "_" + parts[1]) if len(parts) >= 2 else fn
        label = parts[2] if len(parts) >= 3 else ""
        try:
            disp = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%m/%d %H:%M:%S")
        except Exception:
            disp = ts
        out.append({"file": fn, "ts": disp, "label": label, "summary": _snap_summary(p)})
    return JSONResponse(content=out)


@app.post("/api/sector_custom/snapshot")
def api_sector_custom_snapshot_now():
    """현재 상태를 수동 스냅샷."""
    fn = _snapshot_sector_custom("manual")
    return JSONResponse(content={"ok": bool(fn), "file": fn})


@app.post("/api/sector_custom/restore")
async def api_sector_custom_restore(req: Request):
    """스냅샷으로 복원(복원 전 현재 상태도 백업)."""
    body = await req.json()
    fn = (body or {}).get("file", "")
    src = os.path.join(SECTOR_SNAP_DIR, os.path.basename(fn))
    if not fn or not os.path.exists(src) or not os.path.basename(fn).startswith("sc_"):
        return JSONResponse(content={"ok": False, "error": "스냅샷 없음"}, status_code=404)
    _snapshot_sector_custom("prerestore")   # 되돌리기 전 현재도 백업
    shutil.copy2(src, SECTOR_CUSTOM_PATH)
    _heatmap_cache.clear()
    return JSONResponse(content={"ok": True, "file": os.path.basename(fn)})


# ── 관심종목(워치리스트) ───────────────────────────────────
WATCHLIST_PATH = os.path.join(ROOT, "pipeline", "watchlist.json")


def _load_watchlist_codes():
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, encoding="utf-8") as f:
                return json.load(f).get("codes", [])
        except Exception:
            pass
    return []


@app.get("/api/watchlist")
def api_watchlist_get(flow: int = 1):
    """관심종목 목록 + 현재가/등락률 (멀티시세).

    flow=1(기본): 종목별 잠정수급(외인/기관/개인/프로그램)도 키움에서 병렬로 끌어와 첨부.
    flow=0: 가격만 빠르게.
    """
    codes = _load_watchlist_codes()
    items = []
    if codes:
        # ETF바와 동일한 KIS-다운 감지(쿨다운/프로브) — 장마감·주말·KIS 장애 시 라이브 시도를
        # 건너뛰고 네이버로 마지막 거래일 종가·등락률 폴백(0/0.00%로 비는 것 방지).
        skip_live = (time.time() - _etf_kis_down["ts"] < _ETF_DOWN_COOLDOWN) or not _kis_reachable()
        prices = {}
        if not skip_live:
            try:
                import kis_api
                prices = kis_api.get_prices_multi([c["code"] for c in codes])
                if not any((p or {}).get("price") for p in prices.values()):
                    skip_live = True
                    _etf_kis_down["ts"] = time.time()
            except Exception:
                skip_live = True
                _etf_kis_down["ts"] = time.time()
        if skip_live:
            naver = _naver_sessions_batch([c["code"] for c in codes])
            for c in codes:
                r = naver.get(c["code"]) or {}
                items.append({"code": c["code"], "name": c.get("name", ""),
                              "price": r.get("price", 0),
                              "change_rate": r.get("change_rate", 0)})
        else:
            for c in codes:
                p = prices.get(c["code"]) or {}
                items.append({"code": c["code"],
                              "name": c.get("name") or p.get("name") or c["code"],
                              "price": p.get("price", 0),
                              "change_rate": p.get("change_rate", 0)})

    # 종목별 잠정수급 첨부 (키움 ka10059+ka90013, 종목당 2콜 → 종목 단위 병렬)
    # 키움 실패/전부 0(서버에 키움 키 미등록) → KIS(FHKST01010900+FHPPG04650200) 폴백
    # KIS가 죽어있으면(쿨다운/프로브) 이 KIS 폴백도 종목당 타임아웃까지 기다리게 되어 전체
    # /api/watchlist 응답이 통째로 멈추는 문제 발견(2026-07-04) — ETF바와 동일한 가드로 건너뛴다.
    kis_down_for_supply = (time.time() - _etf_kis_down["ts"] < _ETF_DOWN_COOLDOWN) or not _kis_reachable()
    if flow and items:
        try:
            import kiwoom_api, kis_api
            from concurrent.futures import ThreadPoolExecutor

            def _fetch(code):
                try:
                    d = kiwoom_api.get_stock_supply(code)
                except Exception:
                    d = None
                if (not d or not any(d.get(k) for k in ("외인", "기관", "개인", "프로그램"))) and not kis_down_for_supply:
                    try:
                        d = kis_api.get_stock_supply(code)
                    except Exception:
                        pass
                return d

            with ThreadPoolExecutor(max_workers=min(10, len(items))) as ex:
                futs = {it["code"]: ex.submit(_fetch, it["code"]) for it in items}
                for it in items:
                    try:
                        it["supply"] = futs[it["code"]].result(timeout=12)
                    except Exception:
                        it["supply"] = None
        except Exception:
            pass
    return JSONResponse(content={"items": items})


@app.post("/api/watchlist")
async def api_watchlist_post(req: Request):
    """관심종목 저장. body: {codes:[{code,name},...]}.
    프론트가 항상 클라이언트 로컬상태(_wlCodes) 전체로 덮어쓰는 구조라, 그 로컬상태가
    (서버 재시작 타이밍 등으로) 비어있는 채로 저장을 호출하면 실수로 전체 목록이 사라질 수
    있다(2026-07-04 실제 발생). 덮어쓰기 전에 직전 파일을 .bak으로 한 벌 남겨 항상 복구 가능하게 함."""
    data = await req.json()
    codes = data.get("codes", [])
    try:
        if os.path.exists(WATCHLIST_PATH):
            with open(WATCHLIST_PATH, encoding="utf-8") as f:
                prev = json.load(f)
            if prev.get("codes"):
                with open(WATCHLIST_PATH + ".bak", "w", encoding="utf-8") as f:
                    json.dump(prev, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump({"codes": codes}, f, ensure_ascii=False, indent=2)
    return JSONResponse(content={"ok": True})


# 흔한 약칭·구명칭 → KRX 정식 종목명 (substring 검색으로 안 잡히는 별칭 보강)
_SEARCH_ALIASES = {
    "현대차": "현대자동차", "현차": "현대자동차",
    "기아차": "기아",
    "삼전": "삼성전자", "삼성전자우": "삼성전자우",
    "하이닉스": "SK하이닉스", "하닉": "SK하이닉스", "sk하닉": "SK하이닉스",
    "네이버": "NAVER",
    "엔솔": "LG에너지솔루션", "lg엔솔": "LG에너지솔루션", "엘지엔솔": "LG에너지솔루션",
    "삼바": "삼성바이오로직스",
    "카뱅": "카카오뱅크", "카페이": "카카오페이",
    "포스코": "POSCO홀딩스",
    "현대중공업": "HD현대중공업", "한국전력": "한국전력공사",
}

# KRX 정식명 → 실제 통용 종목명(표시·저장용). 예: 현대자동차 → 현대차
_DISPLAY_NAME = {
    "현대자동차": "현대차",
}


def _disp_name(name: str) -> str:
    return _DISPLAY_NAME.get(name, name)


@app.get("/api/stock_search")
def api_stock_search(q: str = ""):
    if not q.strip():
        return JSONResponse(content=[])
    try:
        with open(KRX_CODES_PATH, encoding="utf-8") as f:
            codes_data = json.load(f)
        codes = codes_data.get("codes", {})
        q_l = q.strip().lower()
        results = [{"name": _disp_name(n), "code": c} for n, c in codes.items()
                   if q_l in n.lower() or q_l in _disp_name(n).lower()]
        seen = {r["code"] for r in results}
        # 별칭 매칭 → 정식명 종목을 항상 최상단으로 (예: '현대차' → 현대차[005380]가 현대차증권보다 위)
        for alias, official in _SEARCH_ALIASES.items():
            if q_l in alias.lower():
                c = codes.get(official)
                if c:
                    results = [r for r in results if r["code"] != c]
                    results.insert(0, {"name": _disp_name(official), "code": c})
                    seen.add(c)
        return JSONResponse(content=results[:20])
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── 종목 캔들 차트 (종목 클릭 → 차트 모달, 키움 ka10081/ka10080) ──
_candle_cache: dict = {}      # {"code:tf": {"data": [...], "ts": float}}
_last_good_candles: dict = {}  # {"code:tf": [...]} — 분봉 다일치 급감 방어용(네이버 fchart 일시실패 대비)


@app.get("/api/stock_candles")
def api_stock_candles(code: str = "", tf: str = "D"):
    """종목 OHLCV 캔들. tf='D'일/'W'주/'M'월 / '5'·'30'·'60'분봉. 60초 캐시."""
    code = code.strip()
    if not code:
        return JSONResponse(content={"candles": []})
    if tf not in ("D", "W", "M", "1", "3", "5", "10", "15", "30", "60"):
        tf = "D"
    key = f"{code}:{tf}"
    now = time.time()
    ent = _candle_cache.get(key)
    if ent and now - ent["ts"] < 60:
        return JSONResponse(content={"tf": tf, "candles": ent["data"]})
    try:
        import kiwoom_api, kis_api
        try:
            data = kiwoom_api.get_stock_candles(code, tf)
        except Exception:
            data = []
        # ── 키움 부재/실패(예: 서버) → KIS 폴백 ──
        if not data:
            if tf in ("D", "W", "M"):
                data = kis_api.get_daily_ohlc(code, tf)
                # KIS도 죽어있으면(2026-07-04 KIS 장애처럼) 네이버 공개 일봉으로 최종 폴백
                if not data and tf == "D":
                    try:
                        import naver_api as _nv
                        data = _nv.daily_candles(code)
                    except Exception:
                        data = []
            else:
                # 분봉: 네이버 fchart로 '다일치' 캔들 확보(사용자 요청) + 오늘치는 KIS 정밀 OHLC로 덮어씀
                try:
                    import naver_api as _nv
                    data = _nv.minute_candles(code, int(tf))
                except Exception:
                    data = []
                try:
                    kis_today = kis_api.get_minute_bars_ohlc(code, tf)
                except Exception:
                    kis_today = []
                if data and kis_today:
                    by_t = {b["time"]: b for b in data}
                    for b in kis_today:
                        by_t[b["time"]] = b   # 오늘 버킷을 KIS 정밀값으로 교체
                    data = [by_t[t] for t in sorted(by_t)]
                elif not data:
                    data = kis_today   # fchart 실패 시 오늘치라도
        # ── NXT 반영: 장외(15:30 이후·09시 이전)엔 KIS 통합(UN) 시세를 차트에 이어붙임 ──
        try:
            import datetime as _dt, kis_api
            hhmm = _dt.datetime.now().strftime("%H%M")
            afterhours = hhmm > "1530" or hhmm < "0900"
            if afterhours and data:
                if tf in ("1", "3", "5", "10", "15", "30", "60"):
                    ext = kis_api.get_minute_bars_ohlc(code, tf)   # NXT 시간외 분봉 포함
                    last_t = data[-1]["time"]
                    add = [b for b in ext if isinstance(b.get("time"), (int, float)) and b["time"] > last_t]
                    if add:
                        data = data + add
                # 모든 봉: 마지막 봉 종가를 NXT 실시간가(순위·현재가와 동일 소스)로 통일
                p = kis_api.get_price(code)  # UN(통합) 현재가
                px = p.get("price") or 0
                if px > 0:
                    b = data[-1]
                    b["close"] = px
                    b["high"] = max(b.get("high", px), px)
                    b["low"] = min(b.get("low", px) or px, px)
        except Exception:
            pass
        # ── 분봉 다일치 급감 방어: 네이버 fchart 일시 실패로 캔들 수가 확 줄면 직전 정상 데이터 유지 ──
        # (일봉/주봉/월봉은 매번 전체 재계산이라 대상 아님. 분봉은 여러 날 누적이라 과거 봉이
        #  줄어드는 건 항상 비정상 — market_flow bars 급감방어(47df85c0)와 같은 패턴, 분봉판)
        if tf not in ("D", "W", "M"):
            prev_good = _last_good_candles.get(key)
            if data and prev_good and len(data) < len(prev_good) * 0.7:
                data = prev_good
            elif data:
                _last_good_candles[key] = data
        _candle_cache[key] = {"data": data, "ts": now}
        return JSONResponse(content={"tf": tf, "candles": data})
    except Exception as e:
        return JSONResponse(content={"error": str(e), "candles": []}, status_code=500)


@app.get("/api/taerini_stock")
def api_taerini_stock(code: str = ""):
    code = (code or "").strip()
    if code.isdigit():
        code = code.zfill(6)
    if not code or not os.path.exists(TAERINI_STOCK_PATH):
        return JSONResponse(content={"found": False, "date": None})
    try:
        with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
            data = json.load(f)
        stock = (data.get("stocks") or {}).get(code)
        if not stock:
            live = _live_osc_fallback(code)  # 엑셀 미수록 종목(커스텀 추가 등) → 실시간 osc
            if live:
                return JSONResponse(content={"found": True, "live": True,
                                             "date": data.get("date"), "stock": live})
            return JSONResponse(content={"found": False, "date": data.get("date")})
        return JSONResponse(content={"found": True, "date": data.get("date"), "stock": stock})
    except Exception as e:
        return JSONResponse(content={"found": False, "error": str(e)})


def _live_osc_fallback(code: str):
    """taerini(엑셀)에 없는 종목의 실시간 수급 osc. 실패·오류는 조용히 None."""
    try:
        import osc_live
        return osc_live.live_osc_entry(code)
    except Exception:
        return None


# 빈집(수급 오실레이터)을 어디서 가져올지 **한 군데서만** 정한다.
#
# 엑셀 경로가 등급(A완전빈집/B반빈집/C정상/D과매수)까지 주지만, 전종목 분포가 있어야
# 백분위가 나오므로 실시간 경로는 방향(↑재진입 등)만 준다.
# ⚠️ 실측(2026-08-15): taerini_stock.json에 종목은 132개 있는데 **osc 키를 가진 종목이 0개**다
#    (엑셀 산출물이 2026-05-27에서 멈춤). 그래서 "엑셀에 종목이 있다"만 보고 판단하면
#    빈집 칸이 조용히 빈다 — 반드시 osc 값 자체가 있는지를 확인하고 없으면 실시간으로 넘긴다.
def _vacuum_for(code: str) -> dict | None:
    """{osc, pct, grade, trend, series, source} — 못 구하면 None."""
    code = (code or "").strip().zfill(6) if (code or "").strip().isdigit() else (code or "").strip()
    if not code:
        return None

    entry, source = None, ""
    try:
        if os.path.exists(TAERINI_STOCK_PATH):
            with open(TAERINI_STOCK_PATH, encoding="utf-8") as f:
                data = json.load(f)
            cand = (data.get("stocks") or {}).get(code) or {}
            if cand.get("osc") is not None:
                entry, source = cand, "excel"
    except Exception:
        entry = None

    if entry is None:
        entry = _live_osc_fallback(code)
        source = "live"
    if not entry:
        return None

    # ⚠️ 두 경로가 모양이 다르다 — taerini(엑셀)는 osc 값을 평평하게 담고,
    #    osc_live.live_osc_entry()는 {"osc": {...}} 로 한 겹 감싸 준다.
    #    안 풀면 osc가 dict로 들어가 trend·series가 조용히 빈다(실측으로 잡음).
    inner = entry.get("osc")
    if isinstance(inner, dict):
        entry = inner
    if entry.get("osc") is None:
        return None

    pct = entry.get("pct")
    return {
        "osc": entry.get("osc"),
        "pct": pct,
        "grade": _vacuum_grade(pct),
        "trend": entry.get("trend") or "",
        "series": entry.get("series") or [],
        "group": entry.get("group") or "",
        "source": source,
    }


def _vacuum_grade(pct) -> str:
    """백분위 → 등급. calc_oscillator.grade()와 같은 경계(10/25/75)를 쓴다.
    백분위가 없으면(실시간 경로) 등급을 지어내지 않고 빈 문자열."""
    if pct is None:
        return ""
    if pct <= 10:
        return "A 완전빈집"
    if pct <= 25:
        return "B 반빈집"
    if pct <= 75:
        return "C 정상"
    return "D 과매수"


@app.get("/api/taerini_consensus")
def api_taerini_consensus(code: str = ""):
    """종목별 주간 컨센 시계열(12MF/FY1/FY2) — 차트 오버레이용."""
    code = (code or "").strip()
    if code.isdigit():
        code = code.zfill(6)
    if not code or not os.path.exists(TAERINI_CONSENSUS_PATH):
        return JSONResponse(content={"found": False})
    try:
        with open(TAERINI_CONSENSUS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        stock = (data.get("stocks") or {}).get(code)
        if not stock:
            return JSONResponse(content={"found": False, "date": data.get("date")})
        return JSONResponse(content={
            "found": True,
            "date": data.get("date"),
            "dates": data.get("dates") or [],
            "name": stock.get("name"),
            "series": {k: stock.get(k) for k in ("12mf", "fy1", "fy2") if stock.get(k)},
        })
    except Exception as e:
        return JSONResponse(content={"found": False, "error": str(e)})


# ── 종목별 잠정수급 배치 (히트맵 타일 행용) ──────────────────
_supply_cache: dict = {}      # {code: {"data": supply, "ts": float}}
_SUPPLY_TTL = 600             # 10분 (수급은 분 단위로 천천히 변함)


@app.get("/api/stock_supply_batch")
def api_stock_supply_batch(codes: str = ""):
    """여러 종목 잠정수급(외인/기관/개인/프로그램) 일괄 조회. 종목당 10분 캐시.

    codes: 콤마구분 종목코드 (최대 60). 반환: {code: {외인,기관,개인,프로그램,ts}}
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()][:60]
    if not code_list:
        return JSONResponse(content={})
    now = time.time()
    out: dict = {}
    need = []
    for c in code_list:
        ent = _supply_cache.get(c)
        if ent and now - ent["ts"] < _SUPPLY_TTL:
            out[c] = ent["data"]
        else:
            need.append(c)
    if need:
        try:
            import kiwoom_api, kis_api
            from concurrent.futures import ThreadPoolExecutor

            def _fetch(c):
                try:
                    d = kiwoom_api.get_stock_supply(c)
                except Exception:
                    d = None
                # 키움 실패/전부 0(서버에 키움 키 미등록) → KIS 폴백
                if not d or not any(d.get(k) for k in ("외인", "기관", "개인", "프로그램")):
                    try:
                        d = kis_api.get_stock_supply(c)
                    except Exception:
                        pass
                return d

            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {c: ex.submit(_fetch, c) for c in need}
                for c in need:
                    try:
                        d = futs[c].result(timeout=12)
                    except Exception:
                        d = None
                    if d:
                        _supply_cache[c] = {"data": d, "ts": now}
                        out[c] = d
        except Exception:
            pass
    return JSONResponse(content=out)


@app.get("/api/sector_names")
def api_sector_names():
    """섹터 이름 목록 (가격 조회 없음, 빠름). 편집 탭 초기화용. 꺼낸 세부테마(CXL 등)도 포함해 복원 가능."""
    try:
        from sector_heatmap import parse_watchlist, surfaced_sub_names  # noqa: E402
        sections = parse_watchlist(top_n=1)
        names = [s["sector"] for s in sections]
        for n in surfaced_sub_names():
            if n not in names:
                names.append(n)
        return JSONResponse(content=names)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/ws_status")
def api_ws_status():
    """WebSocket 실시간 상태 확인."""
    if not kis_ws:
        return JSONResponse(content={"status": "disabled"})
    now = time.time()
    live = {}
    for k, v in kis_ws._LIVE.items():
        live[k] = {"price": v["price"], "change_rate": v["change_rate"],
                   "age_sec": round(now - v["ts"], 1)}
    st = kis_ws.status()
    st["live"] = live
    return JSONResponse(content=st)


@app.get("/api/sector_stocks")
def api_sector_stocks(sector: str = ""):
    """특정 섹터의 기본 종목 목록 반환 (가격 없음, 편집탭용)."""
    if not sector.strip():
        return JSONResponse(content={"base": [], "extra": [], "removed": []})
    try:
        from sector_heatmap import (  # noqa: E402
            parse_watchlist, _parse_raw_full, _collect_split_subs, _collect_surfaced_subs,
        )
        # custom 데이터는 파일에서 직접 읽기 (server.py에 _load_sector_custom 없음)
        custom: dict = {}
        if os.path.exists(SECTOR_CUSTOM_PATH):
            with open(SECTOR_CUSTOM_PATH, encoding="utf-8") as f:
                custom = json.load(f)
        sections = parse_watchlist(top_n=999)
        base = []
        for sec in sections:
            if sec["sector"] == sector:
                base = [{"name": s["name"], "code": s["code"]} for s in sec["stocks"]]
                break
        if not base:
            # 분할/서브 타일(전선·변압기·HBM 등)은 parse_watchlist 상위 섹션에 없음 —
            # 히트맵 타일 생성과 같은 소스(split/surfaced subs)에서 폴백 검색
            raw_full = _parse_raw_full()
            for nm, _parent, sts in _collect_split_subs(raw_full) + _collect_surfaced_subs(raw_full):
                if nm == sector:
                    base = [{"name": s["name"], "code": s["code"]} for s in sts]
                    break
        if not base:
            # 커스텀 타일(사용자가 만든 테마)은 watchlist/서브에 없고 custom_tiles[].stocks에 있다.
            # 이걸 안 읽어서 편집모달이 커스텀 타일을 "종목 없음"으로 표시하던 버그 수정.
            for ct in custom.get("custom_tiles", []):
                if ct.get("name") == sector:
                    base = [{"name": s["name"], "code": s["code"]}
                            for s in ct.get("stocks", []) if s.get("code")]
                    break
        extra = custom.get("extra_stocks", {}).get(sector, [])
        removed = custom.get("removed_stocks", {}).get(sector, [])
        return JSONResponse(content={"base": base, "extra": extra, "removed": removed})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── 딸깍 스튜디오 ─────────────────────────────────────────
@app.get("/studio", response_class=HTMLResponse)
def studio_page():
    p = os.path.join(HERE, "studio.html")
    if not os.path.exists(p):
        return "<h1>studio.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        return f.read()


@app.get("/studio/gallery")
def studio_gallery():
    p = os.path.join(STUDIO_DIR, "index.json")
    if not os.path.exists(p):
        return JSONResponse(content=[])
    with open(p, encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.post("/studio/generate")
def studio_generate(date: str, mode: str = "picks"):
    gen = generate_briefing if mode == "briefing" else generate_picks

    def event_stream():
        if gen is None:
            yield 'data: {"type": "error", "message": "studio_pipeline 없음"}\n\n'
            return
        for ev in gen(date):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/studio/file")
def studio_file(path: str):
    # out/studio 내부만 허용 (경로 탈출 차단)
    base = os.path.abspath(STUDIO_DIR)
    full = os.path.abspath(os.path.join(base, path))
    # out/studio 내부만 허용 (형제 디렉토리 studio_evil 우회 차단)
    if not (full == base or full.startswith(base + os.sep)):
        return JSONResponse(content={"error": "허용되지 않은 경로"}, status_code=403)
    if not os.path.exists(full):
        return JSONResponse(content={"error": "없음"}, status_code=404)
    return FileResponse(full)


# ── 백그라운드 캐시 프리워밍 ────────────────────────────────────
_prewarm_cache: dict = {}   # {"market_flow": {data, ts}, "etf_bar": {data, ts}, "heatmap": {data, ts}}
_PREWARM_TTL = 60           # 1분

def _prewarm_worker():
    """서버 시작 시 즉시 + 이후 5분마다 핵심 API를 미리 fetch해 캐시에 저장."""
    import kis_api, kiwoom_api, naver_api
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 서버 시작 시 전일종가 스크래핑 (백그라운드)
    if global_api:
        try:
            global_api.scrape_all_prevclose()
        except Exception:
            pass

    def _fetch_market_flow():
        try:
            kis_api._token()
            kiwoom_api._token()
        except Exception:
            pass
        with ThreadPoolExecutor(max_workers=22) as ex:
            tasks = {
                "J_bars":     ex.submit(kis_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kis_api.get_index_minutebar, "1001", 15),
                "J_bars_1m":  ex.submit(kis_api.get_index_minutebar, "0001", 1),
                "Q_bars_1m":  ex.submit(kis_api.get_index_minutebar, "1001", 1),
                "J_bars_1d":  ex.submit(kis_api.get_index_daily_bars, "0001", 30),
                "Q_bars_1d":  ex.submit(kis_api.get_index_daily_bars, "1001", 30),
                "J_price":    ex.submit(kis_api.get_index_price, "0001"),
                "Q_price":    ex.submit(kis_api.get_index_price, "1001"),
                "J_investor":     ex.submit(kiwoom_api.get_market_investor, "J"),
                "Q_investor":     ex.submit(kiwoom_api.get_market_investor, "Q"),
                "J_prog":         ex.submit(kiwoom_api.get_program_trade, "J"),
                "Q_prog":         ex.submit(kiwoom_api.get_program_trade, "Q"),
                "J_prog_series":  ex.submit(kiwoom_api.get_program_trade_series, "J"),
                "Q_prog_series":  ex.submit(kiwoom_api.get_program_trade_series, "Q"),
                "NQ":         ex.submit(global_api.get_nasdaq_futures) if global_api else None,
                "KSF":        ex.submit(global_api.get_kospi_futures) if global_api else None,
                "KSFN":       ex.submit(global_api.get_kospi_night_futures) if global_api else None,
                "USDKRW":     ex.submit(global_api.get_usdkrw) if global_api else None,
                "WTI":        ex.submit(global_api.get_wti) if global_api else None,
                "RANK_POP":   ex.submit(naver_api.get_popular_stocks, 30),
                "RANK_AMT":   ex.submit(kis_api.get_inquiry_rank, 30),
            }
            done = {}
            for k, f in tasks.items():
                try: done[k] = f.result()
                except Exception: done[k] = None
        _enrich_rank_prices(done)  # 순위 목록 가격을 KIS 시세로 통일
        return done

    def _fetch_etf_bar():
        try:
            from sector_heatmap import parse_etf_bar
            from concurrent.futures import ThreadPoolExecutor as _TPE2, as_completed as _ac2
            etfs = parse_etf_bar()
            # KIS가 죽어있으면(쿨다운 중이거나 프로브 실패) 이 사이클은 라이브 시도를 건너뛴다.
            # 안 건너뛰면 종목당 8초 타임아웃이 누적되어(19종목=최대 수십초~분) 다음 프리워밍
            # 사이클(market_flow·heatmap 포함)까지 통째로 지연시킴.
            if (time.time() - _etf_kis_down["ts"] < _ETF_DOWN_COOLDOWN) or not _kis_reachable():
                _etf_kis_down["ts"] = time.time()
                return []
            codes = [e["code"] for e in etfs]
            prices = kis_api.get_prices_batch_parallel(codes)
            # 분봉(스파크라인)도 캐시에 포함 → 캐시 히트 시 차트 사라지는 문제 해결
            bars_map = {c: [] for c in codes}
            with _TPE2(max_workers=5) as _ex2:
                _futs = {_ex2.submit(kis_api.get_minutebar, c, 1): c for c in codes}
                for _f in _ac2(_futs):
                    try: bars_map[_futs[_f]] = _f.result()
                    except Exception: bars_map[_futs[_f]] = []
            for e in etfs:
                p = prices.get(e["code"]) or {}
                e["change_rate"] = float(p.get("change_rate", 0) or 0)
                e["price"] = int(p.get("price", 0) or 0)
                e["bars"] = bars_map.get(e["code"], [])
            # 백그라운드 프리워밍에서 얻은 정상 데이터도 last-good에 반영(디스크 영속)
            # — 장마감·주말·KIS 장애로 요청 핸들러 쪽 재시도가 쿨다운 중이어도 이 갱신은 계속 도니
            # KIS가 복구되면 여기서 먼저 잡아낸다.
            if any((e.get("price") or 0) > 0 for e in etfs):
                _last_good_etf["data"] = etfs
                _last_good_etf["ts"] = time.time()
                _save_etf_persist()
            else:
                _etf_kis_down["ts"] = time.time()
            return etfs
        except Exception:
            _etf_kis_down["ts"] = time.time()
            return []

    def _fetch_heatmap():
        try:
            from sector_heatmap import build_heatmap
            return build_heatmap()
        except Exception:
            return {}

    _last_prevclose_scrape = 0.0
    while True:
        try:
            now = datetime.now()
            # 전일종가 1시간마다 재스크래핑
            if global_api and time.time() - _last_prevclose_scrape > 3600:
                try:
                    global_api.scrape_all_prevclose()
                    _last_prevclose_scrape = time.time()
                except Exception:
                    pass

            # 장중(08:50~15:35) 또는 첫 프리워밍(캐시 비어있을 때) 항상 실행
            is_market_hours = (8, 50) <= (now.hour, now.minute) <= (15, 35)
            cache_empty = "market_flow" not in _prewarm_cache
            if is_market_hours or cache_empty:
                # market_flow / heatmap / etf_bar 병렬 실행
                from concurrent.futures import ThreadPoolExecutor as _TPE
                with _TPE(max_workers=3) as _ex:
                    f_mf  = _ex.submit(_fetch_market_flow)
                    f_hm  = _ex.submit(_fetch_heatmap)
                    f_etf = _ex.submit(_fetch_etf_bar)
                    mf  = f_mf.result()
                    hm  = f_hm.result()
                    etf = f_etf.result()
                j_price = (mf.get("J_price") or {}).get("price", 0)
                q_price = (mf.get("Q_price") or {}).get("price", 0)
                if j_price and q_price:
                    _prewarm_cache["market_flow"] = {"data": mf, "ts": time.time()}
                if etf:
                    _prewarm_cache["etf_bar"] = {"data": etf, "ts": time.time()}
                if hm:
                    _heatmap_cache["all"] = {"data": hm, "ts": time.time()}
        except Exception as e:
            pass
        # 한 사이클 ≈ 빌드 ~45s(레이트게이트 15건/초) + 30s = ~75s 주기로 갱신.
        # (15s로 줄이면 거의 연속 빌드가 되어 강제 새로고침과 게이트 예산 경쟁 → 30s로 균형)
        time.sleep(30)

threading.Thread(target=_prewarm_worker, daemon=True).start()


def _briefing_run_synthesis(alerts: list) -> None:
    """쿨다운 체크 후 종합층 실행 — 성공하면 ai_brief 항목 저장, 실패/생성없음이면 아무것도 안 함."""
    if time.time() - _briefing_last_ai_call["ts"] < 60:
        return
    _briefing_last_ai_call["ts"] = time.time()
    try:
        news_data = _NEWS_FEED.get("data")
        headlines = _briefing_news(news_data, limit=5)
        atoms_db_path = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        atoms_content = _briefing_atoms(atoms_db_path, limit=5)
        stored = _briefing_load(BRIEFING_PATH)
        prior_headlines = [f"{it['headline']}" for it in (stored.get("items") or [])
                           if it.get("kind") == "ai_brief"][:6]   # 최근 6개까지 넘겨 반복 억제
        prompt = _briefing_build_prompt(alerts, headlines, atoms_content, prior_headlines)
        if not prompt:
            return
        res = _gemini_text(prompt, keys=_briefing_keys(), models=GEMINI_TEXT_MODELS)
        if not res.get("ok"):
            return
        parsed = _briefing_parse(res.get("analysis", ""))
        if not parsed:
            return
        # 최근 ai_brief와 너무 유사하면(같은 얘기 반복) 저장 안 함 — "중복이 계속" 방지
        if any(_news_sim(parsed["headline"], p) >= 0.35 for p in prior_headlines):
            return
        severity = "red" if alerts else "yellow"
        _briefing_append(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"), "date": datetime.now().strftime("%Y-%m-%d"),
            "severity": severity,
            "headline": parsed["headline"], "body": parsed["body"],
            "sector": parsed.get("sector", ""), "kind": "ai_brief"})
    except Exception:
        pass


import briefing_phase
import briefing_events as _bev
import briefing_weather as _bw
import briefing_digest as _bdig
import briefing_state as _bstate

_WEATHER_STATE_PATH = os.path.join(ROOT, "output", "weather_state.json")
_WEATHER_CALIB_DIR = os.path.join(ROOT, "output", "weather_calib")
_BRIEFING_AGENT_CWD = os.environ.get("BRIEFING_AGENT_CWD", "/home/ubuntu/briefing_agent")
_WEATHER_MIN_INTERVAL_S = 90
_WEATHER_DAILY_CAP = 60
_weather = {"detect": {"cooldown": {}, "leg": {}}, "state": None,
            "batcher": _bdig.DigestBatcher(900), "model_toggle": 0,
            "calib_today": [], "synth_count": 0, "last_synth_ts": 0.0,
            "circulation_seen": set()}   # 순환매: 오늘 (트리거섹터,mover코드) 중복카드 방지


def _weather_tg(text: str):
    """텔레그램 전송 (BOT_TOKEN + CHAT_ID/OWNER_CHAT_ID). 실패 무시."""
    import urllib.request, urllib.parse
    token = os.environ.get("BOT_TOKEN", "")
    chat = os.environ.get("CHAT_ID", "") or os.environ.get("OWNER_CHAT_ID", "")
    if not token or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",
                               data=data, timeout=8)
    except Exception:
        pass


def _weather_calib_append(date_str, row, results):
    try:
        os.makedirs(_WEATHER_CALIB_DIR, exist_ok=True)
        rec = dict(row)
        rec["outputs"] = {m: {"verdict": r.get("verdict"), "latency_ms": r.get("_latency_ms"),
                              "model": r.get("_model")} for m, r in results.items()}
        with open(os.path.join(_WEATHER_CALIB_DIR, f"{date_str}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _weather_tick():
    """30초 틱: 스냅샷→디텍터→(발동 시)종합→스토리·insight·다이제스트. Phase0 관측."""
    now = datetime.now()
    phase = briefing_phase.session_phase(now)
    date_str = now.strftime("%Y-%m-%d")

    st = _weather["state"] or _bstate.load_state(_WEATHER_STATE_PATH)
    if _bstate.is_new_day(st or {}, date_str):
        st = _bstate.reset_state(date_str)
        _weather["detect"] = {"cooldown": {}, "leg": {}}
        _weather["calib_today"] = []
        _weather["synth_count"] = 0
        _weather["circulation_seen"] = set()   # 날짜 바뀌면 순환매 중복셋도 초기화
    _weather["state"] = st

    mf_ready = _prewarm_cache.get("market_flow") is not None
    mf = (_prewarm_cache.get("market_flow") or {}).get("data") or {}
    hm = (_heatmap_cache.get("all") or {}).get("data") or {}
    sectors = hm.get("sectors", []) if isinstance(hm, dict) else []
    j_bars = mf.get("J_bars") or []
    nq_bars = (mf.get("NQ") or {}).get("bars") or []
    curr = _bev.build_snapshot(mf, sectors, j_bars, mf.get("Q_bars") or [],
                               ts=now.strftime("%H:%M"))
    prev = st.get("baseline")
    live_ok = curr["idx"]["J"]["price"] > 0

    events = []
    if live_ok:
        events = _bev.detect_all(prev, curr, sectors, j_bars, nq_bars, phase, _weather["detect"])

    focus = briefing_phase.phase_focus(phase)
    extra_facts = {}
    if phase in ("premarket", "premarket_nxt", "afterhours", "afterhours_night"):
        ksfn = mf.get("KSFN") or {}
        extra_facts["night_futures"] = {"price": ksfn.get("price", 0), "rate": ksfn.get("change_rate", 0)}
    if phase == "premarket_nxt":
        atoms_db_path = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        movers = _pick_notable_movers(mf.get("RANK_POP") or [], mf.get("RANK_AMT") or [],
                                       _NEWS_FEED.get("data"), n=8)
        for m in movers:
            if not m.get("news_reason"):
                found = _recent_atoms_for_stock(atoms_db_path, m["name"], limit=1)
                if found:
                    m["news_reason"] = found[0]
        extra_facts["nxt_movers"] = movers
    if phase == "afterhours_night" and global_api:
        try:
            extra_facts["nasdaq_movers"] = global_api.get_nasdaq_premarket_movers()
        except Exception:
            pass
    if phase in ("intraday", "afterhours") and isinstance(hm, dict) and hm.get("sectors"):
        # 원인추적 캐스케이드(cause_hunt/strength_net) 연동 — "왜"를 숫자 나열 대신
        # 실제 귀속된 근거로 채운다. 이미 캐시된 히트맵을 재사용(별도 스크레이핑 없음).
        try:
            from pipeline.atoms import strength_net as _snet, edges as _snet_edges
            movers = _snet.movers_from_heatmap(hm, min_rate=3.0)[:8]
            ranked = _snet.rank_results(_snet.scan_movers(
                movers, days=1, related_fn=_snet_edges.related_assets))
            causes = [f"{r['name']} {r['rate']:+.1f}% — {r['issue']}"
                      for r in ranked if r.get("attributed")][:3]
            unattributed = [f"{r['name']} {r['rate']:+.1f}%"
                            for r in ranked if not r.get("attributed")][:3]
            if causes:
                extra_facts["mover_causes"] = causes
            if unattributed:
                extra_facts["unattributed_movers"] = unattributed
        except Exception:
            pass

    news = []
    try:
        atoms_db = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        news = [t.get("content", "")[:120] for t in _recent_topick_mentions(atoms_db, limit=8)]
    except Exception:
        pass
    # 전쟁·지정학·연준/금리 등 매크로 이벤트는 atoms.db 수동 ingest를 기다리지 않고
    # 원문 뉴스피드에서 바로 뽑아 종합(_weather_tick)에 넣는다 — 안 그러면 LLM이
    # 시황을 종목 순환매 얘기로만 채워서 정작 시장을 움직인 매크로 이슈가 빠짐(2026-07-08).
    try:
        macro = []
        today_md = now.strftime("%m/%d")
        seen_macro = set()
        for sec in ((_NEWS_FEED.get("data") or {}).get("sectors") or []):
            rows = list(sec.get("news") or [])
            for st_ in (sec.get("stocks") or []):
                rows += st_.get("news") or []
            for n in rows:
                t = (n.get("title") or "").strip()
                d = n.get("date") or ""
                if not t or not d.startswith(today_md) or not _MACRO_RE.search(t):
                    continue
                key = _news_norm(t)
                if key in seen_macro:
                    continue
                seen_macro.add(key)
                macro.append(f"[매크로] {t}")
        if macro:
            news = macro[:5] + news
    except Exception:
        pass

    phase_changed = st.get("session_phase") != phase
    if phase == "afterhours" and st.get("session_phase") == "intraday":
        try:
            _weather_tg(_bdig.format_daily(_weather.get("calib_today", [])))
        except Exception:
            pass
    heartbeat = phase != "weekend" and time.time() - _weather["last_synth_ts"] >= 1800
    # mf_ready 없으면(서버 막 재시작해 프리워밍 캐시 아직 미충전) heartbeat/phase_changed로
    # 절대 발동시키지 않는다 — 안 그러면 빈 mf(0값)를 "실시간 지표 전부 0"으로 잘못 서술한
    # 인사이트가 저장돼, 실제 데이터가 돌아온 뒤에도 다음 heartbeat(최대 30분)까지 안 고쳐짐
    # (2026-07-06: 배포 중 재시작을 여러 번 하면서 이 버그가 반복 재현됨).
    fire = bool(events) or (mf_ready and phase_changed and phase != "weekend") or \
           (mf_ready and heartbeat and (live_ok or news))

    if fire and (time.time() - _weather["last_synth_ts"] < _WEATHER_MIN_INTERVAL_S):
        fire = False
    if fire and _weather["synth_count"] >= _WEATHER_DAILY_CAP and not events:
        fire = False

    if fire:
        has_major = any(e.get("major") for e in events)
        facts = {"phase": phase, "J": curr["idx"]["J"], "Q": curr["idx"]["Q"],
                 "inv": curr["inv"], "prog": curr["prog"], "nq": curr["nq"], **extra_facts}
        models = ["opus", "sonnet"] if has_major else \
                 (["opus"] if _weather["model_toggle"] % 2 == 0 else ["sonnet"])
        _weather["model_toggle"] += 1
        results = {}
        for m in models:
            r = _bw.synthesize(facts, events, st, news, phase, model=m,
                               gemini_fn=_gemini_text, cwd=_BRIEFING_AGENT_CWD,
                               claude_bin=CLAUDE_BIN or "claude", focus=focus)
            if r:
                results[m] = r
        _weather["last_synth_ts"] = time.time()
        _weather["synth_count"] += 1

        primary = results.get("opus") or (results.get("sonnet") if results else None)
        if primary:
            st["verdict"] = {**primary["verdict"], "ts": now.strftime("%H:%M")}
            st["narrative"] = primary.get("narrative", "")
            _nowmin = now.hour * 60 + now.minute
            for tp in primary.get("new_turning_points", []):
                # LLM이 시각을 엉뚱하게(플레이스홀더 "HH:MM", 또는 미래 17:00 등) 내는 경우가 잦다.
                # 무효 포맷이거나 '지금보다 미래'면 현재 종합 시각으로 강제 → 17:00 같은 가짜시각 차단.
                _m = re.match(r"^(\d{1,2}):(\d{2})$", str(tp.get("ts", "")).strip())
                _tm = (int(_m.group(1)) * 60 + int(_m.group(2))) if _m else -1
                if _tm < 0 or _tm > _nowmin + 2:
                    tp["ts"] = now.strftime("%H:%M")
                tp["date"] = now.strftime("%Y-%m-%d")   # 날짜 붙여 어제 이벤트가 오늘 뜨는 것 방지
                st["turning_points"].append(tp)
            st["session_phase"] = phase
            st["baseline"] = curr
            st["updated_at"] = now.strftime("%H:%M")
            _bstate.save_state(_WEATHER_STATE_PATH, st)
            _briefing_set_insight(BRIEFING_PATH, {
                "ts": now.strftime("%H:%M"),
                "verdict": st["verdict"], "narrative": st["narrative"],
                "turning_points": st["turning_points"][-12:],
                "session_phase": phase})
            row = {"ts": now.strftime("%H:%M"), "fired_events": events,
                   "models": list(results.keys()), "noise_flag": False,
                   "verdict": st["verdict"]}
            _weather["calib_today"].append(row)
            _weather_calib_append(date_str, row, results)
            digest_result = results.get("opus") or primary
            if has_major and "sonnet" in results:
                digest_result = {**digest_result,
                                 "narrative": digest_result.get("narrative", "") +
                                 f"\n---[sonnet] {results['sonnet']['verdict'].get('line','')}"}
            msg = _weather["batcher"].add(events, digest_result, time.time())
            if msg:
                _weather_tg(msg)
        else:
            st["session_phase"] = phase
    else:
        if live_ok and prev is not None:
            st["baseline"] = curr
        st["session_phase"] = phase
    _weather["state"] = st


_CIRC_INTERVAL_S = 900   # 순환매 매칭 독립주기 15분


def _circ_gemini(prompt: str) -> dict:
    """순환매 매칭용 LLM 호출(1차 Gemini Flash). Sonnet 교체 시 여기만 바꾸면 됨.
    반환: {"ok":True,"analysis":str} | {"error":str} — circulation.detect 규약."""
    return _gemini_text(prompt, keys=_briefing_keys(), models=GEMINI_TEXT_MODELS)


def _circulation_tick():
    """15분 게이트: 강한 원자(트리거섹터)+타섹터 급등(히트맵+5%)이 둘 다 있을 때만
    Gemini에게 순환매 인과 매칭을 물어 카드 생성. 억지 연결이면 빈 결과가 정상.
    _weather_tick과 같은 스레드에서 호출 → state 동시변경 레이스 없음."""
    from pipeline.atoms import circulation as _circ
    hm = (_heatmap_cache.get("all") or {}).get("data") or {}
    if not hm.get("sectors"):
        return   # 히트맵 아직 없음(재시작 직후·장전) → 조용히 스킵
    triggers = _circ.trigger_candidates(days=3, min_strength=3)  # 기본 db.query_atoms 사용
    if not triggers:
        return
    exclude = {t["sector"] for t in triggers}
    movers = _circ.mover_candidates(hm, exclude_sectors=exclude, min_rate=5.0)
    if not movers:
        return
    now = datetime.now()
    cards = _circ.detect(triggers, movers, llm_fn=_circ_gemini,
                         ts=now.strftime("%H:%M"))
    if not cards:
        return
    seen = _weather["circulation_seen"]
    fresh = []
    for c in cards:
        key = (c.get("trigger_sector"), c.get("mover_code"))
        if key in seen:
            continue          # 오늘 이미 나온 조합 → 스킵
        seen.add(key)
        c["date"] = now.strftime("%Y-%m-%d")
        c["major"] = True     # 순환매는 시장상황 타임라인 상단(⭐급) 대우
        fresh.append(c)
    if not fresh:
        return
    # 한 틱(15분)에 여러 매칭이 한꺼번에 나오면 전부 major로 꽂혀 시장상황 타임라인
    # (최근 12개 롤링)을 순환매 카드로 도배함 — 전쟁·매크로 등 다른 이벤트가 밀려남(2026-07-08).
    # 틱당 1건(최상위 매칭)만 반영해 다른 이벤트에도 자리를 남긴다.
    fresh = fresh[:1]
    st = _weather["state"] or _bstate.load_state(_WEATHER_STATE_PATH)
    st.setdefault("turning_points", [])
    st["turning_points"].extend(fresh)
    _weather["state"] = st
    _bstate.save_state(_WEATHER_STATE_PATH, st)
    # insight의 verdict/narrative는 보존하고 turning_points만 갱신해 재기록
    _briefing_set_insight(BRIEFING_PATH, {
        "ts": now.strftime("%H:%M"),
        "verdict": st.get("verdict"), "narrative": st.get("narrative", ""),
        "turning_points": st["turning_points"][-12:],
        "session_phase": st.get("session_phase")})


def _poll_briefing():
    """30초 주기 — market_flow 임계치 감지 + 12분 고정주기 종합. 감지 즉시 종합도 트리거."""
    _last_fixed_synth = 0.0
    _last_circ = 0.0
    while True:
        try:
            mf_cached = _prewarm_cache.get("market_flow") or {}
            curr = mf_cached.get("data")
            if curr:
                prev = _briefing_last_metrics["data"]
                alerts = _briefing_detect_alerts(prev, curr)
                _briefing_last_metrics["data"] = curr
                for a in alerts:
                    _briefing_append(BRIEFING_PATH, {
                        "ts": a["ts"], "severity": "gray",
                        "headline": f"{a['label']} 변동", "body": None, "kind": "raw_alert"})
                if alerts:
                    _briefing_run_synthesis(alerts)
                elif time.time() - _last_fixed_synth >= 720:
                    _last_fixed_synth = time.time()
                    _briefing_run_synthesis([])

            # 시황 브리핑 엔진: market_flow 캐시 유무와 무관하게 매 틱 실행
            # (주말·KIS다운으로 캐시 비어도 자체 가드로 heartbeat+뉴스 기반 갱신)
            _weather_tick()

            # 순환매 감지기: 15분 게이트(같은 스레드 → weather state 레이스 없음).
            # _weather_tick 직후 실행해야 st["turning_points"] 최신본에 얹는다.
            if time.time() - _last_circ >= _CIRC_INTERVAL_S:
                _last_circ = time.time()
                _circulation_tick()
        except Exception:
            # 예전엔 조용히 삼켜서 원인 추적이 안 됐음(2026-07-06) — 트레이스백은 로그에 남긴다.
            import traceback as _tb
            _tb.print_exc()
        time.sleep(30)

threading.Thread(target=_poll_briefing, daemon=True).start()


def _insight_run_synthesis(curr: dict) -> None:
    """지수 흐름+특징종목 종합 — 15분 독립 타이머로 _poll_briefing에서 호출."""
    try:
        bars = curr.get("J_bars") or curr.get("Q_bars") or []
        shape = _compute_index_shape(bars)
        if not shape:
            return
        news_data = _NEWS_FEED.get("data")
        movers = _pick_notable_movers(curr.get("RANK_POP") or [], curr.get("RANK_AMT") or [],
                                       news_data, n=4)
        atoms_db_path = os.path.join(ROOT, "pipeline", "atoms", "atoms.db")
        for m in movers:
            if not m.get("news_reason"):
                found = _recent_atoms_for_stock(atoms_db_path, m["name"], limit=1)
                if found:
                    m["news_reason"] = found[0]
        market_atoms = _briefing_atoms(atoms_db_path, limit=5)
        prompt = _build_insight_prompt(shape, movers, market_atoms)
        if not prompt:
            return
        res = _gemini_text(prompt, keys=_briefing_keys(), models=GEMINI_TEXT_MODELS)
        if not res.get("ok"):
            return
        parsed = _parse_insight_response(res.get("analysis", ""))
        if not parsed:
            return
        topick = _recent_topick_mentions(atoms_db_path, limit=3)
        _briefing_set_insight(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"),
            "headline": parsed["headline"], "body": parsed["body"], "topick": topick})
    except Exception:
        pass


@app.get("/api/market_briefing")
def api_market_briefing():
    # 타임라인엔 '오늘' 항목만 — date 없는 과거 누적분이 시간(HH:MM)만 맞아 섞여 뜨던 문제 차단
    data = _briefing_load(BRIEFING_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    data["items"] = [it for it in (data.get("items") or []) if it.get("date") == today]
    # 시장상황(turning_points)도 오늘것만 — 어제 오후 이벤트(16:20 등)가 오늘 뜨던 문제 차단
    ins = data.get("insight")
    if isinstance(ins, dict) and ins.get("turning_points"):
        ins["turning_points"] = [t for t in ins["turning_points"] if t.get("date") == today]
    return JSONResponse(content=data)


@app.get("/api/atom_raw/{atom_id}")
def api_atom_raw(atom_id: str):
    """리포트 탑픽 '원본보기' — atoms.db에서 atom_id의 raw_file 경로를 찾아 원문
    반환. raw/ 디렉터리 밖은 절대 못 읽도록 경로를 검증(디렉터리 탈출 방지)."""
    import sqlite3
    try:
        conn = sqlite3.connect(ATOMS_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT raw_file FROM atoms WHERE id = ?", (atom_id,)).fetchone()
        conn.close()
    except Exception:
        return PlainTextResponse("원본을 불러올 수 없습니다.", status_code=500)
    if not row or not row["raw_file"]:
        return PlainTextResponse("원본 파일 정보가 없습니다.", status_code=404)
    raw_dir = os.path.realpath(os.path.join(ROOT, "raw"))
    target = os.path.realpath(row["raw_file"])
    if os.path.commonpath([raw_dir, target]) != raw_dir:
        return PlainTextResponse("잘못된 경로입니다.", status_code=403)
    if not os.path.isfile(target):
        return PlainTextResponse("원본 파일을 찾을 수 없습니다.", status_code=404)
    try:
        with open(target, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return PlainTextResponse("원본 파일을 읽을 수 없습니다.", status_code=500)
    return PlainTextResponse(content)


# ══════════════════════════════════════════════════════════════
# 인사이트 허브 라우트 (§4.1 ~ §4.9)
# ══════════════════════════════════════════════════════════════

# ── §4.1 GET /insights → insights.html 서빙 ──────────────────
@app.get("/insights", response_class=HTMLResponse)
def insights_page():
    p = os.path.join(HERE, "insights.html")
    if not os.path.exists(p):
        return "<h1>insights.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        return f.read()


# ── 인사이트2 (신규 UI 초안, ★운영자 전용) ────────────────────
# 기존 /insights 는 그대로 두고 옆에 새로 만든다. 완성되면 교체 판단.
#
# 접근제어: /insights2 와 /api/insights2/ 를 _USER_PAGES·_USER_API_PREFIX 에
# **일부러 넣지 않았다** → 미들웨어(_user_allowed)가 일반 사용자를 자동 차단한다
# (페이지는 /home 리다이렉트, API는 403). admin_page(:707)와 같은 방식.
# 아래 _require_admin 은 그 방어선이 뚫렸을 때를 대비한 2중 잠금이다
# (미들웨어를 나중에 누가 고치다 초안이 외부로 새는 걸 막는다).
def _ins2_require_admin(request: Request):
    """운영자가 아니면 True(차단해야 함). 미완성 초안이라 외부 노출 금지.

    인증 OFF(로컬 개발: DASH_PASS·GOOGLE_CLIENT_ID 둘 다 없음)일 땐 통과시킨다 —
    다른 관리자 경로(:744, :818)와 같은 판단이다. 라이브는 둘 다 설정돼 있으므로
    _AUTH_ON=True → 아래 쿠키 검사가 그대로 걸린다(잠금 그대로).
    """
    if not _AUTH_ON:
        return False
    uid = _verify_session(request.cookies.get("dash_auth", ""))
    return uid is None or not _is_admin(uid)


@app.get("/stock", response_class=HTMLResponse)
def stock_page(request: Request):
    """종목검색 브리프. insights2와 같은 2중 잠금(초안이라 외부 노출 금지)."""
    if _ins2_require_admin(request):
        return RedirectResponse("/home")
    p = os.path.join(HERE, "stock.html")
    if not os.path.exists(p):
        return "<h1>stock.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/insights2", response_class=HTMLResponse)
def insights2_page(request: Request):
    if _ins2_require_admin(request):
        return RedirectResponse("/home")
    p = os.path.join(HERE, "insights2.html")
    if not os.path.exists(p):
        return "<h1>insights2.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


# ── 인사이트 헬퍼 ────────────────────────────────────────────

_CAT_TYPE_MAP = {
    "youtube":  "source_type IN ('youtube','yt')",
    "telegram": "source_type = 'telegram'",
    "blog":     "source_type = 'blog'",
    "report":   "source_type = 'report'",
    "news":     "source_type = 'news'",
}


def _ins_conn():
    """atoms.db 연결 (doc_summary 모듈 없어도 동작)."""
    import sqlite3
    from pathlib import Path
    db_path = Path(ROOT) / "pipeline" / "atoms" / "atoms.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _doc_key(category: str, source_name: str, date: str, raw_file: str) -> str:
    """재현 가능한 doc_key 생성 (스펙 §2)."""
    if category == "telegram":
        return f"telegram:{source_name}:{date}"
    basename = os.path.basename(raw_file or "")
    return f"{category}:{basename}"


def _ts_to_seconds(ts: str) -> int:
    """'HH:MM:SS' 또는 'MM:SS' 또는 숫자 문자열 → 초."""
    if not ts:
        return 0
    ts = ts.strip()
    if ts.isdigit():
        return int(ts)
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        pass
    return 0


def _has_summary(doc_key: str) -> bool:
    """doc_summaries 테이블에 해당 doc_key 캐시 존재 여부."""
    conn = _ins_conn()
    if not conn:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM doc_summaries WHERE doc_key=? LIMIT 1", (doc_key,)
        ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()


def _get_summary_row(doc_key: str) -> dict | None:
    """doc_summaries 행 반환 (없으면 None)."""
    conn = _ins_conn()
    if not conn:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM doc_summaries WHERE doc_key=?", (doc_key,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["summary3"] = [l for l in (d.get("summary3") or "").split("\n") if l.strip()]
        for k in ("stocks_json", "seeds_json", "highlights_json"):
            try:
                d[k] = json.loads(d[k] or "[]")
            except Exception:
                d[k] = []
        return d
    except Exception:
        return None
    finally:
        conn.close()


_TITLE_CACHE: dict = {}        # raw_file → 추출된 제목 (파일 재읽기 방지)
_YT_LINK_RE = re.compile(r"\[유튜브 바로가기\]\(([^)]+)\)")
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([_ ]\d{3,4})?[_ ]")  # 2026-06-29_1100_ 또는 2026-06-29_


def _clean_title(name: str) -> str:
    """파일명에서 날짜·시각 접두어 제거."""
    name = _DATE_PREFIX_RE.sub("", name).strip()
    return name


def _youtube_title_from_file(raw_file: str) -> str | None:
    """유튜브 크롤 원본에서 실제 영상 제목 추출 (서버 필드꼬임 대비).
    [유튜브 바로가기](X) 의 X가 URL이 아니면 그게 제목."""
    if raw_file in _TITLE_CACHE:
        return _TITLE_CACHE[raw_file]
    title = None
    try:
        if os.path.exists(raw_file):
            head = open(raw_file, encoding="utf-8", errors="replace").read(800)
            m = _YT_LINK_RE.search(head)
            if m:
                cand = m.group(1).strip()
                if cand and not cand.startswith("http"):
                    title = cand
    except Exception:
        title = None
    _TITLE_CACHE[raw_file] = title
    return title


def _build_doc_title(raw_file: str, source_name: str, date: str, category: str) -> str:
    """표시용 제목 추정. 유튜브는 원본에서 실제 제목 시도, 그 외는 파일명 정리."""
    if raw_file:
        if category == "youtube":
            real = _youtube_title_from_file(raw_file)
            if real:
                return real
        base = os.path.splitext(os.path.basename(raw_file))[0]
        cleaned = _clean_title(base)
        # 정리 후 남은 게 채널명뿐이거나 비면 채널+날짜로
        if not cleaned or cleaned == source_name:
            return f"{source_name} · {date}" if date else (source_name or base)
        return cleaned
    return f"{source_name} ({date})"


# ── §4.2 GET /api/insights/overview ──────────────────────────
@app.get("/api/insights/overview")
def api_insights_overview():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)

    try:
        categories = []
        feed_items = []

        for cat_id, type_cond in _CAT_TYPE_MAP.items():
            label, icon = _CAT_LABEL[cat_id]

            # 채널 수, 전체 원자 수
            channels_row = conn.execute(
                f"SELECT COUNT(DISTINCT source_name) as cnt FROM atoms WHERE {type_cond}"
            ).fetchone()
            channels_cnt = (channels_row["cnt"] if channels_row else 0)

            atoms_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM atoms WHERE {type_cond}"
            ).fetchone()
            atoms_cnt = atoms_row["cnt"] if atoms_row else 0

            # 문서(L2) 목록 집계
            if cat_id == "telegram":
                doc_rows = conn.execute(
                    f"""SELECT source_name, date, COUNT(*) as atom_cnt,
                               MAX(raw_file) as raw_file
                        FROM atoms WHERE {type_cond}
                        GROUP BY source_name, date
                        ORDER BY date DESC, source_name"""
                ).fetchall()
            else:
                doc_rows = conn.execute(
                    f"""SELECT source_name, date, COUNT(*) as atom_cnt,
                               raw_file, MAX(raw_file) as raw_file
                        FROM atoms WHERE {type_cond} AND raw_file IS NOT NULL
                        GROUP BY raw_file
                        ORDER BY date DESC"""
                ).fetchall()

            docs_cnt = len(doc_rows)

            # 오늘 신규
            today_new = sum(
                1 for r in doc_rows
                if (r["date"] or "").startswith(today[:7]) and r["date"] >= today[:8]
            )
            # 정확한 오늘만
            today_new = sum(1 for r in doc_rows if r["date"] == today)

            # hot 3개
            hot = []
            for r in doc_rows[:3]:
                dk = _doc_key(cat_id, r["source_name"], r["date"], r["raw_file"])
                title = _build_doc_title(r["raw_file"], r["source_name"], r["date"], cat_id)
                hot.append({
                    "doc_key": dk,
                    "title": title,
                    "source": r["source_name"],
                    "date": r["date"],
                    "atoms": r["atom_cnt"],
                })

            categories.append({
                "id": cat_id,
                "label": label,
                "icon": icon,
                "channels": channels_cnt,
                "docs": docs_cnt,
                "atoms": atoms_cnt,
                "today_new": today_new,
                "hot": hot,
            })

            # feed용
            for r in doc_rows[:7]:
                dk = _doc_key(cat_id, r["source_name"], r["date"], r["raw_file"])
                title = _build_doc_title(r["raw_file"], r["source_name"], r["date"], cat_id)
                feed_items.append({
                    "category": cat_id,
                    "doc_key": dk,
                    "title": title,
                    "source": r["source_name"],
                    "date": r["date"],
                    "atoms": r["atom_cnt"],
                    "has_summary": _has_summary(dk),
                })

        # 통합 피드: 날짜 역순 20개
        feed_items.sort(key=lambda x: x["date"] or "", reverse=True)
        feed_items = feed_items[:20]

        return JSONResponse(content={
            "today": today,
            "categories": categories,
            "feed": feed_items,
        })
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 인사이트2 API — 화면 하나가 필요한 걸 한 번에 준다
#
# 설계 의도: 기존 /api/insights/* 는 "카테고리→소스→문서→상세" 드릴다운용이라
# 화면을 그리려면 4번 호출해야 한다. 인사이트2는 한 화면에 다 펼치므로
# 한 방에 필요한 모양(판세 3칸 + 영상별 발언)으로 만들어 준다.
# ══════════════════════════════════════════════════════════════

# 신호 → 부호. 화면의 초록/빨강 점이 이걸로 갈린다.
_SIGN_MAP = {
    "bullish": 1, "momentum": 1,
    "bearish": -1, "risk": -1, "volatility": -1,
    # neutral·data·catalyst 등은 0 (기본값)
}


def _sign_of(signal: str) -> int:
    return _SIGN_MAP.get((signal or "").strip().lower(), 0)


# 텔레 원자 머리말 분해 — 한 군데에서만 판단한다(0순위-B).
#
# 실측(2026-08-15, atoms.db): 텔레 content 상당수가 아래 모양으로 시작한다.
#   "[중계:신한투자증권] 목표가 18,000원 매수 / 12MF BPS ..."
#   "[중계:그로쓰리서치] 목표가 None None / 삼성바이오로직스와 셀트리온 ..."
#   "[긍정] 구리 가격 1만 4,000달러 근접 ..."
# 즉 머리말은 **구조 정보**(중계처·목표가·의견)인데 문자열로 박혀 있다.
# 화면에서 걷어내기만 하면 정보를 버리는 것이고, 그대로 두면 'None None'이 보인다.
# → 필드로 쪼개서 값이 있는 것만 배지로 쓴다. None은 자연히 사라진다.
#
# 8월 표본 971건 중: [중계:*] 94 / [긍정]·[중립]·[부정] 41 / 'None' 포함 140
_RE_RELAY = re.compile(r"\[중계:([^\]]*)\]\s*")
_RE_TP = re.compile(r"^목표가\s+(\S+)(?:\s+(\S+))?\s*/\s*")
# 부호 접두어는 두 가지 모양으로 온다 — "[긍정] ..." 과 "긍정: ..." (실측 둘 다 존재).
# 한쪽만 걷으면 화면에 섞여 나온다.
_RE_TONE = re.compile(r"^(?:\[(?:긍정|중립|부정|None)\]|(?:긍정|중립|부정)\s*:)\s*")

# 원자화가 값 없음을 문자열로 흘린다 — 실측(2026-08-05 텔레): 'None' 60건, 'null' 8건.
# 판정을 여기 한 군데서만 한다(0순위-B: 같은 판단을 두 번 적지 않는다).
_EMPTYISH = {"", "none", "null", "n/a", "-", "미정"}


def _ins2_blank(v: str) -> bool:
    return (v or "").strip().lower() in _EMPTYISH


def _ins2_split_head(content: str) -> dict:
    """{text, relay, tp, opinion} — 값이 없으면 빈 문자열."""
    t = (content or "").strip()
    relay = tp = opinion = ""

    m = _RE_TONE.match(t)
    if m:
        t = t[m.end():]  # 부호는 화면의 점(dot)이 이미 보여준다 → 글자로 반복하지 않는다

    m = _RE_RELAY.search(t)
    if m:
        if not _ins2_blank(m.group(1)):
            relay = m.group(1).strip()
        t = (t[:m.start()] + t[m.end():]).strip()

        # '목표가 ...' 는 [중계:*] 바로 뒤에만 온다. 앞에 붙은 '글로벌 램리서치: ' 같은
        # 문맥은 살려야 하므로, 잘라낸 자리 이후만 본다.
        head = t[m.start():]
        m2 = _RE_TP.match(head)
        if m2:
            for val, slot in ((m2.group(1), "tp"), (m2.group(2), "opinion")):
                if _ins2_blank(val):
                    continue
                if slot == "tp":
                    tp = val.strip()
                else:
                    opinion = val.strip()
            t = (t[:m.start()] + head[m2.end():]).strip()

    return {"text": t, "relay": relay, "tp": tp, "opinion": opinion}


def _ins2_latest_date(conn, type_cond: str) -> str:
    """데이터가 있는 가장 최근 날짜. 오늘 크롤이 아직이면 화면이 비니까,
    '오늘'을 고집하지 않고 실제로 있는 마지막 날을 쓴다."""
    row = conn.execute(
        f"SELECT MAX(date) d FROM atoms WHERE {type_cond} AND date IS NOT NULL AND date != ''"
    ).fetchone()
    return (row["d"] if row and row["d"] else "") or ""


@app.get("/api/insights2/stock")
def api_insights2_stock(request: Request, q: str = "", days: int = 45):
    """종목검색 한 화면 분량의 **재료**를 한 번에. ★운영자 전용(초안).

    종합(5칸 문장)은 여기서 하지 않는다 — 재료와 종합을 갈라둬야
    LLM이 죽어도 화면은 원문으로 살아남는다.

    반환: {q, canonical, code, too_short, counts, atoms[], flow, vacuum}
    """
    if _ins2_require_admin(request):
        return JSONResponse(content={"error": "forbidden"}, status_code=403)

    q = (q or "").strip()
    if not q:
        return JSONResponse(content={"error": "검색어가 없습니다"}, status_code=400)

    from pipeline.atoms import stock_search
    from pipeline.atoms.codemap import code_for

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)

    try:
        canonical = stock_search.canonical_name(q)
        since = (datetime.now() - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
        rows = stock_search.search(conn, q, since=since, limit=240)

        atoms, srcs = [], {}
        for r in rows:
            head = _ins2_split_head(r.get("content") or "")
            srcs[r.get("source_type") or "?"] = srcs.get(r.get("source_type") or "?", 0) + 1
            atoms.append({
                "id": r.get("id"),
                "date": r.get("date") or "",
                "src": r.get("source_type") or "",
                "who": r.get("source_name") or "",
                "sector": r.get("sector") or "",
                "asset": r.get("asset") or "",
                "sign": _sign_of(r.get("signal")),
                "signal": r.get("signal") or "",
                "ts": (r.get("yt_timestamp") or "") or (r.get("msg_ts") or ""),
                "deeplink": r.get("deeplink") or "",
                "content": head["text"],
                "relay": head["relay"],
                "tp": head["tp"],
                "opinion": head["opinion"],
                "rel": r.get("rel", 0),
            })

        dates = [a["date"] for a in atoms if a["date"]]
        code = code_for(canonical) or ""

        # 수급·공매도 — 종목코드를 못 찾으면 건너뛴다(키워드가 종목이 아닐 수 있다)
        # 둘 다 KIS 왕복이고 서로를 안 쓴다 → 순차로 돌면 대기시간이 그냥 더해진다.
        # 스레드 2개로 겹쳐 부른다(kis_api가 전역 레이트게이트를 갖고 있어 안전).
        flow, short, peers, vacuum = {}, {}, {}, None
        if code:
            def _get_flow():
                try:
                    import stock_flow
                    return stock_flow.flow_summary(code)
                except Exception as e:
                    return {"error": f"{type(e).__name__}: {e}", "rows": []}

            def _get_short():
                try:
                    import stock_short
                    return stock_short.short_summary(code)
                except Exception as e:
                    return {"error": f"{type(e).__name__}: {e}", "series": []}

            def _get_peers():
                try:
                    import stock_peers
                    return stock_peers.compare(code)
                except Exception as e:
                    return {"found": False, "error": f"{type(e).__name__}: {e}", "peers": []}

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as ex:
                fu_flow = ex.submit(_get_flow)
                fu_short = ex.submit(_get_short)
                fu_peers = ex.submit(_get_peers)
                flow, short, peers = fu_flow.result(), fu_short.result(), fu_peers.result()
            vacuum = _vacuum_for(code)

        return JSONResponse(content={
            "q": q,
            "canonical": canonical,
            "code": code,
            "too_short": stock_search.is_too_short(q),
            "counts": {
                "atoms": len(atoms),
                "sources": srcs,
                "date_from": min(dates) if dates else "",
                "date_to": max(dates) if dates else "",
                "days": days,
            },
            "atoms": atoms,
            "flow": flow,
            "short": short,
            "peers": peers,
            "vacuum": vacuum,
        })
    finally:
        conn.close()


FLOW_DB_PATH = os.path.join(ROOT, "data", "flow.db")


def _flow_by_date(code: str) -> dict:
    """{YYYY-MM-DD: {frgn, orgn, prsn}} — 억원. 적재 전이면 빈 dict."""
    if not code or not os.path.exists(FLOW_DB_PATH):
        return {}
    import sqlite3          # 이 파일은 최상위에서 sqlite3를 import하지 않는다(기존 관례)
    try:
        conn = sqlite3.connect(FLOW_DB_PATH, timeout=5)
        rows = conn.execute(
            "SELECT date, frgn, orgn, prsn FROM stock_flow_daily WHERE code=?", (code,)
        ).fetchall()
        conn.close()
    except Exception:
        return {}
    out = {}
    for d, f, g, p in rows:
        # 저장은 KIS 원표기(YYYYMMDD)·백만원. 화면은 YYYY-MM-DD·억원을 쓴다.
        out[f"{d[:4]}-{d[4:6]}-{d[6:8]}"] = {
            "frgn": round((f or 0) / 100), "orgn": round((g or 0) / 100),
            "prsn": round((p or 0) / 100),
        }
    return out


# 「중요한 날」 점수 — 하나라도 걸리면 마커, 합이 클수록 굵게.
# 매일 찍으면 못 보므로 사건이 있었던 날만 남긴다.
_KEYDAY_MIN_SCORE = 2


def _score_days(candles: list, atoms_by_date: dict, flow: dict) -> list:
    """[{date, score, why[], chg, volx, atoms, frgn, orgn}] — 점수순."""
    if len(candles) < 5:
        return []
    closes = [c.get("close") or 0 for c in candles]
    vols = [c.get("value") or 0 for c in candles]
    n_atoms = [len(atoms_by_date.get(c["time"], [])) for c in candles]
    avg_atoms = (sum(n_atoms) / len(n_atoms)) if n_atoms else 0
    frgns = sorted(abs(v["frgn"]) for v in flow.values()) if flow else []
    big_flow = frgns[int(len(frgns) * 0.9)] if len(frgns) >= 10 else None

    out = []
    for i, c in enumerate(candles):
        if i == 0:
            continue
        d = c["time"]
        prev = closes[i - 1] or 0
        chg = ((closes[i] / prev) - 1) * 100 if prev else 0
        base = vols[max(0, i - 60):i]
        volx = (vols[i] / (sum(base) / len(base))) if base and sum(base) else 0
        na = n_atoms[i]
        fl = flow.get(d) or {}

        score, why = 0, []
        if abs(chg) >= 5:
            score += 3; why.append(f"{chg:+.1f}% 급등락")
        elif abs(chg) >= 3:
            score += 2; why.append(f"{chg:+.1f}%")
        if volx >= 3:
            score += 3; why.append(f"거래량 {volx:.1f}배")
        elif volx >= 2:
            score += 2; why.append(f"거래량 {volx:.1f}배")
        if avg_atoms and na >= max(3, avg_atoms * 2):
            score += 2; why.append(f"발언 {na}건")
        if big_flow and fl and abs(fl.get("frgn", 0)) >= big_flow:
            score += 2
            why.append(f"외국인 {fl['frgn']:+,}억")
        # 60일 신고가·신저가
        win = closes[max(0, i - 59):i + 1]
        if len(win) >= 20 and closes[i] == max(win):
            score += 2; why.append("60일 신고가")
        elif len(win) >= 20 and closes[i] == min(win):
            score += 2; why.append("60일 신저가")

        if score >= _KEYDAY_MIN_SCORE:
            out.append({
                "date": d, "score": score, "why": why,
                "chg": round(chg, 2), "volx": round(volx, 1),
                "atoms": na, "close": closes[i],
                "frgn": fl.get("frgn"), "orgn": fl.get("orgn"),
            })
    out.sort(key=lambda x: (-x["score"], x["date"]))
    return out


@app.get("/api/insights2/keydays")
def api_insights2_keydays(request: Request, q: str = "", days: int = 180, top: int = 30):
    """차트 + 그날 있었던 일. ★운영자 전용.

    반환: {code, candles[], flow{}, byDate{}, keydays[], coverage{}}
      - byDate: 날짜별 발언(마커 호버·클릭이 이걸 쓴다)
      - coverage: 발언·수급이 **언제부터** 있는지. 없는 구간을 화면이 흐리게 처리해야
        "조용한 시기"로 오해하지 않는다.
    """
    if _ins2_require_admin(request):
        return JSONResponse(content={"error": "forbidden"}, status_code=403)
    q = (q or "").strip()
    if not q:
        return JSONResponse(content={"error": "검색어가 없습니다"}, status_code=400)

    from pipeline.atoms import stock_search
    from pipeline.atoms.codemap import code_for

    canonical = stock_search.canonical_name(q)
    code = code_for(canonical) or ""
    if not code:
        return JSONResponse(content={"error": f"「{canonical}」 종목코드를 찾지 못했습니다",
                                     "canonical": canonical}, status_code=404)

    # 캔들 — 이미 있는 엔드포인트를 그대로 쓴다(키움→KIS→네이버 3중 폴백이 붙어 있다)
    try:
        raw = json.loads(bytes(api_stock_candles(code=code, tf="D").body).decode("utf-8"))
        candles = (raw.get("candles") or [])[-max(30, days):]
    except Exception as e:
        return JSONResponse(content={"error": f"캔들 조회 실패: {e}"}, status_code=503)

    # 발언 — 날짜별로 묶는다
    by_date: dict = {}
    conn = _ins_conn()
    if conn is not None:
        try:
            since = candles[0]["time"] if candles else ""
            for r in stock_search.search(conn, q, since=since, limit=1500):
                d = (r.get("date") or "").strip()
                if len(d) != 10 or d.startswith("0000"):
                    continue  # 깨진 날짜(atoms에 '0000-00-00'이 섞여 있다)는 버린다
                head = _ins2_split_head(r.get("content") or "")
                by_date.setdefault(d, []).append({
                    "content": head["text"], "who": r.get("source_name") or "",
                    "src": r.get("source_type") or "", "sign": _sign_of(r.get("signal")),
                    "relay": head["relay"], "tp": head["tp"],
                })
        finally:
            conn.close()

    flow = _flow_by_date(code)
    keydays = _score_days(candles, by_date, flow)[:max(5, top)]

    # 차트 구조(A·B층) — 실패해도 화면은 캔들만으로 살아야 한다
    try:
        import chart_ta
        ta = chart_ta.analyze(candles)
        ta["lines"] = chart_ta.describe(ta)
    except Exception as e:
        ta = {"error": f"{type(e).__name__}: {e}"}

    return JSONResponse(content={
        "q": q, "canonical": canonical, "code": code,
        "candles": candles,
        "flow": flow,
        "byDate": by_date,
        "keydays": keydays,
        "ta": ta,
        "coverage": {
            "atoms_from": min(by_date) if by_date else "",
            "flow_from": min(flow) if flow else "",
            "candles_from": candles[0]["time"] if candles else "",
        },
    })


# 종합 결과 캐시 — 같은 종목을 다시 열 때 LLM을 또 부르지 않는다.
# 발언은 하루 단위로 쌓이므로 날짜가 바뀌면 자연히 갱신된다.
_BRIEF_CACHE: dict = {}
_BRIEF_TTL = 60 * 60 * 6  # 6시간


@app.get("/api/insights2/brief")
def api_insights2_brief(request: Request, q: str = "", days: int = 45, force: int = 0):
    """5칸 종합. ★운영자 전용.

    LLM은 **슬롯 값만** 만든다(stock_brief 참조) — 화면을 다시 쓰게 하지 않는다.
    실패해도 `ok:false`만 돌아가고, 화면은 /stock 재료로 그대로 그려진다.
    """
    if _ins2_require_admin(request):
        return JSONResponse(content={"error": "forbidden"}, status_code=403)
    q = (q or "").strip()
    if not q:
        return JSONResponse(content={"error": "검색어가 없습니다"}, status_code=400)

    key = f"{q}|{days}|{datetime.now().strftime('%Y-%m-%d')}"
    hit = _BRIEF_CACHE.get(key)
    if hit and not force and (time.time() - hit["at"]) < _BRIEF_TTL:
        return JSONResponse(content={**hit["data"], "cached": True})

    import stock_brief

    # 재료는 위 엔드포인트와 같은 함수를 쓴다 — 두 벌로 갈라지면 언젠가 어긋난다
    src = api_insights2_stock(request, q=q, days=days)
    if getattr(src, "status_code", 200) != 200:
        return src
    mat = json.loads(bytes(src.body).decode("utf-8"))
    if mat.get("error"):
        return JSONResponse(content=mat, status_code=400)

    atoms = mat.get("atoms") or []
    if not atoms:
        return JSONResponse(content={"ok": False, "reason": "발언이 없습니다", "q": q})

    prompt = stock_brief.build_prompt(q, atoms, mat.get("flow") or {}, mat.get("vacuum"))
    res = _gemini_text(prompt, _summary_keys(), timeout=90)
    if res.get("error"):
        return JSONResponse(content={"ok": False, "reason": res["error"], "q": q})

    slots = stock_brief.parse(res.get("analysis") or "")
    data = {**slots, "q": q, "model": res.get("model", ""), "cached": False}
    _BRIEF_CACHE[key] = {"at": time.time(), "data": data}
    return JSONResponse(content=data)


@app.get("/api/insights2/daily")
def api_insights2_daily(request: Request, category: str = "youtube", date: str = ""):
    """인사이트2 한 화면 분량을 통째로. ★운영자 전용(초안).

    반환: {date, counts, market, sectors[], stocks[], videos[], atoms[]}
      - atoms[]  : 발언 원자 (video 인덱스로 영상과 연결)
      - sectors[]: [{name, plus, minus}]  ← 막대 그래프용
      - videos[] : [{title, source, url, n}]
    """
    if _ins2_require_admin(request):
        return JSONResponse(content={"error": "forbidden"}, status_code=403)

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)

    type_cond = _CAT_TYPE_MAP.get(category)
    if type_cond is None:
        return JSONResponse(content={"error": "unknown category"}, status_code=400)

    try:
        day = date or _ins2_latest_date(conn, type_cond)
        if not day:
            return JSONResponse(content={
                "date": "", "counts": {"videos": 0, "atoms": 0, "channels": 0},
                "market": {"plus": 0, "minus": 0, "zero": 0},
                "sectors": [], "stocks": [], "videos": [], "atoms": [],
            })

        rows = conn.execute(
            f"""SELECT id, date, source_name, raw_file, sector, asset, signal,
                       content, speaker, yt_timestamp, msg_ts, deeplink
                FROM atoms
                WHERE {type_cond} AND date = ?
                ORDER BY COALESCE(NULLIF(yt_timestamp,''), msg_ts, ''), raw_file, id""",
            (day,),
        ).fetchall()

        # 영상(raw_file) 단위로 묶는다 — 화면의 썸네일 카드 하나 = raw_file 하나
        videos, vidx = [], {}
        atoms = []
        for r in rows:
            rf = r["raw_file"] or ""
            if rf not in vidx:
                vidx[rf] = len(videos)
                videos.append({
                    "title": _build_doc_title(rf, r["source_name"] or "", day, category),
                    "source": r["source_name"] or "",
                    "doc_key": _doc_key(category, r["source_name"] or "", day, rf),
                    "url": "", "n": 0,
                })
            i = vidx[rf]
            videos[i]["n"] += 1
            # 영상 URL은 딥링크에서 역산 (&t= 앞부분)
            if not videos[i]["url"] and r["deeplink"]:
                videos[i]["url"] = str(r["deeplink"]).split("&t=")[0]

            # ⏱ 시각은 소스마다 의미가 다르다 — 유튜브 yt_timestamp = 영상 재생위치(딥링크 가능),
            # 텔레 msg_ts = 메시지 발송 시각(딥링크 없음, 시간순 정렬용). 값은 같은 칸에 담되
            # 뜻은 ts_kind로 알린다(화면이 ▶01:53 / 🕘09:58 로 갈라 그린다).
            head = _ins2_split_head(r["content"] or "")
            atoms.append({
                "video": i,
                "ts": (r["yt_timestamp"] or "") or (r["msg_ts"] or ""),
                "deeplink": r["deeplink"] or "",
                "speaker": r["speaker"] or "",
                "sector": r["sector"] or "",
                "asset": r["asset"] or "",
                "sign": _sign_of(r["signal"]),
                "signal": r["signal"] or "",
                "content": head["text"],
                "relay": head["relay"],
                "tp": head["tp"],
                "opinion": head["opinion"],
                "source": r["source_name"] or "",
            })

        # 판세 집계 — '시장'은 따로 빼고, 나머지를 섹터/종목으로 센다
        def tally(key: str, skip=("", "기타")):
            acc = {}
            for a in atoms:
                v = (a.get(key) or "").strip()
                if not v or v in skip:
                    continue
                # asset은 "삼성전자, SK하이닉스" 처럼 여러 개가 한 칸에 들어있다
                for name in ([x.strip() for x in v.split(",")] if key == "asset" else [v]):
                    if not name or name in skip:
                        continue
                    d = acc.setdefault(name, {"name": name, "plus": 0, "minus": 0, "n": 0})
                    d["n"] += 1
                    if a["sign"] > 0:
                        d["plus"] += 1
                    elif a["sign"] < 0:
                        d["minus"] += 1
            out = list(acc.values())
            out.sort(key=lambda d: (-(d["plus"] + d["minus"]), -d["n"], d["name"]))
            return out

        market_atoms = [a for a in atoms if (a["sector"] or "") == "시장"]
        market = {
            "plus": sum(1 for a in market_atoms if a["sign"] > 0),
            "minus": sum(1 for a in market_atoms if a["sign"] < 0),
            "zero": sum(1 for a in market_atoms if a["sign"] == 0),
            "n": len(market_atoms),
        }

        return JSONResponse(content={
            "date": day,
            "ts_kind": "play" if category in ("youtube", "yt") else "clock",
            "counts": {
                "videos": len(videos),
                "atoms": len(atoms),
                "channels": len({v["source"] for v in videos if v["source"]}),
                "with_ts": sum(1 for a in atoms if a["ts"]),
            },
            "market": market,
            "sectors": tally("sector", skip=("", "기타", "시장"))[:8],
            "stocks": tally("asset", skip=("", "기타", "시장"))[:8],
            "videos": videos,
            "atoms": atoms,
        })
    finally:
        conn.close()


# ── §4.3 GET /api/insights/sources?category=youtube ──────────
@app.get("/api/insights/sources")
def api_insights_sources(category: str = "youtube"):
    type_cond = _CAT_TYPE_MAP.get(category)
    if type_cond is None:
        return JSONResponse(content={"error": "unknown category"}, status_code=400)

    label, icon = _CAT_LABEL.get(category, (category, ""))
    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        if category == "telegram":
            rows = conn.execute(
                f"""SELECT source_name, COUNT(DISTINCT date) as docs,
                           COUNT(*) as atoms, MAX(date) as last_date
                    FROM atoms WHERE {type_cond}
                    GROUP BY source_name ORDER BY last_date DESC"""
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT source_name, COUNT(DISTINCT raw_file) as docs,
                           COUNT(*) as atoms, MAX(date) as last_date
                    FROM atoms WHERE {type_cond}
                    GROUP BY source_name ORDER BY last_date DESC"""
            ).fetchall()

        sources = [
            {
                "name": r["source_name"],
                "docs": r["docs"],
                "atoms": r["atoms"],
                "last_date": r["last_date"],
            }
            for r in rows
        ]
        return JSONResponse(content={
            "category": category,
            "label": label,
            "icon": icon,
            "sources": sources,
        })
    finally:
        conn.close()


# ── §4.4 GET /api/insights/docs?category=youtube&source=XXX ──
@app.get("/api/insights/docs")
def api_insights_docs(category: str = "youtube", source: str = ""):
    type_cond = _CAT_TYPE_MAP.get(category)
    if type_cond is None:
        return JSONResponse(content={"error": "unknown category"}, status_code=400)

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        if category == "telegram":
            rows = conn.execute(
                f"""SELECT source_name, date, COUNT(*) as atom_cnt,
                           MAX(raw_file) as raw_file
                    FROM atoms WHERE {type_cond} AND source_name=?
                    GROUP BY source_name, date ORDER BY date DESC""",
                (source,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT source_name, date, COUNT(*) as atom_cnt, raw_file
                    FROM atoms WHERE {type_cond} AND source_name=?
                      AND raw_file IS NOT NULL
                    GROUP BY raw_file ORDER BY date DESC""",
                (source,),
            ).fetchall()

        docs = []
        for r in rows:
            dk = _doc_key(category, r["source_name"], r["date"], r["raw_file"])
            title = _build_doc_title(r["raw_file"], r["source_name"], r["date"], category)
            docs.append({
                "doc_key": dk,
                "title": title,
                "date": r["date"],
                "atoms": r["atom_cnt"],
                "has_summary": _has_summary(dk),
            })

        return JSONResponse(content={
            "category": category,
            "source": source,
            "docs": docs,
        })
    finally:
        conn.close()


# ── §4.5 GET /api/insights/doc?doc_key=... ───────────────────
@app.get("/api/insights/doc")
def api_insights_doc(doc_key: str = ""):
    if not doc_key:
        return JSONResponse(content={"error": "doc_key 필요"}, status_code=400)

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        # doc_key 파싱
        parts = doc_key.split(":", 2)
        category = parts[0] if parts else ""
        type_cond = _CAT_TYPE_MAP.get(category)
        if type_cond is None:
            return JSONResponse(content={"error": "unknown category"}, status_code=400)

        # 원자 조회
        if category == "telegram":
            source_name = parts[1] if len(parts) > 1 else ""
            date = parts[2] if len(parts) > 2 else ""
            rows = conn.execute(
                f"""SELECT id, date, source_type, source_name, raw_file, sector, asset,
                           signal, content, stance_key, speaker, yt_timestamp, deeplink, msg_ts
                    FROM atoms WHERE {type_cond} AND source_name=? AND date=?
                    ORDER BY id""",
                (source_name, date),
            ).fetchall()
        else:
            raw_basename = parts[1] if len(parts) > 1 else ""
            rows = conn.execute(
                f"""SELECT id, date, source_type, source_name, raw_file, sector, asset,
                           signal, content, stance_key, speaker, yt_timestamp, deeplink, msg_ts
                    FROM atoms WHERE {type_cond}
                      AND (raw_file=? OR raw_file LIKE ? OR raw_file LIKE ?)
                    ORDER BY yt_timestamp, id""",
                (raw_basename, f"%/{raw_basename}", f"%\\{raw_basename}"),
            ).fetchall()

        atoms_list = [dict(r) for r in rows]

        # 메타
        source_name_meta = atoms_list[0]["source_name"] if atoms_list else ""
        date_meta = atoms_list[0]["date"] if atoms_list else ""
        raw_file_meta = atoms_list[0]["raw_file"] if atoms_list else ""
        title = _build_doc_title(raw_file_meta, source_name_meta, date_meta, category)

        # 유튜브 video_url
        video_url = None
        if category == "youtube" and atoms_list:
            dl = atoms_list[0].get("deeplink") or ""
            if dl:
                video_url = dl.split("&t=")[0]

        # 요약 캐시
        summary_row = _get_summary_row(doc_key)
        summary = None
        if summary_row:
            summary = {
                "tldr": summary_row.get("tldr"),
                "summary3": summary_row.get("summary3") or [],
                "market_view": summary_row.get("market_view"),
                "market_reason": summary_row.get("market_reason"),
                "stocks": summary_row.get("stocks_json") or [],
                "seeds": summary_row.get("seeds_json") or [],
                "highlights": summary_row.get("highlights_json") or [],
                "generated_at": summary_row.get("generated_at"),
            }

        # 타임라인 원자 (날짜+시간 명시)
        atoms_out = []
        for a in atoms_list:
            ts_raw = a.get("yt_timestamp") or ""
            secs = _ts_to_seconds(ts_raw)
            a_date = a.get("date") or ""
            msg_ts = a.get("msg_ts") or ""
            # when: 사람이 읽는 날짜+시간. msg_ts가 HH:MM 형식이면 날짜와 결합
            if msg_ts and re.match(r"^\d{1,2}:\d{2}$", msg_ts):
                when = f"{a_date} {msg_ts}"
            else:
                when = a_date
            atoms_out.append({
                "timestamp": ts_raw,
                "seconds": secs,
                "date": a_date,
                "when": when,
                "speaker": a.get("speaker"),
                "signal": a.get("signal"),
                "stance": a.get("stance_key"),
                "content": a.get("content"),
                "deeplink": a.get("deeplink"),
                "asset": a.get("asset"),
                "sector": a.get("sector"),
            })

        # 타임라인 정렬 (영상=초 오름차순, 그 외=원래 순서 유지)
        if category == "youtube":
            atoms_out.sort(key=lambda x: x["seconds"])

        return JSONResponse(content={
            "doc_key": doc_key,
            "category": category,
            "source": source_name_meta,
            "title": title,
            "date": date_meta,
            "video_url": video_url,
            "summary": summary,
            "atoms": atoms_out,
        })
    finally:
        conn.close()


# ── §4.6 POST /api/insights/summarize ────────────────────────
@app.post("/api/insights/summarize")
async def api_insights_summarize(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    doc_key = (body.get("doc_key") or "").strip()
    force = bool(body.get("force", False))
    if not doc_key:
        return JSONResponse(content={"error": "doc_key 필요"}, status_code=400)
    if not _DS_AVAIL:
        return JSONResponse(content={"error": "doc_summary 모듈 없음"}, status_code=503)

    result = await run_in_threadpool(get_or_build_summary, doc_key, force=force)
    return JSONResponse(content={"ok": True, "summary": result})


# ── §4.7 GET /api/insights/search?q=삼성전자 ─────────────────
@app.get("/api/insights/search")
def api_insights_search(q: str = ""):
    if not q.strip():
        return JSONResponse(content={"q": q, "total": 0, "hits": []})

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        toks = _tokenize_query(q)
        where = " OR ".join(["content LIKE ? OR asset LIKE ?"] * len(toks))
        params = []
        for t in toks:
            params += [f"%{t}%", f"%{t}%"]
        rows = conn.execute(
            f"""SELECT source_type, source_name, raw_file, date,
                       content, asset, stance_key, yt_timestamp, deeplink
                FROM atoms
                WHERE {where}
                ORDER BY date DESC
                LIMIT 300""",
            params,
        ).fetchall()

        # 매칭 토큰 수로 랭킹 (많이 겹칠수록 위로), 동점은 최신순
        def _score(r):
            text = (r["content"] or "") + " " + (r["asset"] or "")
            return sum(1 for t in toks if t in text)
        rows = sorted(rows, key=lambda r: (_score(r), r["date"] or ""), reverse=True)[:50]

        hits = []
        for r in rows:
            # source_type 기반 카테고리
            st = r["source_type"] or ""
            if st in ("youtube", "yt"):
                cat = "youtube"
            elif st == "telegram":
                cat = "telegram"
            elif st in ("report", "blog", "news"):
                cat = st
            else:
                cat = st

            raw_file = r["raw_file"] or ""
            dk = _doc_key(cat, r["source_name"], r["date"], raw_file)
            title = _build_doc_title(raw_file, r["source_name"], r["date"], cat)
            hits.append({
                "category": cat,
                "source": r["source_name"],
                "doc_key": dk,
                "title": title,
                "date": r["date"],
                "timestamp": r["yt_timestamp"],
                "stance": r["stance_key"],
                "content": (r["content"] or "")[:200],
                "deeplink": r["deeplink"],
            })

        return JSONResponse(content={"q": q, "total": len(hits), "hits": hits})
    finally:
        conn.close()


# 종목 집계에서 제외할 일반어(섹터/노이즈)
_SIGNAL_STOP = {
    "기타", "전체", "국내", "관련주", "테마", "섹터",
}

# 매크로/이슈(종목 아님) 판별 힌트
_MACRO_HINT = (
    "실업", "경제", "은행", "지수", "부동산", "금리", "환율", "물가", "증시", "국채",
    "유가", "달러", "엔화", "위안", "정책", "프로젝트", "실적발표", "고용", "무역",
    "관세", "gdp", "pmi", "pce", "cpi", "fomc", "나스닥", "코스피", "코스닥", "다우",
    "s&p", "필라델피아", "연방", "시장", "펀드", "경고", "투경", "정부", "규제",
    "반도체", "이차전지", "2차전지", "조선", "방산", "바이오", "로봇", "전력", "자동차",
    "통신", "제약", "화학", "철강", "건설", "AI", "HBM",
)
_MACRO_SOLO = {"미국", "중국", "일본", "독일", "유럽", "한국", "캐나다", "인도", "대만",
               "영국", "프랑스", "러시아", "대장주", "후발주"}


def _sig_kind(a):
    al = (a or "").lower()
    if a in _MACRO_SOLO or any(h.lower() in al for h in _MACRO_HINT):
        return "macro"
    return "stock"


@app.get("/api/insights/signals")
def api_insights_signals():
    """오늘의 시그널 — 종목 언급 버즈 스파이크 + 소스 합의/충돌."""
    from collections import Counter
    from datetime import timedelta
    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        d8 = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT asset, source_type, source_name, date, stance_key, content FROM atoms "
            "WHERE asset IS NOT NULL AND asset!='' AND date>=?", (d8,)).fetchall()
    finally:
        conn.close()

    def _assets(a):
        out = []
        for t in re.split(r"[,/·|]", a or ""):
            t = t.strip()
            if 1 < len(t) < 14 and t not in _SIGNAL_STOP and not t.isdigit():
                out.append(t)
        return out

    today_cnt = Counter()
    prior = {}       # asset -> {date: n}
    cats = {}        # asset -> set(category)
    stance = {}      # asset -> Counter
    facts = {}       # asset -> [ {content, source, cat, date, stance, hit} ]
    srcs = {}        # asset -> {source_name: cat}
    for r in rows:
        cat = _nb_cat_of(r["source_type"])
        for a in _assets(r["asset"]):
            if r["date"] == today:
                today_cnt[a] += 1
                cats.setdefault(a, set()).add(cat)
                sk = (r["stance_key"] or "")
                if sk in ("bullish", "bearish", "neutral"):
                    stance.setdefault(a, Counter())[sk] += 1
                content = (r["content"] or "").strip()
                if content:
                    srcs.setdefault(a, {})[r["source_name"] or "미상"] = cat
                    facts.setdefault(a, []).append({
                        "content": content[:280],
                        "source": r["source_name"] or "미상",
                        "cat": cat,
                        "date": r["date"],
                        "stance": sk,
                        # 종목명이 본문에 실제 등장 → 그 종목 관련 팩트일 확률 ↑
                        "hit": 1 if a in content else 0,
                    })
            else:
                prior.setdefault(a, {}).setdefault(r["date"], 0)
                prior[a][r["date"]] += 1

    signals = []
    for a, tn in today_cnt.items():
        pdays = prior.get(a, {})
        pavg = (sum(pdays.values()) / len(pdays)) if pdays else 0.0
        catset = cats.get(a, set())
        st = stance.get(a, Counter())
        # 본문에 종목명 실제 등장한 팩트 먼저(지어내지 않기), 그 다음 최신순
        flist = sorted(facts.get(a, []), key=lambda f: (f["hit"], f["date"]), reverse=True)
        # 중복 본문 제거
        seen_c, uniq = set(), []
        for f in flist:
            k = f["content"][:60]
            if k in seen_c:
                continue
            seen_c.add(k)
            uniq.append(f)
        src_list = [{"name": (n if len(n) <= 18 else n[:17] + "…"), "cat": c}
                    for n, c in list(srcs.get(a, {}).items())[:8]]
        signals.append({
            "asset": a, "kind": _sig_kind(a), "today": tn, "prior_avg": round(pavg, 1),
            "spike": round(tn - pavg, 1), "is_new": (pavg == 0),
            "cats": [c for c in ("youtube", "telegram", "report", "news", "blog") if c in catset],
            "n_cats": len(catset),
            "bull": st.get("bullish", 0), "bear": st.get("bearish", 0),
            "sample": (uniq[0]["content"][:130] if uniq else ""),
            "facts": uniq[:6],
            "sources": src_list,
        })
    # 랭킹: 다채널(합의) + 오늘 언급 + 스파이크
    signals.sort(key=lambda s: (s["n_cats"] * 2 + s["today"] + max(0.0, s["spike"])), reverse=True)
    stocks = [s for s in signals if s["kind"] == "stock"][:15]
    macro = [s for s in signals if s["kind"] == "macro"][:10]
    return JSONResponse(content={"today": today, "stocks": stocks, "macro": macro,
                                 "signals": (stocks + macro)})


# ── §4.9 NotebookLM 다리: 가로검색 묶음 → 노트북 자동 생성 ──────


# 리모션(채널) 브랜드 디자인 지침 — 인포그래픽/슬라이드/영상에 기본 적용




@app.get("/api/insights/notebook_preview")
def api_insights_notebook_preview(q: str = ""):
    """옵션 패널용 집계: 카테고리별 건수·기간별 건수·날짜범위."""
    if not q.strip():
        return JSONResponse(content={"error": "q 필요"}, status_code=400)
    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        rows, toks, label = _nb_fetch_rows(conn, q, cats=None, period="all", limit=500)
    finally:
        conn.close()
    cats_count = {"youtube": 0, "telegram": 0, "report": 0, "blog": 0, "news": 0}
    today = datetime.now().strftime("%Y-%m-%d")
    d3, d7 = _nb_period_min("d3"), _nb_period_min("d7")
    per = {"today": 0, "d3": 0, "d7": 0, "all": len(rows)}
    dates = []
    for r in rows:
        c = _nb_cat_of(r["source_type"])
        if c in cats_count:
            cats_count[c] += 1
        d = r["date"] or ""
        if d:
            dates.append(d)
            if d == today:
                per["today"] += 1
            if d3 and d >= d3:
                per["d3"] += 1
            if d7 and d >= d7:
                per["d7"] += 1
    return JSONResponse(content={
        "q": q, "label": label, "total": len(rows), "cats": cats_count,
        "dates": {"min": min(dates) if dates else "", "max": max(dates) if dates else ""},
        "periods": per,
    })


@app.post("/api/insights/to_notebook")
async def api_insights_to_notebook(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    q = (body.get("q") or "").strip()
    if not q:
        return JSONResponse(content={"error": "q(검색어) 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(
            content={"error": "nlm CLI 없음 — 터미널에서 nlm login 후 재시도"},
            status_code=503)

    # ── 옵션 파싱 ──
    cats_raw = body.get("cats")
    research = bool(body.get("research", False))   # NotebookLM 웹 리서치 추가
    # 리서치 ON + 소스 미선택(빈 배열) → 크롤링 없이 웹 리서치만
    no_crawl = research and isinstance(cats_raw, list) and len(cats_raw) == 0
    cats = cats_raw if (isinstance(cats_raw, list) and cats_raw) else None
    period = _valid_period(body.get("period"))
    try:
        limit = int(body.get("limit") or 200)
    except Exception:
        limit = 200
    split = bool(body.get("split", False))
    include_urls = bool(body.get("include_urls", True))
    # 프론트가 넘긴 깔끔한 이름(카테고리/종목) — 있으면 토큰라벨 대신 이걸로 명명
    label_override = re.sub(r"\s+", " ", (body.get("label") or "")).strip()[:40]

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "out", "insights_notebook")
    os.makedirs(out_dir, exist_ok=True)
    file_specs = []           # (source_title, path)
    yt_urls, web_urls = [], []
    md_for_cache = []

    if no_crawl:
        label = label_override or re.sub(r"\s+", " ", q).strip()[:40] or "리서치"
        atoms_n = 0
    else:
        bundle = await run_in_threadpool(
            _build_notebook_bundle, q, cats, period, limit, split, include_urls)
        if bundle is None:
            return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
        label = label_override or bundle["label"]
        atoms_n = bundle["atoms_n"]
        if atoms_n == 0 and not research:
            return JSONResponse(content={"error": f"'{q}' (필터 조건) 매칭 발언 없음"}, status_code=400)
        if not (label or "").strip():
            label = re.sub(r"\s+", " ", q).strip()[:40] or "리서치"
        safe_q = re.sub(r'[\\/:*?"<>|]', '_', label)[:40] or "검색"
        if atoms_n > 0:
            for i, (src_title, md_text) in enumerate(bundle["md_files"]):
                suffix = f"_{i}" if len(bundle["md_files"]) > 1 else ""
                mp = os.path.join(out_dir, f"{safe_q}_{period}{suffix}_{today}.md")
                with open(mp, "w", encoding="utf-8") as f:
                    f.write(md_text)
                file_specs.append((src_title, mp))
            md_for_cache = [t for _t, t in bundle["md_files"]]
        yt_urls = bundle["yt_urls"]
        web_urls = bundle["web_urls"]

    def _do():
        title = f"[허브] {label} · {today}"
        cr = create_notebook(title)
        if not cr["ok"]:
            return {"error": f"노트북 생성 실패: {cr['error']}"}
        nb_id = cr["notebook_id"]

        added, last_err = 0, ""
        for src_title, mp in file_specs:
            r2 = add_source_file(nb_id, mp, src_title)
            if r2["ok"]:
                added += 1
            else:
                last_err = r2["error"]
        if yt_urls or web_urls:
            r3 = add_source_urls(nb_id, yt_urls, web_urls)
            if r3["ok"]:
                added += 1
        researched = 0
        if research:
            okr, outr, _er = _run_nlm(
                ["research", "start", q, "-n", nb_id, "-m", "fast", "--force", "--auto-import"],
                timeout=150)
            if okr:
                ok4, out4, _ = _run_nlm(["notebook", "get", nb_id])
                try:
                    researched = max(0, json.loads(out4).get("source_count", added) - added)
                except Exception:
                    researched = 0
                added += researched
        return {
            "ok": True,
            "notebook_id": nb_id,
            "url": f"https://notebooklm.google.com/notebook/{nb_id}",
            "atoms": atoms_n,
            "yt_urls": len(yt_urls),
            "web_urls": len(web_urls),
            "md_sources": len(file_specs),
            "sources_added": added,
            "researched": researched,
            "research": research,
            "period": period,
            "label": label,
            "source_warn": ("" if added >= 1 else (last_err or "")[:160]),
        }

    result = await run_in_threadpool(_do)
    # Claude 직접 대화용 캐시 + 레지스트리 영속(이전 자료 끌어오기용)
    if result.get("ok") and result.get("notebook_id"):
        nbid = result["notebook_id"]
        if md_for_cache:
            _NB_BUNDLES[nbid] = "\n\n".join(md_for_cache)[:60000]
        _nb_registry_add({
            "id": nbid, "label": label, "date": today, "url": result["url"],
            "atoms": atoms_n, "paths": [p for _t, p in file_specs],
        })
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.post("/api/insights/notebook_research")
async def api_insights_notebook_research(req: Request):
    """노트북에 웹 딥리서치 소스 자동 추가 (nlm research start --auto-import)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    q = (body.get("q") or "").strip()
    mode = (body.get("mode") or "fast").strip()
    if mode not in ("fast", "deep"):
        mode = "fast"
    if not nb_id or not q:
        return JSONResponse(content={"error": "notebook_id·q 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    def _do():
        before = 0
        ok0, out0, _ = _run_nlm(["notebook", "get", nb_id])
        if ok0:
            try:
                before = json.loads(out0).get("source_count", 0)
            except Exception:
                pass
        # fast~30s / deep~5min. deep는 HTTP 한계 → fast만 동기, deep는 그대로 길게.
        tmo = 120 if mode == "fast" else 360
        ok, out, errm = _run_nlm(
            ["research", "start", q, "-n", nb_id, "-m", mode, "--force", "--auto-import"],
            timeout=tmo)
        if not ok:
            return {"error": f"리서치 실패: {_friendly_nlm_err(errm)}"}
        after = before
        ok1, out1, _ = _run_nlm(["notebook", "get", nb_id])
        if ok1:
            try:
                after = json.loads(out1).get("source_count", before)
            except Exception:
                pass
        return {"ok": True, "added": max(0, after - before), "total_sources": after, "mode": mode}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.post("/api/insights/notebook_card")
async def api_insights_notebook_card(req: Request):
    """노트북 소스로 카드/인포(브리핑 리포트) 생성 (nlm report create)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    fmt = (body.get("format") or "Briefing Doc").strip()
    if fmt not in ("Briefing Doc", "Study Guide", "Blog Post"):
        fmt = "Briefing Doc"
    if not nb_id:
        return JSONResponse(content={"error": "notebook_id 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    def _do():
        r = nlm_create_report(nb_id, fmt=fmt, language="ko")
        if not r["ok"]:
            return {"error": f"카드 생성 실패: {r['error']}"}
        return {"ok": True, "format": fmt, "markdown": r["markdown"],
                "ready": r["ready"], "url": r["url"]}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.post("/api/insights/notebook_query")
async def api_insights_notebook_query(req: Request):
    """허브 안에서 노트북에 질문 → 인용 달린 답변 반환 (nlm notebook query)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    question = (body.get("question") or "").strip()
    conv = (body.get("conversation_id") or "").strip()
    if not nb_id or not question:
        return JSONResponse(content={"error": "notebook_id·question 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    def _do():
        r = nlm_notebook_query(nb_id, question, conv=conv, timeout=180)
        if not r["ok"]:
            return {"error": f"질문 실패: {r['error']}"}
        return {"ok": True, "answer": r["answer"], "conversation_id": r["conversation_id"]}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


# 만들기 종류 → 생성/다운로드/표시 정보
# show=True 면 완료까지 폴링 후 다운로드해 허브 UI에 인라인 표시.
_STUDIO_KINDS = {
    "infographic": {"create": ["infographic", "create"], "label": "인포그래픽", "eta": "~1분",
                    "types": ("infographic",), "dl": ["download", "infographic"], "ext": "png", "media": "image", "show": True},
    "slides":      {"create": ["slides", "create"], "label": "슬라이드", "eta": "~1분",
                    "types": ("slide_deck", "slides"), "dl": ["download", "slide-deck"], "ext": "pdf", "media": "pdf", "show": True},
    "audio":       {"create": ["audio", "create"], "label": "오디오(팟캐스트)", "eta": "2~5분",
                    "types": ("audio",), "dl": ["download", "audio"], "ext": "mp3", "media": "audio", "show": False},
    "video":       {"create": ["video", "create"], "label": "영상", "eta": "3~6분",
                    "types": ("video",), "dl": ["download", "video"], "ext": "mp4", "media": "video", "show": False},
    "mindmap":     {"create": ["mindmap", "create"], "label": "마인드맵", "eta": "~1분",
                    "types": ("mind_map",), "dl": None, "ext": None, "media": None, "show": False},
}


def _studio_arts(nb_id, types):
    """해당 타입 아티팩트 (id, status) 목록."""
    ok, out, _ = _run_nlm(["studio", "status", nb_id])
    res = []
    if ok:
        try:
            for a in json.loads(out):
                if a.get("type") in types:
                    res.append((a.get("id"), (a.get("status") or "")))
        except Exception:
            pass
    return res


_STUDIO_DONE_STATUSES = ("completed", "done", "ready", "success")


def _in_progress_studio_jobs(nb_id: str) -> list[dict]:
    """이 노트북에서 아직 안 끝난(생성 중) 아티팩트를 kind별로 조회.
    NotebookLM 자체 studio status를 진실의 원천으로 써서, 브라우저 탭을 닫았다 열어도
    재접속 시 '진행 중이던 게 있었다'를 알 수 있게 한다(서버 프로세스 재시작에도 안 끊김 —
    로컬 상태를 따로 안 두고 NotebookLM 쪽 상태를 그대로 조회)."""
    ok, out, _ = _run_nlm(["studio", "status", nb_id])
    if not ok:
        return []
    try:
        arts = json.loads(out)
    except Exception:
        return []
    type_to_kind = {}
    for kind, spec in _STUDIO_KINDS.items():
        for t in spec["types"]:
            type_to_kind[t] = kind
    jobs = []
    for a in arts:
        status = (a.get("status") or "").lower()
        kind = type_to_kind.get(a.get("type"))
        if not kind or status in _STUDIO_DONE_STATUSES or not status:
            continue
        jobs.append({"kind": kind, "artifact_id": a.get("id"), "status": status,
                     "label": _STUDIO_KINDS[kind]["label"]})
    return jobs


@app.get("/api/insights/studio_jobs")
def api_insights_studio_jobs(notebook_id: str = ""):
    """워크스페이스 재접속 시 '이미 생성 중이던 게 있는지' 확인용.
    있으면 프론트가 로딩카드를 다시 붙여서 폴링을 이어간다."""
    if not notebook_id or not _nlm_exe():
        return JSONResponse(content={"jobs": []})
    jobs = _in_progress_studio_jobs(notebook_id)
    return JSONResponse(content={"jobs": jobs})


@app.get("/api/insights/artifact")
def api_insights_artifact(f: str = ""):
    """생성된 아티팩트(png/pdf/mp3/mp4) 서빙 — out/insights_notebook 한정."""
    name = os.path.basename(f or "")
    if not name:
        return JSONResponse(content={"error": "f 필요"}, status_code=400)
    path = os.path.join(ROOT, "out", "insights_notebook", name)
    if not os.path.exists(path):
        return JSONResponse(content={"error": "not found"}, status_code=404)
    mt = {"png": "image/png", "pdf": "application/pdf",
          "mp3": "audio/mpeg", "mp4": "video/mp4"}.get(name.rsplit(".", 1)[-1].lower())
    return FileResponse(path, media_type=mt)


@app.post("/api/insights/notebook_studio")
async def api_insights_notebook_studio(req: Request):
    """인포/슬라이드/오디오/영상 생성. show=True(인포·슬라이드)는 완료까지 폴링→다운로드→허브 표시."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    kind = (body.get("kind") or "").strip()
    focus = (body.get("focus") or "").strip()
    if not nb_id or kind not in _STUDIO_KINDS:
        return JSONResponse(content={"error": "notebook_id·kind(infographic/slides/audio/video/mindmap) 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    spec = _STUDIO_KINDS[kind]

    def _do():
        before = {i for i, _s in _studio_arts(nb_id, spec["types"])}
        args = list(spec["create"]) + [nb_id, "--confirm"]
        if kind != "mindmap":
            args += ["--language", "ko"]      # 결과물 한국어로
        # 시각 결과물엔 채널(리모션) 브랜드 디자인 + 업로드한 레퍼런스 스타일 적용
        f2 = focus
        if kind in ("infographic", "slides", "video"):
            parts = ([focus] if focus else []) + [_BRAND_DESIGN]
            ref = _NB_DESIGN.get(nb_id)
            if ref:
                parts.append("[레퍼런스 스타일 — 이 느낌을 반영] " + ref)
            f2 = " / ".join(parts)
            if kind == "infographic":
                args += ["--style", "professional"]
                orient = (body.get("orientation") or "").strip()
                if orient in ("landscape", "portrait", "square"):
                    args += ["--orientation", orient]
                detail = (body.get("detail") or "").strip()
                if detail in ("concise", "standard", "detailed"):
                    args += ["--detail", detail]
        if kind == "slides":
            length = (body.get("length") or "").strip()
            if length in ("short", "default"):
                args += ["--length", length]
        if f2:
            args += ["--focus", f2]
        ok, out, errm = _run_nlm(args, timeout=120)
        if not ok:
            return {"error": f"{spec['label']} 생성 실패: {_friendly_nlm_err(errm)}"}
        # 시작 출력에서 artifact id 파싱
        m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out or "")
        art_id = m.group(0) if m else None
        if not art_id:
            # 출력에 없으면 새로 생긴 아티팩트로 추정
            for i, _s in _studio_arts(nb_id, spec["types"]):
                if i not in before:
                    art_id = i
                    break
        return {"ok": True, "kind": kind, "label": spec["label"], "eta": spec["eta"],
                "media": spec["media"], "show": bool(spec["show"] and spec["dl"]),
                "artifact_id": art_id,
                "url": f"https://notebooklm.google.com/notebook/{nb_id}"}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/studio_poll")
def api_insights_studio_poll(notebook_id: str = "", artifact_id: str = "", kind: str = ""):
    """생성 중인 아티팩트 완료 확인 → 완료 시 다운로드해 서빙 URL 반환."""
    spec = _STUDIO_KINDS.get(kind)
    if not notebook_id or not artifact_id or not spec or not spec.get("dl"):
        return JSONResponse(content={"ready": False, "error": "잘못된 요청"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"ready": False, "error": "nlm CLI 없음"}, status_code=503)

    def _do():
        status = ""
        for i, s in _studio_arts(notebook_id, spec["types"]):
            if i == artifact_id:
                status = s.lower()
                break
        if status not in ("completed", "done", "ready", "success"):
            return {"ready": False, "status": status or "in_progress"}
        fname = f"{kind}_{re.sub(r'[^0-9a-zA-Z-]', '', artifact_id)}.{spec['ext']}"
        fpath = os.path.join(ROOT, "out", "insights_notebook", fname)
        if not os.path.exists(fpath):
            dargs = list(spec["dl"]) + [notebook_id, "-o", fpath, "--id", artifact_id]
            okd, _o, _e = _run_nlm(dargs, timeout=120)
            if not (okd and os.path.exists(fpath)):
                return {"ready": False, "status": "downloading"}
        return {"ready": True, "media": spec["media"], "file_url": f"/api/insights/artifact?f={fname}"}

    return JSONResponse(content=_do())


@app.post("/api/insights/claude_chat")
async def api_insights_claude_chat(req: Request):
    """Claude와 직접 대화 — 노트북 수집 자료를 컨텍스트로 제공(있으면)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    messages = body.get("messages") or []
    messages = [m for m in messages if isinstance(m, dict) and m.get("content")]
    if not messages:
        return JSONResponse(content={"error": "messages 필요"}, status_code=400)
    key = _env_key("ANTHROPIC_API_KEY")
    if not key:
        return JSONResponse(content={"error": "Claude 대화는 ANTHROPIC_API_KEY가 필요합니다. .env에 ANTHROPIC_API_KEY=... 추가 후 서버 재시작하세요."}, status_code=503)

    model = _env_key("ANTHROPIC_MODEL") or "claude-opus-4-8"

    def _do():
        try:
            import anthropic
        except Exception:
            return {"error": "anthropic 패키지 없음 (pip install anthropic)"}
        ctx = _NB_BUNDLES.get(nb_id, "")
        system = (
            "너는 한국 주식 트레이더의 리서치 보조다. 아래 '수집 자료'(텔레그램·리포트·뉴스·"
            "유튜브·블로그에서 추출한 발언)를 빠짐없이 1차 근거로 삼되, 일반 지식도 활용해 한국어로 "
            "구체적이고 실전적으로, 종목명·수치·근거를 담아 충실히 답하라. 추측은 추측이라고 밝혀라."
            "\n\n[수집 자료]\n" + (ctx[:40000] or "(자료 없음)")
        )
        msgs = [{"role": ("assistant" if m.get("role") == "assistant" else "user"),
                 "content": str(m.get("content"))[:8000]} for m in messages][-12:]
        try:
            client = anthropic.Anthropic(api_key=key)
            resp = client.messages.create(model=model, max_tokens=2000, system=system, messages=msgs)
            text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
            return {"ok": True, "answer": text or "(빈 응답)"}
        except Exception as e:
            return {"error": f"Claude 호출 실패: {str(e)[:300]}"}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


def _naver_board_posts(code, period="d3", max_pages=15):
    """네이버 종목토론방 게시글 수집(bs4) — 제목·날짜·조회수·추천. period로 기간 필터.
    ※ 본문 텍스트는 네이버가 인증 API(mobilestock)로 가려 단순크롤 불가 → 제목+참여도 기반."""
    import urllib.request
    from datetime import timedelta
    from bs4 import BeautifulSoup
    cut = None
    p = (period or "all").strip()
    if p == "today":
        cut = datetime.now().strftime("%Y.%m.%d")
    else:
        m = re.match(r"^d(\d+)$", p)
        if m:
            cut = (datetime.now() - timedelta(days=int(m.group(1)))).strftime("%Y.%m.%d")

    def _num(td):
        try:
            return int(td.get_text(strip=True).replace(",", ""))
        except Exception:
            return 0

    posts = []
    for pg in range(1, max_pages + 1):
        url = f"https://finance.naver.com/item/board.naver?code={code}&page={pg}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Encoding": "identity"})
            d = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")
        except Exception:
            break
        soup = BeautifulSoup(d, "html.parser")
        page_posts = []
        for a in soup.select('td.title a[title]'):
            href = a.get("href") or ""
            if "board_read" not in href:
                continue
            nm = re.search(r"nid=(\d+)", href)
            tr = a.find_parent("tr")
            tds = tr.find_all("td", recursive=False) if tr else []
            if len(tds) < 4 or not nm:
                continue
            page_posts.append({
                "date": tds[0].get_text(strip=True),
                "title": re.sub(r"\s+", " ", a["title"]).strip(),
                "views": _num(tds[3]),
                "up": _num(tds[4]) if len(tds) > 4 else 0,
                "nid": nm.group(1),
            })
        if not page_posts:
            break
        posts += page_posts
        if cut and page_posts and page_posts[-1]["date"][:10] < cut:
            break
    if cut:
        posts = [x for x in posts if x["date"][:10] >= cut]
    seen, out = set(), []
    for x in posts:
        if x["title"] and x["title"] not in seen:
            seen.add(x["title"])
            out.append(x)
    return out


def _naver_crawl(payload, timeout=60):
    """scripts/naver_crawl.py를 subprocess로 실행 → JSON.
    Playwright를 별도 프로세스로 격리(uvicorn 이벤트루프 반복실행 불안정 회피)+하드 타임아웃."""
    script = os.path.join(ROOT, "scripts", "naver_crawl.py")
    if not os.path.exists(script):
        return None
    try:
        p = subprocess.run(
            [sys.executable, script, json.dumps(payload, ensure_ascii=False)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=ROOT)
        return json.loads((p.stdout or "").strip() or "null")
    except Exception:
        return None


def _naver_post_bodies(code, items, top_n=6):
    """상위 글(조회수순) 본문 {nid: 본문} — Playwright subprocess 격리 크롤."""
    nids = [it["nid"] for it in items[:top_n] if it.get("nid")]
    if not nids:
        return {}
    res = _naver_crawl({"mode": "bodies", "code": code, "nids": nids}, timeout=55)
    return res if isinstance(res, dict) else {}


@app.post("/api/insights/naver_board")
async def api_insights_naver_board(req: Request):
    """네이버 종목토론방 크롤링 → 개인투자자 여론·상승이유 댓글분석 (Gemini)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    period = _valid_period(body.get("period") or "d3")
    code, tried, err = _resolve_stock(body)
    if err:
        return err

    try:
        posts = await run_in_threadpool(_naver_board_posts, code, period)
        if not posts:
            return JSONResponse(content={"error": "해당 기간 종토방 글이 없습니다(또는 네이버 접근 실패)"}, status_code=502)
        dates = [x["date"][:10] for x in posts]
        date_lo, date_hi = min(dates), max(dates)
        # 조회수 높은 순 = 개미들이 많이 본 글(여론 무게)
        top = sorted(posts, key=lambda x: (x["views"], x["up"]), reverse=True)
        total_views = sum(x["views"] for x in posts)
        # 상위 글 본문을 Playwright로 렌더링해 실제 내용까지 분석
        bodies = await run_in_threadpool(_naver_post_bodies, code, top, 6)
        for x in top:
            x["body"] = bodies.get(x.get("nid"), "")
    except Exception as e:
        return JSONResponse(content={"error": f"종토방 분석 실패(크롤링): {str(e)[:160]}"}, status_code=500)

    def _analyze():
        try:
            from google import genai
        except Exception as e:
            return {"error": f"google-genai 없음: {str(e)[:120]}"}
        keys = _gemini_interactive_keys()
        if not keys:
            return {"error": ".env에 GEMINI_API_KEY 없음"}
        # 상위 글은 본문까지, 나머지는 제목만
        body_lines = []
        for x in top[:8]:
            if x.get("body"):
                body_lines.append(f"[조회{x['views']}·추천{x['up']}] 제목: {x['title']}\n  본문: {x['body']}")
        title_lines = "\n".join(f"- (조회{x['views']}·추천{x['up']}) {x['title']}" for x in top[:50])
        prompt = (
            f"아래는 네이버 종목토론방 '{tried}'({code}) {date_lo}~{date_hi} 기간 게시글이다(총 {len(posts)}개). "
            "조회·추천 높은 글일수록 여론의 무게가 크다. 상위 글은 본문까지 제공한다. "
            "이를 반영해 개인투자자(개미) 여론을 한국어로 분석하라:\n"
            "1) 전반 분위기 — 긍정/부정/혼조 + 강도 (조회/추천·본문 근거로 판단)\n"
            "2) 주가 상승/하락 이유 — 본문·제목에 실제 나온 근거만 (구체적으로)\n"
            "3) 자주 나오는 키워드·이슈\n"
            "4) 가장 많이 읽히거나 공감받은 글 2~3개 (내용 요약 + 조회/추천 수)\n"
            "⚠️ 제공된 본문·제목에 있는 내용만. 지어내지 마라. 과열/작전 의심 신호 보이면 표시.\n\n"
            + (("[상위 글 본문]\n" + "\n\n".join(body_lines) + "\n\n") if body_lines else "")
            + "[전체 제목(조회순)]\n" + title_lines)
        return _gemini_text(prompt)

    res = await run_in_threadpool(_analyze)
    if not res.get("ok"):
        return JSONResponse(content=res, status_code=500)
    return JSONResponse(content={
        "ok": True, "stock": tried, "code": code, "count": len(posts),
        "period": period, "date_from": date_lo, "date_to": date_hi,
        "total_views": total_views, "bodies_read": sum(1 for x in top[:6] if x.get("body")),
        "analysis": res["analysis"],
        "top": [{"title": x["title"], "views": x["views"], "up": x["up"], "date": x["date"],
                 "body": x.get("body", "")} for x in top[:12]],
        "url": f"https://finance.naver.com/item/board.naver?code={code}"})


# 광고·홍보성 뉴스 제외 키워드
_NEWS_AD_KW = ("추천주", "급등주", "상한가", "무료", "리딩", "세력", "카톡", "문자", "단톡",
               "세미나", "지금매수", "매수타이밍", "수익인증", "종목문의", "무료추천", "급등임박",
               "인증", "회원모집", "1:1", "VIP", "적중", "포착주")


_KRX_CODES_CACHE = None


def _krx_codes():
    """krx_codes.json → {종목명: 코드} (약 2600종목). 1회 로드 캐시."""
    global _KRX_CODES_CACHE
    if _KRX_CODES_CACHE is None:
        try:
            p = os.path.join(ROOT, "pipeline", "atoms", "krx_codes.json")
            d = json.load(open(p, encoding="utf-8"))
            _KRX_CODES_CACHE = d.get("codes", {}) if isinstance(d, dict) else {}
        except Exception:
            _KRX_CODES_CACHE = {}
    return _KRX_CODES_CACHE


# 대기업 영문약자 ↔ 한글음역 (KRX가 회사마다 제각각 등록: SK하이닉스=영문 / 엘에스일렉트릭=한글)
_BRAND_ALIASES = {
    "ls": "엘에스", "sk": "에스케이", "lg": "엘지", "kt": "케이티", "gs": "지에스",
    "cj": "씨제이", "kb": "케이비", "db": "디비", "dl": "디엘", "hd": "에이치디",
    "hl": "에이치엘", "nh": "엔에이치", "jb": "제이비", "bnk": "비엔케이",
    "dgb": "디지비", "sga": "에스지에이", "hmm": "에이치엠엠", "kcc": "케이씨씨",
}


def _query_variants(ql):
    """쿼리 변형: 영문약자→한글음역, 한글음역→영문약자 (양방향)."""
    vs = {ql}
    for en, ko in _BRAND_ALIASES.items():
        if ql.startswith(en):
            vs.add(ko + ql[len(en):])
        if ql.startswith(ko):
            vs.add(en + ql[len(ko):])
    return vs


# KRX 원명이 한글음역이지만 브랜드명이 확실한 종목만 표시명 교정(검증된 것만; 애매한 지에스이·KT&G 계열 등은 제외)
_DISPLAY_ALIAS = {
    "엘에스일렉트릭": "LS일렉트릭",
    "에스케이바이오팜": "SK바이오팜",
    "에이치엘사이언스": "HL사이언스",
    "케이씨씨": "KCC",
    "케이씨씨글라스": "KCC글라스",
    "케이티": "KT",
    "케이티스카이라이프": "KT스카이라이프",
    "케이티알파": "KT알파",
    "케이티앤지": "KT&G",
    "케이비아이동국실업": "KBI동국실업",
}


def _disp(name):
    return _DISPLAY_ALIAS.get(name, name)


def _resolve_stock(body):
    """body에서 종목코드 해석. code(자동완성 선택) 우선 → 없으면 stock명 code_for.
    반환: (code, 표시명, error_JSONResponse|None)."""
    given = (body.get("code") or "").strip()
    stock = (body.get("stock") or "").strip()
    if given.isdigit() and len(given) == 6:
        name = _disp(stock) if stock else ({v: k for k, v in _krx_codes().items()}.get(given, given))
        return given, name, None
    if not stock:
        return None, None, JSONResponse(content={"error": "종목명 필요"}, status_code=400)
    try:
        from pipeline.atoms.codemap import code_for
    except Exception:
        return None, None, JSONResponse(content={"error": "codemap 없음"}, status_code=500)
    code, tried = code_for(stock), stock
    if not code:
        for tok in re.split(r"[\s,·/]+", stock):
            tok = tok.strip()
            if tok and code_for(tok):
                code, tried = code_for(tok), tok
                break
    if not code:
        return None, None, JSONResponse(
            content={"error": f"'{stock}' 종목코드를 못 찾음 — 정확한 종목명으로 다시 시도"}, status_code=400)
    return code, _disp(tried), None


@app.get("/api/insights/stock_suggest")
def api_stock_suggest(q: str = ""):
    """종목명 자동완성 — 앞글자 우선, 부분일치 보조, 코드일치·약자별칭 포함. 최대 12개.
    name=KRX원명(코드조회용) / display=브랜드 표시명."""
    q = (q or "").strip()
    if not q:
        return JSONResponse(content={"items": []})
    variants = _query_variants(q.lower())
    codes = _krx_codes()
    starts, contains, seen = [], [], set()
    for name, code in codes.items():
        if code in seen:
            continue
        nl = name.lower()
        dl = _disp(name).lower()
        row = {"name": name, "display": _disp(name), "code": code}
        if any(nl.startswith(v) or dl.startswith(v) for v in variants) or code.startswith(q):
            starts.append(row); seen.add(code)
        elif any(v in nl or v in dl for v in variants):
            contains.append(row); seen.add(code)
    starts.sort(key=lambda x: len(x["name"]))
    items = (starts + contains)[:12]
    return JSONResponse(content={"items": items})


def _naver_news(code, limit=25):
    """네이버 종목뉴스 [{title,summary,press,date,url}] — subprocess 격리 크롤 + 광고성 1차 필터."""
    res = _naver_crawl({"mode": "news", "code": code}, timeout=45)
    items = [x for x in (res if isinstance(res, list) else []) if isinstance(x, dict)]

    def _is_ad(x):
        blob = (x.get("title") or "") + " " + (x.get("summary") or "")
        return any(k in blob for k in _NEWS_AD_KW)

    clean = [x for x in items if not _is_ad(x)]
    return (clean or items)[:limit]


@app.post("/api/insights/naver_news")
async def api_insights_naver_news(req: Request):
    """네이버 종목뉴스 → 주가 상승/하락 원인 + 핵심뉴스 (광고성 제외, Gemini)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    code, tried, err = _resolve_stock(body)
    if err:
        return err

    news = await run_in_threadpool(_naver_news, code, 25)
    if not news:
        return JSONResponse(content={"error": "종목뉴스를 가져오지 못했습니다"}, status_code=502)

    def _analyze():
        try:
            from google import genai
        except Exception as e:
            return {"error": f"google-genai 없음: {str(e)[:120]}"}
        keys = _gemini_interactive_keys()
        if not keys:
            return {"error": ".env에 GEMINI_API_KEY 없음"}
        prompt = (
            f"아래는 '{tried}'({code}) 네이버 종목뉴스 {len(news)}건(제목+요약)이다. "
            "광고·홍보·리딩방성 뉴스는 제외하고, 주가에 실제 영향 주는 '이유 있는 뉴스'만 골라 한국어로 정리하라:\n"
            "1) 📈 주가 상승/하락 원인 — 뉴스에 나온 구체적 이유(수주·실적·정책·이벤트 등)를 근거와 함께\n"
            "2) 📰 핵심 뉴스 3~5개 — 각 (제목 요약 + 왜 중요한지 한 줄)\n"
            "3) ⚠️ 주의할 악재/리스크 뉴스 있으면\n"
            "광고성(추천주·급등주·리딩·무료 등)은 빼라. 뉴스에 있는 내용만, 지어내지 마라.\n\n"
            "뉴스 목록:\n" + "\n".join(
                f"- {n.get('title','')} — {n.get('summary','')} ({n.get('press','')}·{n.get('date','')})"
                for n in news[:25]))
        return _gemini_text(prompt)

    res = await run_in_threadpool(_analyze)
    if not res.get("ok"):
        return JSONResponse(content=res, status_code=500)
    return JSONResponse(content={
        "ok": True, "stock": tried, "code": code, "count": len(news),
        "analysis": res["analysis"], "news": news[:12],
        "url": f"https://finance.naver.com/item/news_news.naver?code={code}"})


@app.post("/api/insights/gemini_chat")
async def api_insights_gemini_chat(req: Request):
    """Gemini 리서치 대화 — 구글 검색 그라운딩으로 최신 사실 + 노트북 자료 참고."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    messages = body.get("messages") or []
    messages = [m for m in messages if isinstance(m, dict) and m.get("content")]
    if not messages:
        return JSONResponse(content={"error": "messages 필요"}, status_code=400)

    def _do():
        ctx = _NB_BUNDLES.get(nb_id, "")
        system = (
            "너는 한국 주식 트레이더의 리서치 보조다. 구글 검색으로 최신 사실·뉴스를 확인해 "
            "한국어로 구체적·실전적으로, 종목명·수치·날짜·출처를 담아 충실히 답하라. "
            "아래 '내 수집 자료'도 함께 참고하되, 최신 정보는 검색을 우선하라."
            "\n\n[내 수집 자료]\n" + (ctx[:20000] or "(없음)")
        )
        convo = "\n".join(
            (("어시스턴트: " if m.get("role") == "assistant" else "사용자: ") + str(m.get("content"))[:4000])
            for m in messages[-8:]
        )
        try:
            from google import genai
            from google.genai import types
        except Exception as e:
            return {"error": f"google-genai 패키지 없음: {str(e)[:150]}"}
        keys = _gemini_interactive_keys()
        if not keys:
            return {"error": ".env에 GEMINI_API_KEY 없음"}
        def _gen(k, grounded):
            cfg = types.GenerateContentConfig(temperature=0)
            if grounded:
                cfg.tools = [types.Tool(google_search=types.GoogleSearch())]
            client = genai.Client(api_key=k)   # 변수 유지 — GC가 호출 중 닫지 않게
            return client.models.generate_content(
                model="gemini-3-flash-preview", contents=f"{system}\n\n{convo}", config=cfg)

        last, grounding_out = "", False
        # 1차: 구글 검색 그라운딩(실시간 웹) 시도
        for k in keys:
            try:
                resp = _gen(k, True)
                sources = []
                for c in (resp.candidates or []):
                    gm = getattr(c, "grounding_metadata", None)
                    for ch in (getattr(gm, "grounding_chunks", None) or []):
                        w = getattr(ch, "web", None)
                        if w:
                            sources.append({"title": getattr(w, "title", ""), "url": getattr(w, "uri", "")})
                return {"ok": True, "answer": (resp.text or "").strip() or "(빈 응답)", "sources": sources[:8]}
            except Exception as e:
                last = str(e)
                if "429" in last or "RESOURCE_EXHAUSTED" in last:
                    grounding_out = True
                    continue   # 다음(예비) 키로
                return {"error": f"Gemini 호출 실패: {last[:300]}"}
        # 2차: 그라운딩 쿼터 소진(무료티어=구글검색 0) → 웹검색 없이 답변
        if grounding_out:
            for k in keys:
                try:
                    resp = _gen(k, False)
                    return {"ok": True, "answer": (resp.text or "").strip() or "(빈 응답)",
                            "sources": [],
                            "note": "무료 티어는 구글 검색(그라운딩) 쿼터가 없어 웹검색 없이 모델 지식·내 수집자료로 답했습니다. 실시간 웹리서치는 🔎리서치(NotebookLM)를 쓰세요."}
                except Exception as e:
                    last = str(e)
                    continue
        return {"error": f"Gemini 쿼터 소진(키 {len(keys)}개 모두): {last[:200]}"}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/notebooks")
def api_insights_notebooks():
    """만든 브리핑(자료) 목록 — 이전 자료 끌어오기 픽커용."""
    reg = _load_nb_registry()   # 최신이 앞
    out, seen = [], set()
    for e in reg:
        nid = e.get("id")
        if not nid or nid in seen:   # id 자체는 _nb_registry_add에서 이미 유일 보장됨
            continue
        seen.add(nid)
        out.append({
            "id": nid, "label": e.get("label", ""), "date": e.get("date", ""),
            "atoms": e.get("atoms", 0),
            "url": e.get("url", "") or f"https://notebooklm.google.com/notebook/{nid}"})
    return JSONResponse(content={"notebooks": out})


@app.post("/api/insights/notebook_forget")
async def api_insights_notebook_forget(req: Request):
    """브리핑을 목록에서 삭제(레지스트리+스냅샷). hard=true면 NotebookLM 노트북도 삭제."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nid = (body.get("id") or "").strip()
    if not nid:
        return JSONResponse(content={"error": "id 필요"}, status_code=400)
    reg = [e for e in _load_nb_registry() if e.get("id") != nid]
    _save_nb_registry(reg)
    try:
        os.remove(_history_path(nid))
    except Exception:
        pass
    if body.get("hard") and _nlm_exe():
        _run_nlm(["notebook", "delete", nid, "--confirm"], timeout=60)
    return JSONResponse(content={"ok": True})


@app.post("/api/insights/notebook_add_fresh")
async def api_insights_notebook_add_fresh(req: Request):
    """현재 노트북에 카테고리+기간 기준 '새 자료(추출발언 .md + 원본 URL)'를 소스로 추가."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    cats_raw = body.get("cats")
    cats = cats_raw if (isinstance(cats_raw, list) and cats_raw) else None
    period = _valid_period(body.get("period"))
    if not nb_id:
        return JSONResponse(content={"error": "notebook_id 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    bundle = await run_in_threadpool(
        _build_notebook_bundle, "", cats, period, 200, False, True)
    if bundle is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    if bundle["atoms_n"] == 0:
        return JSONResponse(content={"error": "해당 소스·기간에 발언이 없습니다"}, status_code=400)

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "out", "insights_notebook")
    os.makedirs(out_dir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', '_', _nb_scope_label(cats, period))[:40] or "추가"

    def _do():
        added = 0
        for i, (src_title, md_text) in enumerate(bundle["md_files"]):
            mp = os.path.join(out_dir, f"add_{safe}_{period}_{i}_{today}.md")
            try:
                with open(mp, "w", encoding="utf-8") as f:
                    f.write(md_text)
            except Exception:
                continue
            ok2, _o2, _e2 = _run_nlm(["source", "add", nb_id, "--file", mp, "--title", src_title])
            if ok2:
                added += 1
        url_args = []
        for u in bundle["yt_urls"]:
            url_args += ["--youtube", u]
        for u in bundle["web_urls"]:
            url_args += ["--url", u]
        if url_args:
            ok3, _o3, _e3 = _run_nlm(["source", "add", nb_id] + url_args, timeout=150)
            if ok3:
                added += 1
        total = added
        okg, outg, _ = _run_nlm(["notebook", "get", nb_id])
        if okg:
            try:
                total = json.loads(outg).get("source_count", added)
            except Exception:
                pass
        if added == 0:
            return {"error": "소스 추가 실패 (nlm 인증 확인)"}
        return {"ok": True, "atoms": bundle["atoms_n"],
                "yt": len(bundle["yt_urls"]), "web": len(bundle["web_urls"]),
                "total_sources": total}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/recent_reports")
def api_insights_recent_reports():
    """최근 증권사 리포트 — 종목·목표가/의견 스니펫 (메인 목록용)."""
    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"reports": []})
    try:
        rows = conn.execute(
            "SELECT asset, source_name, date, stance_key, content FROM atoms "
            "WHERE source_type='report' AND date IS NOT NULL AND date!='' "
            "ORDER BY date DESC, rowid DESC LIMIT 200").fetchall()
    finally:
        conn.close()
    out, seen = [], set()
    for r in rows:
        asset = re.split(r"[,/·|]", r["asset"] or "")[0].strip()
        key = (asset, r["date"], r["source_name"])
        if not asset or key in seen:
            continue
        seen.add(key)
        out.append({
            "asset": asset,
            "source": (r["source_name"] or "리포트")[:20],
            "date": r["date"],
            "stance": r["stance_key"] or "",
            "snippet": (r["content"] or "").strip()[:100],
        })
        if len(out) >= 14:
            break
    return JSONResponse(content={"reports": out})


def _history_path(nb_id):
    safe = re.sub(r"[^0-9a-fA-F-]", "", nb_id or "")[:40]
    return os.path.join(ROOT, "out", "insights_notebook", "history", f"{safe}.json")


@app.post("/api/insights/history_save")
async def api_insights_history_save(req: Request):
    """워크스페이스 캔버스 전체 스냅샷을 노트북별로 저장(덮어쓰기) — 나중에 다시보기."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    html = body.get("html") or ""
    if not nb_id or not html:
        return JSONResponse(content={"error": "notebook_id·html 필요"}, status_code=400)
    p = _history_path(nb_id)
    snap = {
        "html": str(html)[:600000],
        "label": (body.get("label") or "")[:120],
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False)
    except Exception as e:
        return JSONResponse(content={"error": str(e)[:120]}, status_code=500)
    return JSONResponse(content={"ok": True})


@app.get("/api/insights/history")
def api_insights_history(notebook_id: str = ""):
    """노트북 캔버스 스냅샷."""
    try:
        with open(_history_path(notebook_id), encoding="utf-8") as f:
            snap = json.load(f)
    except Exception:
        snap = {}
    return JSONResponse(content=snap or {})


@app.get("/api/insights/notebook_sources")
def api_insights_notebook_sources(notebook_id: str = ""):
    """현재 노트북에 쌓인 소스 목록(좌하단 자료 목록)."""
    if not notebook_id or not _nlm_exe():
        return JSONResponse(content={"sources": [], "count": 0})
    ok, out, _ = _run_nlm(["notebook", "get", notebook_id])
    srcs = []
    if ok:
        try:
            srcs = [s.get("title", "") for s in json.loads(out).get("sources", [])]
        except Exception:
            pass
    return JSONResponse(content={"sources": srcs, "count": len(srcs)})


@app.post("/api/insights/notebook_merge")
async def api_insights_notebook_merge(req: Request):
    """이전 브리핑들의 자료(.md)를 현재 노트북에 소스로 추가 → 교차검색."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    ids = body.get("ids") or []
    if not nb_id or not ids:
        return JSONResponse(content={"error": "notebook_id·ids 필요"}, status_code=400)
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)
    byid = {e.get("id"): e for e in _load_nb_registry()}

    def _do():
        added, ctx_add = 0, []
        for sid in ids:
            e = byid.get(sid)
            if not e or sid == nb_id:
                continue
            for p in (e.get("paths") or []):
                if not os.path.exists(p):
                    continue
                ok, _o, _er = _run_nlm(["source", "add", nb_id, "--file", p,
                                        "--title", f"[가져옴] {e.get('label', '')} {e.get('date', '')}"])
                if ok:
                    added += 1
                    try:
                        with open(p, encoding="utf-8") as f:
                            ctx_add.append(f.read())
                    except Exception:
                        pass
        if ctx_add and nb_id in _NB_BUNDLES:
            _NB_BUNDLES[nb_id] = (_NB_BUNDLES[nb_id] + "\n\n" + "\n\n".join(ctx_add))[:90000]
        # 갱신된 소스 수
        total = 0
        ok2, out2, _ = _run_nlm(["notebook", "get", nb_id])
        if ok2:
            try:
                total = json.loads(out2).get("source_count", 0)
            except Exception:
                pass
        return {"ok": True, "added": added, "total_sources": total}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


def _gemini_vision_style(img_bytes, mime):
    """업로드 이미지의 '디자인 스타일'을 텍스트로 추출 (Gemini 비전, 키 폴백)."""
    from google import genai
    from google.genai import types
    keys = _gemini_interactive_keys()
    if not keys:
        raise RuntimeError(".env에 GEMINI_API_KEY 없음")
    prompt = (
        "이 이미지의 '디자인 스타일'만 분석해줘(담긴 내용·텍스트 의미는 무시). "
        "배경색, 메인/보조 색상(hex 추정), 레이아웃 구성, 타이포 느낌, 강조 방식, 전체 분위기를 "
        "인포그래픽/슬라이드 생성 지시문으로 바로 쓸 수 있게 한국어 2~4문장으로 요약해줘."
    )
    last = ""
    for k in keys:
        try:
            client = genai.Client(api_key=k)
            resp = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[types.Part.from_bytes(data=img_bytes, mime_type=mime), prompt],
            )
            return (resp.text or "").strip()
        except Exception as e:
            last = str(e)
            if "429" in last or "RESOURCE_EXHAUSTED" in last:
                continue
            raise
    raise RuntimeError(f"Gemini 쿼터 소진: {last[:150]}")


@app.post("/api/insights/upload_image")
async def api_insights_upload_image(req: Request):
    """이미지 첨부 — mode=source(노트북 소스로 추가) / design(스타일 추출→생성 반영)."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    mode = (body.get("mode") or "source").strip()
    filename = (body.get("filename") or "image.png").strip()
    data_b64 = body.get("data") or ""
    if not nb_id or not data_b64:
        return JSONResponse(content={"error": "notebook_id·data 필요"}, status_code=400)
    import base64
    try:
        if "," in data_b64:           # data:URL 헤더 제거
            data_b64 = data_b64.split(",", 1)[1]
        raw = base64.b64decode(data_b64)
    except Exception:
        return JSONResponse(content={"error": "이미지 디코드 실패"}, status_code=400)
    ext = (os.path.splitext(filename)[1] or ".png").lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
    up_dir = os.path.join(ROOT, "out", "insights_notebook", "uploads")
    os.makedirs(up_dir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(filename))[:50] or "image.png"
    fpath = os.path.join(up_dir, f"{re.sub(r'[^0-9a-fA-F-]', '', nb_id)[:12]}_{safe}")
    with open(fpath, "wb") as f:
        f.write(raw)

    def _do():
        if mode == "design":
            if not _nlm_exe():
                pass
            try:
                style = _gemini_vision_style(raw, mime)
            except Exception as e:
                return {"ok": True, "mode": "design", "style": "",
                        "warn": f"스타일 추출 보류({str(e)[:120]}). 비전 키가 풀리면 자동 적용됩니다."}
            if style:
                _NB_DESIGN[nb_id] = style[:1200]
            return {"ok": True, "mode": "design", "style": style}
        # mode == source
        if not _nlm_exe():
            return {"error": "nlm CLI 없음"}
        ok, _o, err = _run_nlm(["source", "add", nb_id, "--file", fpath,
                                "--title", f"[이미지] {safe}"])
        if not ok:
            return {"error": f"이미지 소스 추가 실패: {_friendly_nlm_err(err)}"}
        total = 0
        ok2, out2, _ = _run_nlm(["notebook", "get", nb_id])
        if ok2:
            try:
                total = json.loads(out2).get("source_count", 0)
            except Exception:
                pass
        return {"ok": True, "mode": "source", "total_sources": total}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


def _gemini_image_bytes(prompt, keys):
    """Gemini 이미지 생성(나노바나나Pro→3Pro→2.5, 키 폴백) → PNG bytes."""
    from google import genai
    from google.genai import types
    last, had_429 = "", False
    for model in ("nano-banana-pro-preview", "gemini-3-pro-image", "gemini-2.5-flash-image"):
        for k in keys:
            try:
                client = genai.Client(api_key=k)
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        return part.inline_data.data
                last = "응답에 이미지 없음"
            except Exception as e:
                last = str(e)
                if "429" in last or "RESOURCE_EXHAUSTED" in last:
                    had_429 = True
                continue
    if had_429:
        raise RuntimeError("Gemini 이미지 무료 쿼터 소진(하루 소량 제한). 내일 재시도하거나 유료 전환 필요.")
    raise RuntimeError(last[:200] or "이미지 생성 실패")


@app.post("/api/insights/gemini_infographic")
async def api_insights_gemini_infographic(req: Request):
    """Gemini 이미지(나노바나나2)로 인포그래픽 생성 — 프롬프트 자유 + 노트북 내용 반영."""
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    nb_id = (body.get("notebook_id") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    if not nb_id:
        return JSONResponse(content={"error": "notebook_id 필요"}, status_code=400)

    def _do():
        keys = _gemini_interactive_keys()
        if not keys:
            return {"error": ".env에 GEMINI_API_KEY 없음"}
        content = _NB_BUNDLES.get(nb_id, "")
        ref = _NB_DESIGN.get(nb_id, "")
        # 1) 내용 → 인포그래픽용 텍스트 브리프
        brief = ""
        if content:
            try:
                from google import genai
                client = genai.Client(api_key=keys[0])
                r = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=("다음 자료를 인포그래픽용으로 한국어로 요약해줘. "
                              "제목 1개 + 핵심 섹션 4~6개(각 핵심 수치·종목·키워드 1~2줄). 간결하게.\n\n"
                              + content[:15000]),
                )
                brief = (r.text or "").strip()
            except Exception:
                brief = content[:2500]
        # 2) 이미지 프롬프트 (내용 + 사용자 + 브랜드 + 레퍼런스)
        img_prompt = (
            "Create ONE detailed Korean stock-market INFOGRAPHIC image, 16:9 landscape. "
            "Render crisp KOREAN text labels, section titles and BIG numbers (한국어 텍스트 정확히). "
            f"\n\n[담을 내용/데이터]\n{brief or (prompt or '한국 증시 핵심 동향')}\n\n"
            f"[사용자 요청] {prompt or '핵심만 한 장으로, 주린이도 이해하게'}\n\n"
            f"[디자인] {_BRAND_DESIGN}"
            + (f"\n[레퍼런스 스타일] {ref}" if ref else "")
        )
        try:
            data = _gemini_image_bytes(img_prompt, keys)
        except Exception as e:
            return {"error": f"Gemini 이미지 실패: {str(e)[:200]}"}
        fname = f"gimg_{uuid.uuid4().hex[:10]}.png"
        fpath = os.path.join(ROOT, "out", "insights_notebook", fname)
        with open(fpath, "wb") as f:
            f.write(data)
        return {"ok": True, "media": "image", "file_url": f"/api/insights/artifact?f={fname}"}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/nlm_status")
def api_insights_nlm_status():
    """nlm 인증 유효성. `login --check`는 로그인 직후에도 오탐하는 버그가 있어(2026-07-03
    확인) 실제 API 호출로 판단한다."""
    if not _nlm_exe():
        return JSONResponse(content={"valid": False, "error": "nlm 없음"})
    ok, _out, _err = _run_nlm(["notebook", "list", "--quiet"], timeout=40, _auth_retry=False)
    return JSONResponse(content={"valid": bool(ok)})


@app.post("/api/insights/nlm_relogin")
async def api_insights_nlm_relogin(req: Request):
    """수동 재로그인 — nlm login(전용 크롬 프로필로 자동 완료)."""
    if not _nlm_exe():
        return JSONResponse(content={"error": "nlm CLI 없음"}, status_code=503)

    def _do():
        ok, _o, err = _run_nlm(["login"], timeout=320)
        if not ok:
            return {"error": f"재로그인 실패: {err[:150]}"}
        return {"ok": True}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.post("/api/insights/nlm_manual_login_start")
async def api_insights_nlm_manual_login_start():
    """수동 로그인(VNC) 시작 — 사용자가 직접 구글 로그인할 브라우저 화면 URL 반환.
    자동 재로그인이 안 될 때의 진짜 폴백(2026-07-03 추가)."""
    result = await run_in_threadpool(start_manual_login)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/nlm_manual_login_status")
async def api_insights_nlm_manual_login_status():
    """수동 로그인 진행 상태: idle | waiting | done | failed."""
    result = await run_in_threadpool(manual_login_status)
    return JSONResponse(content=result)


# ── §4.8 POST /api/insights/to_youtube ───────────────────────
@app.post("/api/insights/to_youtube")
async def api_insights_to_youtube(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    doc_key = (body.get("doc_key") or "").strip()
    if not doc_key:
        return JSONResponse(content={"error": "doc_key 필요"}, status_code=400)

    # 문서 제목을 topic으로 사용
    conn = _ins_conn()
    topic = doc_key
    if conn:
        try:
            parts = doc_key.split(":", 2)
            cat = parts[0] if parts else ""
            type_cond = _CAT_TYPE_MAP.get(cat, "source_type='youtube'")
            if cat == "telegram":
                source_name = parts[1] if len(parts) > 1 else ""
                date = parts[2] if len(parts) > 2 else ""
                r = conn.execute(
                    f"SELECT source_name, date FROM atoms WHERE {type_cond} AND source_name=? AND date=? LIMIT 1",
                    (source_name, date),
                ).fetchone()
                if r:
                    topic = f"{r['source_name']} {r['date']} 발언 요약"
            else:
                raw_basename = parts[1] if len(parts) > 1 else ""
                r = conn.execute(
                    f"SELECT raw_file, source_name, date FROM atoms WHERE {type_cond} AND (raw_file=? OR raw_file LIKE ?) LIMIT 1",
                    (raw_basename, f"%/{raw_basename}"),
                ).fetchone()
                if r:
                    topic = _build_doc_title(r["raw_file"], r["source_name"], r["date"], cat) or topic
            # AI 요약이 있으면 TLDR을 우선 주제로 (가장 핵심적)
            if _DS_AVAIL:
                try:
                    cached = _load_summary(doc_key)
                    if cached and cached.get("tldr"):
                        topic = cached["tldr"]
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            conn.close()

    def _run_yt_plan(topic: str) -> str:
        try:
            from pipeline.atoms.yt_plan import search_yt_atoms, build_speech_card_table, build_script_skeleton
            atoms = search_yt_atoms(topic, n=15)
            card_md = build_speech_card_table(atoms)
            skeleton_md = build_script_skeleton(topic, atoms)
            return f"## 발언카드\n\n{card_md}\n\n{skeleton_md}"
        except Exception:
            # subprocess 폴백
            proc = subprocess.run(
                [sys.executable, "-m", "pipeline.atoms.yt_plan", topic],
                cwd=ROOT, capture_output=True, encoding="utf-8",
                errors="replace", timeout=60,
            )
            return (proc.stdout or "").strip() or "yt_plan 실행 실패"

    markdown = await run_in_threadpool(_run_yt_plan, topic)
    return JSONResponse(content={"ok": True, "markdown": markdown, "topic": topic})


# ── §4.9 POST /api/insights/to_wiki ──────────────────────────
@app.post("/api/insights/to_wiki")
async def api_insights_to_wiki(req: Request):
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    doc_key = (body.get("doc_key") or "").strip()
    if not doc_key:
        return JSONResponse(content={"error": "doc_key 필요"}, status_code=400)

    # 요약 가져오기 (캐시 우선)
    summary_row = _get_summary_row(doc_key)
    if summary_row:
        tldr = summary_row.get("tldr") or ""
        summary3 = summary_row.get("summary3") or []
        market_view = summary_row.get("market_view") or ""
        market_reason = summary_row.get("market_reason") or ""
        stocks = summary_row.get("stocks_json") or []
        highlights = summary_row.get("highlights_json") or []
        source_name = summary_row.get("source_name") or ""
        doc_title = summary_row.get("doc_title") or doc_key
        doc_date = summary_row.get("doc_date") or ""
    else:
        tldr = "요약 없음 (summarize 먼저 실행)"
        summary3 = []
        market_view = ""
        market_reason = ""
        stocks = []
        highlights = []
        source_name = ""
        doc_title = doc_key
        doc_date = ""

    # 마크다운 생성
    summary3_md = "\n".join(f"- {s}" for s in summary3)
    stocks_md = "\n".join(f"- [{s.get('stance','')}] {s.get('name','')}: {s.get('reason','')}" for s in stocks)
    highlights_md = "\n".join(f"- **{h.get('topic','')}**: {h.get('detail','')}" for h in highlights)

    md_content = f"""# {doc_title}

> 출처: {source_name} | 날짜: {doc_date} | doc_key: {doc_key}

## 핵심 한 줄
**{tldr}**

## 핵심 요약
{summary3_md}

## 놓치면 안 되는 포인트
{highlights_md or "_(없음)_"}

## 시장관: {market_view}
{market_reason}

## 언급 종목
{stocks_md or "_(없음)_"}

---
_생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 인사이트 허브 자동 저장_
_위키 정식 ingest는 후속 연결 예정_
"""

    # 저장 경로
    safe_key = re.sub(r'[\\/:*?"<>|]', '_', doc_key)
    if safe_key.lower().endswith(".md"):
        safe_key = safe_key[:-3]
    out_dir = os.path.join(ROOT, "out", "insights_wiki")
    os.makedirs(out_dir, exist_ok=True)
    save_path = os.path.join(out_dir, f"{safe_key}.md")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    rel_path = os.path.relpath(save_path, ROOT)
    return JSONResponse(content={
        "ok": True,
        "path": rel_path.replace("\\", "/"),
        "note": "위키 정식 ingest는 후속 연결",
    })


# ── §5 유튜브 영상제작 대시보드 (/yt) ──────────────────────────
@app.get("/yt", response_class=HTMLResponse)
def yt_page():
    p = os.path.join(HERE, "yt.html")
    if not os.path.exists(p):
        return "<h1>yt.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    # 브라우저 캐시로 옛 버전 남는 것 방지 (계속 수정할 페이지라 매번 최신 서빙)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/yt/refs", response_class=HTMLResponse)
def yt_refs_page():
    p = os.path.join(HERE, "yt_refs.html")
    if not os.path.exists(p):
        return "<h1>yt_refs.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.post("/yt/hot_clips")
async def api_yt_hot_clips(req: Request):
    body = await req.json()
    q = (body.get("q") or "").strip()
    if not q:
        return JSONResponse(content={"error": "검색어 필요"}, status_code=400)
    if find_hot_clips is None:
        return JSONResponse(content={"error": "hot_clips 모듈을 불러올 수 없음"}, status_code=503)

    def _do():
        return find_hot_clips(q)

    try:
        results = await run_in_threadpool(_do)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 502
        if status == 429:
            msg = "유튜브 API 일일 할당량 초과 — 태평양시간 기준 자정에 초기화됩니다. 잠시 후 다시 시도해주세요."
        else:
            msg = f"유튜브 API 오류 (HTTP {status})"
        return JSONResponse(content={"error": msg}, status_code=502)
    except requests.exceptions.RequestException as e:
        return JSONResponse(content={"error": f"유튜브 API 연결 실패: {e}"}, status_code=502)
    return JSONResponse(content={"results": results})


@app.post("/yt/generate_plan")
async def api_yt_generate_plan(req: Request):
    body = await req.json()
    idea = (body.get("idea") or "").strip()
    references = body.get("references") or []
    if not idea:
        return JSONResponse(content={"error": "아이디어 필요"}, status_code=400)
    if run_plan_stage is None:
        return JSONResponse(content={"error": "plan_stage 모듈을 불러올 수 없음"}, status_code=503)

    def _stream():
        try:
            for event in run_plan_stage(idea, references=references, pipeline_id=None):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── §5-B 레퍼런스 창고: 카테고리→검색→해체→믹스 ───────────────
_YT_CATS_PATH = os.path.join(ROOT, "scripts", "yt_agents", "yt_categories.json")


@app.get("/yt/categories")
def api_yt_categories():
    try:
        with open(_YT_CATS_PATH, encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/yt/category_search")
async def api_yt_category_search(req: Request):
    """카테고리 id → 그 카테고리 검색어들로 검색 + 검증순위(금맥/채널빨 판정)."""
    if _hotclips is None:
        return JSONResponse(content={"error": "hot_clips 모듈 없음"}, status_code=503)
    body = await req.json()
    cat_id = (body.get("category_id") or "").strip()
    with open(_YT_CATS_PATH, encoding="utf-8") as f:
        cats = json.load(f)["categories"]
    cat = next((c for c in cats if c["id"] == cat_id), None)
    if not cat:
        return JSONResponse(content={"error": "알 수 없는 카테고리"}, status_code=400)
    queries = cat["queries"][: int(body.get("max_queries", 2))]

    def _do():
        return _hotclips.find_and_rank(queries)

    rows = await run_in_threadpool(_do)
    return JSONResponse(content={"category": cat["name"], "results": rows})


@app.post("/yt/teardown")
async def api_yt_teardown(req: Request):
    """영상 1개 완전 해체(제미니 시청) — SSE. ~1~2분 소요."""
    if _teardown is None:
        return JSONResponse(content={"error": "clip_teardown 모듈 없음"}, status_code=503)
    body = await req.json()
    vid = (body.get("video_id") or "").strip()
    if not vid:
        return JSONResponse(content={"error": "video_id 필요"}, status_code=400)
    title, channel, stats = body.get("title", ""), body.get("channel", ""), body.get("stats") or {}

    def _stream():
        yield f"data: {json.dumps({'type':'running','video_id':vid}, ensure_ascii=False)}\n\n"
        try:
            card = _teardown.teardown(vid, title, channel, stats)
            yield f"data: {json.dumps({'type':'done','card':card}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.post("/yt/mix")
async def api_yt_mix(req: Request):
    """해체카드 여러 개 → 우리 채널 대본 초안 믹스(제미니) — SSE."""
    if _teardown is None:
        return JSONResponse(content={"error": "clip_teardown 모듈 없음"}, status_code=503)
    body = await req.json()
    cards = body.get("cards") or []
    category = body.get("category", "")
    if not cards:
        return JSONResponse(content={"error": "해체카드 필요"}, status_code=400)

    def _stream():
        yield f"data: {json.dumps({'type':'running'}, ensure_ascii=False)}\n\n"
        try:
            draft = _teardown.mix(cards, category)
            yield f"data: {json.dumps({'type':'done','draft':draft}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── §5-C 인용 스튜디오: URL→골든발언 후보(SSE)→픽→저장 ───────────
@app.get("/yt/quote-studio", response_class=HTMLResponse)
def yt_quote_studio_page():
    p = os.path.join(HERE, "quote_studio.html")
    if not os.path.exists(p):
        return "<h1>quote_studio.html 준비중</h1>"
    with open(p, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, must-revalidate"})


@app.post("/yt/quote_extract")
async def api_yt_quote_extract(req: Request):
    """URL → 골든 발언 후보 추출(엔진 extract_stream) — SSE. 4.5h 영상은 수분 소요."""
    body = await req.json()
    url = (body.get("url") or "").strip()
    topic = (body.get("topic") or "").strip()
    if not url:
        return JSONResponse(content={"error": "url 필요"}, status_code=400)
    if _qe is None:
        return JSONResponse(content={"error": "quote_extractor 모듈 없음"}, status_code=503)
    ms = body.get("max_segments")
    max_segments = int(ms) if ms else None

    def _stream():
        yield f"data: {json.dumps({'type':'running'}, ensure_ascii=False)}\n\n"
        try:
            for ev in _qe.extract_stream(url, topic, max_segments=max_segments):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.post("/yt/quote_save")
async def api_yt_quote_save(req: Request):
    """픽한 인용들을 quotes.json으로 저장 → out/quote_studio/<vid>.json."""
    if _qe is None:
        return JSONResponse(content={"error": "quote_extractor 모듈 없음"}, status_code=503)
    body = await req.json()
    url = (body.get("url") or "").strip()
    quotes = body.get("quotes") or []
    vid = _qe.parse_video_id(url) or "unknown"
    out_dir = os.path.join(ROOT, "out", "quote_studio")
    os.makedirs(out_dir, exist_ok=True)
    save_path = os.path.join(out_dir, f"{vid}.json")
    doc = {"topic": body.get("topic", ""), "source": url, "quotes": quotes}
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return JSONResponse(content={"ok": True,
                                 "path": os.path.relpath(save_path, ROOT).replace("\\", "/"),
                                 "count": len(quotes)})


# ══════════════════════════════════════════════════════════════

def _nlm_keepalive(interval=900):
    """서버 구동 중 nlm 세션 선제 유지 — 15분마다 실제 API 호출로 점검, 만료 시 재로그인 시도.
    `login --check`는 로그인 직후에도 오탐하는 버그가 있어(2026-07-03 확인) 쓰지 않는다.
    (작업 실패 시엔 _run_nlm이 그 자리에서 self-heal하므로 이건 선제 유지용.)
    ⚠️ 진짜 만료(구글이 재인증 요구) 시엔 bare `nlm login`이 사람 개입 없이는 못 뚫는다 —
    이땐 인사이트 대시보드의 "🔐 노트북 수동 로그인" 버튼으로 직접 로그인해야 한다."""
    while True:
        try:
            if _nlm_exe():
                ok, _out, _ = _run_nlm(["notebook", "list", "--quiet"], timeout=60, _auth_retry=False)
                if not ok:
                    print("[nlm-keepalive] 인증 만료 감지 → 자동 재로그인 시도")
                    ok2 = _nlm_relogin_locked()
                    print("[nlm-keepalive] 재로그인", "성공" if ok2 else "실패(수동 로그인 버튼 필요)")
        except Exception as e:
            print(f"[nlm-keepalive] 예외: {str(e)[:120]}")
        time.sleep(interval)


def _ingest_worker(interval=1800, limit=40, warmup=180):
    """atoms.db 자동 채우기 — 미처리 파일을 주기적으로 원자추출(백로그 소화 + 최신 유지).
    단일 워커라 중복 없음. Gemini(gemini-3.1-flash-lite) 사용.
    ⚠️ Gemini 무료 쿼터 공유 — 대화형 리서치를 막지 않게 30분/40개로 스로틀."""
    time.sleep(warmup)  # 부팅 직후·수동 실행과 겹치지 않게 잠깐 대기
    while True:
        try:
            p = subprocess.run(
                [sys.executable, "-m", "pipeline.atoms.ingest_pending", "--limit", str(limit)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=900,
            )
            tail = (p.stdout or "").strip().splitlines()[-1:] or [""]
            print(f"[ingest-worker] {tail[0][:100]}")
        except Exception as e:
            print(f"[ingest-worker] 예외: {str(e)[:120]}")
        time.sleep(interval)


def _morning_brief_loop():
    """골-루프: 평일 08:00~08:14 창에 아침 브리핑 1회 자율 실행(품질루프+게이트+에스컬레이션)."""
    from datetime import datetime as _dt
    last = None
    time.sleep(60)   # 기동 직후 안정화
    while True:
        try:
            from scripts.goal_loop import morning_brief as _mb
            now = _dt.now()
            if _mb.should_run_now(now, last):
                r = _mb.run_morning_brief(now.strftime("%Y-%m-%d"))
                last = now.strftime("%Y-%m-%d")
                print(f"[morning-brief] {r.get('status')} — {r.get('reasons')}")
        except Exception as e:
            print(f"[morning-brief] 예외: {str(e)[:120]}")
        time.sleep(180)   # 3분 간격 점검


def _start_keepalive():
    threading.Thread(target=_nlm_keepalive, daemon=True).start()
    print("[nlm-keepalive] 자동 세션 유지 시작 (25분 주기)")
    threading.Thread(target=_ingest_worker, daemon=True).start()
    print("[ingest-worker] 자동 원자추출 시작 (10분마다 60개)")
    # 자율 공개발행이라 기본 OFF — GOAL_LOOP_ENABLED=1일 때만 가동(사장님 명시적 활성화)
    if os.environ.get("GOAL_LOOP_ENABLED") == "1":
        threading.Thread(target=_morning_brief_loop, daemon=True).start()
        print("[morning-brief] 아침 브리핑 데몬 시작 (평일 08:00)")
    else:
        print("[morning-brief] 데몬 비활성 — 활성화하려면 GOAL_LOOP_ENABLED=1")


if __name__ == "__main__":
    print("딸깍 대시보드 → http://localhost:8090")
    _start_keepalive()
    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
