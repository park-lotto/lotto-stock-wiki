"""신규 채널 1,107개 → 엑셀에서 바로 열리는 CSV (UTF-8 BOM)."""
import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(BASE, 'scan_raw.csv')
NEWL = os.path.join(BASE, 'new_only.txt')
OUT = os.path.join(BASE, '신규채널_1107_전수조사.csv')

new_order = [l.strip() for l in open(NEWL, encoding='utf-8') if l.strip()]
by = {}
for r in csv.DictReader(open(SCAN, encoding='utf-8')):
    by[r['username'].lower()] = r


def f(r, k, d=0.0):
    try:
        return float((r.get(k) or '').strip())
    except Exception:
        return d


def status(days):
    if days < 0:
        return '판정불가'
    if days > 100:
        return '폐업(100일+)'
    if days > 60:
        return '휴면(60일+)'
    if days > 14:
        return '저활동(14일+)'
    return '활성'


def grade(v, c, days):
    if days > 60:
        return 'X'
    if v >= 500000 or c >= 1000:
        return 'S'
    if v >= 100000 or c >= 300:
        return 'A'
    if v >= 30000 or c >= 100:
        return 'B'
    if v >= 5000:
        return 'C'
    return 'D'


rows = []
for u in new_order:
    r = by.get(u.lower())
    if not r:
        rows.append([u, '-', '스캔없음', '', '', '', '', '', '', '', ''])
        continue
    v, c = f(r, 'avg_views'), f(r, 'avg_comments')
    days = f(r, 'last_upload_days', -1)
    err = (r.get('error') or '').strip()
    rows.append([
        u,
        '-' if err else grade(v, c, days),
        '수집실패' if err else status(days),
        int(v), int(f(r, 'max_views')), round(c, 1), int(f(r, 'max_comments')),
        round(f(r, 'avg_likes'), 1),
        days if days >= 0 else '',
        f(r, 'posts_per_week') or '',
        'https://www.instagram.com/%s/' % u,
    ])

GO = {'S': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4, 'X': 5, '-': 6}
rows.sort(key=lambda x: (GO.get(x[1], 9), -(x[3] if isinstance(x[3], int) else 0)))

HDR = ['채널ID', '등급', '상태', '평균조회수', '최대조회수', '평균댓글', '최대댓글',
       '평균좋아요', '마지막업로드(일전)', '주당업로드', '주소']

with open(OUT, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.writer(fh)
    w.writerow(HDR)
    w.writerows(rows)

import collections
g = collections.Counter(r[1] for r in rows)
s = collections.Counter(r[2] for r in rows)
print('저장:', OUT)
print('총', len(rows), '채널')
print('등급:', dict(g))
print('상태:', dict(s))
