import win32com.client, os
from datetime import datetime

file_path = os.path.abspath(r'C:\Users\TheRose\Desktop\로또의 주식\raw\매일 엑셀넣을것\추정이익 변경0528.xlsm')
xl = win32com.client.Dispatch('Excel.Application')
xl.Visible = False
xl.DisplayAlerts = False
xl.AutomationSecurity = 3

wb = xl.Workbooks.Open(file_path)

def parse_date(v):
    if v is None: return ''
    s = str(v)
    return s[:10] if len(s) >= 10 else s

def fmt_price(v):
    if v is None or v == '': return '-'
    try:
        n = float(str(v).replace(',', ''))
        if n >= 10000000: return f'{n/10000:.0f}만'
        if n >= 1000000: return f'{n/10000:.1f}만'
        if n >= 1000: return f'{int(n):,}'
        return str(int(n))
    except:
        return str(v)

def chg_rate(old, new):
    try:
        o, n = float(old), float(new)
        if o == 0: return ''
        r = (n - o) / o * 100
        return f'+{r:.0f}%' if r > 0 else f'{r:.0f}%'
    except:
        return ''

all_data = {}
for sheet_name in ['Rating_Up', 'Rating_Down', 'TP_Up', 'TP_Down']:
    ws = wb.Sheets(sheet_name)
    rows = []
    r = 12
    while True:
        v2 = ws.Cells(r, 2).Value
        if v2 is None:
            break
        row = [ws.Cells(r, c).Value for c in range(2, 20)]
        rows.append(row)
        r += 1
    all_data[sheet_name] = rows

wb.Close(False)
xl.Quit()

lines = ['# 추정이익 변경 — 2026-05-28 수집 (5/16~5/28)', '']
lines.append('> 파일: 추정이익 변경0528.xlsm | 수집일: 2026-05-28 | 기간: 20260516~20260528')
lines.append('')

# Rating_Up
lines.append('## 🔺 리레이팅(투자의견 상향) — Rating_Up')
lines.append('')
lines.append('| 일자 | 종목 | 코드 | 증권사 | 기존의견 | 변경의견 | TP기존 | TP신규 | 변화율 |')
lines.append('|------|------|------|--------|---------|---------|-------|-------|-------|')
for row in all_data['Rating_Up']:
    날짜 = parse_date(row[0])
    코드 = str(row[1]).replace('A', '') if row[1] else ''
    종목 = str(row[2]) if row[2] else ''
    증권사 = str(row[4]) if row[4] else ''
    기존의견 = str(row[10]) if row[10] else ''
    변경의견 = str(row[11]) if row[11] else ''
    tp기존 = fmt_price(row[12])
    tp신규 = fmt_price(row[13])
    변화율 = chg_rate(row[12], row[13])
    lines.append(f'| {날짜} | {종목} | {코드} | {증권사} | {기존의견} | **{변경의견}** | {tp기존} | **{tp신규}** | {변화율} |')
lines.append('')

# Rating_Down
lines.append('## 🔻 리레이팅(투자의견 하향) — Rating_Down')
lines.append('')
lines.append('| 일자 | 종목 | 코드 | 증권사 | 기존의견 | 변경의견 | TP기존 | TP신규 | 변화율 |')
lines.append('|------|------|------|--------|---------|---------|-------|-------|-------|')
for row in all_data['Rating_Down']:
    날짜 = parse_date(row[0])
    코드 = str(row[1]).replace('A', '') if row[1] else ''
    종목 = str(row[2]) if row[2] else ''
    증권사 = str(row[4]) if row[4] else ''
    기존의견 = str(row[10]) if row[10] else ''
    변경의견 = str(row[11]) if row[11] else ''
    tp기존 = fmt_price(row[12])
    tp신규 = fmt_price(row[13])
    변화율 = chg_rate(row[12], row[13])
    lines.append(f'| {날짜} | {종목} | {코드} | {증권사} | {기존의견} | **{변경의견}** | {tp기존} | **{tp신규}** | {변화율} |')
lines.append('')

