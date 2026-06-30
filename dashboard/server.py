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
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
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


def _nb_registry_add(entry):
    reg = [e for e in _load_nb_registry() if e.get("id") != entry.get("id")]
    reg.insert(0, entry)
    reg = reg[:100]
    try:
        os.makedirs(os.path.dirname(_REGISTRY_PATH), exist_ok=True)
        with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=1)
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

# ── 투자자/프로그램 시계열 누적 (장 중 15분 폴링) ──────────────────
_FLOW: dict = {
    "J": {"investor": deque(maxlen=30), "program": deque(maxlen=30)},
    "Q": {"investor": deque(maxlen=30), "program": deque(maxlen=30)},
}

def _poll_flow():
    """장 중(09:00~16:00) 5분마다 투자자·프로그램 순매수 스냅샷 수집.
    서버 시작 즉시 첫 수집 (initial=True), 이후 5분 간격.
    """
    initial = True
    while True:
        try:
            now = datetime.now()
            _mins = now.hour * 60 + now.minute
            # 09:00~15:35만 수집 → 이후엔 동결(15:30 종가 모양 유지). 저녁엔 마지막값 그대로 표시.
            if initial or (540 <= _mins <= 935):
                import kiwoom_api as _kiwoom
                for mkt in ("J", "Q"):
                    try:
                        _FLOW[mkt]["investor"].append(_kiwoom.get_market_investor(mkt))
                    except Exception:
                        pass
                    try:
                        _FLOW[mkt]["program"].append(_kiwoom.get_program_trade(mkt))
                    except Exception:
                        pass
                initial = False
        except Exception:
            pass
        time.sleep(120)  # 2분 (누적추이 그래프가 더 빨리 채워지도록)

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


def server_register(cat, name, url):
    """서버 config.yaml에 소스 자동 등록 (add_source.py 호출). best-effort."""
    payload = json.dumps({"category": cat, "name": name, "url": url})
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=20", SSH_HOST, REMOTE_ADD]
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
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=20", SSH_HOST,
           "python3 /home/ubuntu/kmong/crawling_bot/del_source.py"]
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
    return JSONResponse(content={"ok": True})


