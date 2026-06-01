"""
수급오실레이터 시트 B2에 종목코드 입력 → VBA 트리거 → 시기외 값 읽기
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

TARGETS = {
    'SK하이닉스':  'A000660',
    'LS ELECTRIC': 'A010120',
    '일진전기':    'A103590',
    '산일전기':    'A062040',
    '대한전선':    'A001440',
}
CHART_VALS = {
    'SK하이닉스':  -0.064,
    'LS ELECTRIC': -0.070,
    '일진전기':    -0.123,
    '산일전기':    -0.200,
    '대한전선':    -0.200,
}

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = True           # 화면 표시 (VBA 이벤트 활성화)
xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(2)

ws_osc = wb.Sheets('수급오실레이터')
ws_sig = wb.Sheets('시기외')

print(f"{'종목':<14} {'읽은값':>10} {'차트값':>10} {'오차':>10} 판정")
print('-'*55)

for name, code in TARGETS.items():
    # B2에 종목코드 입력 → Change 이벤트 발동
    ws_osc.Cells(2, 2).Value = code
    xl.Calculate()
    time.sleep(2)  # VBA 계산 대기

    # 시기외 시트 최신값 읽기 (row 91 = 마지막 데이터)
    val = None
    for r in range(91, 14, -1):
        v = ws_sig.Cells(r, 3).Value2
        if v is not None:
            val = float(v)
            break

    if val is not None:
        err = abs(val*100 - CHART_VALS[name])
        mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')
        print(f"{name:<14} {val*100:>9.4f}% {CHART_VALS[name]:>9.3f}% {err:>9.4f}%  {mark}")
    else:
        print(f"{name:<14}  읽기실패")

wb.Close(False)
xl.Quit()
