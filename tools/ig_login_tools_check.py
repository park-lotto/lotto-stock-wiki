"""관제 151 로그인 화면 점검 — 인스타 검색 화면의 숫자 배지·좋아요순·동시 미리보기.

로그인 세션 하나(storage_state)로 **검색 화면 1번만** 연다(계정 보호: 집 IP·읽기만).
확장처럼: ig_main.js(메인월드, 페이지 시작 전) + grab_logic.js(페이지 뒤). 서버 검색어 API는 가짜 응답.
  ① 카드 배지에 ❤·⏱가 붙나(ig_main → postMessage → _igMedia)
  ② '❤ 좋아요순' 목록이 뜨고 좋아요 내림차순인가
  ③ 카드 3개에 마우스를 차례로 올린 뒤 떠나도 3개가 같이 재생 중인가(paused=false)
사용: py tools/ig_login_tools_check.py <storage_state.json> [--logic 다른판.js] [--shot 파일.png]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main_world(logic_text, fn="_igMainWorld"):
    """zip 빌더(app._serve_grab_extension)와 같은 규칙으로 메인월드 함수를 잘라낸다."""
    head = "  function " + fn + "() {"
    i = logic_text.find(head)
    if i < 0:
        return ""
    rest = logic_text[i + len(head):]
    end = rest.find("\n  }")
    return "(function () {" + rest[:end] + "\n})();" if end >= 0 else ""


STUB = r"""window.GM_xmlhttpRequest=function(o){var r={ok:true,main:"x",related:[]};
if(o.url.indexOf("/kw/multi")>=0)r={ok:true,candidates:[]};
setTimeout(function(){o.onload({status:200,responseText:JSON.stringify(r)})},50)};"""


def run(state, logic, shot=None):
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(storage_state=state, viewport={"width": 1500, "height": 950}, locale="ko-KR", bypass_csp=True)
        mw = main_world(logic)
        res["main_world_len"] = len(mw)
        if mw:
            ctx.add_init_script(mw)
        ctx.add_init_script(STUB)
        pg = ctx.new_page()
        pg.goto("https://www.instagram.com/explore/search/keyword/?q=amazon%20range%20hood", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        if "/accounts/login" in pg.url or "/challenge" in pg.url:
            return {"ABORT": pg.url}
        pg.add_script_tag(content=logic)
        pg.wait_for_timeout(5000)
        res["main_count"] = pg.evaluate("()=>window.__ssIgCount||0")
        res["badges"] = pg.evaluate("""()=>[...document.querySelectorAll('.ss-card-info')].map(e=>e.textContent).slice(0,6)""")
        res["badges_with_likes"] = pg.evaluate("""()=>[...document.querySelectorAll('.ss-card-info')].filter(e=>e.textContent.indexOf('❤')>=0).length""")
        res["cards"] = pg.evaluate("""()=>document.querySelectorAll('.ss-card-info').length""")
        btn = pg.query_selector("#ss-kwbar button:has-text('좋아요순')")
        if btn:
            btn.click()
            pg.wait_for_timeout(800)
            res["rank"] = pg.evaluate("""()=>{const o=document.getElementById('ss-ig-rank');if(!o)return null;
               const t=[...o.querySelectorAll('a')].map(a=>a.innerText.split('\\n')[1]||'');
               return {n:t.length, head:o.querySelector('div div:nth-child(2)')?.textContent||'', first:t.slice(0,3)}}""")
            if shot:
                pg.screenshot(path=shot)
            pg.evaluate("()=>{const o=document.getElementById('ss-ig-rank'); if(o) o.remove();}")
        cards = pg.query_selector_all('a[href*="/p/"],a[href*="/reel/"]')
        for i in range(min(3, len(cards))):
            cards[i].hover(timeout=5000)
            pg.wait_for_timeout(2500)
        pg.mouse.move(3, 300)
        pg.wait_for_timeout(2500)
        res["pv_tries"] = pg.evaluate("()=>window.__ssPvTries||0")
        res["after_leave"] = pg.evaluate("""()=>[...document.querySelectorAll('a video')].map(v=>({paused:v.paused,keep:!!v.__ssKeep}))""")
        b.close()
    return res


def judge(r):
    if r.get("ABORT"):
        return ["중단: " + r["ABORT"]]
    f = []
    if not r.get("main_world_len"):
        f.append("메인월드 함수가 없다")
    if not r.get("badges_with_likes"):
        f.append("카드 배지에 ❤ 숫자가 없다: " + str(r.get("badges")))
    rk = r.get("rank") or {}
    if not rk.get("n"):
        f.append("좋아요순 목록이 비었다")
    playing = sum(1 for v in r.get("after_leave") or [] if not v["paused"])
    if playing < 3:
        f.append(f"마우스 떠난 뒤 재생 중 {playing}개(3개 이상이어야)")
    return f


if __name__ == "__main__":
    state = sys.argv[1]
    logic = (ROOT / "shopping_shorts" / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
    if "--logic" in sys.argv:
        logic = Path(sys.argv[sys.argv.index("--logic") + 1]).read_text(encoding="utf-8")
    shot = sys.argv[sys.argv.index("--shot") + 1] if "--shot" in sys.argv else None
    r = run(state, logic, shot)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3000])
    f = judge(r)
    print("PASS" if not f else "FAIL\n- " + "\n- ".join(f))
    sys.exit(0 if not f else 1)
