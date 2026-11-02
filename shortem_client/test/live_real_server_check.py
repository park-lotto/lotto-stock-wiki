# -*- coding: utf-8 -*-
"""숏클 실시간 왕복 — 가짜 서버가 아니라 **진짜 서버 코드**로(관제 304). 라이브에는 안 닿는다: 임시 DB·이 PC 127.0.0.1 에 앱을 띄운다.
진짜 FastAPI 앱 + 진짜 회원 프로그램(live.js·api.js) + 진짜 대기실 도구(shortcl_watch.Watcher) + 진짜 관리자 화면(헤드리스 크롬).
텔레그램은 보내지 않는다(claude_live._tg 교체).

    py shortem_client/test/live_real_server_check.py [화면저장.png]
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="live_real_"))
os.environ.update(CLAUDE_STORE_DIR=str(TMP / "store"), CLAUDE_CHANNEL_ROOT=str(TMP / "repo"), CLAUDE_LICENSE_SECRET="check-secret")

import requests  # noqa: E402
import uvicorn  # noqa: E402

from shopping_shorts import app as A  # noqa: E402
from shopping_shorts import claude_live as live  # noqa: E402
from shopping_shorts import claude_portal as cp  # noqa: E402
from shopping_shorts.store import Store  # noqa: E402
from tools import shortcl_watch as W  # noqa: E402

PORT = 18943
BASE = f"http://127.0.0.1:{PORT}"
SHOT = sys.argv[1] if len(sys.argv) > 1 else str(TMP / "admin.png")
sent = []
live._tg = sent.append
db = TMP / "t.db"
A.DB_PATH = db
st = Store(db)
st.set_setting("claude_portal_enabled", "1")
key = cp.issue_license(7, st)["key"]
A._require_admin = lambda request: None         # 관리자 인증은 시험 test_claude_live_1102 가 본다. 여기는 왕복만
threading.Thread(target=lambda: uvicorn.run(A.app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="off"), daemon=True).start()
for _ in range(100):
    try:
        requests.get(BASE + "/api/admin/claude/live/events", timeout=2)
        break
    except OSError:
        time.sleep(.2)

NODE = r"""
process.env.SHORTEM_BASE = process.argv[2]; process.env.SHORTEM_LICENSE = process.argv[3];
const { pullLive, reportLive, withTeam } = await import(process.argv[4]);
const { shape } = await import(process.argv[5]);
const { api } = await import(process.argv[6]);
const act = process.argv[7];
if (act === 'report') { await api.license(); console.log(JSON.stringify(await reportLive({ kind: 'message', level: 'important', text: '쿠팡 검색이 계속 막혀요', stage: '제품 확인' }))); }
if (act === 'pull') { await pullLive(); await pullLive(); console.log(JSON.stringify(shape(withTeam({ need: 'wait', hints: ['기다리세요'] })))); await new Promise(r => setTimeout(r, 500)); }
"""
script = TMP / "c.mjs"
script.write_text(NODE, encoding="utf-8")
srv = ROOT / "shortem_client" / "server"
env = {**os.environ, "SHORTEM_HOME": str(TMP / "home"), "SHORTEM_WORK": str(TMP / "work"), "SHORTEM_DEV_TOOLS": "1", "SHORTEM_INSTALL": ""}
env.pop("SHORTEM_INSTALL")


def node(act):
    url = lambda f: (srv / f).as_uri()
    r = subprocess.run(["node", str(script), BASE, key, url("live.js"), url("firewall.js"), url("api.js"), act], capture_output=True, text=True, encoding="utf-8", env=env, timeout=30)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ① 회원 → 서버
print("① report:", node("report"))
d = requests.get(BASE + "/api/admin/claude/live/events").json()
print("  이벤트:", [(e["kind"], e["level"], e["stage"], e["urgent"], e["text"]) for e in d["events"]])
assert d["events"][0]["text"] == "쿠팡 검색이 계속 막혀요" and len(sent) == 1
print("  텔레그램 판정(가로챔):", sent[0].replace("\n", " / "))

# ② 대기실 도구가 잡는다
out = []
w = W.Watcher(requests.Session(), lambda: "x", out.append, state_file=TMP / "last", base=BASE)
w.last = 0
assert w.tick() and "쿠팡 검색이 계속 막혀요" in out[0]
print("② 대기실 한 줄:", out[0])
w.ping()
print("  대기실 상태:", requests.get(BASE + "/api/admin/claude/live/events").json()["watch"])

# ③ 관리자 → 회원 → 도구 응답 → 전달
r = subprocess.run([sys.executable, str(ROOT / "tools" / "shortcl_send.py"), "7", "다른 검색어로 해 보세요"], capture_output=True, text=True, encoding="utf-8",
                   env={**os.environ, "SHORTCL_BASE": BASE, "SHORTCL_COOKIE": "x", "PYTHONIOENCODING": "utf-8"})
print("③ send:", r.stdout.strip(), r.stderr[-200:])
assert r.returncode == 0
mid = int(r.stdout.split("#")[1].split()[0])
s = node("pull")
print("  도구 응답:", s)
assert s["hints"][0] == "숏클 팀 메시지: 다른 검색어로 해 보세요" and s["need"] == "wait"
m = live.message(st, mid)
print("  DB:", {k: m[k] for k in ("id", "delivered_at", "read_at")})
assert m["delivered_at"] and m["read_at"]

# ④ 관리자 화면 — 헤드리스 크롬으로 실제로 눌러 본다
with cp._tx(st, write=True) as c:
    fid = c.execute("INSERT INTO claude_feedback(ts, cid, kind, text, job_id) VALUES(?,?,?,?,?)", (cp._now(), 7, "code_fix", "--- a/flow.py\n+++ b/flow.py\n+고친 줄", None)).lastrowid
live.note(st, 7, "code_fix", "flow.py 한 줄 고침", level="important", ref=fid)
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.route("**/api/admin/customers", lambda rt: rt.fulfill(json={"settings": {}, "customers": []}))
    pg.goto(BASE + "/admin.html", wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    pg.evaluate("document.getElementById('claudeLiveCard').open=true")
    pg.wait_for_timeout(800)
    print("④ 요약:", pg.inner_text("#claudeLiveSummary"))
    print("  진행판:", pg.inner_text("#claudeLiveMembers").replace("\n", " | ")[:200])
    pg.click("#claudeLiveEvents button")
    pg.wait_for_timeout(500)
    print("  code_fix 내용:", pg.inner_text("#claudeLiveFix").replace("\n", " / ")[:160])
    pg.fill("#claudeLiveCid", "7")
    pg.fill("#claudeLiveText", "화면에서 보낸 말")
    pg.click("#claudeLiveCard button:has-text('보내기')")
    pg.wait_for_timeout(800)
    print("  보내기:", pg.inner_text("#claudeLiveMsg"), "· 남은 글:", repr(pg.input_value("#claudeLiveText")))
    assert "고친 줄" in pg.inner_text("#claudeLiveFix") and pg.inner_text("#claudeLiveMsg") == "보냈습니다"
    pg.screenshot(path=SHOT, full_page=False)
    print("  페이지 오류:", errs)
    b.close()
with cp._tx(st) as c:
    print("  화면에서 보낸 말 DB:", c.execute("SELECT text, delivered_at FROM claude_live_msgs ORDER BY id DESC LIMIT 1").fetchone()[:2])
print("끝 — 전부 통과")
os._exit(0)
