# 쇼핑 안내 세트 점검(2026-09-23): 트랙 폴더에서 py -m http.server 8774 --bind 127.0.0.1 띄운 뒤
#   py tools/check_shopset.py out.png  → 마지막 3장에 화살표+배지 2개씩, 두 번 눌러도 안 쌓임, 빼기 후 0개
import sys
from playwright.sync_api import sync_playwright
URL='http://127.0.0.1:8774/out/scene-style-ui-showcase.html'
OUT=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page(viewport={'width':1500,'height':1000})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(1500)
    print('buttons', pg.locator('[data-shopset]').count(), 'total', pg.evaluate('window.sceneStyle.sceneCount()'))
    # 효과 패널이 숨어 있을 수 있어 JS로 누른다
    pg.evaluate("document.querySelector('[data-shopset=\"last3\"]').click()")
    pg.evaluate("document.querySelector('[data-shopset=\"last3\"]').click()")   # 두 번 눌러도 안 쌓이는지
    r=pg.evaluate("""()=>{const n=sceneStyle.sceneCount(),o={};for(let i=0;i<n;i++){const m=sceneStyle.effectAt(i).masks||[];if(m.length)o[i+1]=m.map(x=>x.kind+':'+(x.text||x.graphic))}return o}""")
    print('masks', r)
    print('status', pg.locator('[data-shopset-status]').inner_text())
    n=pg.evaluate('sceneStyle.sceneCount()'); pg.evaluate(f'sceneStyle.show({n-1})'); pg.wait_for_timeout(800)
    pg.locator('#a-live-preview').screenshot(path=OUT)
    pg.evaluate("document.querySelector('[data-shopset=\"clear\"]').click()")
    r2=pg.evaluate("""()=>{let c=0;for(let i=0;i<sceneStyle.sceneCount();i++)c+=(sceneStyle.effectAt(i).masks||[]).length;return c}""")
    print('after clear total masks', r2, 'errors', errs)
    b.close()
