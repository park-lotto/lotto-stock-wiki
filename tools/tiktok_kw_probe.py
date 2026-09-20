# -*- coding: utf-8 -*-
"""틱톡 무료 경로(pw_tiktok)가 실제로 결과를 주는지 서버에서 확인한다.

    python3 tools/tiktok_kw_probe.py "미니 재봉틀"

★왜: 자동 모으기에 틱톡이 안 보인다는 제보(2026-09-08 사장님 "틱톡은 아까
  파이어폭스로 했으면 자동검색으로 나와야 하는거 아니냐"). 코드상으로는 도는데
  실제로 도는지, 몇 건 주는지는 돌려봐야 안다.
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')

from shopping_shorts import kw_search, kw_backends, config    # noqa: E402

kw = sys.argv[1] if len(sys.argv) > 1 else '미니 재봉틀'

print('① 지금 도는 백엔드 (노브 적용 뒤)')
chain = kw_search._apply_knobs(dict(kw_search._CHAIN))
for p, fns in chain.items():
    print('   %-12s %s' % (p, [getattr(f, '__name__', str(f)) for f in fns]))

print('\n② 틱톡 언어 배치:', kw_search._LANGS_BY_PLATFORM.get('tiktok'))
print('   Apify 유료 켜짐?:', getattr(config, 'KW_SEARCH_TIKTOK_APIFY', None))

print('\n③ pw_tiktok 직접 호출 — "%s"' % kw)
t0 = time.time()
try:
    r = kw_backends.pw_tiktok(kw, 10)
    items = r if isinstance(r, list) else (r or {}).get('items') or []
    print('   %d건 (%.1f초)' % (len(items), time.time() - t0))
    for it in items[:5]:
        d = it if isinstance(it, dict) else {}
        print('     -', str(d.get('title') or d.get('caption') or '')[:52],
              '|', str(d.get('url') or '')[:56])
except Exception as e:
    print('   실패 (%.1f초): %r' % (time.time() - t0, e))
