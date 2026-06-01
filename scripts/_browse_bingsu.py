"""눈꽃빙수 폴더 파일목록 확인"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE  = Path(__file__).parent.parent
links = json.loads((Path(__file__).parent / 'mybox_links.json').read_text(encoding='utf-8'))
URL   = links['bingsu']

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, args=['--no-sandbox', '--lang=ko-KR'])
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='ko-KR')
    page = ctx.new_page()

    print(f'접속: {URL}')
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)

    # 파일 목록 전부 출력
    items = page.query_selector_all('li.class_name_for_init_check_photo_list')
    print(f'\n총 {len(items)}개 항목:')
    for i, item in enumerate(items):
        txt = (item.inner_text() or '').strip().replace('\n', ' | ')
        print(f'  [{i:2d}] {txt}')

    # 스크린샷
    page.screenshot(path=str(BASE / 'raw' / '매일 엑셀넣을것' / 'bingsu_list.png'))
    print('\n스크린샷: raw/매일 엑셀넣을것/bingsu_list.png')

    ctx.close()
    browser.close()
