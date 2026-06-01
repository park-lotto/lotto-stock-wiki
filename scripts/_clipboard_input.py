"""
클립보드로 종목코드 입력 → VBA 트리거 → 시기외 값 읽기
한글/영어 키보드 문제 없음
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

def set_clipboard(text):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True
xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)

ws_osc = wb.Sheets('수급오실레이터')
ws_sig = wb.Sheets('시기외')
ws_osc.Activate()

print(f"{'종목':<14} {'읽은값':>10} {'차트값':>9} {'오차':>9} 판정")
print('-'*52)

for name, code, chart_val in TARGETS:
    # 클립보드에 코드 복사 → 셀에 붙여넣기
    set_clipboard(code)
    ws_osc.Cells(2, 2).Select()
    xl.SendKeys("^v~", True)   # Ctrl+V → Enter
    time.sleep(3)
    xl.Calculate()
    time.sleep(1)

    # 현재 B2 값 확인
    b2 = ws_osc.Cells(2, 2).Value2
    # 시기외 최신값 읽기
    val = None
    for r in range(91, 14, -1):
        v = ws_sig.Cells(r, 3).Value2
        if v is not None:
            val = float(v)
            break

    if val is not None:
        err = abs(val*100 - chart_val)
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {val*100:>9.4f}% {chart_val:>8.3f}% {err:>8.4f}%  {mark}  [B2={b2}]")
    else:
        print(f"{name:<14}  읽기실패  [B2={b2}]")

wb.Close(False)
xl.Quit()
