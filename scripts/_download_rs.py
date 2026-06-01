"""한국 개별종목 상대강도 폴더 탐색 + 다운로드"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / '매일 엑셀넣을것'
links    = json.loads((Path(__file__).parent / 'mybox_links.json').read_text(encoding='utf-8'))
URL      = links['bingsu']

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--lang=ko-KR'])
    ctx = browser.new_context(accept_downloads=True, viewport={'width':1280,'height':900}, locale='ko-KR')
    page = ctx.new_page()

    # 눈꽃빙수 접속
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    # [1] 다양한 코드 폴더 진입
    items = page.query_selector_all('li.class_name_for_init_check_photo_list')
    items[1].click()  # 다양한 코드
    page.wait_for_timeout(2500)

    # [1] 한국 개별종목 상대강도 폴더 진입
    items2 = page.query_selector_all('li.class_name_for_init_check_photo_list')
    print(f'다양한 코드 내 항목 {len(items2)}개:')
    for i, it in enumerate(items2):
        print(f'  [{i}] {(it.inner_text() or "").strip()[:60]}')

    items2[1].click()  # 한국 개별종목 상대강도
    page.wait_for_timeout(2500)

    # 파일 목록
    items3 = page.query_selector_all('li.class_name_for_init_check_photo_list')
    print(f'\n한국 개별종목 상대강도 내 {len(items3)}개:')
    for i, it in enumerate(items3):
        print(f'  [{i}] {(it.inner_text() or "").strip()[:80]}')

    # 첫 번째 파일 다운로드 (xlsm/xlsx)
    for i, item in enumerate(items3):
        txt = (item.inner_text() or '').strip()
        if any(ext in txt.lower() for ext in ['.xlsm', '.xlsx']):
            fname = txt.split('\n')[0].strip()
            print(f'\n다운로드: {fname}')
            dst = SAVE_DIR / f'한국상대강도0601.xlsm'

            with page.expect_download(timeout=180_000) as dl_info:
                item.hover(); page.wait_for_timeout(500)
                more = item.query_selector('[class*="btn_more"],[aria-label*="더보기"]')
                if more: more.click()
                else: item.click(button='right')
                page.wait_for_timeout(600)
                page.locator('text=내려받기').first.click()

            dl = dl_info.value
            # 확장자 맞추기
            sug = dl.suggested_filename
            ext = Path(sug).suffix if sug else '.xlsm'
            dst = SAVE_DIR / f'한국상대강도0601{ext}'
            dl.save_as(str(dst))
            print(f'✅ {dst.name}  ({dst.stat().st_size//1024}KB)')
            break

    ctx.close(); browser.close()
