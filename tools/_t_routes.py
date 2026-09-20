# -*- coding: utf-8 -*-
"""app이 import되고 빌림 엔드포인트가 실제로 붙었는지 확인."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shopping_shorts.app as A

paths = [getattr(r, 'path', '') for r in A.app.routes]
hit = [p for p in paths if 'lens_borrow' in p]
print('app import OK — 라우트 %d개' % len(paths))
print('빌림 엔드포인트:', hit)
print('keyroute 연결:', A.keyroute.BORROW_SETTING, A.keyroute.BORROW_PER_KEY)
sys.exit(0 if hit else 1)
