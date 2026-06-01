"""눈꽃빙수 오실레이터 3개 전부 다운로드"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / '매일 엑셀넣을것'
links    = json.loads((Path(__file__).parent / 'mybox_links.json').read_text(encoding='utf-8'))
URL      = links['bingsu']

TARGETS = [
    (2, '(업종)',     '외국인기관수급오실레이터(업종)',      '.xlsm'),
    (3, '(700-1400)', '외국인기관수급오실레이터(700-1400)', '.xlsm'),
    (5, '(700)',      '외국인기관수급오실레이터(700)',       '.xlsm'),
]

def download_one(page, idx, pattern, save_name, ext):
    items = page.query_selector_all('li.class_name_for_init_check_photo_list')
    item = None
    for it in items:
        if pattern in (it.inner_text() or ''):
            item = it; break
    if not item and idx < len(items):
        item = items[idx]
    if not item:
        print(f'  ❌ [{idx}] {pattern} 없음'); return

    dst = SAVE_DIR / f'{save_name}{ext}'
    if dst.exists(): dst.unlink()

    try:
        with page.expect_download(timeout=180_000) as dl_info:
            item.hover()
            page.wait_for_timeout(500)
            more = item.query_selector(
                '[class*="btn_more"], [class*="more_btn"], '
                '[aria-label*="더보기"], button[title*="더보기"]'
            )
            if more:
                more.click()
            else:
                item.click(button='right')
            page.wait_for_timeout(600)
            page.locator('text=내려받기').first.click()

        dl = dl_info.value
        dl.save_as(str(dst))
        print(f'  ✅ {dst.name}  ({dst.stat().st_size//1024}KB)')
    except Exception as e:
        print(f'  ❌ 실패: {e}')

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--lang=ko-KR'])
    ctx = browser.new_context(
        accept_downloads=True,
        viewport={'width': 1280, 'height': 900},
        locale='ko-KR',
    )
    page = ctx.new_page()

    for idx, pattern, save_name, ext in TARGETS:
        print(f'\n[{idx}] {save_name} 다운로드 중...')
        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        download_one(page, idx, pattern, save_name, ext)

    ctx.close()
    browser.close()

print('\n완료. 파일 목록:')
for f in sorted(SAVE_DIR.glob('*오실레이터*')):
    print(f'  {f.name}  ({f.stat().st_size//1024}KB)')
