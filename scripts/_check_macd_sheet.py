import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 3
wb = xl.Workbooks.Open(str(path))

# MACD 시트 구조
ws = wb.Sheets('MACD')
print("=== MACD 시트 ===")
for r in range(1, 15):
    row = [ws.Cells(r, c).Value2 for c in range(1, 12)]
    if any(v is not None for v in row):
        print(f"행{r}: {row}")

print()
max_col = ws.UsedRange.Columns.Count
max_row = ws.UsedRange.Rows.Count
print(f"사용 범위: {max_row}행 × {max_col}열")

# 대상 종목 컬럼 찾기
targets = {'LS ELECTRIC':'A010120', '일진전기':'A103590', '산일전기':'A062040',
           '대한전선':'A001440', 'SK하이닉스':'A000660'}

print()
print("=== MACD 시트에서 종목 찾기 ===")
for name, code in targets.items():
    col = None
    for c in range(1, min(max_col+1, 800)):
        v = ws.Cells(8, c).Value2  # 코드 행
        if v == code:
            col = c
            break
        v2 = ws.Cells(9, c).Value2  # 이름 행
        if v2 and name in str(v2):
            col = c
            break
    if col:
        # 최신값 읽기
        latest = ws.Cells(max_row, col).Value2
        print(f"  {name}: 컬럼={col}, 최신값={latest}")
    else:
        print(f"  {name}: ❌ 없음")

# 시그널 시트도 확인
print()
print("=== 시그널 시트 앞 5행 ===")
ws2 = wb.Sheets('시그널')
for r in range(1, 10):
    row = [ws2.Cells(r, c).Value2 for c in range(1, 8)]
    if any(v is not None for v in row):
        print(f"행{r}: {row}")
mr = ws2.UsedRange.Rows.Count
mc = ws2.UsedRange.Columns.Count
print(f"사용 범위: {mr}행 × {mc}열")

wb.Close(False); xl.Quit()
