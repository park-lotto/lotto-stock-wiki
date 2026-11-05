# -*- coding: utf-8 -*-
"""설치 묶음 풀기 — 회원 PC 언어와 무관하게 풀리나(관제 311, 일본 회원 11-03 'tar 1' 실패).

윈도 내장 tar.exe 는 시스템 문자표로 못 바꾸는 파일명을 건너뛰고 실패한다. 일본 PC(CP932)에선 한글 이름 309개 전부가 그 꼴.
이 PC(CP949)에서 같은 꼴을 만들려고 묶음에 태국어 이름 파일 하나를 더 넣는다(CP949·CP932 둘 다 표현 못 함).

  py -I installer/win/test_unzip_unicode.py --zip <shortem-win-x64-*.zip> [--path ps1|launcher|both]
        [--script <install.ps1>] [--launcher <launcher.js>]      ← 고치기 전 판을 주면 실패해야 정상(검사가 무언가를 잰다는 증거)

설치 길 둘(판단 주인 = 둘 다 .NET ZipFile 풀기):
  ps1      installer/install.ps1 (시작.md 한 줄 설치) — 가짜 서버(redeem·install·blob·start_menu)를 띄워 진짜 스크립트를 돈다
  launcher installer/mcpb/launcher.js installPack — shortem_client/test/noexe_install_check.js 로 돈다
판정 = 설치 폴더에 그 태국어 파일과 한글 폴더(packs/sfx/팩01)가 있고 파일 수가 묶음과 같다.
★ps1 길은 postinstall 이 실제 바탕화면\\숏템작업\\START.md 를 덮으므로 시험 전 백업·시험 뒤 되돌린다.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ODD = "packs/ไทย_시험.txt"          # CP949·CP932 어디에도 없는 글자 — 일본 PC 의 한글과 같은 처지


def make_zip(base: Path, out: Path) -> tuple[int, str]:
    shutil.copyfile(base, out)
    with zipfile.ZipFile(out, "a") as z:
        z.writestr(ODD, "unicode name test")
    n = sum(1 for i in zipfile.ZipFile(out).infolist() if not i.is_dir())
    h = hashlib.sha256(out.read_bytes()).hexdigest()
    return n, h


def judge(home: Path, n: int) -> dict:
    files = [p for p in home.rglob("*") if p.is_file()] if home.exists() else []
    return {"odd_file": (home / ODD).exists(), "hangul_dir": (home / "packs" / "sfx" / "팩01").exists(),
            "files": len(files), "expect_at_least": n}


def run_ps1(script: Path, zp: Path, n: int, sha: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="shortem_ps1_"))
    menu = (ROOT / "installer" / "shortcl_menu.ps1").read_bytes()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/api/claude/start/redeem":
                return self._send(200, json.dumps({"key": f"SHORTEM-L1.12.{int(time.time()) + 86400}.1.{'ab' * 16}"}).encode())   # license.KEY_RE 모양
            self._send(404, b"{}")

        def do_GET(self):
            if self.path.startswith("/api/claude/install"):
                return self._send(200, json.dumps({"ready": True, "version": "9.9.9", "sha256": sha,
                                                   "size": zp.stat().st_size, "url": "/__blob"}).encode())
            if self.path == "/__blob":
                return self._send(200, zp.read_bytes(), "application/octet-stream")
            if self.path == "/api/claude/start.ps1":      # 회원 PC 와 같은 길: irm … | iex (app.api_claude_start_ps1 꼴)
                body = script.read_text(encoding="utf-8").replace("__BASE__", f"http://127.0.0.1:{srv.server_address[1]}")
                return self._send(200, body.encode("utf-8"), "text/plain; charset=utf-8")
            if self.path == "/api/claude/start_menu.ps1":
                return self._send(200, menu, "text/plain; charset=utf-8")
            self._send(404, b"{}")

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    desk = Path(os.path.expanduser("~")) / "Desktop" / "숏템작업"
    backup = {}
    for name in ("START.md", "install_guide.html"):
        p = desk / name
        if p.exists():
            backup[p] = p.read_bytes()
    home = tmp / "Shortem"
    env = {**os.environ, "SHORTEM_BASE": f"http://127.0.0.1:{srv.server_address[1]}", "SHORTEM_START": "t",
           "SHORTEM_INSTALL_DIR": str(home), "SHORTEM_NO_PERSIST": "1", "SHORTEM_NO_LAUNCH": "1",
           "SHORTEM_PROFILE": str(tmp / "profile.ps1"), "CLAUDE_CONFIG_DIR": str(tmp / "claudecfg"),
           "SHORTEM_HOME": str(tmp / ".shortem")}   # 회원 키 저장이 이 PC 의 진짜 ~/.shortem/license 를 덮지 않게
    env.pop("CLAUDECODE", None)
    t0 = time.time()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                            f"irm http://127.0.0.1:{srv.server_address[1]}/api/claude/start.ps1 | iex"],
                           env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    finally:
        for p, b in backup.items():
            p.write_bytes(b)
        srv.shutdown()
    out = (r.stdout + r.stderr)
    res = {"path": "ps1", "rc": r.returncode, "sec": round(time.time() - t0),
           "tar_fail": "풀기 실패" in out, "skipping_lines": out.count("skipping"),
           "last": [l for l in out.splitlines() if "[숏클]" in l][-4:], "tail": out.strip().splitlines()[-3:], **judge(home, n)}
    res["ok"] = res["odd_file"] and res["hangul_dir"] and res["files"] >= n and not res["tar_fail"]
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def run_launcher(launcher: Path, zp: Path, n: int) -> dict:
    check = ROOT / "shortem_client" / "test" / "noexe_install_check.js"
    d = Path(tempfile.gettempdir()) / f"shortem_noexe_{int(time.time())}"
    work_launcher = ROOT / "installer" / "mcpb" / "launcher.js"
    orig = None
    if launcher.resolve() != work_launcher.resolve():      # 시험 도구는 정해진 자리의 launcher 를 띄운다 — 잠시 바꿔 끼우고 되돌린다
        orig = work_launcher.read_bytes()
        shutil.copyfile(launcher, work_launcher)
    t0 = time.time()
    try:
        r = subprocess.run(["node", str(check), "--zip", str(zp), "--dir", str(d)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
    finally:
        if orig is not None:
            work_launcher.write_bytes(orig)
    home = d / "AppData" / "Local" / "Shortem"
    res = {"path": "launcher", "rc": r.returncode, "sec": round(time.time() - t0),
           "tail": (r.stdout + r.stderr).strip().splitlines()[-2:], **judge(home, n)}
    res["ok"] = res["odd_file"] and res["hangul_dir"] and res["files"] >= n
    shutil.rmtree(d, ignore_errors=True)
    return res


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--path", default="both", choices=["ps1", "launcher", "both"])
    ap.add_argument("--script", default=str(ROOT / "installer" / "install.ps1"))
    ap.add_argument("--launcher", default=str(ROOT / "installer" / "mcpb" / "launcher.js"))
    a = ap.parse_args()
    tmpd = Path(tempfile.mkdtemp(prefix="shortem_zip_"))
    zp = tmpd / "pack.zip"
    n, sha = make_zip(Path(a.zip), zp)
    out = []
    if a.path in ("ps1", "both"):
        out.append(run_ps1(Path(a.script), zp, n, sha))
    if a.path in ("launcher", "both"):
        out.append(run_launcher(Path(a.launcher), zp, n))
    shutil.rmtree(tmpd, ignore_errors=True)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if all(o["ok"] for o in out) else 1


if __name__ == "__main__":
    sys.exit(main())
