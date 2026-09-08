# -*- coding: utf-8 -*-
"""자동 모으기에 더 넣을 수 있는 플랫폼을 실측한다 — 세션이 살아 있나, 공짜인가.

    python3 tools/_probe_platforms.py "미니 재봉틀"

★왜 (2026-09-08 사장님 "언어 하나 고르고 틱톡 인스타 찾고 키워드별로 또 해야되니
  시간이 엄청 걸린다"): 자동 모으기가 도는 곳이 4곳뿐이라 나머지는 전부 수동이다.
  무료로 돌릴 수 있는 곳을 찾아 자동에 합류시키면 손으로 누를 일이 준다.
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')

from shopping_shorts import cn_backends, config      # noqa: E402

kw = sys.argv[1] if len(sys.argv) > 1 else '미니 재봉틀'

for name, fn, sess_attr in (
        ('샤오홍슈 pw_xiaohongshu', cn_backends.pw_xiaohongshu, 'XHS_SESSION_PATH'),
        ('도우인   pw_douyin', cn_backends.pw_douyin, 'DOUYIN_SESSION_PATH')):
    import os
    p = getattr(config, sess_attr, '')
    ok = bool(p and os.path.exists(p))
    print('%-26s 세션=%s (%s)' % (name, ok, (p or '설정없음')[:52]))
    if not ok:
        print('    → 세션이 없어 무료 경로 불가')
        continue
    t0 = time.time()
    try:
        r = fn(kw, 8) or []
        print('    → %d건 (%.1f초) %s' % (len(r), time.time() - t0,
                                          (r[0].get('url', '')[:50] if r else '')))
    except Exception as e:
        print('    → 실패 %r (%.1f초)' % (e, time.time() - t0))
