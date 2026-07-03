"""
딸깍 대시보드 — 로컬 내부 도구
버튼 하나로 이미 생성된 자동화 산출물을 한 화면에 모아 보여준다.

실행:  python dashboard/server.py
접속:  http://localhost:8090
"""
import os, sys, json, glob, re, shutil, subprocess, uuid, time, threading
from collections import deque
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가 (python dashboard/server.py 로 실행 시 pipeline import 가능하게)
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

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
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, RedirectResponse
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
    """대화형(리서치·이미지·비전) Gemini 키 — 인제스트 전용키(GEMINI_INGEST_KEY*)와 분리.
    _1·_2(기존)+_3·_4(추가계정) 순으로 failover."""
    return [k for k in (_env_key("GEMINI_API_KEY"), _env_key("GEMINI_API_KEY_2"),
                        _env_key("GEMINI_API_KEY_3"), _env_key("GEMINI_API_KEY_4")) if k]


def _summary_keys():
    """뉴스요약용 키 풀 — 대화형 키 + 인제스트 키(GEMINI_INGEST_KEY*)까지 총동원해 429 쿼터 여유 확보.
    프리워밍이 여러 섹터를 도는 만큼 키가 많아야 무료 쿼터가 안 터진다."""
    ks = _gemini_interactive_keys() + [
        _env_key("GEMINI_INGEST_KEY"), _env_key("GEMINI_INGEST_KEY_2"),
        _env_key("GEMINI_INGEST_KEY_3"), _env_key("GEMINI_INGEST_KEY_4")]
    seen, out = set(), []
    for k in ks:
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out


def _briefing_keys():
    """실시간 시장 브리핑 종합 전용 키 풀 — 섹터뉴스 요약 등 다른 작업과 쿼터를
    분리해서 한쪽이 소진돼도 브리핑은 계속 돌게 한다. GEMINI_BRIEFING_KEY(전용)가
    있으면 그것만 쓰고, 없으면 기존 _summary_keys()로 자동 폴백(로컬 개발환경 등
    전용키 미설정 시에도 브리핑 기능 자체는 계속 동작하도록)."""
    dedicated = [k for k in (_env_key("GEMINI_BRIEFING_KEY"), _env_key("GEMINI_BRIEFING_KEY_2")) if k]
    return dedicated or _summary_keys()


# 텍스트 생성 모델 폴백: 프리뷰(최고품질) → 안정모델. 프리뷰가 503 과부하일 때 안정모델로 자동 전환.
GEMINI_TEXT_MODELS = ["gemini-3-flash-preview", "gemini-2.5-flash"]


def _gemini_text(prompt, keys=None, models=None):
    """텍스트 생성 공용 호출 — 모델 폴백 + 키 로테이션 + 503 백오프.
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
            client = genai.Client(api_key=k)   # 변수 유지 — GC가 호출 중 닫지 않게
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                txt = (resp.text or "").strip()
                if txt:
                    return {"ok": True, "analysis": txt, "model": model}
                last = "빈 응답"
                continue   # 다음 키
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
    _BRAND_DESIGN,
)
try:
    from studio_pipeline import generate_briefing, generate_picks  # noqa: E402
except (ImportError, SystemExit):
    generate_briefing = None  # type: ignore
    generate_picks = None     # type: ignore

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
    from sector_heatmap import build_heatmap, parse_etf_bar, build_heatmap_tab, TAB_GROUPS  # noqa: E402
except (ImportError, Exception):
    build_heatmap = None        # type: ignore
    parse_etf_bar = None        # type: ignore
    build_heatmap_tab = None    # type: ignore
    TAB_GROUPS = []             # type: ignore

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


# ── 로그인 게이트 (지인 배포용) — 자격증명은 환경변수로만, repo에 안 올림 ──
import hmac as _hmac, hashlib as _hashlib
DASH_USER   = os.environ.get("DASH_USER", "admin")
DASH_PASS   = os.environ.get("DASH_PASS", "")        # 비어있으면 인증 OFF(로컬 개발)
DASH_SECRET = os.environ.get("DASH_SECRET", "stockbrain-local-secret")
_AUTH_ON = bool(DASH_PASS)
_AUTH_ALLOW = ("/login", "/api/login", "/favicon.ico", "/healthz", "/api/push_market_flow")

def _auth_token() -> str:
    return _hmac.new(DASH_SECRET.encode(), f"{DASH_USER}:{DASH_PASS}".encode(), _hashlib.sha256).hexdigest()

_LOGIN_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>STOCK BRAIN 로그인</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0b0e;font-family:system-ui,'Noto Sans KR',sans-serif}
.box{background:#16161c;border:1px solid #2a2a30;border-radius:14px;padding:32px 28px;width:280px}
h1{color:#d4af37;font-size:18px;margin:0 0 18px;text-align:center;letter-spacing:1px}
input{width:100%;box-sizing:border-box;margin:6px 0;padding:11px 12px;background:#0e0e12;
border:1px solid #333;border-radius:8px;color:#eee;font-size:14px}
button{width:100%;margin-top:12px;padding:11px;background:#d4af37;color:#111;border:0;
border-radius:8px;font-weight:700;font-size:14px;cursor:pointer}
.err{color:#e74c3c;font-size:12px;text-align:center;margin-top:10px;min-height:14px}</style></head>
<body><form class=box method=post action=/api/login>
<h1>⚡ STOCK BRAIN</h1>
<input name=user placeholder=아이디 autocomplete=username autofocus>
<input name=pass type=password placeholder=비밀번호 autocomplete=current-password>
<button>로그인</button>
<div class=err>__ERR__</div></form></body></html>"""

