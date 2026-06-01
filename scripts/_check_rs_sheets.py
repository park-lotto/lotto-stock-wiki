"""유동성 파일 주요 시트 RS 확인"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

BASE = Path(__file__).parent.parent
path = next((BASE / 'raw' / '매일 엑셀넣을것').glob('유동성*0601.xlsm'))
wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)

for sname in ['주도주찾기', '코스피최종', '코스닥최종']:
    if sname not in wb.sheetnames: continue
    ws = wb[sname]
    print(f'\n=== [{sname}] {ws.max_row}행 × {ws.max_column}열 ===')
    for r in range(1, 8):
        row = [ws.cell(r, c).value for c in range(1, 15)]
        if any(v is not None for v in row):
            print(f'  행{r}: {row}')

wb.close()
