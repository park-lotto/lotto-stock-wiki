"""유튜브 쇼츠 영상 분석 상자 실물 확인(관제 242).

진짜 유튜브 쇼츠 화면을 헤드리스로 열고 grab_logic.js 를 주입한다. 서버 호출(/api/yt/analytics)은
이 트랙의 app 엔드포인트를 TestClient 로 그대로 돌려 응답한다(가짜 값 아님 — 유튜브 API 실값).
결과: 상자 캡처 PNG + 상자 안 글자·막대 수를 출력한다.

    py tools/yt_analytics_check.py <쇼츠 id> <저장할 png>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient            # noqa: E402
from playwright.sync_api import sync_playwright      # noqa: E402

from shopping_shorts import app as appmod             # noqa: E402

GM_SHIM = """
window.GM_xmlhttpRequest = function (o) {
  fetch(o.url, {method: o.method, headers: o.headers, body: o.data})
    .then(function (r) { return r.text().then(function (t) { o.onload({status: r.status, responseText: t}); }); })
    .catch(function (e) { o.onerror && o.onerror(e); });
};
"""


def main(vid, png):
    client = TestClient(appmod.app)
    logic = open(os.path.join(os.path.dirname(appmod.__file__), "userscript", "grab_logic.js"), encoding="utf-8").read()

    def handle(route):
        body = route.request.post_data or "{}"
        path = "/" + route.request.url.split("/", 3)[3]
        r = client.post(path, content=body, headers={"Content-Type": "application/json"})
        route.fulfill(status=r.status_code, body=r.text,
                      headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
                               "Access-Control-Allow-Headers": "*"})

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])   # 재생 안 되면 <video> 가 화면 밖에 있어 버튼 줄이 숨는다(실측)
        pg = b.new_page(viewport={"width": 1900, "height": 950}, locale="ko-KR")
        # 관련 검색어 상자(/api/lens/kw/*)까지 이 트랙 app 으로 그대로 — 실제 자리 정렬을 보려면 그 상자가 있어야 한다
        pg.route("https://shoppingshorts.duckdns.org/api/**", handle)
        pg.goto("https://www.youtube.com/shorts/" + vid, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
        # 사장님 화면(캡쳐 61)처럼 관련 검색어 상자를 오른쪽 위로 옮겨 둔 상태를 재현
        pg.evaluate("localStorage.setItem('ss_drag:www.youtube.com:ss-kwpost', JSON.stringify({x: 1325, y: 108}))")
        pg.evaluate("(function(){" + GM_SHIM + "})()")       # 유튜브는 Trusted Types 라 script 태그 주입이 막힌다 → evaluate 로
        pg.evaluate("(function(){" + logic + "\n})()")
        try:
            pg.wait_for_selector("#ss-ytstat svg rect", timeout=60000)
        except Exception:
            pg.screenshot(path=png.replace(".png", "_fail.png"))
            print("VIDEOS", pg.evaluate("() => [...document.querySelectorAll('video')].map(v => { var r = v.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom), Math.round(r.width), Math.round(r.height)]; })"))
            print("FAIL", pg.evaluate("""() => ({ver: window.__ssGrabVer, path: location.pathname,
                box: (document.getElementById('ss-ytstat') || {}).innerText || null,
                kw: !!document.getElementById('ss-kwpost')})"""))
            raise
        try:
            pg.wait_for_function("() => { var k = document.querySelector('#ss-kwpost'); return k && k.querySelector('button.ss-kw-fold') && !/중…/.test(k.innerText); }", timeout=90000)
        except Exception:
            print("관련 검색어 상자 다 안 뜸(그대로 찍음)")
        pg.wait_for_timeout(1500)
        pg.locator("#ss-ytstat").screenshot(path=png)
        pg.screenshot(path=png.replace(".png", "_full.png"))
        info = pg.evaluate("""() => { var p = document.getElementById('ss-ytstat');
            return {text: p.innerText.slice(0, 600), bars: p.querySelectorAll('svg rect').length,
                    me: p.querySelectorAll('svg rect[fill="#ff9500"]').length,
                    box: p.getBoundingClientRect().toJSON(),
                    kw: (document.getElementById('ss-kwpost') || {getBoundingClientRect: () => null}).getBoundingClientRect()}; }""")
        print(json.dumps(info, ensure_ascii=False, indent=1))
        print("KW", pg.evaluate("""() => { var k = document.getElementById('ss-kwpost'); if (!k) return null;
            var cs = getComputedStyle(k); return {disp: cs.display, rect: k.getBoundingClientRect().toJSON(), style: k.getAttribute('style').slice(0, 300), text: k.innerText.slice(0, 300)}; }"""))
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