@app.get("/login", response_class=HTMLResponse)
def _login_page(e: str = ""):
    return _LOGIN_HTML.replace("__ERR__", "아이디 또는 비밀번호가 틀렸습니다" if e else "")

@app.post("/api/login")
async def _api_login(req: Request):
    import urllib.parse as _up
    body = (await req.body()).decode("utf-8", "ignore")
    form = _up.parse_qs(body)
    u = (form.get("user") or [""])[0]
    p = (form.get("pass") or [""])[0]
    if u == DASH_USER and p == DASH_PASS and _AUTH_ON:
        r = RedirectResponse("/market", status_code=303)
        r.set_cookie("dash_auth", _auth_token(), max_age=60*60*24*30, httponly=True, samesite="lax")
        return r
    return RedirectResponse("/login?e=1", status_code=303)

@app.get("/healthz")
def _healthz():
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
    if request.cookies.get("dash_auth") == _auth_token():
        response = await call_next(request)
        _no_store(request, response)
        return response
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse("/login")


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
        print("[boot][WARN] kiwoom_api 인증 실패 — 서버에 키움 API 키 미등록 상태로 보임.", flush=True)
        print(f"  사유: {e}", flush=True)
        print("  아래 기능은 kiwoom_api를 직접 호출하면 항상 빈값/0을 반환한다 (2026-07-02 확인됨):", flush=True)
        print("    - 관심종목 개별 잠정수급 (get_stock_supply, /api/watchlist·/api/stock_supply_batch)", flush=True)
        print("  → 위 endpoint를 만지거나 새 기능을 kiwoom_api로 연결할 때는 반드시 서버에서", flush=True)
        print("    실데이터 응답을 확인할 것. 이미 KIS로 이관된 것: 지수분봉/투자자매매동향/", flush=True)
        print("    프로그램매매/거래대금순위(kis_api.get_index_minutebar/get_market_investor/", flush=True)
        print("    get_program_trade/get_inquiry_rank). 종목분봉(get_stock_candles)은 이미 KIS 폴백 있음.", flush=True)
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
SSH_HOST = "ubuntu@3.39.179.148"
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


_last_good_etf: dict = {"data": None}   # ETF바 마지막 정상 응답(KIS 순간실패 시 유지)

