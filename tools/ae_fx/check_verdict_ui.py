# 효과 견본 판정 달기(관제 125) 화면 점검 — 로컬 서버(8871)를 띄운 뒤: py tools/ae_fx/check_verdict_ui.py <스크린샷.png>
# 판정·쓰는 순간·메모를 눌러 저장 → 새로고침 뒤 유지 → 거르기 칸 수를 출력한다(A1 쓸 것·A2 못 씀을 실제로 기록하니 시험용 데이터 폴더에서만).
import json, sys
from playwright.sync_api import sync_playwright
U = "http://127.0.0.1:8871/fx_samples"
shot = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1300,"height":1000})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(U); pg.wait_for_selector(".card .vd button")
    print("카드", pg.locator(".card").count(), "판정버튼", pg.locator(".card .vd button").count())
    a1 = pg.locator('.card[data-id="A1"]')
    a1.locator(".vd button.use").click(); pg.wait_for_timeout(500)
    a1.locator(".mo .chip", has_text="훅 첫 줄").click(); pg.wait_for_timeout(500)
    a1.locator(".mo .chip", has_text="가격").click(); pg.wait_for_timeout(500)
    a1.locator(".memo").fill("쾅 훅에 좋음"); a1.locator(".memo").press("Tab"); pg.wait_for_timeout(600)
    pg.locator('.card[data-id="A2"] .vd button.no').click(); pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_selector(".card .vd button")
    a1 = pg.locator('.card[data-id="A1"]')
    print("새로고침 뒤 A1:", a1.get_attribute("class"), [c.inner_text() for c in a1.locator(".mo .chip.on").all()], a1.locator(".memo").input_value())
    print("A2:", pg.locator('.card[data-id="A2"]').get_attribute("class"))
    print("필터줄:", pg.locator("#filters").inner_text().replace("\n"," "))
    pg.locator("#filters .chip", has_text="쓸 것").click(); pg.wait_for_timeout(300)
    vis = [c.get_attribute("data-id") for c in pg.locator(".card").all() if c.is_visible()]
    print("쓸 것 거르기 보이는 카드:", vis, "보이는 묶음", sum(1 for s in pg.locator("section").all() if s.is_visible()))
    pg.locator("#filters .chip", has_text="미판정").click(); pg.wait_for_timeout(300)
    print("미판정 보이는 카드 수:", sum(1 for c in pg.locator(".card").all() if c.is_visible()))
    pg.locator("#filters .chip", has_text="전체").click(); pg.locator("#mfilters .chip", has_text="가격").click(); pg.wait_for_timeout(300)
    print("가격 거르기:", [c.get_attribute("data-id") for c in pg.locator(".card").all() if c.is_visible()])
    pg.locator("#mfilters .chip", has_text="전부").click(); pg.wait_for_timeout(300)
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(1500)
    pg.screenshot(path=shot)
    print("JS 오류:", errs)
    b.close()
