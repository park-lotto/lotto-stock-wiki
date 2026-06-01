import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32
import win32clipboard

TARGETS = [
    ('SK하이닉스',  -0.064),
    ('LS ELECTRIC', -0.070),
    ('일진전기',    -0.123),
    ('산일전기',    -0.200),
    ('대한전선',    -0.200),
]

def set_clip(t):
    win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(t, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)
ws = wb.Sheets('수급오실레이터')
ws.Activate()

print(f"{'종목':<14} {'L12값':>12} {'차트값':>9} {'오차':>9} 판정")
print('-'*52)

for name, chart_val in TARGETS:
    set_clip(name)
    ws.Cells(2, 3).Select()
    xl.SendKeys("^v~", True)
    time.sleep(4); xl.Calculate(); time.sleep(1)

    l12 = ws.Cells(12, 12).Value2
    if l12 is not None:
        val = float(l12) * 100
        err = abs(val - chart_val)
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {val:>11.5f}% {chart_val:>8.3f}% {err:>8.5f}%  {mark}")
    else:
        print(f"{name:<14}  L12=None")

wb.Close(False); xl.Quit()