def server_crawl(cat, only):
    """서버에서 해당 카테고리/채널 크롤을 백그라운드로 시작 (즉시 반환)."""
    import shlex
    only = only or ""
    remote = ("cd /home/ubuntu/kmong/crawling_bot && nohup python3 crawl_run.py "
              + shlex.quote(cat) + " " + shlex.quote(only)
              + " >> logs/manual_crawl.log 2>&1 </dev/null &")
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
        return f.read()


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
        _prewarm_cache["etf_bar"] = {"data": etfs, "ts": time.time()}
        return JSONResponse(content=etfs)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


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
        result[code] = {
            "label":            label,
            "price":            price_d.get("price", 0),
            "change_rate":      price_d.get("change_rate", 0),
            "bars":             done.get(f"{mkt}_bars") or [],
            "investor_now":     investor,
            "investor_history": list(_FLOW[mkt]["investor"]),
            "program_now":      prog,
            "program_history":  list(_FLOW[mkt]["program"]),
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


@app.get("/api/market_flow")
def api_market_flow():
    """코스피/코스닥/미국선물(SPY)/코스피야간선물 지수 15분봉 + 투자자/프로그램 시계열."""
    try:
        import kis_api, kiwoom_api, naver_api
        from concurrent.futures import ThreadPoolExecutor

        # 프리워밍 캐시 hit → 즉시 반환 (수십 ms)
        cached = _prewarm_cache.get("market_flow")
        if cached and time.time() - cached["ts"] < _PREWARM_TTL:
            return JSONResponse(content=_build_market_flow_result(cached["data"]))

        # 전일종가 캐시 비어있으면 먼저 채움 (서버 시작 직후 레이스컨디션 방지)
        if global_api and not global_api._PW_PREVCLOSE:
            try:
                global_api.scrape_all_prevclose()
            except Exception:
                pass

        # 캐시 미스 → 직접 fetch (분봉·투자자=키움, 나머지=KIS)
        with ThreadPoolExecutor(max_workers=14) as ex:
            tasks = {
                "J_bars":     ex.submit(kiwoom_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kiwoom_api.get_index_minutebar, "1001", 15),
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
                "RANK_AMT":   ex.submit(kiwoom_api.get_trade_rank, 30),
            }
            done = {}
            for k, f in tasks.items():
                try: done[k] = f.result(timeout=15)
                except Exception: done[k] = None
        _enrich_rank_prices(done)  # 순위 목록 가격을 KIS 시세로 통일
        # 가격 0인 빈 데이터는 캐시 오염 방지 (토큰 실패 등)
        j_price = (done.get("J_price") or {}).get("price", 0)
        q_price = (done.get("Q_price") or {}).get("price", 0)
        if j_price and q_price:
            _prewarm_cache["market_flow"] = {"data": done, "ts": time.time()}
        return JSONResponse(content=_build_market_flow_result(done))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── 히트맵 캐시 (탭 전환 속도 개선) ──────────────────────────
_heatmap_cache: dict = {}           # {key: {"data": ..., "ts": float}}
_heatmap_building: set = set()      # 현재 빌드 중인 key 집합
_heatmap_lock = threading.Lock()
_HEATMAP_TTL = 180                  # 3분 캐시


def _heatmap_cached(key: str, fn):
    """캐시 hit이면 즉시 반환, miss면 fn() 호출 후 캐시 저장."""
    now = time.time()
    entry = _heatmap_cache.get(key)
    if entry and now - entry["ts"] < _HEATMAP_TTL:
        return entry["data"]
    data = fn()
    _heatmap_cache[key] = {"data": data, "ts": now}
    return data


def _heatmap_build_bg(key: str, fn):
    """캐시 없을 때 백그라운드 스레드로 빌드. 중복 실행 방지."""
    with _heatmap_lock:
        if key in _heatmap_building:
            return
        _heatmap_building.add(key)

    def _run():
        try:
            data = fn()
            if data:
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
KRX_CODES_PATH     = os.path.join(ATOMS_DIR, "krx_codes.json")


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
    with open(SECTOR_CUSTOM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _heatmap_cache.clear()   # 모든 캐시 무효화
    return JSONResponse(content={"ok": True})


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
        import kiwoom_api
        data = kiwoom_api.get_stock_candles(code, tf)
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
        _candle_cache[key] = {"data": data, "ts": now}
        return JSONResponse(content={"tf": tf, "candles": data})
    except Exception as e:
        return JSONResponse(content={"error": str(e), "candles": []}, status_code=500)


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
    """섹터 이름 목록 (가격 조회 없음, 빠름). 편집 탭 초기화용."""
    try:
        from sector_heatmap import parse_watchlist  # noqa: E402
        sections = parse_watchlist(top_n=1)
        return JSONResponse(content=[s["sector"] for s in sections])
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
        from sector_heatmap import parse_watchlist  # noqa: E402
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
                "J_bars":     ex.submit(kiwoom_api.get_index_minutebar, "0001", 15),
                "Q_bars":     ex.submit(kiwoom_api.get_index_minutebar, "1001", 15),
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
                "RANK_AMT":   ex.submit(kiwoom_api.get_trade_rank, 30),
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

_CAT_LABEL = {
    "youtube":  ("유튜브",   "📺"),
    "telegram": ("텔레그램", "💬"),
    "blog":     ("블로그",   "📝"),
    "report":   ("리포트",   "📰"),
    "news":     ("뉴스",     "🗞️"),
}
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


# ── 검색 키워드 토크나이저 (자연어 문장 → 키워드) ─────────────
_SEARCH_STOP = {
    "오늘", "내일", "어제", "지금", "요즘", "최근", "관련", "어떤", "무슨", "무엇",
    "있는", "있는지", "없는", "인지", "그리고", "정리", "정리해줘", "알려줘", "알려",
    "해줘", "보여줘", "대해", "대한", "이슈", "이슈가", "소식", "현황", "상황",
    "어때", "어떻게", "이게", "저게", "그게", "정도", "관해",
}


def _tokenize_query(q):
    """자연어 문장에서 검색 키워드 토큰 추출. 못 뽑으면 원문만."""
    raw = re.split(r"[\s,./·…]+", (q or "").strip())
    toks, seen = [], set()
    for t in raw:
        t = re.sub(r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|관련|이슈가|이슈|에대해|에대한)$", "", t.strip())
        if len(t) >= 2 and t not in _SEARCH_STOP and t not in seen:
            seen.add(t)
            toks.append(t)
    return toks or [(q or "").strip()]


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


# ── §4.9 NotebookLM 다리: 가로검색 묶음 → 노트북 자동 생성 ──────
def _nlm_exe():
    """nlm 실행 파일 경로. PATH 우선, 없으면 None."""
    return shutil.which("nlm") or shutil.which("nlm.exe")


def _run_nlm(args, timeout=90):
    """nlm CLI 호출. (ok, stdout, stderr) 반환."""
    exe = _nlm_exe()
    if not exe:
        return False, "", "nlm CLI를 찾을 수 없음 (PATH 확인)"
    try:
        p = subprocess.run(
            [exe] + args,
            capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=ROOT,
        )
        if p.returncode != 0:
            return False, p.stdout or "", (p.stderr or p.stdout or f"exit {p.returncode}")
        return True, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return False, "", f"nlm 타임아웃({timeout}s)"
    except Exception as e:
        return False, "", str(e)


def _friendly_nlm_err(msg):
    """nlm 에러를 사용자 친화적으로 — 특히 인증 만료."""
    m = msg or ""
    if any(s in m for s in ("Authentication expired", "Could not retrieve notebook",
                            "re-authenticate", "AuthenticationError")):
        return "⚠️ NotebookLM 로그인이 만료됐습니다. 터미널에서 'nlm login' 실행 후 다시 시도하세요."
    return m[:200]


# 리모션(채널) 브랜드 디자인 지침 — 인포그래픽/슬라이드/영상에 기본 적용
_BRAND_DESIGN = (
    "[디자인 지침] 순수 블랙(#000000) 배경에 라임그린(#AAFF00)을 메인 액센트로 핵심 수치·"
    "키워드·그래프 라인·테두리에 사용하고, 골드/앰버(#C8921A)는 고급 포인트로, 텍스트는 흰색. "
    "미니멀하면서 데이터가 빛나는 HUD/프리미엄 금융 대시보드 느낌. 큰 숫자와 핵심을 강하게 강조하고 "
    "정보 밀도 높게, 디테일하고 세련되게 구성."
)


def _nb_cat_of(st):
    st = st or ""
    if st in ("youtube", "yt"):
        return "youtube"
    if st == "telegram":
        return "telegram"
    if st in ("blog", "report", "news"):
        return st
    return st


def _nb_period_min(period):
    """기간 프리셋 → 시작 날짜(YYYY-MM-DD) 또는 None(전체)."""
    n = {"today": 0, "d3": 2, "d7": 6}.get(period)
    if n is None:
        return None
    from datetime import timedelta
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _nb_cats_types(cats):
    """카테고리 id 리스트 → source_type 리스트(youtube는 yt 포함)."""
    types = []
    for c in (cats or []):
        if c == "youtube":
            types += ["youtube", "yt"]
        elif c in ("telegram", "report", "blog", "news"):
            types.append(c)
    return types


def _nb_fetch_rows(conn, q, cats=None, period="all", limit=200):
    """토큰 매칭 + 카테고리/기간 필터 + 토큰겹침 랭킹. (rows, toks, label)."""
    toks = _tokenize_query(q)
    label = " ".join(toks)
    clauses = ["(" + " OR ".join(["content LIKE ? OR asset LIKE ?"] * len(toks)) + ")"]
    params = []
    for t in toks:
        params += [f"%{t}%", f"%{t}%"]
    types = _nb_cats_types(cats) if cats else None
    if types:
        clauses.append("source_type IN (" + ",".join(["?"] * len(types)) + ")")
        params += types
    dmin = _nb_period_min(period)
    if dmin:
        clauses.append("date >= ?")
        params.append(dmin)
    sql = ("SELECT source_type, source_name, raw_file, date, content, asset, "
           "stance_key, deeplink FROM atoms WHERE " + " AND ".join(clauses) +
           " ORDER BY date DESC LIMIT 500")
    rows = conn.execute(sql, params).fetchall()

    def _score(r):
        text = (r["content"] or "") + " " + (r["asset"] or "")
        return sum(1 for t in toks if t in text)
    cap = max(1, min(int(limit or 200), 500))
    rows = sorted(rows, key=lambda r: (_score(r), r["date"] or ""), reverse=True)[:cap]
    return rows, toks, label


def _nb_md_for_rows(title_label, rows, today):
    """rows → 마크다운 (카테고리/소스별 그룹)."""
    order = ["youtube", "telegram", "report", "blog", "news"]
    groups = {}
    for r in rows:
        groups.setdefault((_nb_cat_of(r["source_type"]), r["source_name"] or "?"), []).append(r)
    lines = [
        f"# {title_label} — 인사이트 허브 가로검색 묶음 ({today})",
        f"_총 {len(rows)}개 발언 · 소스 {len(groups)}개 · 로또의 주식 인사이트 허브 추출_",
        "",
    ]
    for key in sorted(groups.keys(),
                      key=lambda k: (order.index(k[0]) if k[0] in order else 99, k[1])):
        cat, src = key
        clabel, icon = _CAT_LABEL.get(cat, (cat, "•"))
        lines.append(f"## {icon} [{clabel}] {src}")
        for r in groups[key]:
            stance = f" `{r['stance_key']}`" if r["stance_key"] else ""
            asset = f" ({r['asset']})" if r["asset"] else ""
            dl = (r["deeplink"] or "").strip()
            src_tag = f" — {dl}" if dl.startswith("http") else ""
            lines.append(f"- {(r['content'] or '').strip()}{asset}{stance}  ·{r['date'] or ''}{src_tag}")
        lines.append("")
    return "\n".join(lines)


def _nb_scope_label(cats, period):
    """키워드 없을 때 소스+기간 기반 라벨."""
    names = "·".join(_CAT_LABEL.get(c, (c,))[0] for c in (cats or [])) or "전체"
    pl = {"today": "오늘", "d3": "최근3일", "d7": "최근7일"}.get(period, "")
    return (names + (" " + pl if pl else "")).strip()


def _build_notebook_bundle(q, cats=None, period="all", limit=200, split=False, include_urls=True):
    """필터 적용 수집 → dict(label, atoms_n, md_files[(title,text)], yt_urls, web_urls).
    키워드가 매칭 0건이면(순수 요청문) 소스+기간 전체를 담는 '정리 모드'로 폴백."""
    conn = _ins_conn()
    if conn is None:
        return None
    try:
        rows, toks, label = _nb_fetch_rows(conn, q, cats, period, limit)
        if not rows:
            rows, toks, _ = _nb_fetch_rows(conn, "", cats, period, limit)
            label = _nb_scope_label(cats, period)
    finally:
        conn.close()
    if not (label or "").strip():
        label = _nb_scope_label(cats, period)

    yt_urls, web_urls = [], []
    if include_urls:
        for r in rows:
            dl = (r["deeplink"] or "").strip()
            if not dl.startswith("http"):
                continue
            if _nb_cat_of(r["source_type"]) == "youtube" or "youtu" in dl:
                if dl not in yt_urls:
                    yt_urls.append(dl)
            elif dl not in web_urls:
                web_urls.append(dl)

    today = datetime.now().strftime("%Y-%m-%d")
    md_files = []  # (source_title, md_text)
    if split:
        bycat = {}
        for r in rows:
            bycat.setdefault(_nb_cat_of(r["source_type"]), []).append(r)
        order = ["youtube", "telegram", "report", "blog", "news"]
        for cat in sorted(bycat.keys(), key=lambda c: order.index(c) if c in order else 99):
            clabel = _CAT_LABEL.get(cat, (cat, ""))[0]
            md_files.append((f"[허브:{clabel}] {label} {len(bycat[cat])}건",
                             _nb_md_for_rows(f"{label} · {clabel}", bycat[cat], today)))
    else:
        md_files.append((f"[허브추출] {label} 발언 {len(rows)}건",
                         _nb_md_for_rows(label, rows, today)))

    return {
        "label": label, "atoms_n": len(rows), "md_files": md_files,
        "yt_urls": yt_urls[:20], "web_urls": web_urls[:20],
    }


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
    period = (body.get("period") or "all").strip()
    if period not in ("all", "today", "d3", "d7"):
        period = "all"
    try:
        limit = int(body.get("limit") or 200)
    except Exception:
        limit = 200
    split = bool(body.get("split", False))
    include_urls = bool(body.get("include_urls", True))

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "out", "insights_notebook")
    os.makedirs(out_dir, exist_ok=True)
    file_specs = []           # (source_title, path)
    yt_urls, web_urls = [], []
    md_for_cache = []

    if no_crawl:
        label = re.sub(r"\s+", " ", q).strip()[:40] or "리서치"
        atoms_n = 0
    else:
        bundle = await run_in_threadpool(
            _build_notebook_bundle, q, cats, period, limit, split, include_urls)
        if bundle is None:
            return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
        label = bundle["label"]
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
        ok, out, err = _run_nlm(["notebook", "create", title, "--json"])
        if not ok:
            return {"error": f"노트북 생성 실패: {_friendly_nlm_err(err)}"}
        nb_id = None
        try:
            nb_id = json.loads(out.strip().splitlines()[-1]).get("id")
        except Exception:
            pass
        if not nb_id:
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", out)
            nb_id = m.group(0) if m else None
        if not nb_id:
            return {"error": f"노트북 ID 파싱 실패: {out[:200]}"}

        added, last_err = 0, ""
        for src_title, mp in file_specs:
            ok2, _o2, err2 = _run_nlm(["source", "add", nb_id, "--file", mp,
                                       "--title", src_title])
            if ok2:
                added += 1
            else:
                last_err = err2
        url_args = []
        for u in yt_urls:
            url_args += ["--youtube", u]
        for u in web_urls:
            url_args += ["--url", u]
        if url_args:
            ok3, _o3, _e3 = _run_nlm(["source", "add", nb_id] + url_args, timeout=150)
            if ok3:
                added += 1
        researched = 0
        if research:
            okr, outr, _er = _run_nlm(
                ["research", "start", q, "-n", nb_id, "-m", "fast", "--auto-import"],
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
            ["research", "start", q, "-n", nb_id, "-m", mode, "--auto-import"],
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
        ok, out, errm = _run_nlm(
            ["report", "create", nb_id, "--format", fmt, "--language", "ko", "--confirm"],
            timeout=180)
        if not ok:
            return {"error": f"카드 생성 실패: {_friendly_nlm_err(errm)}"}
        # 생성 완료까지 폴링 → 마크다운 다운로드 → 인라인 반환
        art_id = None
        for _ in range(30):  # 최대 ~150s
            ok_s, out_s, _ = _run_nlm(["studio", "status", nb_id])
            try:
                reps = [a for a in json.loads(out_s) if a.get("type") == "report"]
                if reps and reps[-1].get("status") not in ("in_progress", "pending", None):
                    art_id = reps[-1].get("id")
                    break
            except Exception:
                pass
            time.sleep(5)
        md = ""
        rp = os.path.join(ROOT, "out", "insights_notebook",
                          f"report_{re.sub(r'[^0-9a-fA-F-]', '', nb_id)}.md")
        dargs = ["download", "report", nb_id, "-o", rp]
        if art_id:
            dargs += ["--id", art_id]
        ok_d, _od, _ed = _run_nlm(dargs, timeout=60)
        if ok_d and os.path.exists(rp):
            try:
                with open(rp, encoding="utf-8") as f:
                    md = f.read()
            except Exception:
                md = ""
        return {"ok": True, "format": fmt, "markdown": md,
                "ready": bool(md),
                "url": f"https://notebooklm.google.com/notebook/{nb_id}"}

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
        # 채팅에 "만들어줘" 류가 들어가면 NotebookLM이 문서생성 모드로 빠져
        # 영어 사고과정만 뱉는 문제 → 답변만 하도록 제약을 덧붙인다.
        guarded = (
            f"{question}\n\n"
            "[작성 지침] 이 노트북에 연결된 '모든 소스'를 빠짐없이 활용해 한국어로 "
            "충실하고 구체적으로 정리해줘. 종목명·수치·날짜·핵심 주장과 그 근거를 최대한 담고, "
            "주제별(종목/수급/이슈/일정/리스크 등)로 소제목을 나눠 구조화해줘. 소스가 여러 개면 "
            "교차해서 종합하고, 한두 줄로 끝내지 말고 의미 있는 내용은 모두 포함해줘. "
            "단, 새 리포트·문서·노트 같은 아티팩트는 만들지 말고 채팅 답변으로만, "
            "영어 사고과정 설명 없이 결과만 써줘."
        )
        args = ["notebook", "query", nb_id, guarded, "--json"]
        if conv:
            args += ["-c", conv]
        ok, out, errm = _run_nlm(args, timeout=180)
        if not ok:
            return {"error": f"질문 실패: {_friendly_nlm_err(errm)}"}
        answer, conv_id = out.strip(), ""
        try:
            d = json.loads(out)
            answer = d.get("answer") or answer
            conv_id = d.get("conversation_id") or ""
        except Exception:
            pass
        return {"ok": True, "answer": answer, "conversation_id": conv_id}

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
        keys = [k for k in (_env_key("GEMINI_API_KEY"), _env_key("GEMINI_API_KEY_2")) if k]
        if not keys:
            return {"error": ".env에 GEMINI_API_KEY 없음"}
        last = ""
        for k in keys:
            try:
                client = genai.Client(api_key=k)
                resp = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=f"{system}\n\n{convo}",
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        temperature=0,
                    ),
                )
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
                    continue   # 다음(예비) 키로
                return {"error": f"Gemini 호출 실패: {last[:300]}"}
        return {"error": f"Gemini 쿼터 소진(키 {len(keys)}개 모두): {last[:200]}"}

    result = await run_in_threadpool(_do)
    return JSONResponse(content=result, status_code=(200 if result.get("ok") else 500))


@app.get("/api/insights/notebooks")
def api_insights_notebooks():
    """만든 브리핑(자료) 목록 — 이전 자료 끌어오기 픽커용."""
    reg = _load_nb_registry()
    return JSONResponse(content={"notebooks": [
        {"id": e.get("id"), "label": e.get("label", ""), "date": e.get("date", ""),
         "atoms": e.get("atoms", 0)} for e in reg]})


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
    keys = [k for k in (_env_key("GEMINI_API_KEY"), _env_key("GEMINI_API_KEY_2")) if k]
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
    """Gemini 이미지 생성(나노바나나2→2.5 폴백, 키 폴백) → PNG bytes."""
    from google import genai
    from google.genai import types
    last = ""
    for model in ("gemini-3-flash-preview-image", "gemini-2.5-flash-image"):
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
                continue
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
        keys = [k for k in (_env_key("GEMINI_API_KEY"), _env_key("GEMINI_API_KEY_2")) if k]
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

if __name__ == "__main__":
    print("딸깍 대시보드 → http://localhost:8090")
    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
