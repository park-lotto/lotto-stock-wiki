"""시안 v4 브라우저 점검 — 실제 크롬으로 열어 탭·정렬·상세·즐겨찾기·CSV·휴대폰 폭을 눌러 보고 스크린샷을 남긴다.
실행: py -I check4.py  → work/shots/v4_*.png, 콘솔 오류·탭별 행 수 출력"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.abspath(os.path.join(HERE, "..", "..", "out", "인기상품랭킹_시안_v4.html"))
SH = os.path.join(HERE, "work", "shots"); os.makedirs(SH, exist_ok=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 950}, accept_downloads=True)
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///" + HTML.replace("\\", "/")); pg.wait_for_timeout(800)
    tabs = pg.eval_on_selector_all("[data-tab]", "els => els.map(e => [e.dataset.tab, e.innerText.split(String.fromCharCode(10)).join(' ')])")
    for tid, label in tabs:
        pg.click(f"[data-tab='{tid}']"); pg.wait_for_timeout(200)
        n = pg.eval_on_selector_all("tr.r", "e => e.length")
        print(f"탭 {label:<22} 표시 행 {n}")
    pg.click("[data-tab='hot']"); pg.wait_for_timeout(200); pg.screenshot(path=os.path.join(SH, "v4_hot.png"))
    first = pg.eval_on_selector("tr.r", "e => e.dataset.kw") if pg.query_selector("tr.r") else None
    # 정렬: 월 검색 열 두 번 누르면 방향이 바뀌나
    pg.click("[data-tab='best']"); pg.click("th[data-sort='search']"); a = pg.eval_on_selector_all("tr.r td.num", "e => e[0] && e[0].innerText")
    pg.click("th[data-sort='search']"); bb = pg.eval_on_selector_all("tr.r td.num", "e => e[0] && e[0].innerText"); print("정렬 뒤집힘:", a != bb, a, "→", bb)
    # 상세
    pg.click("[data-tab='hot']"); pg.click("tr.r"); pg.wait_for_timeout(400)
    print("상세 열림:", pg.eval_on_selector("#drawer", "e => e.classList.contains('open')"), "| 상세 제목:", pg.inner_text("#drawer h2"))
    pg.screenshot(path=os.path.join(SH, "v4_drawer.png")); pg.keyboard.press("Escape")
    # 즐겨찾기
    pg.click("tr.r [data-fav]"); pg.click("[data-tab='fav']"); print("즐겨찾기 행:", pg.eval_on_selector_all("tr.r", "e => e.length"))
    # CSV
    pg.click("[data-tab='hot']")
    with pg.expect_download() as d: pg.click("#csv")
    path = d.value.path(); print("CSV 줄 수:", len(open(path, encoding="utf-8-sig").read().splitlines()), d.value.suggested_filename)
    # 보기 옵션: 1년 추이 끄기
    pg.click("#colbtn"); pg.click("[data-col='ser']"); print("추이 열 숨김:", "1년 추이" not in pg.inner_text("#head"))
    pg.click("[data-col='ser']")
    # 휴대폰 폭
    m = b.new_page(viewport={"width": 390, "height": 844}); m.goto("file:///" + HTML.replace("\\", "/")); m.wait_for_timeout(600)
    print("휴대폰 가로 넘침:", m.evaluate("document.documentElement.scrollWidth > innerWidth"), m.evaluate("document.documentElement.scrollWidth"))
    m.screenshot(path=os.path.join(SH, "v4_mobile.png"))
    b.close()
print("콘솔 오류:", errs or "없음")
