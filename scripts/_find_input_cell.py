"""
수급오실레이터 시트에서 실제 종목코드 입력 셀 찾기
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(2)

ws = wb.Sheets('수급오실레이터')

# 1. 현재 SK하이닉스 코드(A000660)가 들어있는 셀 찾기
print("=== 'A000660' 포함 셀 ===")
used = ws.UsedRange
for r in range(1, min(used.Rows.Count+1, 20)):
    for c in range(1, min(used.Columns.Count+1, 20)):
        v = ws.Cells(r, c).Value2
        if v and 'A000660' in str(v):
            print(f"  행{r} 열{c}: '{v}'")

# 2. 컨트롤(드롭다운 등) 확인
print("\n=== OLEObjects (ActiveX 컨트롤) ===")
try:
    for obj in ws.OLEObjects():
        print(f"  {obj.Name}: {obj.TopLeftCell.Address}")
except: print("  없음")

print("\n=== Shapes (Form 컨트롤) ===")
try:
    for sh in ws.Shapes:
        print(f"  {sh.Name} ({sh.Type}): {sh.TopLeftCell.Address if hasattr(sh, 'TopLeftCell') else 'N/A'}")
        try:
            if sh.Type == 8:  # msoComboBox
                print(f"    → ComboBox!")
        except: pass
except Exception as e:
    print(f"  {e}")

# 3. Named Ranges 중 종목 관련
print("\n=== Named Ranges (종목 관련) ===")
for nm in wb.Names:
    try:
        name = nm.Name
        if any(k in name for k in ['종목', 'code', 'Code', 'stock', 'Stock', '코드']):
            print(f"  {name}: {nm.RefersTo}")
    except: pass

wb.Close(False); xl.Quit()
