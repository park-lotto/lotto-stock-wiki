# -*- coding: utf-8 -*-
"""회원 SerpApi 키 빌림 — 라이브 서버에서 실제로 도는지 확인한다(0순위-A1).

    python3 tools/lens_borrow_check.py          현황만 본다
    python3 tools/lens_borrow_check.py --on     스위치를 켜고 실제 경로를 확인한다
    python3 tools/lens_borrow_check.py --off    끈다

★서버에서 돌린다. 라이브 설정(admin_borrow_serpapi)을 실제로 바꾼다.
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')

from shopping_shorts import config, keyroute as K          # noqa: E402
from shopping_shorts.store import Store                    # noqa: E402
import shopping_shorts.app as A                            # noqa: E402

st = Store(str(config.DB_PATH))
arg = sys.argv[1] if len(sys.argv) > 1 else ''

if arg == '--off':
    st.set_setting(K.BORROW_SETTING, '0')
    print('빌림 껐습니다:', K.borrow_status(st))
    sys.exit(0)

print('① 지금 상태:', K.borrow_status(st))
if arg != '--on':
    print('   (켜려면 --on)')
    sys.exit(0)

print('   꺼진 채로 빌려보기 →', len(K.borrow_serpapi(st)), '개 (0이어야 정상)')

st.set_setting(K.BORROW_SETTING, '1')
print('\n② 스위치 켬:', K.borrow_status(st))

print('\n③ 사장님(cid 0)이 실제로 받는 렌즈 키 — _lens_api_keys(0)')
own, _ = K.keys_for(st, 0, K.SVC_SERPAPI)
keys = A._lens_api_keys(0)
print('   사장님 키 %d개 + 빌린 키 %d개 = 총 %d개'
      % (len(own), len(keys) - len(own), len(keys)))
print('   빌린 키 앞자리:', [k[:8] for k in keys[len(own):]])

print('\n④ 회원은 영향 없나 — cid 2(자기 키 없는 회원)')
print('   _lens_api_keys(2) →', len(A._lens_api_keys(2)), '개 (빌림이 안 붙어야 정상)')
g = A._lens_quota_guard(st, '2026-09', 2)
print('   가드 →', getattr(g, 'status_code', 'None(통과)'), '(429면 막힘 = 정상)')

print('\n⑤ 최종 현황:', K.borrow_status(st))
