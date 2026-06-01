"""
Excel 셀에 직접 키보드 입력 → Worksheet_Change 이벤트 발동 → 시기외 값 읽기
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32
import win32con
import win32gui

TARGETS = [
    ('SK하이닉스',  'A000660', -0.064),
    ('LS ELECTRIC', 'A010120', -0.070),
    ('일진전기',    'A103590', -0.123),
    ('산일전기',    'A062040', -0.200),
    ('대한전선',    'A001440', -0.200),
]

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True
xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)

ws_osc = wb.Sheets('수급오실레이터')
ws_sig = wb.Sheets('시기외')

# 수급오실레이터 시트 활성화 + B2 셀 선택
ws_osc.Activate()

print(f"{'종목':<14} {'읽은값':>10} {'차트값':>9} {'오차':>9} 판정")
print('-'*52)

for name, code, chart_val in TARGETS:
    # B2에 코드 입력 후 Enter
    ws_osc.Cells(2, 2).Select()
    xl.SendKeys(code + "~", True)   # ~ = Enter
    time.sleep(2)
    xl.Calculate()
    time.sleep(1)

    # 시기외 최신값
    val = None
    for r in range(91, 14, -1):
        v = ws_sig.Cells(r, 3).Value2
        if v is not None:
            val = float(v)
            break

    if val is not None:
        err = abs(val*100 - chart_val)
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {val*100:>9.4f}% {chart_val:>8.3f}% {err:>8.4f}%  {mark}")
    else:
        print(f"{name:<14}  읽기실패")

wb.Close(False)
xl.Quit()
