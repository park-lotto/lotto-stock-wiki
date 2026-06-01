"""눈꽃빙수 서브폴더 + 카페라떼 전체 파일목록 탐색"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE  = Path(__file__).parent.parent
links = json.loads((Path(__file__).parent / 'mybox_links.json').read_text(encoding='utf-8'))

def browse(url, label):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--lang=ko-KR'])
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='ko-KR')
        page = ctx.new_page()
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        items = page.query_selector_all('li.class_name_for_init_check_photo_list')
        print(f'\n=== {label} ({len(items)}개) ===')
        for i, item in enumerate(items):
            txt = (item.inner_text() or '').strip().replace('\n', ' | ')
            print(f'  [{i:2d}] {txt}')

        # 서브폴더 진입 (자산배분, 다양한 코드)
        for fi, fname in [(0,'자산배분'), (1,'다양한 코드')]:
            try:
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(1500)
                items2 = page.query_selector_all('li.class_name_for_init_check_photo_list')
                if fi < len(items2):
                    items2[fi].click()
                    page.wait_for_timeout(2500)
                    sub = page.query_selector_all('li.class_name_for_init_check_photo_list')
                    print(f'\n  📁 {fname} ({len(sub)}개):')
                    for i, it in enumerate(sub):
                        txt = (it.inner_text() or '').strip().replace('\n', ' | ')
                        print(f'    [{i:2d}] {txt}')
            except: pass
        ctx.close(); browser.close()

browse(links['bingsu'], '눈꽃빙수')
browse(links['cafe'],   '카페라떼')
