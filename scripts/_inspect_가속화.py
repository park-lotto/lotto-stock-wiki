"""가속화모멘텀 시트 구조 파악"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

BASE = Path(__file__).parent.parent
path = next((BASE / 'raw' / '매일 엑셀넣을것').glob('유동성*0601.xlsm'))
print(f'파일: {path.name}  ({path.stat().st_size//1024}KB)\n')

wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)
print(f'시트목록: {wb.sheetnames}\n')

ws = wb['가속화모멘텀']
print(f'크기: {ws.max_row}행 × {ws.max_column}열\n')

# 1~15행 전체 출력
print('=== 1~15행 ===')
for r in range(1, 16):
    row = [ws.cell(r, c).value for c in range(1, min(ws.max_column+1, 20))]
    if any(v is not None for v in row):
        print(f'  행{r:2d}: {row}')

# 헤더 찾기 (종목명·코드 있는 행)
print('\n=== 헤더 탐색 (처음 30행) ===')
for r in range(1, 31):
    row = [ws.cell(r, c).value for c in range(1, min(ws.max_column+1, 25))]
    vals = [str(v) for v in row if v is not None]
    if any(k in ' '.join(vals) for k in ['종목', '코드', '섹터', '업종', 'Rank', '순위', '수익률']):
        print(f'  행{r:2d} [헤더후보]: {vals[:15]}')

# 데이터 샘플 (헤더 이후 10행)
print('\n=== 데이터 샘플 (16~30행) ===')
for r in range(16, 31):
    row = [ws.cell(r, c).value for c in range(1, min(ws.max_column+1, 20))]
    if any(v is not None for v in row):
        print(f'  행{r:2d}: {row[:15]}')

wb.close()
