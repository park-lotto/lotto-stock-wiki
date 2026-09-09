# -*- coding: utf-8 -*-
"""pw_tiktok 이 왜 0건인지 갈라 본다 — 예외를 삼키지 않고 화면을 본다.

    python3 tools/tiktok_probe_deep.py "미니 재봉틀"

★pw_tiktok은 `except Exception: return []` 라 원인이 안 보인다(도우인에서 겪은
  것과 같은 함정). 여기서는 같은 흐름을 그대로 돌리되 단계마다 결과를 찍는다.
"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')

from urllib.parse import quote                                  # noqa: E402
from shopping_shorts import kw_backends, config                 # noqa: E402

kw = sys.argv[1] if len(sys.argv) > 1 else '미니 재봉틀'
session = getattr(config, 'TIKTOK_SESSION_PATH', '')
print('세션 경로:', session, '| 있음:', os.path.exists(session or ''))
prox = {} if '--noproxy' in sys.argv else kw_backends._tiktok_proxy_kw()
print('프록시:', {k: (str(v)[:40] if k != 'proxy' else {kk: str(vv)[:28] for kk, vv in v.items()})
                for k, v in prox.items()} or '직결')

url = 'https://www.tiktok.com/search?q=' + quote(kw)
from playwright.sync_api import sync_playwright                 # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch(headless=('--headful' not in sys.argv), channel=('chrome' if '--headful' in sys.argv else None),
                                args=['--disable-blink-features=AutomationControlled'])
    ctx = browser.new_context(storage_state=session, locale='ko-KR', **prox)
    page = ctx.new_page()
    kw_backends.block_heavy_assets(page)
    t0 = time.time()
    page.goto(url, timeout=60000, wait_until='domcontentloaded')
    page.wait_for_timeout(9000)
    print('\n도착 URL:', page.url[:110])
    print('제목:', (page.title() or '')[:70], '| %.1f초' % (time.time() - t0))

    body = (page.inner_text('body') or '')
    print('본문 길이:', len(body))
    print('본문 앞 260자:')
    print('  ' + body[:260].replace('\n', ' / '))

    for w, label in (('로그인', '로그인 요구'), ('Log in', '로그인(영문)'),
                     ('보안', '보안검사'), ('Verify', '캡차(영문)'),
                     ('결과를 찾을 수 없', '결과없음'), ('검색', '검색어 정상')):
        if w in body:
            print('  ★신호:', label)

    cards = page.evaluate(kw_backends._TIKTOK_EXTRACT)
    print('\n_TIKTOK_EXTRACT 결과:', len(cards or []), '건')
    for c in (cards or [])[:4]:
        print('   -', str(c.get('title'))[:46], '|', str(c.get('url'))[:56])

    # 셀렉터가 낡았을 수 있다 — 페이지에 영상 링크가 있는지 직접 센다
    n = page.evaluate(
        "document.querySelectorAll('a[href*=\"/video/\"]').length")
    print('a[href*=/video/] 개수:', n)
    page.screenshot(path='/tmp/tiktok_probe.png', full_page=False)
    print('스크린샷: /tmp/tiktok_probe.png')
    ctx.close()
    browser.close()
