"""관제 183 검사 — 장면꾸미기 '내 프리셋'이 브라우저 저장소를 비워도 계정에서 되살아나는가.
실제 앱(트랙 코드)을 임시 DB로 띄우고 실제 크롬으로 편집기를 연다:
 ① 옛 방식처럼 localStorage에만 있던 프리셋 → 열면 계정으로 이관되는가
 ② 저장소를 통째로 비우고 다시 열면 목록이 서버에서 다시 뜨는가
 ③ 화면에서 '저장' 버튼으로 만든 프리셋도 서버에 들어가는가
쓰는 법: py tools/scene_preset_server_check.py"""
import os, sys, json, threading, time, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts import app as appmod
from shopping_shorts.store import Store
import uvicorn
from playwright.sync_api import sync_playwright

tmp = tempfile.mkdtemp(); db = os.path.join(tmp, "t.db")
appmod.DB_PATH = db; appmod._AUTH_ON = True; appmod.DASH_SECRET = "chk-secret"
s = Store(db); s.ensure_paywall_schema(); cid = s.create_customer("chk", "pw12")
try: s.approve_customer(cid)
except Exception: pass
PORT = 8793
threading.Thread(target=lambda: uvicorn.run(appmod.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True).start()
time.sleep(4)
URL = f"http://127.0.0.1:{PORT}/api/produce/scene-style/assets/out/scene-style-ui-showcase.html"
exp = int(time.time()) + 3600
KEY = "scene_style_my_presets"
old = [{"id": "old1", "name": "옛 브라우저 프리셋", "at": 1, "snap": {"presetId": "t11", "fontSet": "jalnan"}}]
def server_items():
    return s.get_pref("preset::" + KEY, customer_id=cid) or []
res = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()
    ctx.add_cookies([{"name": "dash_auth", "value": appmod._sign_session(cid, exp), "url": f"http://127.0.0.1:{PORT}"}])
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.evaluate(f"localStorage.setItem('{KEY}', {json.dumps(json.dumps(old, ensure_ascii=False))})")
    pg.reload(); pg.wait_for_timeout(4000)
    res["①이관"] = [x["name"] for x in server_items()]
    pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(4000)
    res["②비운뒤_화면사본"] = [x["name"] for x in json.loads(pg.evaluate(f"localStorage.getItem('{KEY}')") or "[]")]
    # ③ 화면의 저장 버튼
    pg.on("dialog", lambda d: d.accept("화면 저장 프리셋") if d.type == "prompt" else d.accept())
    btn = pg.locator("[data-my-save]")
    if btn.count() == 0:
        pg.evaluate("document.querySelector('[data-left-tab]')&&[...document.querySelectorAll('[data-left-tab]')].forEach(()=>0)")
    pg.evaluate("document.querySelector('[data-my-save]')?.click()"); pg.wait_for_timeout(2500)
    res["③저장버튼후_서버"] = [x["name"] for x in server_items()]
    pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(4000)
    res["③비운뒤_목록화면"] = pg.evaluate("[...document.querySelectorAll('.my-preset-card b')].map(x=>x.textContent)")
    res["JS오류"] = errs
    b.close()
for k, v in res.items(): print(k, v)
ok = ("옛 브라우저 프리셋" in res["①이관"] and res["②비운뒤_화면사본"] and "화면 저장 프리셋" in res["③저장버튼후_서버"]
      and "화면 저장 프리셋" in res["③비운뒤_목록화면"] and not res["JS오류"])
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
