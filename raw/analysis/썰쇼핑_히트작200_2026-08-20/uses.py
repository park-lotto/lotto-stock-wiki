# -*- coding: utf-8 -*-
"""용도(장면) 개수를 제대로 센다.

앞선 시도의 실패: 키워드 출현횟수를 셌더니 '쓰면/붙이면'이 한 문장에 여러 번 나오거나
아예 안 나오는 영상이 0개로 떨어졌다(5.1M 활용정점이 용도0인데 실제론 2개).

바꾼 방법: **용도가 바뀌는 경계**를 센다. 오용형 대본은 용도를 나열할 때
반드시 전환어로 새 용도를 연다 - '바로', '~하는가 하면', '근데', '심지어', '초보들은/중수들은/고수들은'.
경계 개수 + 1 = 용도 개수. 경계는 문장 단위로만 인정한다(같은 문장 내 중복 방지).
"""
import json, io, re, sys
from collections import Counter

_W = io.open("uses_report.txt", "w", encoding="utf-8")


def emit(*a):
    _W.write(" ".join(str(x) for x in a) + "\n")


SRC = sys.argv[1] if len(sys.argv) > 1 else 'hits_subs.json'
D = json.load(open(SRC, encoding='utf-8'))

# 새 용도를 여는 전환 신호 (실측 문구)
OPEN = [
    '바로', '하는가 하면', '사용하는가 하면', '쓰는가 하면',
    '근데 미친', '진짜 미친', '따로 있었는데', '미친 포인트',
    '심지어', '게다가', '뿐만 아니라',
    '초보들은', '중수들은', '고수들은', '진짜 고수',
    '이게 미친', '더 놀라운', '또 다른',
]
# 실제 '쓰임'을 서술하는 동사 - 이게 있어야 용도로 친다(그냥 전환어만으론 안 셈)
USEV = ['쓰', '사용', '붙이', '넣', '깔', '씌우', '끼우', '올리', '담', '걸', '만들',
        '적용', '활용', '보관', '고정', '수납', '자르', '얼리']


def split_sents(t):
    """자막엔 마침표가 드물다 - 종결어미로도 끊는다."""
    t = re.sub(r'\s+', ' ', t)
    parts = re.split(r'(?<=[.。!?])\s+|(?<=거임)\s+|(?<=있음)\s+|(?<=됨)\s+|(?<=함)\s+'
                     r'|(?<=는 거)\s+|(?<=버림)\s+|(?<=한다는 거)\s+', t)
    return [p.strip() for p in parts if p.strip()]


def count_uses(t):
    sents = split_sents(t)
    n = 0
    for s in sents:
        if any(o in s for o in OPEN) and any(v in s for v in USEV):
            n += 1
    return max(1, n) if any(v in t for v in USEV) else 0


rows = []
for d in D:
    t = d['full_text']
    rows.append({'views': d['views'], 'ch': d['channel'], 'uses': count_uses(t),
                 'len': len(t), 'vid': d.get('video_id', ''), 'text': t})

emit('표본 %d편' % len(rows))
emit('\n=== 용도(장면) 개수 분포 ===')
uc = Counter(r['uses'] for r in rows)
for k in sorted(uc):
    emit('  용도 %2d개 -> %3d편 %5d%%  %s' % (k, uc[k], uc[k] * 100 // len(rows), '#' * min(uc[k], 50)))
vals = sorted(r['uses'] for r in rows)
emit('  평균 %.1f개 / 중앙값 %d개' % (sum(vals) / len(vals), vals[len(vals) // 2]))

emit('\n=== 조회수 구간별 평균 용도 개수 ===')
for lo, hi, lab in [(3000000, 99999999, '300만+'), (1000000, 3000000, '100~300만'),
                    (500000, 1000000, '50~100만'), (0, 500000, '50만 미만')]:
    g = [r for r in rows if lo <= r['views'] < hi]
    if g:
        emit('  %-10s %3d편  평균 용도 %.1f개  평균 %d자' % (
            lab, len(g), sum(r['uses'] for r in g) / len(g), sum(r['len'] for r in g) // len(g)))

emit('\n=== 상위 15편 검산 (용도 개수가 맞는지 원문으로 확인) ===')
for r in sorted(rows, key=lambda x: -x['views'])[:15]:
    emit('\n[%s] %s | 용도 %d개' % (format(r['views'], ','), r['ch'], r['uses']))
    emit('   ' + r['text'][:230])

json.dump(rows, io.open('uses.json', 'w', encoding='utf-8'), ensure_ascii=False)
emit('\nwritten uses.json')
_W.close()
