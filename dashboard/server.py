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
            if initial or (9 <= now.hour < 16):
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
    # 야간선물 WebSocket 실시간값 우선 사용
    if kis_ws:
        ws_ksfn = kis_ws.get("101W9")
        if ws_ksfn:
            ksfn = {"price": ws_ksfn["price"], "change_rate": ws_ksfn["change_rate"], "bars": ksfn.get("bars") or []}
    result["global"] = {
        "label": "글로벌 지표",
        "items": [
            {"name": "나스닥선물(NQ)",  "price": nq["price"],   "change_rate": nq["change_rate"],   "bars": nq.get("bars") or []},
            {"name": "코스피선물",      "price": ksf["price"],  "change_rate": ksf["change_rate"],  "bars": ksf.get("bars") or []},
            {"name": "코스피야간선물",  "price": ksfn["price"], "change_rate": ksfn["change_rate"], "bars": ksfn.get("bars") or []},
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


@app.get("/api/stock_search")
def api_stock_search(q: str = ""):
    if not q.strip():
        return JSONResponse(content=[])
    try:
        with open(KRX_CODES_PATH, encoding="utf-8") as f:
            codes_data = json.load(f)
        codes = codes_data.get("codes", {})
        q_l = q.strip().lower()
        results = [{"name": n, "code": c} for n, c in codes.items()
                   if q_l in n.lower()][:20]
        return JSONResponse(content=results)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


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


# ── §4.7 GET /api/insights/search?q=삼성전자 ─────────────────
@app.get("/api/insights/search")
def api_insights_search(q: str = ""):
    if not q.strip():
        return JSONResponse(content={"q": q, "total": 0, "hits": []})

    conn = _ins_conn()
    if conn is None:
        return JSONResponse(content={"error": "atoms.db 없음"}, status_code=503)
    try:
        like = f"%{q}%"
        rows = conn.execute(
            """SELECT source_type, source_name, raw_file, date,
                      content, asset, stance_key, yt_timestamp, deeplink
               FROM atoms
               WHERE content LIKE ? OR asset LIKE ?
               ORDER BY date DESC
               LIMIT 50""",
            (like, like),
        ).fetchall()

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
