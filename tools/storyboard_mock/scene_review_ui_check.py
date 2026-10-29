"""장면 점검(관제 257) 화면 확인 — 라이브 관리자 화면에 이 폴더 produce.html 을 끼워(--local) 진짜 AI(서버·사장님 버텍스)로 누른다.

    py tools/storyboard_mock/scene_review_ui_check.py <work_id> [--local] [--row 7] [--shot <png>]

읽기 전용: 저장(POST)은 막는다. 통과시키는 POST 는 셋 — /scene_review·/api/script/chat(서버에서 이 폴더 코드로 판정),
/picks(짤·효과음·초 계산만, 저장 안 함).
  ① 줄 아래 [🔍 장면 점검] → 판정 카드(아이콘·이유·초) — 교체 제안이면 지금/제안 사진과 [이 장면으로 바꾸기]
  ② [이 장면으로 바꾸기] → 그 줄 장면(sbLiveIds = 확정·3단계로 넘어가는 값)이 제안 조각으로 바뀌고 [↩ 장면 되돌리기] → 원래대로
  ③ 대화창 "전체 장면 점검해줘" → 대화창 요약(유지·교체·없음 개수) + 글 있는 줄마다 카드
  ④ 대화창 "N번째 줄 문장 바꿔줘" → 제안 안에 장면 한 줄 판정 → [적용] 뒤 그 줄 카드가 새 문장 기준(낡음 아님)
--local 없이(라이브 그대로) 돌리면 ①에서 버튼이 없어 실패해야 한다 — 고치기 전 코드에서 실패하는 검사인지 확인용.
"""
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "storyboard_mock"))
import scene_review_check as SR          # noqa: E402
import sb_paste_chat_check as CH         # noqa: E402

ROWS_JS = "() => SB.made[SB.view].slots.map((sl,k)=>sbLiveIds(SB.view,k,sl))"


