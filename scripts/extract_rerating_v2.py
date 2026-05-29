import win32com.client, os
from datetime import datetime, date, timedelta
from collections import defaultdict

file_path = os.path.abspath(r'C:\Users\TheRose\Desktop\로또의 주식\raw\매일 엑셀넣을것\추정이익 변경0528.xlsm')
xl = win32com.client.Dispatch('Excel.Application')
xl.Visible = False
xl.DisplayAlerts = False
xl.AutomationSecurity = 3

wb = xl.Workbooks.Open(file_path)

def parse_date(v):
    if v is None: return None
    s = str(v)
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    except:
        return None

def fmt_tp(v):
    if v is None or v == '': return '-'
    try:
        n = float(str(v).replace(',', ''))
        if n >= 10000000: return f'{n/10000:.0f}만'
        if n >= 1000000: return f'{n/10000:.1f}만'
        if n >= 1000: return f'{int(n):,}'
        return str(int(n))
    except:
        return str(v)

def chg_pct(old, new):
    try:
        o, n = float(old), float(new)
        if o == 0: return ''
        r = (n - o) / o * 100
        return f'+{r:.0f}%' if r > 0 else f'{r:.0f}%'
    except:
        return ''

def week_label(d):
    # 오늘(5/29) 기준
    today = date(2026, 5, 29)
    delta = (today - d).days
    if delta <= 7:
        return 'this_week'   # 5/22~5/28
    elif delta <= 14:
        return 'last_week'   # 5/15~5/21
    else:
        return 'older'

# 데이터 수집
all_data = {}
for sn in ['Rating_Up', 'Rating_Down', 'TP_Up', 'TP_Down']:
    ws = wb.Sheets(sn)
    rows = []
    r = 12
    while True:
        d_val = ws.Cells(r, 2).Value
        if d_val is None:
            break
        row = {
            'date': parse_date(d_val),
            'code': str(ws.Cells(r, 3).Value or '').replace('A', ''),
            'name': str(ws.Cells(r, 4).Value or ''),
            'firm': str(ws.Cells(r, 6).Value or ''),
            'analyst': str(ws.Cells(r, 7).Value or ''),
            'opinion_old': str(ws.Cells(r, 12).Value or ''),
            'opinion_new': str(ws.Cells(r, 13).Value or ''),
            'tp_old': ws.Cells(r, 14).Value,
            'tp_new': ws.Cells(r, 15).Value,
        }
        rows.append(row)
        r += 1
    all_data[sn] = rows

wb.Close(False)
xl.Quit()

# ─────────────────────────────────────────
# 출력 작성
# ─────────────────────────────────────────
lines = []
lines.append('# 추정이익 변경 — 리레이팅 & TP 상향 분석')
lines.append(f'> 수집: 2026-05-28 | 기간: 5/16~5/28 | 파일: 추정이익 변경0528.xlsm')
lines.append('')

WEEK_KO = {
    'this_week': '📅 이번 주 (5/22~5/28)',
    'last_week': '📅 지난 주 (5/15~5/21)',
    'older':     '📅 그 이전',
}

# ─── 1. 리레이팅 상향 ───
lines.append('---')
lines.append('## 🔺 리레이팅 상향 (Rating_Up)')
lines.append('')
lines.append('> 투자의견 자체가 올라간 것만. TP만 오른 건 아래 TP 섹션 참조.')
lines.append('')

by_week = defaultdict(list)
for row in all_data['Rating_Up']:
    if row['date']:
        wk = week_label(row['date'])
        by_week[wk].append(row)

for wk_key in ['this_week', 'last_week', 'older']:
    if wk_key not in by_week:
        continue
    lines.append(f'### {WEEK_KO[wk_key]}')
    lines.append('')
    lines.append('| 날짜 | 종목 | 증권사 | 기존→변경 | TP 기존→신규 | 변화율 |')
    lines.append('|------|------|--------|----------|------------|-------|')
    for row in sorted(by_week[wk_key], key=lambda x: x['date'], reverse=True):
        d_str = row['date'].strftime('%m/%d')
        op_change = f"{row['opinion_old']} → **{row['opinion_new']}**"
        tp_str = f"{fmt_tp(row['tp_old'])} → **{fmt_tp(row['tp_new'])}**"
        pct = chg_pct(row['tp_old'], row['tp_new'])
        lines.append(f"| {d_str} | {row['name']} | {row['firm']} | {op_change} | {tp_str} | {pct} |")
    lines.append('')

