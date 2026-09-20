# -*- coding: utf-8 -*-
"""릴레이의 틱톡 처리(handle_tiktok)를 서버 없이 단독으로 돌려 본다.

    python tools/_t_relay_tiktok.py "미니 재봉틀"

★서버로 결과를 올리는 _post 만 가로채고, 나머지는 라이브와 같은 코드다.
  크롬 창이 잠깐 떴다 사라진다 — 그게 정상이다(headless면 틱톡이 막는다).
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
os.environ.setdefault('COUPANG_RELAY_TOKEN', 'dummy')

import coupang_relay_client as C   # noqa: E402

sent = {}


def fake_post(path, payload, timeout=20):
    sent.update({'path': path, 'payload': payload})
    return {'ok': True}


C._post = fake_post
kw = sys.argv[1] if len(sys.argv) > 1 else '미니 재봉틀'
print('세션 파일:', C._TIKTOK_SESSION, '| 있음:', os.path.exists(C._TIKTOK_SESSION))
C.handle_tiktok({'id': 'test-1', 'kind': 'tiktok',
                 'payload': {'keyword': kw, 'limit': 10}})

p = sent.get('payload') or {}
items = p.get('items') or []
print('\n서버로 보낼 내용 — ok=%s / %d건 / notice=%r'
      % (p.get('ok'), len(items), p.get('notice')))
for it in items[:6]:
    print('   -', (str(it.get('account'))+' '+str(it.get('views')))[:20], '|', str(it.get('title'))[:40], '|', str(it.get('url'))[:46])
print('\n판정:', '통과' if items else '★0건 — 실패')
sys.exit(0 if items else 1)
