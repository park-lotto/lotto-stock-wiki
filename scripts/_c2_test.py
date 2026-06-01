"""
C2에 종목이름 입력 → 출력 셀 탐색
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

print(f"C2 현재값: {ws.Cells(2,3).Value2}")
print()

# 일진전기로 테스트 (정답=-0.123%)
set_clip('일진전기')
ws.Cells(2, 3).Select()
xl.SendKeys("^v~", True)
time.sleep(5)
xl.Calculate()
time.sleep(1)

print(f"C2 변경 후: {ws.Cells(2,3).Value2}")
print()

# -0.123% 근처 셀 전체 탐색
target = -0.123 / 100
print("=== -0.123% ± 0.02% 범위 셀 ===")
found = []
for r in range(1, 200):
    for c in range(1, 50):
        try:
            v = ws.Cells(r, c).Value2
            if v is None: continue
            fv = float(v)
            if abs(fv - target) < 0.0002:
                col_l = chr(64+c) if c<=26 else f"A{chr(64+c-26)}"
                found.append((r, c, col_l, fv))
                print(f"  {col_l}{r}: {fv*100:.5f}%  ← 차트값!")
        except: pass

if not found:
    print("  없음")

# 시기외 col3도 확인
ws_sig = wb.Sheets('시기외')
sig_latest = None
for r in range(91, 14, -1):
    v = ws_sig.Cells(r, 3).Value2
    if v is not None:
        try:
            f = float(v)
            if abs(f) < 10:
                sig_latest = f; break
        except: pass
print(f"\n시기외 col3 최신: {sig_latest*100:.5f}%" if sig_latest else "\n시기외 col3: 없음")

wb.Close(False); xl.Quit()
