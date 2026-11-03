# 관제 316 점검: 편집 화면 준비 과정에 일부러 오류를 넣고 편집 저장(/apply)이 나가는지 옛(main)/새(트랙) 판 비교. 쓰기는 전부 가짜 응답(고객 작업 안 바뀜).
import sys
sys.path.insert(0, r"C:/Users/TheRose/Desktop/로또의 주식")
from tools.live_admin import admin_page
SRC = {"옛": r"C:/Users/TheRose/Desktop/로또의 주식/shopping_shorts/static/scene_lab.html",
       "새": r"C:/Users/TheRose/Desktop/로또의 주식/.tracks/편집저장막힘/shopping_shorts/static/scene_lab.html"}
for name, path in SRC.items():
    html = open(path, encoding="utf-8").read()
    mark = "  autoOpenRoll();"
    assert mark in html, name
    html = html.replace(mark, "  throw new Error('시험오류');", 1)
    log = []
    def setup(pg, html=html, log=log):
        def h(route):
            r = route.request
            if r.method != "GET":
                log.append(r.url.split("/api/")[-1][:60])
                return route.fulfill(status=200, body='{"ok":true,"state":"building"}', content_type="application/json")
            if "scene_lab.html" in r.url:
                return route.fulfill(status=200, body=html, content_type="text/html; charset=utf-8")
            route.continue_()
        pg.route("**/*", h)
    with admin_page("scene_lab.html?job=4ab8d1e0c5d3", setup=setup) as pg:
        pg.wait_for_timeout(6000)
        b = pg.evaluate("() => _booting")
        log.clear()
        pg.evaluate("() => { _lastPersistedWork='x'; saveWork(); }")
        pg.wait_for_timeout(2500)
        print(name, "| 준비멈춤(_booting):", b, "| 편집 저장 요청(apply):", sum('/apply' in x for x in log), "| 오류:", pg.errors[:1])
