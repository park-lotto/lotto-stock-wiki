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
        r = client.post("/api/yt/analytics", content=body, headers={"Content-Type": "application/json"})
        route.fulfill(status=r.status_code, body=r.text,
                      headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
                               "Access-Control-Allow-Headers": "*"})

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1900, "height": 950}, locale="ko-KR")
        pg.route("https://shoppingshorts.duckdns.org/api/**",
                 lambda r: r.fulfill(status=200, body='{"ok":true}', headers={"Access-Control-Allow-Origin": "*"}))
        # 나중에 등록한 route 가 먼저 잡는다(playwright) — 분석 경로를 뒤에
        pg.route("https://shoppingshorts.duckdns.org/api/yt/analytics", handle)
        pg.goto("https://www.youtube.com/shorts/" + vid, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
        pg.evaluate("(function(){" + GM_SHIM + "})()")       # 유튜브는 Trusted Types 라 script 태그 주입이 막힌다 → evaluate 로
        pg.evaluate("(function(){" + logic + "\n})()")
        try:
            pg.wait_for_selector("#ss-ytstat svg rect", timeout=60000)
        except Exception:
            pg.screenshot(path=png.replace(".png", "_fail.png"))
            print("FAIL", pg.evaluate("""() => ({ver: window.__ssGrabVer, path: location.pathname,
                box: (document.getElementById('ss-ytstat') || {}).innerText || null,
                kw: !!document.getElementById('ss-kwpost')})"""))
            raise
        pg.wait_for_timeout(800)
        pg.locator("#ss-ytstat").screenshot(path=png)
        pg.screenshot(path=png.replace(".png", "_full.png"))
        info = pg.evaluate("""() => { var p = document.getElementById('ss-ytstat');
            return {text: p.innerText.slice(0, 600), bars: p.querySelectorAll('svg rect').length,
                    me: p.querySelectorAll('svg rect[fill="#ff9500"]').length}; }""")
        print(json.dumps(info, ensure_ascii=False, indent=1))
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