def main(argv):
    wid = argv[0]
    local = "--local" in argv
    row = int(argv[argv.index("--row") + 1]) - 1 if "--row" in argv else 6
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else ""
    SR.upload()
    CH._server_upload()
    from playwright.sync_api import sync_playwright
    from tools.live_admin import BASE, admin_cookie
    html = (ROOT / "shopping_shorts" / "static" / "produce.html").read_bytes()
    errs, posts, secs, res = [], [], [], {}
    ok = True
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1750, "height": 1000})
        ctx.add_cookies([{"name": "dash_auth", "value": admin_cookie(), "domain": "shoppingshorts.duckdns.org", "path": "/",
                          "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))

        def route(r):
            q = r.request
            if q.method != "GET":
                posts.append(q.url)
                t0 = time.time()
                if q.url.endswith("/scene_review"):
                    st, body = SR.serve(wid, q.post_data)
                    secs.append(("장면 점검", round(time.time() - t0, 1)))
                    return r.fulfill(status=st, content_type="application/json", body=body)
                if q.url.endswith("/api/script/chat"):
                    st, body = CH._server_chat(q.post_data or "{}", "0")
                    secs.append(("대화", round(time.time() - t0, 1)))
                    return r.fulfill(status=st, content_type="application/json", body=body)
                if q.url.endswith("/picks"):
                    return r.continue_()
                return r.abort()                      # 저장 막기 — 라이브 작업을 바꾸지 않는다
            if q.url.endswith("/api/script/chat/models"):
                st, body = CH._server_chat("{}", "0", "models")
                return r.fulfill(status=st, content_type="application/json", body=body)
            if local and q.resource_type == "document" and "/produce" in q.url:
                return r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
            return r.continue_()

        pg.route("**/*", route)
        pg.goto(BASE + "/produce?work=" + wid, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        ready = pg.evaluate("""async () => { const w=ms=>new Promise(r=>setTimeout(r,ms));
            for(let k=0;k<60&&!(window.STORYBOARD_ON&&SB.data&&Object.keys(SB.made||{}).length);k++) await w(500);
            if(!(window.STORYBOARD_ON&&Object.keys(SB.made||{}).length)) return null;
            if(!SB.made[SB.view]) SB.view=Object.keys(SB.made)[0]; cur=8; showPanel(); window.SCRIPT_CHAT_ON=true; sbRender(); return SB.view; }""")
        if not ready:
            print("✖ 스토리보드가 있는 작업을 못 열었다", errs[:2])
            return 1
        rows0 = pg.evaluate(ROWS_JS)
        # ① 🔍 장면 점검
        btn = pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="장면 점검")
        if not btn.count():
            print("✖ ① %d번 줄에 「🔍 장면 점검」 버튼이 없다(고치기 전 화면)" % (row + 1))
            b.close()
            return 1
        btn.first.click()
        pg.wait_for_function("() => !Object.keys(SB.revBusy).length && document.querySelector('#s2Storyboard .sb-rev:not(:empty)')", timeout=200000)
        pg.wait_for_timeout(500)
        card = pg.evaluate("""(i) => { const ek=SB.view, v=SB.rev[ek+'#'+i]; const el=document.querySelectorAll('#s2Storyboard .sb-row')[i].querySelector('.sb-rev');
            return {v: v?{verdict:v.verdict, why:v.why, ids:v.ids, cur:v.cur_ids}:null, text: el?el.innerText:'',
                    thumbs: el?el.querySelectorAll('.sb-rvth .sb-th').length:0, swapBtn: !!(el&&[...el.querySelectorAll('button')].some(x=>x.innerText.includes('이 장면으로 바꾸기')))}; }""", row)
        res["① 카드"] = card
        v = card["v"] or {}
        ok1 = bool(v) and v.get("verdict") in ("keep", "swap", "none") and len(v.get("why") or "") > 10 and card["text"]
        if v.get("verdict") == "swap":
            ok1 = ok1 and card["swapBtn"] and card["thumbs"] == len(v["cur"]) + len(v["ids"])
        ok &= bool(ok1)
        print("①", "통과" if ok1 else "실패", json.dumps(card, ensure_ascii=False)[:600])
        if shot:
            pg.locator("#s2Storyboard .sb-row").nth(row).screenshot(path=shot.replace(".png", "_row.png"))
        # ② 바꾸기 → 되돌리기
        if v.get("verdict") == "swap":
            pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="이 장면으로 바꾸기").click()
            pg.wait_for_timeout(2500)
            after = pg.evaluate(ROWS_JS)
            undo = pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="장면 되돌리기")
            has_undo = undo.count() > 0
            if has_undo:
                undo.first.click()
                pg.wait_for_timeout(2500)
            back = pg.evaluate(ROWS_JS)
            ok2 = after[row] == v["ids"] and all(after[k] == rows0[k] for k in range(len(rows0)) if k != row) and has_undo and back == rows0
            res["② 바꾸기"] = {"전": rows0[row], "후": after[row], "되돌림": back[row]}
            ok &= ok2
            print("②", "통과" if ok2 else "실패", res["② 바꾸기"])
        else:
            print("② 건너뜀 — 이 줄 판정이 교체가 아님(%s). --row 로 교체가 나오는 줄을 고르세요" % v.get("verdict"))
        # ③ 대화창 전체 점검
        pg.evaluate("() => { SB.rev={}; sbRender(); }")
        pg.fill("#sbChatIn", "전체 장면 점검해줘")
        pg.press("#sbChatIn", "Enter")
        t0 = time.time()
        while time.time() - t0 < 300:
            pg.wait_for_timeout(1500)
            if pg.evaluate("() => !SB.chat.busy && !Object.keys(SB.revBusy).length && SB.chat.msgs.some(m=>/교체 제안 \\d/.test(m.text||'')) ") or \
               pg.evaluate("() => !SB.chat.busy && SB.chat.msgs.slice(-1)[0] && SB.chat.msgs.slice(-1)[0].text.startsWith('❌')"):
                break
        st3 = pg.evaluate("""() => { const ek=SB.view, n=SB.made[ek].slots.filter((sl,k)=>String(sbLine(ek,k,sl)).trim()).length;
            return {last: SB.chat.msgs.slice(-1)[0].text, cards: document.querySelectorAll('#s2Storyboard .sb-row .sb-rev.keep,#s2Storyboard .sb-row .sb-rev.swap,#s2Storyboard .sb-row .sb-rev.none').length, lines: n}; }""")
        ok3 = "교체 제안" in st3["last"] and st3["cards"] == st3["lines"]
        res["③ 전체"] = st3
        ok &= ok3
        print("③", "통과" if ok3 else "실패", json.dumps(st3, ensure_ascii=False)[:700])
        if shot:
            pg.screenshot(path=shot)
        # ④ 문장 바꾸기 제안 안의 장면 판정 → 적용
        pg.evaluate("() => { SB.rev={}; sbRender(); }")
        pg.fill("#sbChatIn", "%d번째 줄 문장을 조금 더 짧게 바꿔줘" % (row + 1))
        pg.press("#sbChatIn", "Enter")
        pg.wait_for_function("() => !SB.chat.busy && (SB.chat.prop ? !SB.chat.prop.revBusy : SB.chat.msgs.slice(-1)[0].role==='ai')", timeout=300000)
        st4 = pg.evaluate("() => { const P=SB.chat.prop; return P?{changed:P.changed, rev:Object.keys(P.rev||{}), mini:[...document.querySelectorAll('.sb-rvmini')].map(x=>x.innerText)}:null; }")
        ok4 = bool(st4 and st4["changed"] and len(st4["rev"]) == len(st4["changed"]) and st4["mini"])
        if ok4:
            pg.locator(".sb-cprop button", has_text="적용").click()
            pg.wait_for_timeout(1500)
            k = st4["changed"][0]
            st4["after"] = pg.evaluate("(k) => { const el=document.querySelectorAll('#s2Storyboard .sb-row')[k].querySelector('.sb-rev'); return el?{cls:el.className, text:el.innerText.slice(0,200)}:null; }", k)
            ok4 = bool(st4["after"]) and "stale" not in st4["after"]["cls"]
        res["④ 제안"] = st4
        ok &= ok4
        print("④", "통과" if ok4 else "실패", json.dumps(st4, ensure_ascii=False)[:700])
        saves = [u for u in posts if not u.endswith(("/scene_review", "/api/script/chat", "/picks"))]
        print("막은 저장 요청", len(saves), "· AI 걸린 초", secs, "· 페이지 오류", errs)
        ok &= not errs
        b.close()
    print("결과:", "통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
