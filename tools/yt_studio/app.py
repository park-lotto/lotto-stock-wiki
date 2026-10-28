# -*- coding: utf-8 -*-
"""숏템하우스 영상제작소 — 사장님 전용 로컬 앱 (2026-09-15)

폴더를 손으로 고르지 않게 한다. 씬 카드에 파일을 끌어다 놓으면
확장자로 음성/녹화를 알아서 가르고, 저장 위치는 이 앱만 안다.

  실행: py tools/yt_studio/app.py   → http://127.0.0.1:8777
  자료: C:/Users/TheRose/영상제작소/<편>/<씬키>/{음성,녹화,완성}/
"""
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
# 대사·리모션은 main 폴더가 정본(트랙 폴더에서 띄워도 main을 본다)
MAIN = PROJECT.parents[1] if PROJECT.parent.name == ".tracks" else PROJECT
EPISODE = "숏템하우스_2편"
SCENE_DIR = MAIN / "out" / f"{EPISODE}_씬별"
REMOTION = MAIN / "remotion-stock"
TIMING_TOOL = MAIN / "tools" / "shottem2_timing.py"
DATA = Path.home() / "영상제작소" / EPISODE

AUDIO_EXT = {".mp3", ".wav", ".m4a"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
KINDS = ("음성", "녹화", "자료", "완성")

app = FastAPI()
JOBS: dict = {}  # 씬키 → {"state": running|done|fail, "log": str}


def scenes():
    out = []
    for f in sorted(SCENE_DIR.glob("*.txt")):
        key = f.stem
        m = re.match(r"(\d+)_(.*)", key)
        no = int(m.group(1)) if m else 0
        comp = f"ST2-S{no:02d}" if no else ""
        has_comp = bool(comp) and comp in (REMOTION / "src" / "Root.tsx").read_text(encoding="utf-8")
        d = DATA / key
        files = {k: sorted(p.name for p in (d / k).glob("*") if p.is_file()) for k in KINDS}
        out.append({
            "key": key, "no": no, "title": m.group(2) if m else key,
            "text": f.read_text(encoding="utf-8"),
            "files": files, "comp": comp if has_comp else "",
            "timing": (d / "timing.json").exists(),
            "memo": (d / "memo.txt").read_text(encoding="utf-8") if (d / "memo.txt").exists() else "",
            "job": JOBS.get(key),
        })
    return out


def kind_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in AUDIO_EXT:
        return "음성"
    if ext in VIDEO_EXT:
        return "녹화"
    return "자료"


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "index.html").read_text(encoding="utf-8")


@app.get("/api/scenes")
def api_scenes():
    return {"episode": EPISODE, "data": str(DATA), "scenes": scenes()}


@app.post("/api/{key}/upload")
async def upload(key: str, files: list[UploadFile] = File(...)):
    saved = []
    for up in files:
        k = kind_of(up.filename)
        d = DATA / key / k
        d.mkdir(parents=True, exist_ok=True)
        with open(d / Path(up.filename).name, "wb") as fp:
            shutil.copyfileobj(up.file, fp)
        saved.append({"name": up.filename, "kind": k})
    return {"saved": saved}


@app.get("/file/{key}/{kind}/{name}")
def get_file(key: str, kind: str, name: str):
    p = DATA / key / kind / Path(name).name
    return FileResponse(p)


@app.delete("/api/{key}/{kind}/{name}")
def delete_file(key: str, kind: str, name: str):
    p = DATA / key / kind / Path(name).name
    if p.exists():
        trash = DATA / "_휴지통"
        trash.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(trash / f"{key}__{p.name}"))
    return {"ok": True}


@app.post("/api/{key}/memo")
async def memo(key: str, body: dict):
    d = DATA / key
    d.mkdir(parents=True, exist_ok=True)
    (d / "memo.txt").write_text(body.get("memo", ""), encoding="utf-8")
    return {"ok": True}


def _run(key: str, cmd: list, cwd: Path, label: str = ""):
    JOBS[key] = {"state": "running", "log": f"[{label}] " + " ".join(map(str, cmd))[-200:]}
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        tail = ((r.stdout or "") + (r.stderr or ""))[-1500:]
        JOBS[key] = {"state": "done" if r.returncode == 0 else "fail", "log": f"[{label}]\n{tail}"}
    except Exception as e:  # noqa: BLE001 — 화면에 그대로 보여준다
        JOBS[key] = {"state": "fail", "log": repr(e)}


@app.post("/api/{key}/timing")
def timing(key: str):
    audio = sorted((DATA / key / "음성").glob("*"))
    if not audio:
        return JSONResponse({"error": "음성 파일이 없습니다"}, 400)
    cmd = [sys.executable, str(TIMING_TOOL), str(SCENE_DIR / f"{key}.txt"),
           str(audio[0]), str(DATA / key / "timing.json")]
    if (JOBS.get(key) or {}).get("state") == "running":
        return JSONResponse({"error": "이 씬은 다른 작업이 진행 중입니다"}, 409)
    threading.Thread(target=_run, args=(key, cmd, MAIN, "타이밍"), daemon=True).start()
    return {"ok": True}


@app.post("/api/{key}/render")
def render(key: str):
    sc = next((s for s in scenes() if s["key"] == key), None)
    if not sc or not sc["comp"]:
        return JSONResponse({"error": "아직 리모션 씬이 없습니다 — Claude에게 만들어 달라고 하세요"}, 400)
    out = DATA / key / "완성" / f"{sc['comp']}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    # ★npx.cmd는 한글 경로 인자를 깨뜨려 "No entry point"로 죽는다(실측) — node 직접 + 영문 임시경로
    tmp = Path.home() / "AppData" / "Local" / "Temp" / f"yt_studio_{sc['comp']}.mp4"
    cmd = ["node", "node_modules/@remotion/cli/remotion-cli.js", "render", "src/index.ts", sc["comp"], str(tmp)]
    if (JOBS.get(key) or {}).get("state") == "running":
        return JSONResponse({"error": "이 씬은 다른 작업이 진행 중입니다"}, 409)

    def job():
        _run(key, cmd, REMOTION, "영상 만들기")
        if JOBS[key]["state"] == "done" and tmp.exists():
            shutil.move(str(tmp), str(out))
    threading.Thread(target=job, daemon=True).start()
    return {"ok": True}


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    print(f"영상제작소 → http://127.0.0.1:8777   자료: {DATA}")
    uvicorn.run(app, host="127.0.0.1", port=8777, log_level="warning")
