# 진짜 회원 프로그램(MCP 서버)을 PC 3대·Claude 계정 2개로 흉내 내 끝까지 돌린다.
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:18871"
R = Path(r"C:\t\guard")
KEY = (R / "key.txt").read_text(encoding="ascii").strip()
UUID = {"나": "uuid-me", "친구": "uuid-friend"}
for who, u in UUID.items():
    d = R / "cfg" / who
    d.mkdir(parents=True, exist_ok=True)
    (d / ".claude.json").write_text(json.dumps({"oauthAccount": {"accountUuid": u, "emailAddress": who + "@x.test"}}), encoding="utf-8")


class Pc:
    def __init__(self, name, who="나"):
        self.name, self.out = name, {}
        (R / "home" / name).mkdir(parents=True, exist_ok=True)
        (R / "work" / name).mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, SHORTEM_BASE=BASE, SHORTEM_HOME=str(R / "home" / name), SHORTEM_WORK=str(R / "work" / name),
                   SHORTEM_LICENSE=KEY, SHORTEM_MACHINE_ID="machine-" + name, SHORTEM_OS_USER="u", SHORTEM_DEVICE_NAME="PC-" + name,
                   CLAUDE_CONFIG_DIR=str(R / "cfg" / who), SHORTEM_CLIENT="claude-code")
        env.pop("SHORTEM_CLAUDE_ACCOUNT", None)
        self.p = subprocess.Popen(["node", str(R / "client/server/index.js")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=str(R / "work" / name))
        threading.Thread(target=self._read, daemon=True).start()
        self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
        assert self._wait(1, 30), "초기화 실패"
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.n = 1

    def _read(self):
        for raw in self.p.stdout:
            try:
                m = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if "id" in m:
                self.out[m["id"]] = m

    def _send(self, o):
        self.p.stdin.write((json.dumps(o) + "\n").encode())
        self.p.stdin.flush()

    def _wait(self, i, sec):
        t = time.time()
        while i not in self.out and time.time() - t < sec and self.p.poll() is None:
            time.sleep(.2)
        return self.out.get(i)

    def setup(self):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": {"name": "shortem_setup", "arguments": {}}})
        r = self._wait(self.n, 90)
        txt = " ".join(c.get("text", "") for c in (r or {}).get("result", {}).get("content", []))
        try:
            d = json.loads(txt)
        except ValueError:
            return "해석 불가 " + txt[:300]
        lic = (d.get("info") or {}).get("license") or {}
        if lic.get("ok"):
            return f"정상 · {lic['device']['slot']}번 칸 · {lic['device']['name']}"
        return f"막힘 [{lic.get('code')}] {lic.get('why')} / {lic.get('fix')}"

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(8)
        except subprocess.TimeoutExpired:
            self.p.kill()
        time.sleep(1)


def api(path, body=None):
    q = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(q, timeout=20).read())


A = Pc("A")
time.sleep(1.5)
print("1 PC-A 내 계정 첫 점검:", A.setup())
F = Pc("F", "친구")
time.sleep(1.5)
print("2 PC-F 친구 계정(빈자리 있음):", F.setup())
F.close()
print("  등록 기기 수:", len(api("/api/admin/claude/devices?cid=7")["devices"]))
print("  계정 변경 요청:", [(c["kind"], c["done_30d"]) for c in api("/api/admin/claude/changes")["changes"]])
c0 = api("/api/admin/claude/changes")["changes"][0]
api("/api/admin/claude/changes/decide", {"id": c0["id"], "approve": False})
B = Pc("B")
time.sleep(1.5)
print("3 PC-B 내 계정, PC-A 켜 둠:", B.setup())
A.close()
print("4 PC-A 닫은 뒤 PC-B:", B.setup())
B.close()
C = Pc("C")
time.sleep(1.5)
print("5 PC-C 3대째:", C.setup())
for _ in range(3):
    C.setup()
print("  같은 PC 반복 시도 뒤 정지 여부:", C.setup())

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    pg.on("dialog", lambda d: d.accept())
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/claude", wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    print("6 회원 화면 안내:", pg.inner_text("#swapNote"))
    print("  버튼:", pg.locator("#devList [data-dev]").all_inner_texts(), "| 기기", pg.inner_text("#devCount"))
    pg.locator("#license").screenshot(path=str(R / "회원_요청전.png"))
    pg.locator("#devList [data-dev]").first.click()
    pg.wait_for_timeout(1500)
    print("7 요청 뒤 회원 화면:", pg.inner_text("#swapNote"))
    pg.locator("#license").screenshot(path=str(R / "회원_요청뒤.png"))
    print("8 승인 전 PC-C:", C.setup())
    ad = b.new_page(viewport={"width": 1400, "height": 900})
    ad.goto(BASE + "/admin", wait_until="domcontentloaded")
    ad.wait_for_timeout(2500)
    print("9 관리자 요청:", ad.inner_text("#claudeChangeBoard").replace("\n", " | "))
    ad.screenshot(path=str(R / "관리자_승인.png"))
    ad.locator("#claudeChangeBoard button:has-text('승인')").click()
    ad.wait_for_timeout(1200)
    print("  승인 뒤 남은 요청:", repr(ad.inner_text("#claudeChangeBoard")))
    print("  화면 오류:", errs)
    b.close()
print("10 승인 뒤 PC-C (재설치 없음):", C.setup())
print("  기기:", [(d["slot"], d["name"]) for d in api("/api/admin/claude/devices?cid=7")["devices"]])
C.close()
A = Pc("A")
time.sleep(1.5)
print("11 뺀 PC-A:", A.setup())
A.close()
