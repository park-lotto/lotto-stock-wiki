import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32
import win32clipboard

TARGETS = [
    ('SK하이닉스',  'A000660', -0.064),
    ('LS ELECTRIC', 'A010120', -0.070),
    ('일진전기',    'A103590', -0.123),
    ('산일전기',    'A062040', -0.200),
    ('대한전선',    'A001440', -0.200),
]

def set_clip(text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)

ws_osc = wb.Sheets('수급오실레이터')
ws_sig = wb.Sheets('시기외')
ws_osc.Activate()

print(f"D2 현재값: {ws_osc.Cells(2,4).Value2}")
print(f"H2 현재값: {ws_osc.Cells(2,8).Value2}")
print()
print(f"{'종목':<14} {'D2입력':>10} {'읽은값':>10} {'차트값':>9} {'오차':>9} 판정")
print('-'*60)

for name, code, chart_val in TARGETS:
    # D2에 코드 붙여넣기
    set_clip(code)
    ws_osc.Cells(2, 4).Select()
    xl.SendKeys("^v~", True)
    time.sleep(3)
    xl.Calculate()
    time.sleep(1)

    d2_val = ws_osc.Cells(2, 4).Value2
    val = None
    for r in range(91, 14, -1):
        v = ws_sig.Cells(r, 3).Value2
        if v is not None and abs(float(v)) < 10:   # 합리적 범위만
            val = float(v); break

    if val is not None:
        err = abs(val*100 - chart_val)
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {str(d2_val):>10} {val*100:>9.4f}% {chart_val:>8.3f}% {err:>8.4f}%  {mark}")
    else:
        print(f"{name:<14} {str(d2_val):>10}  읽기실패")

wb.Close(False); xl.Quit()
