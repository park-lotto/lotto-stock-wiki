"""
딸깍 대시보드 — 로컬 내부 도구
버튼 하나로 이미 생성된 자동화 산출물을 한 화면에 모아 보여준다.

실행:  python dashboard/server.py
접속:  http://localhost:8090
"""
import os, sys, json, glob, re, shutil, subprocess
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print("의존성 설치 필요:  pip install fastapi uvicorn")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
SIGNAL_DIR = os.path.join(ROOT, "output", "signal")
OUT_DIR = os.path.join(ROOT, "out")
AGENTS_DIR = os.path.join(HERE, "agents")

# claude CLI 위치 (PATH 우선, 없으면 알려진 경로)
CLAUDE_BIN = shutil.which("claude") or r"C:\Users\TheRose\.local\bin\claude.exe"
AGENT_TIMEOUT = 240  # 초

app = FastAPI(title="딸깍 대시보드")


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
    return JSONResponse(content=run_agent(role, request_text))


if __name__ == "__main__":
    print("딸깍 대시보드 → http://localhost:8090")
    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
