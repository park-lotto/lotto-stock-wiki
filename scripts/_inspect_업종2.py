"""오실 시트 실제 값 확인"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

path = Path(__file__).parent.parent / 'raw' / '매일 엑셀넣을것' / '외국인기관수급오실레이터(업종).xlsm'
wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)
ws = wb['오실']

# 업종명 9행 전체
names = {}
for c in range(2, ws.max_column + 1):
    v = ws.cell(9, c).value
    if v and isinstance(v, str): names[c] = v

print(f'업종명 컬럼 수: {len(names)}')
print('처음 20개:', list(names.items())[:20])

# 마지막 행 (91행) 값 샘플
print('\n=== 오실 91행 최신값 (처음 20열) ===')
row91 = {}
for c in range(2, min(42, ws.max_column + 1)):
    v = ws.cell(91, c).value
    if v is not None:
        row91[c] = round(float(v), 6)
print(row91)

# 15행 첫 날짜 값
print('\n=== 오실 15행 (첫날) 처음 20열 ===')
for c in range(2, min(22, ws.max_column+1)):
    v = ws.cell(15, c).value
    print(f'  열{c} [{names.get(c,"?")}]: {v}')

wb.close()