# TP_Up
wiki_stocks = {
    'SK하이닉스', '삼성전자', '삼성전기', '코미코', '솔브레인', '한미반도체', 'LG이노텍', '심텍',
    '파크시스템스', '브이엠', '피에스케이', '아이씨티케이', '대덕전자', '두산테스나', 'HD현대중공업',
    '한화오션', '비에이치아이', '수산인더스트리', '한화에어로스페이스', '한국항공우주',
    'LIG디펜스앤에어로스페이스', '한화시스템', 'LS ELECTRIC', 'LS에코에너지', '산일전기', '일진전기',
    '한전KPS', '한전기술', '레인보우로보틱스', '두산로보틱스', '에스피지', 'HD한국조선해양',
    '이수페타시스', '아모텍', 'SK스퀘어', '솔루엠', '이오테크닉스', '테크윙', '코리아써키트'
}

tp_up_scored = []
for row in all_data['TP_Up']:
    try:
        o, n = float(row[12]), float(row[13])
        rate = (n - o) / o * 100 if o > 0 else 0
    except:
        rate = 0
    tp_up_scored.append((rate, row))

wiki_rows = [(r, row) for r, row in tp_up_scored if str(row[2]) in wiki_stocks]
other_rows = sorted([(r, row) for r, row in tp_up_scored if str(row[2]) not in wiki_stocks], key=lambda x: -x[0])

lines.append(f'## 🔺 TP 상향 — TP_Up (전체 {len(all_data["TP_Up"])}건)')
lines.append('')
lines.append('> ⭐ = 위키 보유 종목 | 나머지는 상승률 순 정렬')
lines.append('')
lines.append('| 일자 | 종목 | 코드 | 증권사 | TP기존 | TP신규 | 상승률 | 의견 |')
lines.append('|------|------|------|--------|-------|-------|-------|------|')

seen = set()
for rate, row in wiki_rows + other_rows:
    날짜 = parse_date(row[0])
    코드 = str(row[1]).replace('A', '') if row[1] else ''
    종목 = str(row[2]) if row[2] else ''
    key = f'{종목}-{str(row[4])}'
    if key in seen:
        continue
    seen.add(key)
    증권사 = str(row[4]) if row[4] else ''
    tp기존 = fmt_price(row[12])
    tp신규 = fmt_price(row[13])
    변화율 = f'+{rate:.0f}%' if rate > 0 else f'{rate:.0f}%'
    의견 = str(row[11]) if row[11] else ''
    mark = '⭐' if 종목 in wiki_stocks else ''
    lines.append(f'| {날짜} | {mark}{종목} | {코드} | {증권사} | {tp기존} | **{tp신규}** | **{변화율}** | {의견} |')

lines.append('')

# TP_Down
lines.append(f'## 🔻 TP 하향 — TP_Down (전체 {len(all_data["TP_Down"])}건)')
lines.append('')
lines.append('| 일자 | 종목 | 코드 | 증권사 | TP기존 | TP신규 | 변화율 | 의견 |')
lines.append('|------|------|------|--------|-------|-------|-------|------|')
for row in all_data['TP_Down']:
    날짜 = parse_date(row[0])
    코드 = str(row[1]).replace('A', '') if row[1] else ''
    종목 = str(row[2]) if row[2] else ''
    증권사 = str(row[4]) if row[4] else ''
    tp기존 = fmt_price(row[12])
    tp신규 = fmt_price(row[13])
    변화율 = chg_rate(row[12], row[13])
    의견 = str(row[11]) if row[11] else ''
    lines.append(f'| {날짜} | {종목} | {코드} | {증권사} | {tp기존} | **{tp신규}** | {변화율} | {의견} |')

out = '\n'.join(lines)
save_path = r'C:\Users\TheRose\Desktop\로또의 주식\raw\매일요약\20260529_추정이익변경_리레이팅TP상향.md'
with open(save_path, 'w', encoding='utf-8') as f:
    f.write(out)

print(f'저장 완료: {save_path}')
print(f'Rating_Up: {len(all_data["Rating_Up"])}건')
print(f'Rating_Down: {len(all_data["Rating_Down"])}건')
print(f'TP_Up: {len(all_data["TP_Up"])}건')
print(f'TP_Down: {len(all_data["TP_Down"])}건')
