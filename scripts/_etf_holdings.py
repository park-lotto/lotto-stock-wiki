import sys; sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from scripts.ingest_excel import find_excel, load_wb

path = find_excel("소라티노ETF상대강도")
wb = load_wb(path)
print('시트 목록:')
for s in wb.sheetnames:
    print(f'  {s}')
wb.close()
