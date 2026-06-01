"""
D2 변경 후 시기외 시트 전체 77행 읽기 → EMA 적용 → 차트값과 비교
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

def ema(vals, k):
    r=[vals[0]]
    for v in vals[1:]: r.append(v*k+r[-1]*(1-k))
    return r

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))
time.sleep(3)
ws_osc = wb.Sheets('수급오실레이터'); ws_sig = wb.Sheets('시기외')
ws_osc.Activate()

# SK하이닉스 기준 col3 전체 시리즈 (이미 EMA 적용된 oscillator)
sk_series = [float(ws_sig.Cells(r,3).Value2) for r in range(15,92)
             if ws_sig.Cells(r,3).Value2 is not None]
print(f"SK하이닉스 시기외 col3: 최신={sk_series[-1]*100:.4f}% (차트=-0.064%) → {'✅' if abs(sk_series[-1]*100+0.064)<0.02 else '❌'}")
print()

print(f"{'종목':<14} {'col3 raw':>10} {'EMA26':>10} {'EMA12':>10} {'MACD':>10} {'차트':>8}")
print('-'*65)

for name, code, chart_val in TARGETS:
    set_clip(code)
    ws_osc.Cells(2, 4).Select()
    xl.SendKeys("^v~", True)
    time.sleep(3); xl.Calculate(); time.sleep(1)

    # 전체 77행 읽기
    series = []
    for r in range(15, 92):
        v = ws_sig.Cells(r, 3).Value2
        if v is not None:
            try: series.append(float(v))
            except: pass

    if not series:
        print(f"{name:<14}  데이터없음"); continue

    raw_latest = series[-1]

    if len(series) >= 26:
        e12 = ema(series, 2/13)
        e26 = ema(series, 2/27)
        macd_val = e12[-1] - e26[-1]
    else:
        e12 = e26 = [0]; macd_val = 0

    best_candidates = {
        'raw': raw_latest,
        'EMA12': e12[-1],
        'EMA26': e26[-1],
        'MACD12-26': macd_val,
    }
    best_name = min(best_candidates, key=lambda x: abs(best_candidates[x]*100 - chart_val))
    best_val = best_candidates[best_name]
    err = abs(best_val*100 - chart_val)
    mark = '✅' if err < 0.02 else ('⚠️' if err < 0.05 else '❌')

    print(f"{name:<14} {raw_latest*100:>9.4f}% {e26[-1]*100:>9.4f}% {e12[-1]*100:>9.4f}% {macd_val*100:>9.4f}%  {chart_val:>6.3f}%")
    print(f"  최적: {best_name}={best_val*100:.4f}% 오차={err:.4f}% {mark}")

wb.Close(False); xl.Quit()
