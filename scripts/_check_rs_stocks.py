import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

path = Path(__file__).parent.parent / 'raw' / '매일 엑셀넣을것' / '한국상대강도0601.xlsx'
wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
ws = wb['종가']
headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
stocks = [h for h in headers if h and h not in ['DATE', '코스피']]
print(f'총 종목 수: {len(stocks)}개')
print(f'종목 목록:')
for i, s in enumerate(stocks, 1):
    print(f'  {i:3d}. {s}')
wb.close()
