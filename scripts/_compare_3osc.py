"""오실레이터 3개 내부 구조 비교"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / '매일 엑셀넣을것'

files = [
    ('(700)',      SAVE_DIR / '외국인기관수급오실레이터(700).xlsm'),
    ('(700-1400)', SAVE_DIR / '외국인기관수급오실레이터(700-1400).xlsm'),
    ('(업종)',      SAVE_DIR / '외국인기관수급오실레이터(업종).xlsm'),
]

KEY_SHEETS = ['수급오실레이터', '외국인매수데이터', '기관매수데이터', '시가총액', '시기외', '업종오실레이터']

for label, path in files:
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)
    print(f'=== {label}  ({path.stat().st_size//1024}KB) ===')
    print(f'  시트: {wb.sheetnames}')

    for sname in KEY_SHEETS:
        if sname in wb.sheetnames:
            ws = wb[sname]
            print(f'  [{sname}] {ws.max_row}행 × {ws.max_column}열')

    # 종목명 수 (외국인매수데이터 9행)
    for sheet_cand in ['외국인매수데이터', '수급오실레이터']:
        if sheet_cand not in wb.sheetnames: continue
        ws = wb[sheet_cand]
        names = []
        for cell in ws[9]:
            if cell.value and isinstance(cell.value, str) and len(cell.value) > 1:
                names.append(cell.value)
        if names:
            print(f'  종목/항목 수 ({sheet_cand} 9행): {len(names)}개')
            print(f'  샘플: {names[:5]}')
            break

    # 날짜범위 (1열 15~91행)
    for sheet_cand in ['외국인매수데이터', '수급오실레이터']:
        if sheet_cand not in wb.sheetnames: continue
        ws = wb[sheet_cand]
        dates = []
        for r in range(15, 92):
            v = ws.cell(r, 1).value
            if v: dates.append(str(v)[:10])
        if dates:
            print(f'  날짜범위: {dates[0]} ~ {dates[-1]} ({len(dates)}거래일)')
            break

    # p10/p25 기준값 (수급오실레이터 L10, L11)
    for sheet_cand in ['수급오실레이터']:
        if sheet_cand not in wb.sheetnames: continue
        ws = wb[sheet_cand]
        p10 = ws.cell(11, 12).value
        p25 = ws.cell(10, 12).value
        try:
            if p10: print(f'  기준 p10={float(p10):.6f}  p25={float(p25):.6f}')
        except: print(f'  기준 p10={p10}  p25={p25}')

    wb.close()
    print()
