import sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
F = pathlib.Path(r"C:/Users/TheRose/Desktop/로또의 주식/out/인기상품랭킹_시안.html").as_uri()
J = "e=>e.map(x=>x.innerText.split(String.fromCharCode(10)).join(''))"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome"); pg = b.new_page(viewport={"width":1280,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(F); pg.wait_for_timeout(2500)
    print("사이트", pg.eval_on_selector_all("[data-site]", J))
    for s in ["all","naver","1688","temu","amazon"]:
        pg.click(f"[data-site='{s}']")
        for so in ["total","speed","opp"]:
            pg.click(f"[data-sort='{so}']"); pg.wait_for_timeout(300)
            t = pg.eval_on_selector_all("#grid .card .title", "e=>e.slice(0,2).map(x=>x.innerText.slice(0,22))")
            print(s, so, pg.locator("#grid .card").count(), t)
    pg.click("[data-site='all']"); pg.click("[data-sort='total']"); pg.wait_for_timeout(2500)
    imgs = pg.evaluate("()=>{const im=[...document.querySelectorAll('#grid img')].slice(0,15);return [im.filter(x=>x.complete&&x.naturalWidth>0).length, im.length]}")
    print("이미지", imgs); pg.screenshot(path="v3_all.png")
    pg.click("[data-pcat='제외']"); print("제외 첫", pg.inner_text("#grid .why"))
    print("JS 오류", errs); b.close()
