"""관제 252 검사 — 장면꾸미기 '내 프리셋'의 채널명 + 마지막 적용 프리셋 기억.
실제 앱(트랙 코드)을 임시 DB로 띄우고 실제 크롬으로 편집기를 연다(브라우저 저장소는 매번 새 창 = 다른 PC 와 같다):
 ① 채널명 있는 프리셋(쓸데수집)을 '적용' → 채널명 칸·미리보기가 쓸데수집, 계정 목록에 usedAt 이 찍히는가
 ② 저장 버튼으로 만든 프리셋에 지금 채널명이 담기는가
 ③ 새 창(빈 저장소)에서 저장본 없는 새 영상을 열면 마지막에 적용한 프리셋(템플릿·채널명·워터마크)으로 시작하는가
 ④ 저장본 있는 영상은 마지막 프리셋을 안 건다(그 영상 설정 그대로)
 ⑤ ③에서 편집기가 만든 스냅샷을 그대로 렌더(render_layer_one = 썸네일, render_layers = 렌더·캡컷 공용)에 넣어
    채널명만 숏템메이커로 바꾼 것과 그림이 달라지는가(채널명이 결과물까지 가나)
쓰는 법: py tools/scene_preset_last_check.py   (고치기 전 코드에서는 ①③ 이 FAIL 이어야 한다)"""
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
PORT = 8794
threading.Thread(target=lambda: uvicorn.run(appmod.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True).start()
time.sleep(4)
URL = f"http://127.0.0.1:{PORT}/api/produce/scene-style/assets/out/scene-style-ui-showcase.html"
CTX = json.load(open(os.path.join(ROOT, "tools", "fixtures", "scene_style_context_sample.json"), encoding="utf-8"))["context"]
KEY = "preset::scene_style_my_presets"
WM = {"watermark": {"on": True, "text": "ⓒ 쓸데수집", "x": 50, "y": 90, "size": 4.8, "opacity": 34, "color": "#ffffff", "align": "center"}}
s.set_pref(KEY, [
    {"id": "p_ssul", "name": "쓸데수집", "at": 2, "snap": {"version": 1, "mode": "story", "presetId": "s0101", "branding": WM, "channel": "쓸데수집"}},
    {"id": "p_old", "name": "옛 프리셋", "at": 1, "snap": {"version": 1, "mode": "story", "presetId": "t11"}},
], customer_id=cid)
STATE = """() => ({tpl: window.sceneStyle?.snapshot?.()?.presetId, channel: document.querySelector('[data-field-key="channel"] input,[data-field-key="channel"] textarea')?.value,
  shown: [...document.querySelectorAll('[data-preview-channel]')].map(x=>x.textContent)[0], snapChannel: window.sceneStyle?.snapshot?.()?.text?.channel,
  wm: [...document.querySelectorAll('.scene-brand-ink')].map(x=>x.textContent)})"""
exp = int(time.time()) + 3600
res = {}

def fresh(b):
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    ctx.add_cookies([{"name": "dash_auth", "value": appmod._sign_session(cid, exp), "url": f"http://127.0.0.1:{PORT}"}])
    pg = ctx.new_page(); pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)[:200]))
    pg.on("dialog", lambda d: d.accept("화면 저장") if d.type == "prompt" else d.accept())
    pg.goto(URL); pg.wait_for_timeout(4000)
    return ctx, pg

def send_ctx(pg, snapshot):
    pg.evaluate("([c,s])=>window.postMessage({type:'scene-style-context',context:c,snapshot:s},location.origin)", [CTX, snapshot])
    pg.wait_for_timeout(3500)

