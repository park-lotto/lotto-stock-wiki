# -*- coding: utf-8 -*-
"""레퍼런스 랭킹 상단 정리(관제 136) 결과물 검사 — 라이브 화면을 관리자로 열어 **눈에 보이는 것**을 잰다.

    py tools/ranking_topbar_check.py                 # 지금 라이브 그대로
    py tools/ranking_topbar_check.py --local         # 라이브 데이터 + 이 폴더의 index.html (배포 전 확인)
    py tools/ranking_topbar_check.py --shot out.png  # 화면도 저장

재는 것(전부 실제 화면 기준):
  1) 숨김: 키워드·등록채널 패널(#seedPanel) · 카테고리 수집(#ytCatBox) · 채널당 2개 줄(.fcount-row) 이 안 보인다
  2) 줄: 골라보기 한 줄(#pickRow)만 있고 '전체'가 하나 — 보이는 버튼 건수는 전부 1 이상
  3) 골라보기 버튼을 누르면 그 버튼 건수 = 채널당 상한을 푼 카드 수(200장 넘으면 200)
  4) 검색국가 버튼이 검색창 줄에 있고, 누르면 칩이 펼쳐지며, 버튼 글자의 나라 수 = 켠 칩 수
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.live_admin import BASE, admin_cookie  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_VIS = """(sel)=>{const e=document.querySelector(sel); if(!e) return null;
  const r=e.getBoundingClientRect(); return !!(r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden');}"""

_PICKS = """()=>[...document.querySelectorAll('#pickRow .ftog')].filter(b=>b.getBoundingClientRect().width>0)
  .map(b=>({key:b.dataset.g?('g:'+b.dataset.g):b.dataset.t?('t:'+b.dataset.t):'all',
            text:b.textContent.trim(), n:b.querySelector('b')?parseInt(b.querySelector('b').textContent,10):null,
            on:b.classList.contains('on')}))"""


def main(argv):
    local = "--local" in argv
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else None
    from playwright.sync_api import sync_playwright
    fails, notes = [], []

    def check(ok, msg):
        (notes if ok else fails).append(("OK   " if ok else "FAIL ") + msg)

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1500, "height": 1100})
        ctx.add_cookies([{"name": "dash_auth", "value": admin_cookie(), "domain": "shoppingshorts.duckdns.org",
                          "path": "/", "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
        if local:
            body = io.open(os.path.join(HERE, "shopping_shorts", "static", "index.html"), encoding="utf-8").read()
            pg.route(BASE + "/", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=body))
        pg.goto(BASE + "/", wait_until="domcontentloaded")
        pg.wait_for_function("typeof STATE!=='undefined' && STATE.items && STATE.items.length>0", timeout=60000)
        pg.wait_for_timeout(2500)
        print("판: %s · 플랫폼 %s · 받은 건수 %s" % ("이 폴더 index.html" if local else "라이브 그대로",
                                              pg.evaluate("PLATFORM"), pg.evaluate("STATE.items.length")))

        # 1) 숨김
        for sel, name in (("#seedPanel", "키워드·등록채널 패널"), ("#ytCatBox", "카테고리 수집"),
                          (".fcount-row", "채널당 2개 줄"), ("#status", "수집분 안내 글")):
            v = pg.evaluate(_VIS, sel)
            if sel == "#status":
                t = pg.evaluate("document.getElementById('status').textContent")
                check("수집분" not in t or "⚠" in t, "%s 없음 (지금 글: %r)" % (name, t[:40]))
            else:
                check(v is False, "%s 안 보임 (실측 %s)" % (name, v))

        # 2) 줄 구성
        check(pg.evaluate("!!document.getElementById('pickRow')"), "골라보기 줄(#pickRow) 있음")
        alls = pg.evaluate("[...document.querySelectorAll('.filters .ftog')].filter(b=>b.getBoundingClientRect().width>0 && b.textContent.trim()==='전체').length")
        check(alls <= 1, "필터 줄의 '전체' 버튼 %d개(1개 이하여야 함)" % alls)
        labels = pg.evaluate("[...document.querySelectorAll('.flabel')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.textContent.trim())")
        check("뱃지로 보기" not in labels and "이번 주 추세" not in labels, "옛 두 줄 라벨 없음 (보이는 라벨 %s)" % labels)
        picks = pg.evaluate(_PICKS) if pg.evaluate("!!document.getElementById('pickRow')") else []
        print("골라보기 버튼:", [x["text"] for x in picks])
        for x in picks:
            if x["key"] != "all":
                check(x["n"] is not None and x["n"] > 0, "보이는 버튼 '%s' 건수 1 이상" % x["text"])

        # 3) 누르면 건수 = 카드 수 (채널당 상한을 풀고 잰다)
        if picks:
            pg.evaluate("if(PER_CHANNEL_ON) togglePerChannel()")
            for x in [q for q in picks if q["key"] != "all"]:
                kind, key = x["key"].split(":")
                pg.evaluate("(a)=>a[0]==='g'?setGrade(a[1]):setTrend(a[1])", [kind, key])
                pg.wait_for_timeout(600)
                cards = pg.evaluate("document.querySelectorAll('#cards > .card').length")
                on_n = pg.evaluate("[...document.querySelectorAll('#pickRow .ftog.on')].length")
                check(cards == min(x["n"], 200), "'%s' 누름 → 카드 %d장 (버튼 건수 %d)" % (x["text"], cards, x["n"]))
                check(on_n == 1, "'%s' 누름 → 켜진 버튼 %d개(택1)" % (x["text"], on_n))
            pg.evaluate("setPick('')")
            pg.wait_for_timeout(400)
            check(pg.evaluate("document.getElementById('pickAll').classList.contains('on')"), "전체로 되돌리면 '전체'가 켜짐")
            # 다시 접기 버튼이 바닥에 있나(위 버튼을 숨겼으므로 되돌릴 길)
            check(pg.evaluate("[...document.querySelectorAll('#cards button')].some(b=>b.textContent.includes('다시 접기'))"),
                  "채널당 상한을 푼 상태 → 바닥에 '다시 접기' 버튼")
            pg.evaluate("if(!PER_CHANNEL_ON) togglePerChannel()")
            pg.wait_for_timeout(400)

        # 4) 검색국가
        in_search_row = pg.evaluate("""()=>{const w=document.getElementById('lensLocales'), s=document.getElementById('rankSearch');
            return !!(w && s && w.parentElement===s.parentElement && w.getBoundingClientRect().width>0)}""")
        check(in_search_row, "검색국가가 검색창 줄에 보임")
        if in_search_row:
            txt = pg.evaluate("document.getElementById('lensLocaleBtn').textContent")
            pg.click("#lensLocaleBtn")
            pg.wait_for_timeout(300)
            chips = pg.evaluate("[...document.querySelectorAll('#lensLocaleChips .ftog')].filter(b=>b.getBoundingClientRect().width>0).map(b=>[b.textContent.trim(), b.classList.contains('on')])")
            on = [c[0] for c in chips if c[1]]
            check(len(chips) > 0, "버튼 누름 → 칩 %d개 펼쳐짐" % len(chips))
            check(all(lbl in txt for lbl in on) and len(on) > 0, "버튼 글자 %r 에 켠 나라 %s 전부" % (txt, on))
            param = pg.evaluate("lensLocalesParam()")
            check(len([k for k in param.split(",") if k]) == len(on), "렌즈가 보낼 나라 %r = 켠 칩 %d개" % (param, len(on)))
            if shot:
                pg.screenshot(path=shot.replace(".png", "_국가펼침.png"), clip={"x": 0, "y": 0, "width": 1500, "height": 700})
            pg.mouse.click(1200, 900)
            pg.wait_for_timeout(300)
            check(pg.evaluate(_VIS, "#lensLocalePop") is False, "바깥을 누르면 닫힘")
            box = pg.evaluate("(()=>{const p=document.getElementById('lensLocalePop');p.style.display='block';const r=p.getBoundingClientRect();p.style.display='none';return [r.left,r.right,innerWidth]})()")
            check(box[0] >= 0 and box[1] <= box[2], "펼침 상자가 화면 안 (좌 %d · 우 %d · 화면 %d)" % tuple(box))
        if shot:
            pg.evaluate("window.scrollTo(0,0)")
            pg.screenshot(path=shot, clip={"x": 0, "y": 0, "width": 1500, "height": 700})
        # 5) 다른 플랫폼(인스타) — 추세 버튼은 조회수 축에만. 넘어가도 화면이 안 죽는다.
        pg.evaluate("switchPlatform('instagram', document.querySelector('#platformTabs .ctype[data-platform=\"instagram\"]'))")
        pg.wait_for_timeout(4000)
        tv = pg.evaluate("[...document.querySelectorAll('#trendFilters .ftog')].filter(b=>b.getBoundingClientRect().width>0).length")
        check(tv == 0, "인스타 탭 → 추세 버튼 %d개 보임(0이어야 함)" % tv)
        print("인스타 골라보기:", [x["text"] for x in pg.evaluate(_PICKS)], "· 카드", pg.evaluate("document.querySelectorAll('#cards > .card').length"))
        check(not errors, "화면 오류 0건 %s" % (errors[:2] if errors else ""))
        if False:
            pg.evaluate("window.scrollTo(0,0)")
            pg.screenshot(path=shot, clip={"x": 0, "y": 0, "width": 1500, "height": 700})
        b.close()

    for line in notes + fails:
        print(line)
    print("결과: 통과 %d · 실패 %d" % (len(notes), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
