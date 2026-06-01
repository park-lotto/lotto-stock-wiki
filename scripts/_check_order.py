"""
D2=LS ELECTRIC 후 H8~H20 전체 출력 → 어느 행이 최신값인지 확인
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32
import win32clipboard

def set_clip(text):
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)
ws = wb.Sheets('수급오실레이터')
ws.Activate()

for name, code, chart in [('SK하이닉스','A000660',-0.064), ('LS ELECTRIC','A010120',-0.070)]:
    set_clip(code)
    ws.Cells(2,4).Select(); xl.SendKeys("^v~", True)
    time.sleep(4); xl.Calculate(); time.sleep(1)

    print(f"=== {name} (차트≈{chart}%) ===")
    print(f"{'행':>4} {'날짜(A열)':>12} {'H(오실레이터)':>14}")
    for r in range(8, 25):
        a = ws.Cells(r, 1).Value2
        h = ws.Cells(r, 8).Value2
        if h is not None:
            try:
                print(f"  행{r:2d}  {str(a)[:10]:>12}  {float(h)*100:>12.5f}%  {'← 차트값!' if abs(float(h)*100-chart)<0.02 else ''}")
            except: pass
    print()

wb.Close(False); xl.Quit()
