# -*- coding: utf-8 -*-
"""폰 공유 페이지의 제목·설명·태그 칸 점검(2026-10-18). 로컬 앱 + 시험 DB 로 실제 페이지를 폰 크기 크롬에서 연다.

사용: py tools/share_seo_check.py <스크린샷.png>
확인: ① 로그인 없이 /api/share/seo/<sid> 가 저장값을 준다 ② 영상 없는 링크(seo=1)는 영상 칸을 숨기고 제목·태그만
      ③ 칸마다 복사 버튼 ④ 만료 sid 는 403
"""
import json, os, sys, tempfile, time
sys.path.insert(0, ".")
tmp = tempfile.mkdtemp()
os.environ["SHOPPING_SHORTS_DB"] = os.path.join(tmp, "t.db")
from shopping_shorts import app as A
from shopping_shorts.store import Store
from fastapi.testclient import TestClient

st = Store(A.DB_PATH)
JID = "seochk" + str(int(time.time()))[-6:]
st.create_mix_job(JID, ["https://x"], 30, "auto")
st.update_mix_job(JID, seo={"title": "다들 이거 보고 충격받음! 자동 변기", "description": "설명 첫 줄\n둘째 줄",
                             "tags": ["스마트변기", "#자동변기"], "hashtags": {"instagram": ["#욕실", "#꿀템"]},
                             "insta_caption": "인스타 본문", "comment_bait": "댓글에 '변기'"})
sid = A._share_put(JID)
c = TestClient(A.app)
r = c.get(f"/api/share/seo/{sid}"); print("seo", r.status_code, r.json().get("title"), r.json().get("tags"))
print("expired", c.get("/api/share/seo/nope").status_code)
html = c.get(f"/s/{sid}").text
print("page has __SEO__ replaced:", "__SEO__" not in html, "video empty:", 'const V=""' in html)
from playwright.sync_api import sync_playwright
import threading, uvicorn
srv = uvicorn.Server(uvicorn.Config(A.app, host="127.0.0.1", port=8791, log_level="error"))
threading.Thread(target=srv.run, daemon=True).start(); time.sleep(3)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 1200}, is_mobile=True)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:8791/s/{sid}"); pg.wait_for_timeout(1500)
    info = pg.evaluate("""()=>({media:getComputedStyle(document.querySelector('.media')).display,
        seo:getComputedStyle(document.getElementById('seoBox')).display,
        fields:[...document.querySelectorAll('.fld .lb span')].map(x=>x.textContent),
        tags:(document.querySelectorAll('.fld .tx')[2]||{}).textContent})""")
    print(json.dumps(info, ensure_ascii=False)); print("errors", errs)
    pg.screenshot(path=sys.argv[1], full_page=True); b.close()
srv.should_exit = True
