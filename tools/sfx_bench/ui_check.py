# -*- coding: utf-8 -*-
"""3단계 [🔊 썰 효과음 자동 넣기] 스위치 실브라우저 검증.

임시 DB에 썰 대본(발명품형) job과 사회증거형 job을 만들고, 로그인 게이트만 끈 실제 앱을 띄워
헤드리스 크롬으로 produce.html 3단계를 연다.
  ① 썰 job → 스위치가 보이고 켜져 있다   ② 누르면 DB deco.sfx_pack='off'로 저장
  ③ 새로고침해도 꺼진 채 유지             ④ 사회증거형 job → 스위치는 보이되 꺼져 있고, 켜면 저장된다
사용: py tools/sfx_bench/ui_check.py [--shot 폴더]
"""
import argparse, os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts.store import Store          # noqa: E402
from shopping_shorts import app as A             # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--shot", default=tempfile.gettempdir()); a = ap.parse_args()
tmp = Path(tempfile.mkdtemp(prefix="sfxui_")); db = tmp / "t.db"
st = Store(str(db))
sul = st.add_spine("유튜브 「OO도 당황한 천재 발명품」", fit_categories=["발명품형"], status="approved")
soc = st.add_spine("사회증거형", fit_categories=["기타", "사회증거형"], status="approved")
st.set_setting("sfx_pack_enabled", "1")
for jid, sp in (("jsul0001", sul), ("jsoc0001", soc)):
    st.create_mix_job(jid, ["https://x/1"], 25, "free", customer_id=0, script_structure={"script_style_id": sp})
    roles = ["훅", "미끼", "공개", "고조1", "반전", "마무리"] if jid == "jsul0001" else ["situation", "notice", "ask", "method", "result"]
    st.update_mix_job(jid, edit_plan={"beats": [{"beat_idx": i, "role": r, "narration": "줄"} for i, r in enumerate(roles)]})
A.DB_PATH = str(db); A._AUTH_ON = False
import uvicorn                                    # noqa: E402
PORT = 8793
th = threading.Thread(target=lambda: uvicorn.run(A.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True)
th.start(); time.sleep(4)

from playwright.sync_api import sync_playwright  # noqa: E402
ok = True
def check(cond, msg):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + msg); ok &= bool(cond)

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{PORT}/produce.html", wait_until="domcontentloaded"); time.sleep(3)

    def open_job(jid):
        pg.evaluate(f"() => {{ MIX_JOB = '{jid}'; if (typeof stepGo==='function') stepGo('mix'); return sfxPackRefresh(true); }}")
        time.sleep(1.5)

    print("① 썰 대본 job")
    open_job("jsul0001")
    vis = pg.evaluate("() => { const b=document.getElementById('sfxPackBar'); return !!b && getComputedStyle(b).display!=='none' && b.offsetParent!==null; }")
    check(vis, "스위치가 화면에 보인다")
    check(pg.is_checked("#sfxPackToggle"), "처음엔 켜져 있다")
    pg.screenshot(path=str(Path(a.shot) / "sfx_toggle_on.png"), clip=pg.locator("#sfxPackBar").bounding_box() or None)
    print("② 눌러서 끄기")
    pg.click("#sfxPackToggle"); time.sleep(1.2)
    check(Store(str(db)).get_mix_job("jsul0001")["deco"].get("sfx_pack") == "off", "DB에 deco.sfx_pack='off' 저장")
    check("껐어요" in pg.inner_text("#sfxPackInfo"), "안내 문구가 '껐어요'로 바뀜")
    print("③ 새로고침 후")
    pg.reload(wait_until="domcontentloaded"); time.sleep(3); open_job("jsul0001")
    check(not pg.is_checked("#sfxPackToggle"), "꺼진 채 유지")
    pg.screenshot(path=str(Path(a.shot) / "sfx_toggle_off.png"), clip=pg.locator("#sfxPackBar").bounding_box() or None)
    pg.click("#sfxPackToggle"); time.sleep(1.2)
    check(Store(str(db)).get_mix_job("jsul0001")["deco"].get("sfx_pack") == "auto", "다시 켜면 'auto' 저장")
    print("④ 사회증거형 job — 보이되 기본 꺼짐, 켜면 들어간다")
    open_job("jsoc0001")
    vis2 = pg.evaluate("() => { const b=document.getElementById('sfxPackBar'); return getComputedStyle(b).display!=='none'; }")
    check(vis2, "스위치가 보인다")
    check(not pg.is_checked("#sfxPackToggle"), "기본은 꺼짐")
    check("체크하면" in pg.inner_text("#sfxPackInfo"), "안내 문구가 켜보라고 안내")
    pg.click("#sfxPackToggle"); time.sleep(1.2)
    check(Store(str(db)).get_mix_job("jsoc0001")["deco"].get("sfx_pack") == "auto", "켜면 저장된다")
    check(not errs, f"페이지 오류 없음 {errs[:2]}")
    b.close()
print("결과:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