# ─── 2. 리레이팅 하향 ───
lines.append('---')
lines.append('## 🔻 리레이팅 하향 (Rating_Down)')
lines.append('')

by_week_down = defaultdict(list)
for row in all_data['Rating_Down']:
    if row['date']:
        wk = week_label(row['date'])
        by_week_down[wk].append(row)

if not by_week_down:
    lines.append('> 해당 기간 리레이팅 하향 없음')
    lines.append('')
else:
    for wk_key in ['this_week', 'last_week', 'older']:
        if wk_key not in by_week_down:
            continue
        lines.append(f'### {WEEK_KO[wk_key]}')
        lines.append('')
        lines.append('| 날짜 | 종목 | 증권사 | 기존→변경 | TP 기존→신규 | 변화율 |')
        lines.append('|------|------|--------|----------|------------|-------|')
        for row in sorted(by_week_down[wk_key], key=lambda x: x['date'], reverse=True):
            d_str = row['date'].strftime('%m/%d')
            op_change = f"{row['opinion_old']} → **{row['opinion_new']}**"
            tp_str = f"{fmt_tp(row['tp_old'])} → **{fmt_tp(row['tp_new'])}**"
            pct = chg_pct(row['tp_old'], row['tp_new'])
            lines.append(f"| {d_str} | {row['name']} | {row['firm']} | {op_change} | {tp_str} | {pct} |")
        lines.append('')

# ─── 3. TP 상향 — 종목별 컨센서스 추적 ───
lines.append('---')
lines.append('## 🎯 TP 상향 — 주간 컨센서스 추적 (TP_Up)')
lines.append('')
lines.append('> 이번 주(5/22~5/28) 같은 종목에 여러 애널이 동시에 TP 올리면 컨센서스 형성 신호')
lines.append('')

# 이번 주 데이터만 추출, 종목별 그룹
this_week_tp = [r for r in all_data['TP_Up'] if r['date'] and week_label(r['date']) == 'this_week']
last_week_tp = [r for r in all_data['TP_Up'] if r['date'] and week_label(r['date']) == 'last_week']

def group_by_stock(rows):
    d = defaultdict(list)
    for r in rows:
        d[r['name']].append(r)
    return d

def avg_tp(rows, field):
    vals = []
    for r in rows:
        try:
            vals.append(float(r[field]))
        except:
            pass
    return sum(vals) / len(vals) if vals else 0

def max_tp(rows):
    vals = []
    for r in rows:
        try:
            vals.append(float(r['tp_new']))
        except:
            pass
    return max(vals) if vals else 0

# 이번 주 — 업그레이드 수 많은 순
this_grouped = group_by_stock(this_week_tp)
this_sorted = sorted(this_grouped.items(), key=lambda x: len(x[1]), reverse=True)

lines.append('### 📅 이번 주 (5/22~5/28) — 증권사 수 많은 순')
lines.append('')

for name, rows in this_sorted:
    cnt = len(rows)
    # 신호 강도
    if cnt >= 5:
        sig = '🔴🔴🔴 강력 컨센서스'
    elif cnt >= 3:
        sig = '🔴🔴 컨센서스 형성중'
    elif cnt == 2:
        sig = '🔴 2개사 동시 상향'
    else:
        sig = '🟡 단독 상향'

    # TP 범위
    tp_olds = [float(r['tp_old']) for r in rows if r['tp_old']]
    tp_news = [float(r['tp_new']) for r in rows if r['tp_new']]
    tp_range = f"{fmt_tp(min(tp_news))}~{fmt_tp(max(tp_news))}" if len(tp_news) > 1 else fmt_tp(tp_news[0]) if tp_news else '-'
    tp_old_range = f"{fmt_tp(min(tp_olds))}~{fmt_tp(max(tp_olds))}" if len(tp_olds) > 1 else fmt_tp(tp_olds[0]) if tp_olds else '-'

    lines.append(f'#### {name} — {cnt}개사 | {sig}')
    lines.append(f'> TP 기존 범위: {tp_old_range} → 신규 범위: **{tp_range}**')
    lines.append('')
    lines.append('| 날짜 | 증권사 | TP 기존 | TP 신규 | 상승률 | 의견 |')
    lines.append('|------|--------|-------|-------|-------|------|')
    for r in sorted(rows, key=lambda x: x['date'], reverse=True):
        d_str = r['date'].strftime('%m/%d')
        pct = chg_pct(r['tp_old'], r['tp_new'])
        lines.append(f"| {d_str} | {r['firm']} | {fmt_tp(r['tp_old'])} | **{fmt_tp(r['tp_new'])}** | **{pct}** | {r['opinion_new']} |")
    lines.append('')

