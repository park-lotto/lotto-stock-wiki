"""상대강도 종목(한국).txt 코드 파일 다운로드"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw'
links    = json.loads((Path(__file__).parent / 'mybox_links.json').read_text(encoding='utf-8'))
URL      = links['bingsu']

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--lang=ko-KR'])
    ctx = browser.new_context(accept_downloads=True, viewport={'width':1280,'height':900}, locale='ko-KR')
    page = ctx.new_page()

    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    items = get_items = lambda: page.query_selector_all('li.class_name_for_init_check_photo_list')

    # 다양한 코드 [1] 진입
    items()[1].click()
    page.wait_for_timeout(2500)

    # 한국 개별종목 상대강도 [1] 진입
    items()[1].click()
    page.wait_for_timeout(2500)

    # [1] 상대강도 종목(한국).txt 다운로드
    all_items = items()
    print(f'파일 목록:')
    for i, it in enumerate(all_items):
        print(f'  [{i}] {(it.inner_text() or "").strip()[:60]}')

    dst = SAVE_DIR / '상대강도_종목_한국.txt'
    with page.expect_download(timeout=30000) as dl_info:
        all_items[1].hover(); page.wait_for_timeout(400)
        more = all_items[1].query_selector('[class*="btn_more"],[aria-label*="더보기"]')
        if more: more.click()
        else: all_items[1].click(button='right')
        page.wait_for_timeout(500)
        page.locator('text=내려받기').first.click()

    dl = dl_info.value
    dl.save_as(str(dst))
    print(f'✅ {dst.name}  ({dst.stat().st_size}bytes)')

    ctx.close(); browser.close()
