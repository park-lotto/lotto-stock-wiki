"""
D2에 종목코드 입력 → 수급오실레이터 C7 읽기 (오실레이터 절대값)
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
xl.Visible = False; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)

ws_osc = wb.Sheets('수급오실레이터')
ws_osc.Activate()

# 현재 상태 확인
print(f"C7 현재값: {ws_osc.Cells(7,3).Value2}")
print(f"C8 현재값: {ws_osc.Cells(8,3).Value2}")
print(f"D2 현재값: {ws_osc.Cells(2,4).Value2}")
print()
print(f"{'종목':<14} {'C7 오실레이터':>14} {'차트값':>9} {'오차':>9} 판정")
print('-'*55)

for name, code, chart_val in TARGETS:
    set_clip(code)
    ws_osc.Cells(2, 4).Select()
    xl.SendKeys("^v~", True)
    time.sleep(3)
    xl.Calculate()
    time.sleep(1)

    c7 = ws_osc.Cells(7, 3).Value2
    c8 = ws_osc.Cells(8, 3).Value2
    d2 = ws_osc.Cells(2, 4).Value2

    if c7 is not None:
        try:
            val = float(c7) * 100
            err = abs(val - chart_val)
            mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
            print(f"{name:<14} {val:>13.5f}% {chart_val:>8.3f}% {err:>8.5f}%  {mark}  [D2={d2}]")
        except:
            print(f"{name:<14}  C7={c7}  [D2={d2}]")
    else:
        print(f"{name:<14}  C7=None  [D2={d2}]")

wb.Close(False); xl.Quit()
