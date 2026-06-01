"""
D2 변경 후 수급오실레이터 H91 (최신 오실레이터) 읽기
"""
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

# H 컬럼 마지막 유효 행 찾기 (SK하이닉스 기준)
last_row = 91
for r in range(200, 7, -1):
    v = ws.Cells(r, 8).Value2
    if v is not None:
        try:
            float(v)
            last_row = r
            break
        except: pass
print(f"H 컬럼 마지막 유효 행: {last_row}")
print(f"H{last_row} (SK기준 현재): {ws.Cells(last_row, 8).Value2}")
print()

print(f"{'종목':<14} {'H마지막':>12} {'차트값':>9} {'오차':>9} 판정")
print('-'*52)

for name, code, chart_val in TARGETS:
    set_clip(code)
    ws.Cells(2, 4).Select()
    xl.SendKeys("^v~", True)
    time.sleep(4)
    xl.Calculate()
    time.sleep(1)

    # H 컬럼 최신값
    val = None
    for r in range(last_row, 7, -1):
        v = ws.Cells(r, 8).Value2
        if v is not None:
            try:
                val = float(v)
                break
            except: pass

    if val is not None:
        err = abs(val*100 - chart_val)
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {val*100:>11.5f}% {chart_val:>8.3f}% {err:>8.5f}%  {mark}")
    else:
        print(f"{name:<14}  읽기실패")

wb.Close(False); xl.Quit()
