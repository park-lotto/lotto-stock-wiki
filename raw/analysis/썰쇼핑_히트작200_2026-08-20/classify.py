# -*- coding: utf-8 -*-
"""히트작 대본을 골격(스파인) 단위로 분해해 테이블 후보를 뽑는다.

측정하는 것 (전부 대사 문구로 판정 - 추측 없음):
  - 어떤 골격인가        오용형 / 은폐형 / 목격담형 / 나열형
  - 용도(장면)가 몇 개인가  <- 핵심: 해외영상 장면이 몇 개 필요한가
  - 고조(심지어)가 있나
출력은 전부 report.txt (윈도 콘솔 cp949 회피)
"""
import json, io, re, sys
from collections import Counter

_W = io.open("report.txt", "w", encoding="utf-8")


def emit(*a):
    _W.write(" ".join(str(x) for x in a) + "\n")


SRC = sys.argv[1] if len(sys.argv) > 1 else 'hits_subs.json'
D = json.load(open(SRC, encoding='utf-8'))

AUTH = ['개발자도', '제조사도', '본사도', '만든 사람도', '판매자도', '직원도', '설계자도',
        '기획자도', '다이소도', '다이소의 실수', '코스트코 본사', '엄마가 감탄', '의사도',
        '전문가도', '예상 못한', '예상못한', '몰랐던']
ORIG = ['원래는', '원래 이', '이건 원래', '원래 이것', '본래', '원래 용도']
REVEAL = ['이건 바로', '이게 바로', '제품의 정체', '정체는']
HOOKQ = ['어디에 쓰', '어디에다', '용도를 알', '뭐에 쓰', '무슨 장난감', '정체를 알']
WITNES = ['갔다가', '친구네', '시댁', '지인 집', '동료 책상', '놀러 갔']
LIST = ['첫 번째', '두 번째', '세 번째', '1위', '2위', '다섯 개', '세 가지']

USE_SW = ['하는가 하면', '사용하는가', '활용법', '용도로', '에 쓰면', '붙이면', '넣으면',
          '쓰면', '깔면', '씌워주면', '끼워서', '올리면', '담으면']
CLIMAX = ['근데 미친', '진짜 미친', '미친 사용법은 따로', '따로 있었는데', '진짜 충격적인',
          '더 놀라운', '미친 포인트', '대박인게', '말도 안 되는게', '말도안되는게']
EVEN = ['심지어', '게다가', '더 놀라운', '뿐만 아니라']


def has(t, ms):
    return any(m in t for m in ms)


def spine_of(t):
    if has(t, LIST):
        return '나열형'
    if has(t, ORIG) and has(t, AUTH):
        return '오용형(권위자)'
    if has(t, ORIG):
        return '오용형'
    if has(t, REVEAL) or has(t, HOOKQ):
        return '은폐형'
    if has(t, WITNES):
        return '목격담형'
    if has(t, AUTH):
        return '권위자형'
    return '기타'


def count_uses(t):
    n = sum(t.count(m) for m in USE_SW)
    sents = max(1, len(re.split(r'[.。]', t)))
    return min(n, sents)


rows = []
for d in D:
    t = d['full_text']
    rows.append({'views': d['views'], 'ch': d['channel'], 'len': len(t),
                 'spine': spine_of(t), 'climax': has(t, CLIMAX), 'even': has(t, EVEN),
                 'orig': has(t, ORIG), 'auth': has(t, AUTH), 'uses': count_uses(t),
                 'vid': d.get('video_id', ''), 'text': t})

emit('표본 %d편 | 조회수 %s ~ %s' % (len(rows), format(rows[-1]['views'], ','),
                                 format(rows[0]['views'], ',')))

emit('\n=== 골격 분포 ===')
sp = Counter(r['spine'] for r in rows)
for k, n in sp.most_common():
    avg = sum(r['views'] for r in rows if r['spine'] == k) // max(1, n)
    emit('  %-14s %3d편 %3d%%   평균조회 %12s' % (k, n, n * 100 // len(rows), format(avg, ',')))

emit('\n=== 골격별 요소 보유율 ===')
emit('  %-14s %8s %7s %8s %8s' % ('골격', '클라이맥스', '심지어', '원래용도', '평균길이'))
for k, n in sp.most_common():
    g = [r for r in rows if r['spine'] == k]
    emit('  %-14s %7d%% %6d%% %7d%% %7d자' % (
        k, sum(r['climax'] for r in g) * 100 // n, sum(r['even'] for r in g) * 100 // n,
        sum(r['orig'] for r in g) * 100 // n, sum(r['len'] for r in g) // n))

emit('\n=== 용도(장면) 개수 분포 - 해외영상 장면이 몇 개 필요한가 ===')
uc = Counter(r['uses'] for r in rows)
for k in sorted(uc):
    emit('  용도 %2d개 -> %3d편  %s' % (k, uc[k], '#' * min(uc[k], 60)))
emit('  평균 %.1f개 / 중앙값 %d개' % (
    sum(r['uses'] for r in rows) / len(rows),
    sorted(r['uses'] for r in rows)[len(rows) // 2]))

emit('\n=== 조회수 상위 15편의 골격 ===')
for r in rows[:15]:
    emit('  %12s %-14s %-14s 용도%-2d %s%s' % (
        format(r['views'], ','), r['ch'][:14], r['spine'], r['uses'],
        '클라이맥스 ' if r['climax'] else '', '심지어' if r['even'] else ''))

# 골격별 대표 대본 (테이블 만들 때 원문 근거)
emit('\n=== 골격별 대표작 (조회수 1위) ===')
for k, n in sp.most_common():
    g = sorted([r for r in rows if r['spine'] == k], key=lambda x: -x['views'])
    if g:
        emit('\n[%s] %s회 | %s | 용도%d개' % (k, format(g[0]['views'], ','), g[0]['ch'], g[0]['uses']))
        emit('  ' + g[0]['text'][:300])

w = io.open('classify_out.txt', 'w', encoding='utf-8')
for r in rows:
    w.write('[%s] %s | %s | 용도%d | %d자 | climax=%s even=%s | %s\n  %s\n\n' % (
        format(r['views'], ','), r['ch'], r['spine'], r['uses'], r['len'],
        r['climax'], r['even'], r['vid'], r['text'][:300]))
w.close()
json.dump(rows, io.open('classified.json', 'w', encoding='utf-8'), ensure_ascii=False)
emit('\nwritten classify_out.txt / classified.json')
_W.close()