with sync_playwright() as p:
    b = p.chromium.launch()
    # ① 적용
    c1, pg = fresh(b)
    pg.click('[data-left-tab="mine"]'); pg.wait_for_timeout(800)
    pg.locator('[data-my-id="p_ssul"] [data-my-apply]').click(); pg.wait_for_timeout(2500)
    res["①적용후"] = pg.evaluate(STATE)
    res["①usedAt"] = [x.get("usedAt") for x in s.get_pref(KEY, customer_id=cid) if x["id"] == "p_ssul"][0]
    # ② 저장 버튼 — 지금 채널명(쓸데수집)이 담기는가
    pg.evaluate("document.querySelector('[data-my-save]')?.click()"); pg.wait_for_timeout(2500)
    saved = [x for x in s.get_pref(KEY, customer_id=cid) if x["name"] == "화면 저장"]
    res["②저장본_채널명"] = saved[0]["snap"].get("channel") if saved else None
    # 마지막 적용 = 쓸데수집 으로 되돌려 둔다(저장도 usedAt 을 찍으므로)
    pg.locator('[data-my-id="p_ssul"] [data-my-apply]').click(); pg.wait_for_timeout(2000)
    res["JS오류①②"] = pg.errs; c1.close()
    # ③ 새 창 + 저장본 없는 새 영상
    c3, pg = fresh(b)
    send_ctx(pg, None); pg.wait_for_timeout(1500)
    res["③새영상"] = pg.evaluate(STATE); res["JS오류③"] = pg.errs
    snap3 = pg.evaluate("window.sceneStyle.snapshot()"); c3.close()
    # ④ 저장본 있는 영상 — 그 영상 설정(t11·계정채널) 그대로여야 한다
    c4, pg = fresh(b)
    send_ctx(pg, {"version": 1, "mode": "story", "presetId": "t11", "text": dict(CTX["text"])}); pg.wait_for_timeout(1500)
    res["④저장본영상"] = pg.evaluate(STATE); res["JS오류④"] = pg.errs; c4.close()
    b.close()
# ⑤ 결과물: 같은 스냅샷에서 채널명만 바꿔 렌더 → 그림이 달라야 한다
from shopping_shorts import scene_style
from PIL import Image, ImageChops
tts = os.path.join(tmp, "v.wav"); open(tts, "wb").close()
timeline = [{"beat_idx": i, "t0": i, "dur": 1, "narration": c, "caption_lines": [c], "tts_path": tts, "target_seconds": 1,
             "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": i, "end": i + 1}}
            for i, c in enumerate(["주부들도 감탄한 천재 아이디어", "이건 바로 핑거 찹스틱"])]
for k in ("sceneTexts", "captionTexts", "effects"): snap3.pop(k, None)
shots = {}
for ch in ("쓸데수집", "숏템메이커"):
    sn = json.loads(json.dumps(snap3)); sn["text"]["channel"] = ch; sn["sceneIndex"] = 0
    shots[ch] = scene_style.render_layer_one(timeline, sn, os.path.join(tmp, "r_" + str(len(shots))), 0)
a_img, b_img = Image.open(shots["쓸데수집"]).convert("RGBA"), Image.open(shots["숏템메이커"]).convert("RGBA")
box = ImageChops.difference(a_img.convert("RGB"), b_img.convert("RGB")).getbbox()   # RGBA 그대로면 getbbox 가 알파만 본다(둘 다 불투명이면 None)
res["⑤렌더_채널명차이영역"] = box
out_png = os.path.join(tmp, "render_ssul.png"); a_img.convert("RGB").resize((a_img.width // 3, a_img.height // 3)).save(out_png)
res["⑤렌더그림"] = out_png
layers = scene_style.render_layers(timeline, dict(json.loads(json.dumps(snap3)), sceneIndex=0), os.path.join(tmp, "layers"))
res["⑤render_layers"] = bool(layers)
for k, v in res.items(): print(k, json.dumps(v, ensure_ascii=False))
a, n, o = res["①적용후"], res["③새영상"], res["④저장본영상"]
ok = (a["channel"] == "쓸데수집" and a["shown"] == "쓸데수집" and a["snapChannel"] == "쓸데수집" and res["①usedAt"]
      and res["②저장본_채널명"] == "쓸데수집"
      and n["tpl"] == "s0101" and n["channel"] == "쓸데수집" and n["snapChannel"] == "쓸데수집" and "ⓒ 쓸데수집" in n["wm"]
      and res["⑤렌더_채널명차이영역"] and res["⑤렌더_채널명차이영역"][1] < 400 and res["⑤render_layers"]
      and o["tpl"] == "t11" and o["channel"] == "계정채널"
      and not (res["JS오류①②"] or res["JS오류③"] or res["JS오류④"]))
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
