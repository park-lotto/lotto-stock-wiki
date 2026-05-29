import win32com.client, os

file_path = os.path.abspath(r'C:\Users\TheRose\Desktop\로또의 주식\raw\매일 엑셀넣을것\추정이익 변경0528.xlsm')
xl = win32com.client.Dispatch('Excel.Application')
xl.Visible = False
xl.DisplayAlerts = False
xl.AutomationSecurity = 1  # msoAutomationSecurityLow — 매크로 허용

wb = xl.Workbooks.Open(file_path)

import time
time.sleep(3)  # 매크로 실행 대기

for sheet_name in ['Rating_Up', 'Rating_Down']:
    ws = wb.Sheets(sheet_name)
    print(f'=== {sheet_name} ===')
    # 행 개수 파악 (빈 행 나올 때까지)
    r = 12
    count = 0
    while r < 200:
        v = ws.Cells(r, 4).Value  # 종목명 컬럼
        if v is None:
            empty_check = ws.Cells(r, 2).Value
            if empty_check is None:
                break
        if v:
            print(f'  R{r}: 종목={v} | 증권사={ws.Cells(r,6).Value} | 기존={ws.Cells(r,12).Value} | 변경={ws.Cells(r,13).Value}')
            count += 1
        r += 1
    print(f'  → 총 {count}건')
    print()

wb.Close(False)
xl.Quit()
