"""업종 오실레이터 파일 구조 상세 파악"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

path = Path(__file__).parent.parent / 'raw' / '매일 엑셀넣을것' / '외국인기관수급오실레이터(업종).xlsm'
wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)

print('=== 시트목록 ===')
for s in wb.sheetnames:
    ws = wb[s]
    print(f'  [{s}] {ws.max_row}행 × {ws.max_column}열')

# 시기외 구조 파악 (업종명 있는 행 찾기)
print('\n=== 시기외 시트 1~10행 ===')
ws = wb['시기외']
for r in range(1, 11):
    row = [ws.cell(r, c).value for c in range(1, 15)]
    print(f'  행{r}: {row}')

# 시기외 8~9행 (업종명 헤더 예상)
print('\n=== 시기외 8~9행 전체 (업종명) ===')
for r in [8, 9]:
    vals = []
    for c in range(1, 260):
        v = ws.cell(r, c).value
        if v: vals.append(f'[{c}]{v}')
    print(f'  행{r}: {vals[:30]}')

# 15~91행 1열 (날짜)
print('\n=== 시기외 날짜 (1열 15~20행) ===')
for r in range(15, 21):
    print(f'  행{r}: {ws.cell(r, 1).value}')

# 오실 시트 파악
if '오실' in wb.sheetnames:
    print('\n=== 오실 시트 1~10행 ===')
    ws2 = wb['오실']
    print(f'  크기: {ws2.max_row}행 × {ws2.max_column}열')
    for r in range(1, 6):
        row = [ws2.cell(r, c).value for c in range(1, 15)]
        print(f'  행{r}: {row}')

# 그래프뽑기 시트
if '그래프뽑기' in wb.sheetnames:
    print('\n=== 그래프뽑기 시트 1~15행 ===')
    ws3 = wb['그래프뽑기']
    print(f'  크기: {ws3.max_row}행 × {ws3.max_column}열')
    for r in range(1, 16):
        row = [ws3.cell(r, c).value for c in range(1, 10)]
        if any(v is not None for v in row):
            print(f'  행{r}: {row}')

wb.close()
