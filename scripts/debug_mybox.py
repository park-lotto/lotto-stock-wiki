import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

JS_FILES = """
() => {
    const items = document.querySelectorAll('li.class_name_for_init_check_photo_list a.item');
    return Array.from(items).map((el,i) => ({
        idx: i,
        text: (el.innerText || '').trim().split('\\n')[0],
        size: (el.innerText || '').trim().split('\\n')[1] || ''
    }));
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})

    # 카페라떼 - 첫번째 폴더(컨센관련데이터) 내부 확인
    page.goto('https://naver.me/xvC6NfsH', wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)

    files = page.evaluate(JS_FILES)
    print('=== 카페라떼 루트 ===')
    for f in files:
        print(f"  [{f['idx']}] {f['text']}  {f['size']}")

    # 첫번째 폴더(컨센관련데이터) 클릭
    print('\n→ 컨센관련데이터 폴더 진입...')
    if files:
        page.click('li.class_name_for_init_check_photo_list:first-child a.item')
        page.wait_for_timeout(2500)

        inner = page.evaluate(JS_FILES)
        print('=== 컨센관련데이터 폴더 내부 ===')
        for f in inner:
            print(f"  [{f['idx']}] {f['text']}  {f['size']}")

    browser.close()
