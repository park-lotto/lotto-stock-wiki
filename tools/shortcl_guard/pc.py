# 진짜 회원 프로그램(MCP 서버) 흉내 — PC 여러 대·Claude 계정 2개. e2e.py(관제 296)·admin_e2e.py(관제 329)가 같이 쓴다.
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

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
