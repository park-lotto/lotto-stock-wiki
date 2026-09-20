# -*- coding: utf-8 -*-
"""회원 SerpApi 키 빌림 로직 검증 — 라이브 DB를 안 쓴다(가짜 저장소)."""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopping_shorts import keyroute as K


class FakeStore:
    def __init__(self, keys, on=True):
        self.s = {K.BORROW_SETTING: '1' if on else ''}
        self.keys = keys

    def get_setting(self, k, d=None):
        return self.s.get(k, d)

    def set_setting(self, k, v):
        self.s[k] = v

    def get_pooled_keys(self, svc):
        return list(self.keys) if svc == K.SVC_SERPAPI else []


KEYS = ['key-A', 'key-B', 'key-C']
M = 'TEST-9999'
ok = True


def check(label, cond, detail=''):
    global ok
    ok = ok and cond
    print('  %s %-46s %s' % ('OK ' if cond else '실패', label, detail))


print('① 스위치가 꺼져 있으면 아무것도 안 빌린다')
st = FakeStore(KEYS, on=False)
check('꺼짐 → 빈 목록', K.borrow_serpapi(st, month=M) == [])

print('\n② 켜면 1개씩만 준다')
st = FakeStore(KEYS)
got = [K.borrow_serpapi(st, month=M) for _ in range(3)]
check('한 번에 1개', all(len(g) == 1 for g in got), str(got))
check('세 키를 돌아가며 준다', sorted(g[0] for g in got) == sorted(KEYS))

print('\n③ 한 키당 10회에서 멈추고 다음으로 넘어간다')
st = FakeStore(KEYS)
cnt = {}
for _ in range(K.BORROW_PER_KEY * len(KEYS)):
    g = K.borrow_serpapi(st, month=M)
    if g:
        cnt[g[0]] = cnt.get(g[0], 0) + 1
check('총 %d회' % (K.BORROW_PER_KEY * len(KEYS)), sum(cnt.values()) == K.BORROW_PER_KEY * len(KEYS), str(cnt))
check('어느 키도 10회를 안 넘는다', all(v <= K.BORROW_PER_KEY for v in cnt.values()))
check('다 쓰면 더는 안 준다', K.borrow_serpapi(st, month=M) == [])

print('\n④ 평문 키를 설정값에 저장하지 않는다')
blob = st.get_setting('%s::%s' % (K.BORROW_COUNTER, M), '')
check('설정값에 키 원문 없음', all(k not in blob for k in KEYS), blob[:60])

print('\n⑤ 카운터 저장이 실패하면 빌리지 않는다(한도를 못 지키므로)')


class Broken(FakeStore):
    def set_setting(self, k, v):
        raise RuntimeError('디스크 꽉참')


check('저장 실패 → 빈 목록', K.borrow_serpapi(Broken(KEYS), month=M) == [])

print('\n⑥ 회원 키가 하나도 없으면 빈 목록')
check('키 0개 → 빈 목록', K.borrow_serpapi(FakeStore([]), month=M) == [])

print('\n⑦ 현황 보고')
st = FakeStore(KEYS)
for _ in range(7):
    K.borrow_serpapi(st, month=M)
s = K.borrow_status(st, month=M)
check('쓴 횟수 7', s['used'] == 7, str(s))
check('남은 횟수 %d' % (K.BORROW_PER_KEY * 3 - 7), s['left'] == K.BORROW_PER_KEY * 3 - 7)

print('\n' + ('전부 통과' if ok else '★실패 있음'))
sys.exit(0 if ok else 1)
