"""숏템 윈도 설치 exe 실설치 검사 — 시험용(/SANDBOX)으로 임시 폴더에 무인 설치 → 결과물 검사 → 제거 → 흔적 검사.

실행: py installer/win/test_install.py --exe <설치 exe> --dir <임시 설치 폴더(없는 경로)> [--keep]
검사:
  1) tools/tools.manifest.json 의 files[]·tools{} sha256 전부 일치
  2) ffmpeg -filters 에 ' ass ' · chrome-headless-shell --version · node -v · python import PIL,numpy · yt-dlp --version
  3) 연결기(launcher.js)로 MCP initialize → tools/list → tools/call shortem_setup 실제 왕복
  4) 제거 프로그램 등록 키·환경변수(시험용 이름)가 생겼는지 → 제거 후 전부 사라졌는지
실제 %LOCALAPPDATA%·바탕화면은 건드리지 않는다(/SANDBOX: 등록 키·환경변수 이름에 _SANDBOXTEST, 바탕화면은 설치 폴더 안).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ShortemSandboxTest"
ENV_NAMES = ("SHORTEM_INSTALL_SANDBOXTEST", "SHORTEM_NODE_SANDBOXTEST")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    return subprocess.run([str(c) for c in cmd], **kw)


def reg_exists(path: str) -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, path))
        return True
    except OSError:
        return False


def env_value(name: str):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def mcp_roundtrip(node: Path, launcher: Path, inst: Path) -> dict:
    sb = inst / "_sandbox_desktop"   # 제거 때 같이 지워지는 시험용 자리(실제 ~/.shortem·바탕화면 안 건드림)
    env = dict(os.environ, SHORTEM_INSTALL=str(inst), SHORTEM_LICENSE="", SHORTEM_HOME=str(sb / "_userdata"),
               SHORTEM_WORK=str(sb / "숏템작업"))
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "shortem_setup", "arguments": {"selftest": False}}},
    ]
    p = subprocess.Popen([str(node), str(launcher)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=env, cwd=str(inst.parent))
    got: dict = {}
    try:
        for m in msgs:
            p.stdin.write((json.dumps(m) + "\n").encode())
            p.stdin.flush()
            if "id" not in m:
                continue
            deadline = time.time() + 120
            while time.time() < deadline:
                line = p.stdout.readline()
                if not line:
                    break
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("id") == m["id"]:
                    got[m["method"]] = r
                    break
    finally:
        try:
            p.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
        err = p.stderr.read().decode("utf-8", "replace")
    got["_stderr_tail"] = err[-600:]
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    exe, inst = Path(a.exe).resolve(), Path(a.dir).resolve()
    if inst.exists():
        print(f"설치 폴더가 이미 있습니다(빈 경로를 주세요): {inst}")
        return 2
    res: dict = {"exe": str(exe), "exe_mb": round(exe.stat().st_size / 1e6, 1), "dir": str(inst)}
    fails = []

    t0 = time.time()
    # NSIS 규칙: /D= 와 _?= 는 맨 끝·따옴표 없이(공백 있어도). 리스트로 넘기면 파이썬이 따옴표를 씌워 무시된다
    r = subprocess.run(f'"{exe}" /S /SANDBOX /D={inst}', capture_output=True, text=True)
    res["install_rc"] = r.returncode
    res["install_seconds"] = round(time.time() - t0, 1)
    if r.returncode != 0:
        fails.append(f"설치 rc={r.returncode}")

    if not (inst / "tools" / "tools.manifest.json").exists():
        print(json.dumps({"ok": False, "why": f"지정한 폴더에 설치되지 않음: {inst}"}, ensure_ascii=False))
        return 1
    tdir = inst / "tools"
    man = json.loads((tdir / "tools.manifest.json").read_text(encoding="utf-8"))
    bad = [f["path"] for f in man["files"] if not (tdir / f["path"]).exists() or sha(tdir / f["path"]) != f["sha256"]]
    tbad = [n for n, t in man["tools"].items() if sha(tdir / t["path"]) != t["sha256"]]
    res["sha"] = {"files_ok": len(man["files"]) - len(bad), "files_total": len(man["files"]), "files_bad": bad[:5],
                  "tools_ok": len(man["tools"]) - len(tbad), "tools_total": len(man["tools"])}
    if bad or tbad:
        fails.append("sha 불일치")

    T = {n: tdir / t["path"] for n, t in man["tools"].items()}
    filters = run([T["ffmpeg"], "-hide_banner", "-filters"]).stdout
    res["ffmpeg_version"] = run([T["ffmpeg"], "-hide_banner", "-version"]).stdout.splitlines()[0]
    res["ffmpeg_ass_filter"] = " ass " in filters
    res["ffprobe_version"] = run([T["ffprobe"], "-hide_banner", "-version"]).stdout.splitlines()[0]
    res["chrome_version"] = run([T["chrome"], "--version"]).stdout.strip()
    res["node_version"] = run([T["node"], "-v"]).stdout.strip()
    pr = run([T["python"], "-I", "-c", "import sys,PIL,numpy;print(sys.version.split()[0],'PIL',PIL.__version__,'numpy',numpy.__version__)"],
             cwd=inst.parent)
    res["python_import"] = (pr.stdout.strip() or pr.stderr.strip()[-300:])
    res["ytdlp_version"] = run([T["ytdlp"], "--version"]).stdout.strip()
    if not res["ffmpeg_ass_filter"]:
        fails.append("ass 필터 없음")
    if pr.returncode != 0:
        fails.append("python import 실패")

    files = {n: (inst / n).exists() for n in ("server/index.js", "shortem.mcpb", "시작.md", "install.json", "uninstall.exe",
                                              "claude-plugin/shortem/launcher.js", "claude-plugin/.claude-plugin/marketplace.json",
                                              "_sandbox_desktop/숏템작업/시작.md")}
    res["files"] = files
    if not all(files.values()):
        fails.append("설치 파일 빠짐")
    start_md = (inst / "시작.md").read_text(encoding="utf-8") if files["시작.md"] else ""
    res["start_md_has_path"] = (inst / "claude-plugin").as_posix() in start_md
    if not res["start_md_has_path"]:
        fails.append("시작.md 경로 치환 안 됨")

    rt = mcp_roundtrip(T["node"], inst / "claude-plugin" / "shortem" / "launcher.js", inst)
    tl = rt.get("tools/list", {}).get("result", {}).get("tools", [])
    call = rt.get("tools/call", {}).get("result", {})
    res["mcp"] = {
        "server": rt.get("initialize", {}).get("result", {}).get("serverInfo"),
        "tools": [t["name"] for t in tl],
        "setup_call_text": (call.get("content") or [{}])[0].get("text", "")[:400],
        "stderr_tail": rt["_stderr_tail"][-300:],
    }
    if len(tl) < 6:
        fails.append("MCP 도구 6개 아님")

    res["registered"] = {"uninstall_key": reg_exists(REG_KEY), **{n: env_value(n) for n in ENV_NAMES}}
    if not res["registered"]["uninstall_key"] or not all(res["registered"][n] for n in ENV_NAMES):
        fails.append("등록 안 됨")

    if not a.keep:
        un = inst / "uninstall.exe"
        r = subprocess.run(f'"{un}" /S _?={inst}', capture_output=True, text=True)
        res["uninstall_rc"] = r.returncode
        try:
            un.unlink()  # _?= 로 제자리 실행하면 제거 프로그램 자신은 남는다(NSIS 규칙)
        except OSError:
            pass
        left = [p.relative_to(inst).as_posix() for p in inst.rglob("*")] if inst.exists() else []
        res["after_uninstall"] = {"left_files": left[:10], "left_count": len(left),
                                  "uninstall_key": reg_exists(REG_KEY), **{n: env_value(n) for n in ENV_NAMES}}
        if inst.exists() and not left:
            inst.rmdir()
        if left or res["after_uninstall"]["uninstall_key"] or any(res["after_uninstall"][n] for n in ENV_NAMES):
            fails.append("제거 흔적 남음")

    res["fails"] = fails
    res["ok"] = not fails
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
