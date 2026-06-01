"""한국 상대강도 파일 구조 파악"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

path = Path(__file__).parent.parent / 'raw' / '매일 엑셀넣을것' / '한국상대강도0601.xlsx'
wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
print(f'시트: {wb.sheetnames}\n')

for sname in wb.sheetnames:
    ws = wb[sname]
    print(f'=== [{sname}] {ws.max_row}행 × {ws.max_column}열 ===')
    for r in range(1, 6):
        row = [ws.cell(r, c).value for c in range(1, 15)]
        if any(v is not None for v in row):
            print(f'  행{r}: {row}')
    print()

wb.close()
