import sys,pathlib
from playwright.sync_api import sync_playwright
d=pathlib.Path(sys.argv[1])
with sync_playwright() as p:
    b=p.chromium.launch()
    for m in ('off','on'):
        pg=b.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto((d/f't_{m}.html').as_uri())
        for i,v in (('a','y2elnRSB9_Y'),('b','Kl68xnFGqXE'),('c','UHpVPuisr9w')):
            pg.evaluate(f"emb('{i}','{v}')"); pg.wait_for_timeout(300)
        n=pg.evaluate("document.querySelectorAll('iframe').length")
        btn=pg.evaluate("[...document.querySelectorAll('button')].filter(x=>x.textContent.includes('다시 재생')).length")
        pg.click("text=▶ 다시 재생") if btn else None; pg.wait_for_timeout(300)
        n2=pg.evaluate("document.querySelectorAll('iframe').length")
        print(m,'재생기',n,'다시재생버튼',btn,'버튼누른뒤 재생기',n2,'오류',errs[:2])
    b.close()
