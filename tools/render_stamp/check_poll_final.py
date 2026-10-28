"""9단계 최종 렌더 화면 — 렌더 중에 서버가 결과를 버리면(status=ready_for_review) 무한 대기 대신 안내가 뜨는가(관제 122).
  py tools/render_stamp/check_poll_final.py [출력폴더]
진짜 앱(격리 DB·로그인 끔)으로 /produce 를 열고, 렌더 중 화면을 만든 뒤 상태 API 만 가로채
ready_for_review / done / rendering 을 돌려주며 **실제 pollFinal** 을 돌린다. 화면 글자·버튼·스크린샷을 남긴다.
옛 화면(수정 전)에서는 ready_for_review 칸이 실패해야 한다(무한 '렌더 중')."""
import sys, time, shutil, threading, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools/render_stamp/_out").resolve()
out.mkdir(parents=True, exist_ok=True)
work = out / "_work"; shutil.rmtree(work, ignore_errors=True); work.mkdir()
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright
module.DB_PATH = str(work / "qa.db"); module._AUTH_ON = False
PORT = 8798
server = uvicorn.Server(uvicorn.Config(module.app, host="127.0.0.1", port=PORT, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(2)

RENDER_BOX = """
MIX_JOB='qa_job';
document.getElementById('finalVideo').innerHTML='<div id="rfBar" style="width:40%">bar</div><div>숏템메이커 최종 렌더 중</div>';
const b=document.getElementById('btnFinalRender'); if(b.dataset.orig==null) b.dataset.orig=b.innerHTML; b.disabled=true; b.innerHTML='렌더 중…';
_rfStart=Date.now(); clearInterval(_rfTimer); _rfTimer=setInterval(_rfTick,1000);
"""
results, fails = [], 0
with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    state = {"status": "rendering"}
    def handle(route):
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"ok": True, "status": state["status"], "error": None}))
    pg.route("**/api/mix/status/qa_job", handle)
    pg.route("**/api/mix/video/qa_job", lambda r: r.fulfill(status=404, body=""))
    pg.goto(f"http://127.0.0.1:{PORT}/produce", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    # 9단계 칸은 job 이 없으면 숨어 있다 — 조상 display:none 을 풀어 실제 칸을 보이게 한다
    pg.evaluate("""(()=>{let e=document.getElementById('finalVideo');while(e){if(getComputedStyle(e).display==='none')e.style.display='block';e=e.parentElement;}})()""")
    for st, want_box_gone, want_btn_enabled, want_text in [
        ("rendering", False, False, None),
        ("ready_for_review", True, True, "설정이 바뀌어 다시 렌더가 필요해요"),
        ("done", True, True, "렌더 완료"),
    ]:
        state["status"] = st
        pg.evaluate(RENDER_BOX)
        pg.evaluate("pollFinal()"); pg.wait_for_timeout(1200)
        txt = pg.evaluate("(document.getElementById('finalStatus')||{}).textContent||''")
        btn_dis = pg.evaluate("document.getElementById('btnFinalRender').disabled")
        btn_label = pg.evaluate("document.getElementById('btnFinalRender').textContent.trim()")
        box = pg.evaluate("!!document.getElementById('rfBar')")
        ok = (box != want_box_gone) and ((not btn_dis) == want_btn_enabled) and (want_text is None or want_text in txt)
        if want_btn_enabled and "렌더 중" in btn_label:
            ok = False                      # 버튼이 풀렸는데 글자가 그대로 '렌더 중'이면 고객은 멈춘 줄 안다
        fails += 0 if ok else 1
        shot = out / f"poll_{st}.png"
        area = pg.locator("#btnFinalRender").locator("xpath=ancestor::*[.//*[@id='finalVideo']][1]")
        area.screenshot(path=str(shot))
        results.append({"status": st, "ok": ok, "text": txt.strip()[:120], "btn_disabled": btn_dis, "btn": btn_label, "render_box": box, "shot": shot.name})
        pg.evaluate("clearInterval(MIX_POLL); clearInterval(_rfTimer)")
    br.close()
for r in results: print(json.dumps(r, ensure_ascii=False))
print("page errors:", errs[:3])
print("FAIL" if fails or errs else "PASS", f"{len(results)-fails}/{len(results)}")
sys.exit(1 if fails else 0)
