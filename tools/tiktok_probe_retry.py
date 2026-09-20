# -*- coding: utf-8 -*-
"""틱톡 검색의 「다시 시도」가 통하는지 실측한다.

    python3 tools/tiktok_probe_retry.py "미니 재봉틀"

★배경(2026-09-08 실측): 로그인은 정상인데 검색 결과 자리에
  "죄송합니다. 서버에서 문제가 발생했습니다. 다시 시도하세요."가 뜬다.
  버튼이 있다는 건 **재시도로 풀릴 수 있다**는 뜻이라 그걸 확인한다.
  풀리면 pw_tiktok에 재시도를 붙이면 되고, 안 풀리면 프록시·지문 쪽이다.
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')

from urllib.parse import quote                                  # noqa: E402
from shopping_shorts import kw_backends, config                 # noqa: E402
from playwright.sync_api import sync_playwright                 # noqa: E402

kw = sys.argv[1] if len(sys.argv) > 1 else '미니 재봉틀'
url = 'https://www.tiktok.com/search?q=' + quote(kw)
ERR = '문제가 발생했습니다'


def count(page):
    try:
        return page.evaluate("document.querySelectorAll('a[href*=\"/video/\"]').length")
    except Exception:
        return -1


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,
                                args=['--disable-blink-features=AutomationControlled'])
    ctx = browser.new_context(storage_state=config.TIKTOK_SESSION_PATH,
                              locale='ko-KR', **kw_backends._tiktok_proxy_kw())
    page = ctx.new_page()
    kw_backends.block_heavy_assets(page)
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    page.wait_for_timeout(9000)
    print('1회차: 영상링크 %d개 / 오류표시 %s' % (count(page), ERR in page.inner_text('body')))

    # ① 「다시 시도」 버튼을 눌러 본다
    for i in range(2, 5):
        try:
            btn = page.get_by_text('다시 시도', exact=True).first
            btn.click(timeout=5000)
        except Exception as e:
            print('%d회차: 버튼 못 누름 (%s)' % (i, str(e)[:50]))
            break
        page.wait_for_timeout(7000)
        n = count(page)
        print('%d회차(버튼): 영상링크 %d개 / 오류표시 %s'
              % (i, n, ERR in page.inner_text('body')))
        if n > 0:
            break

    # ② 그래도 안 되면 페이지를 새로 연다(같은 컨텍스트=같은 쿠키)
    if count(page) <= 0:
        for i in range(1, 4):
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)
            n = count(page)
            print('재로드 %d회: 영상링크 %d개 / 오류표시 %s'
                  % (i, n, ERR in page.inner_text('body')))
            if n > 0:
                break
            time.sleep(3)

    n = count(page)
    if n > 0:
        cards = page.evaluate(kw_backends._TIKTOK_EXTRACT)
        print('\n★성공 — _TIKTOK_EXTRACT %d건' % len(cards or []))
        for c in (cards or [])[:5]:
            print('   -', str(c.get('title'))[:46], '|', str(c.get('url'))[:56])
    else:
        print('\n재시도로는 안 풀린다 — 프록시·지문 쪽을 봐야 한다')
    ctx.close()
    browser.close()
