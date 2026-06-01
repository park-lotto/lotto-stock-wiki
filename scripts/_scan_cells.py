"""
D2=A010120(LS ELECTRIC) 변경 후 어떤 셀이 -0.07% 에 가까운 값을 가지는지 전수 탐색
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

ws_osc = wb.Sheets('수급오실레이터')
ws_osc.Activate()

# LS ELECTRIC 입력
set_clip('A010120')
ws_osc.Cells(2, 4).Select()
xl.SendKeys("^v~", True)
time.sleep(5)
xl.Calculate()
time.sleep(2)

print(f"D2: {ws_osc.Cells(2,4).Value2}")
print()
print("=== -0.07% ± 0.05% 범위 셀 탐색 ===")
target = -0.070 / 100  # -0.00070

hits = []
for r in range(1, 50):
    for c in range(1, 30):
        try:
            v = ws_osc.Cells(r, c).Value2
            if v is None: continue
            fv = float(v)
            if abs(fv - target) < 0.0005:  # ±0.05% 범위
                col_letter = chr(64+c) if c <= 26 else f"A{chr(64+c-26)}"
                hits.append((r, c, col_letter, fv))
                print(f"  {col_letter}{r}: {fv*100:.5f}%")
        except: pass

if not hits:
    print("  없음 — 범위 확장해서 재탐색")
    for r in range(1, 100):
        for c in range(1, 60):
            try:
                v = ws_osc.Cells(r, c).Value2
                if v is None: continue
                fv = float(v)
                if abs(fv - target) < 0.002:  # ±0.2% 범위로 확장
                    col_letter = chr(64+c) if c <= 26 else f"A{chr(64+c-26)}"
                    print(f"  {col_letter}{r}: {fv*100:.5f}%")
            except: pass

# L12도 확인
print()
print(f"L12 값: {ws_osc.Cells(12, 12).Value2}")
print(f"L7~L12:")
for r in range(7, 13):
    v = ws_osc.Cells(r, 12).Value2
    vk = ws_osc.Cells(r, 11).Value2
    print(f"  K{r}={vk}  L{r}={v}")

wb.Close(False); xl.Quit()