@app.get("/api/etf_bar")
def api_etf_bar():
    if parse_etf_bar is None:
        return JSONResponse(content={"error": "parse_etf_bar 없음"}, status_code=503)
    try:
        # 프리워밍 캐시 hit → 즉시 반환
        cached = _prewarm_cache.get("etf_bar")
        if cached and time.time() - cached["ts"] < _PREWARM_TTL:
            return JSONResponse(content=cached["data"])

        import kis_api
        from concurrent.futures import ThreadPoolExecutor, as_completed
        etfs  = parse_etf_bar()
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
            return JSONResponse(content=etfs)
        if _last_good_etf["data"]:
            return JSONResponse(content=_last_good_etf["data"])
        return JSONResponse(content=etfs)
    except Exception as e:
        if _last_good_etf["data"]:
            return JSONResponse(content=_last_good_etf["data"])
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
        kw = nf.load_keywords()
        sv = _compute_sector_vacuum(top_sectors)
        out_sectors = []
        for s in sv.get("sectors", []):
            stocks = []
            for st in (s.get("stocks") or [])[:per_stock]:
                stocks.append({"code": st.get("code"), "name": st.get("name"),
                               "pct": st.get("pct"), "group": st.get("group"),
                               "news": nf.stock_news(st.get("code"), name=st.get("name"), top=2)})
            out_sectors.append({"etf": s.get("etf"), "code": s.get("code"),
                                "rate": s.get("rate"),
                                "news": nf.sector_news(s.get("code"), kw, top=3),
                                "stocks": stocks})
        data = {"sectors": out_sectors, "ts": time.time()}
        _NEWS_FEED["data"] = data
        _NEWS_FEED["ts"] = time.time()
        try:
            with open(NEWS_FEED_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
    except Exception:
        pass

def _news_loop():
    while True:
        _refresh_news()
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
        return {"code": cc, "name": resolved_name,
                "pct": o.get("pct"), "group": o.get("group"),
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
        f"너는 주식 유튜브 채널의 시장 인사이트 애널리스트다. 아래는 '{sector}' 섹터의 **오늘({today_md}) 뉴스 헤드라인만** 모은 것이다.\n"
        f"시청자가 흥미롭게 읽고 '여러 정보를 한 번에 얻었다'고 느끼도록 정리하라.\n"
        f"오직 아래 오늘자 헤드라인 사실만 반영하라(과거 호재로 낙관 금지).\n\n"
        f"[오늘 뉴스 헤드라인]\n" + "\n".join(uniq[:16]) + "\n\n"
        "[출력 형식 · 마크다운, 짧게]\n"
        "**🔑 한 줄**: 이 섹터가 지금 왜 주목받는지 한 문장 (구체적·흥미롭게)\n"
        "**📌 핵심 이슈**\n"
        "- 이슈 2~3개, 각 한 줄. 종목명·수치·계약/실적 등 구체 팩트 포함\n"
        "**👀 관전 포인트**: 투자자가 뭘 봐야 하는지 한 줄\n\n"
        "규칙: 헤드라인에 있는 사실만 사용. 양면론·'관망하라' 금지. 과장·추천 금지. 존댓말로 간결하게."
    )
    # 쿼터 여유: 키 6개 총동원 + 무료쿼터 넉넉한 gemini-2.5-flash 우선(프리뷰는 폴백)
    res = _gemini_text(prompt, keys=_summary_keys(),
                       models=["gemini-2.5-flash", "gemini-3-flash-preview"])
    out = {"summary": res.get("analysis", ""), "model": res.get("model", ""),
           "error": res.get("error", ""), "sources": len(uniq)}
    if out["summary"]:
        _sector_summary_cache[key] = {"data": out, "ts": now, "hkey": hkey}
    return out


_stock_summary_cache: dict = {}

# 종목 뉴스 관련성 필터용 언론 관용 약칭(정식명만으로는 "삼전"·"하닉" 등 기사가 다 걸러짐)
_STOCK_ABBREV = {
    "삼성전자": ["삼전"],
    "SK하이닉스": ["하이닉스", "하닉", "SK닉스"],
    "LG에너지솔루션": ["LG엔솔", "엔솔"],
    "삼성바이오로직스": ["삼바"],
    "현대차": ["현차"],
    "기아": ["기아차"],
    "POSCO홀딩스": ["포스코"],
    "한화에어로스페이스": ["한화에어로"],
    "두산에너빌리티": ["두산에너"],
    "SK이노베이션": ["SK이노"],
    "HD현대중공업": ["현대중공업"],
    "HD한국조선해양": ["한국조선해양"],
    "NAVER": ["네이버"],
}


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
        f"너는 주식 유튜브 채널의 애널리스트다. 아래는 '{nm}' 종목의 최근 뉴스 헤드라인이다.\n"
        f"시청자가 이 종목의 현재 상황을 빠르게 파악하도록 정리하라. 아래 헤드라인 사실만 사용.\n\n"
        f"[최근 뉴스 헤드라인]\n" + "\n".join(headlines[:12]) + "\n\n"
        "[출력 형식 · 마크다운, 짧게]\n"
        "**🔑 한 줄**: 이 종목이 지금 왜 주목받는지 한 문장 (구체적)\n"
        "**📌 핵심 이슈**\n- 이슈 2~3개, 각 한 줄. 수치·계약·실적 등 구체 팩트 포함\n"
        "**👀 관전 포인트**: 투자자가 뭘 봐야 하는지 한 줄\n\n"
        "규칙: 헤드라인 사실만 사용. 양면론·'관망하라' 금지. 과장·추천 금지. 존댓말로 간결하게."
    )
    res = _gemini_text(prompt, keys=_summary_keys(),
                       models=["gemini-2.5-flash", "gemini-3-flash-preview"])
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
                    "bars": ksfn.get("bars") or [], "last_ts": ksfn_last_ts}
    result["global"] = {
        "label": "글로벌 지표",
        "items": [
            {"name": "나스닥선물(NQ)",  "price": nq["price"],   "change_rate": nq["change_rate"],   "bars": nq.get("bars") or []},
            {"name": "코스피선물",      "price": ksf["price"],  "change_rate": ksf["change_rate"],  "bars": ksf.get("bars") or [],
             "closed": ksf_closed, "night": False, "cdate": _today_md},
            {"name": "코스피야간선물",  "price": ksfn["price"], "change_rate": ksfn["change_rate"], "bars": ksfn.get("bars") or [],
             "closed": ksfn_closed, "night": True, "cdate": ksfn_md, "last_ts": ksfn_last_ts},
            {"name": "원달러환율",      "price": fx["price"],   "change_rate": fx["change_rate"],   "bars": fx.get("bars") or []},
            {"name": "국제유가(WTI)",   "price": oil["price"],  "change_rate": oil["change_rate"],  "bars": oil.get("bars") or []},
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
        with ThreadPoolExecutor(max_workers=14) as ex:
            tasks = {
                "J_bars":     ex.submit(kis_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kis_api.get_index_minutebar, "1001", 15),
                "J_price":    ex.submit(kis_api.get_index_price, "0001"),
                "Q_price":    ex.submit(kis_api.get_index_price, "1001"),
                "J_investor": ex.submit(kis_api.get_market_investor, "J"),
                "Q_investor": ex.submit(kis_api.get_market_investor, "Q"),
                "J_prog":         ex.submit(kis_api.get_program_trade, "J"),
                "Q_prog":         ex.submit(kis_api.get_program_trade, "Q"),
                "J_prog_series":  ex.submit(kis_api.get_program_trade_series, "J"),
                "Q_prog_series":  ex.submit(kis_api.get_program_trade_series, "Q"),
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
def api_heatmap():
    if build_heatmap is None:
        return JSONResponse(content={"error": "sector_heatmap 로드 실패"}, status_code=503)
    # 캐시 hit → 즉시 반환
    entry = _heatmap_cache.get("all")
    if entry and time.time() - entry["ts"] < _HEATMAP_TTL:
        return JSONResponse(content=entry["data"])
    # 캐시 miss → 백그라운드 빌드 시작 후 "준비 중" 즉시 응답
    _heatmap_build_bg("all", build_heatmap)
    return JSONResponse(content={"loading": True, "retry_after": 5, "sectors": [],
                                 "updated_at": "데이터 준비 중…"})


@app.get("/api/heatmap/refresh")
def api_heatmap_refresh():
    """캐시 무효화 후 강제 재조회."""
    _heatmap_cache.pop("all", None)
    return api_heatmap()


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
        try:
            import kis_api
            prices = kis_api.get_prices_multi([c["code"] for c in codes])
            for c in codes:
                p = prices.get(c["code"]) or {}
                items.append({"code": c["code"],
                              "name": c.get("name") or p.get("name") or c["code"],
                              "price": p.get("price", 0),
                              "change_rate": p.get("change_rate", 0)})
        except Exception:
            items = [{"code": c["code"], "name": c.get("name", ""),
                      "price": 0, "change_rate": 0} for c in codes]

    # 종목별 잠정수급 첨부 (키움 ka10059+ka90013, 종목당 2콜 → 종목 단위 병렬)
    if flow and items:
        try:
            import kiwoom_api
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(10, len(items))) as ex:
                futs = {it["code"]: ex.submit(kiwoom_api.get_stock_supply, it["code"])
                        for it in items}
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
    """관심종목 저장. body: {codes:[{code,name},...]}"""
    data = await req.json()
    codes = data.get("codes", [])
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
            return JSONResponse(content={"found": False, "date": data.get("date")})
        return JSONResponse(content={"found": True, "date": data.get("date"), "stock": stock})
    except Exception as e:
        return JSONResponse(content={"found": False, "error": str(e)})


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
            import kiwoom_api
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {c: ex.submit(kiwoom_api.get_stock_supply, c) for c in need}
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
        with ThreadPoolExecutor(max_workers=14) as ex:
            tasks = {
                "J_bars":     ex.submit(kis_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kis_api.get_index_minutebar, "1001", 15),
                "J_price":    ex.submit(kis_api.get_index_price, "0001"),
                "Q_price":    ex.submit(kis_api.get_index_price, "1001"),
                "J_investor":     ex.submit(kis_api.get_market_investor, "J"),
                "Q_investor":     ex.submit(kis_api.get_market_investor, "Q"),
                "J_prog":         ex.submit(kis_api.get_program_trade, "J"),
                "Q_prog":         ex.submit(kis_api.get_program_trade, "Q"),
                "J_prog_series":  ex.submit(kis_api.get_program_trade_series, "J"),
                "Q_prog_series":  ex.submit(kis_api.get_program_trade_series, "Q"),
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
            return etfs
        except Exception:
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
                           if it.get("kind") == "ai_brief"][:2]
        prompt = _briefing_build_prompt(alerts, headlines, atoms_content, prior_headlines)
        if not prompt:
            return
        res = _gemini_text(prompt, keys=_briefing_keys(), models=GEMINI_TEXT_MODELS)
        if not res.get("ok"):
            return
        parsed = _briefing_parse(res.get("analysis", ""))
        if not parsed:
            return
        severity = "red" if alerts else "yellow"
        _briefing_append(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"), "severity": severity,
            "headline": parsed["headline"], "body": parsed["body"], "kind": "ai_brief"})
    except Exception:
        pass


def _poll_briefing():
    """30초 주기 — market_flow 임계치 감지 + 12분 고정주기 종합. 감지 즉시 종합도 트리거."""
    _last_fixed_synth = 0.0
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

                if time.time() - _insight_last_run["ts"] >= 900:
                    _insight_last_run["ts"] = time.time()
                    _insight_run_synthesis(curr)
        except Exception:
            pass
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
        topick = _recent_topick_mentions(atoms_db_path, limit=2)
        _briefing_set_insight(BRIEFING_PATH, {
            "ts": datetime.now().strftime("%H:%M"),
            "comment": parsed["comment"], "topick": topick})
    except Exception:
        pass


@app.get("/api/market_briefing")
def api_market_briefing():
    return JSONResponse(content=_briefing_load(BRIEFING_PATH))


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
    """nlm 인증 유효성 (브라우저 없이 --check)."""
    if not _nlm_exe():
        return JSONResponse(content={"valid": False, "error": "nlm 없음"})
    ok, out, _ = _run_nlm(["login", "--check"], timeout=40)
    return JSONResponse(content={"valid": bool(ok and "valid" in (out or "").lower())})


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


# ══════════════════════════════════════════════════════════════

def _nlm_keepalive(interval=900):
    """서버 구동 중 nlm 세션 선제 유지 — 15분마다 --check, 만료 시 재로그인.
    (작업 실패 시엔 _run_nlm이 그 자리에서 self-heal하므로 이건 선제 유지용.)"""
    while True:
        try:
            if _nlm_exe():
                ok, out, _ = _run_nlm(["login", "--check"], timeout=60, _auth_retry=False)
                if not ok or "valid" not in (out or "").lower():
                    print("[nlm-keepalive] 인증 만료 감지 → 자동 재로그인 시도")
                    ok2 = _nlm_relogin_locked()
                    print("[nlm-keepalive] 재로그인", "성공" if ok2 else "실패")
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