# 지난 주 — 요약만 (간략)
last_grouped = group_by_stock(last_week_tp)
last_sorted = sorted(last_grouped.items(), key=lambda x: len(x[1]), reverse=True)

lines.append('---')
lines.append('### 📅 지난 주 (5/15~5/21) — 요약')
lines.append('')
lines.append('| 종목 | 증권사 수 | TP 신규 범위 | 최고 상승률 |')
lines.append('|------|---------|------------|-----------|')
for name, rows in last_sorted:
    cnt = len(rows)
    tp_news = [float(r['tp_new']) for r in rows if r['tp_new']]
    tp_range = f"{fmt_tp(min(tp_news))}~{fmt_tp(max(tp_news))}" if len(tp_news) > 1 else fmt_tp(tp_news[0]) if tp_news else '-'
    # 최고 상승률
    max_r = 0
    for r in rows:
        try:
            o, n = float(r['tp_old']), float(r['tp_new'])
            if o > 0:
                max_r = max(max_r, (n - o) / o * 100)
        except:
            pass
    max_pct = f'+{max_r:.0f}%' if max_r > 0 else '-'
    cnt_str = f'{cnt}개사 {"🔴🔴🔴" if cnt>=5 else "🔴🔴" if cnt>=3 else "🔴" if cnt>=2 else ""}'
    lines.append(f'| {name} | {cnt_str} | {tp_range} | **{max_pct}** |')

lines.append('')

# ─── 4. TP 하향 요약 ───
lines.append('---')
lines.append('## 🔻 TP 하향 요약 (TP_Down)')
lines.append('')

tp_down_this = [r for r in all_data['TP_Down'] if r['date'] and week_label(r['date']) == 'this_week']
tp_down_last = [r for r in all_data['TP_Down'] if r['date'] and week_label(r['date']) == 'last_week']

for label, rows in [('이번 주 (5/22~5/28)', tp_down_this), ('지난 주 (5/15~5/21)', tp_down_last)]:
    if not rows:
        continue
    lines.append(f'### 📅 {label}')
    lines.append('')
    lines.append('| 날짜 | 종목 | 증권사 | TP 기존 | TP 신규 | 변화율 | 의견 |')
    lines.append('|------|------|--------|-------|-------|-------|------|')
    for r in sorted(rows, key=lambda x: x['date'], reverse=True):
        d_str = r['date'].strftime('%m/%d')
        pct = chg_pct(r['tp_old'], r['tp_new'])
        lines.append(f"| {d_str} | {r['name']} | {r['firm']} | {fmt_tp(r['tp_old'])} | **{fmt_tp(r['tp_new'])}** | {pct} | {r['opinion_new']} |")
    lines.append('')

out = '\n'.join(lines)
save_path = r'C:\Users\TheRose\Desktop\로또의 주식\raw\매일요약\20260529_추정이익변경_리레이팅TP상향.md'
with open(save_path, 'w', encoding='utf-8') as f:
    f.write(out)

print(f'저장 완료: {save_path}')
print()
print(f'Rating_Up: {len(all_data["Rating_Up"])}건')
print(f'Rating_Down: {len(all_data["Rating_Down"])}건')
print(f'TP_Up 이번주: {len(this_week_tp)}건 ({len(this_grouped)}종목)')
print(f'TP_Up 지난주: {len(last_week_tp)}건 ({len(last_grouped)}종목)')
print(f'TP_Down 이번주: {len(tp_down_this)}건 / 지난주: {len(tp_down_last)}건')
print()
print('=== 이번 주 TP_Up TOP10 (증권사 수) ===')
for name, rows in this_sorted[:10]:
    print(f'  {name}: {len(rows)}개사')
