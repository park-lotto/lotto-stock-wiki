"""
수급오실레이터 전체 종목 스캔
단계1: 매크로 비활성으로 데이터 읽기 (팝업 없음)
단계2: 매크로 활성으로 C2→L12 스캔 (팝업 자동클릭)
"""
import sys, os, time, json, threading
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32
import win32gui, win32con, win32api
from pathlib import Path
from datetime import date

XLSM_PATH = str(co.find_xlsm())
BATCH = 100

def auto_dismiss(timeout=15):
    """업데이트/확인 팝업 자동 클릭 스레드"""
    KEYWORDS = {'업데이트', '확인', '예', 'Update', 'OK', 'Yes', '계속', 'Enable', '사용'}
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.3)
        def check(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return True
            title = win32gui.GetWindowText(hwnd)
            if not title: return True
            def check_btn(h, _):
                txt = win32gui.GetWindowText(h)
                if txt in KEYWORDS:
                    win32api.PostMessage(h, win32con.WM_LBUTTONDOWN, 0, 0)
                    win32api.PostMessage(h, win32con.WM_LBUTTONUP, 0, 0)
            try: win32gui.EnumChildWindows(hwnd, check_btn, None)
            except: pass
            return True
        try: win32gui.EnumWindows(check, None)
        except: pass

# ── 단계1: 종목목록 + 기준값 읽기 (매크로 비활성) ──────────────────
xl = win32.Dispatch('Excel.Application')
xl.Visible = False
xl.DisplayAlerts = False
xl.AskToUpdateLinks = False
xl.AutomationSecurity = 3   # 매크로 비활성 → 팝업 없음
wb = xl.Workbooks.Open(XLSM_PATH, UpdateLinks=0)
time.sleep(3)

ws_osc  = wb.Sheets('수급오실레이터')
ws_forn = wb.Sheets('외국인매수데이터')

p10 = float(ws_osc.Cells(11, 12).Value2)
p25 = float(ws_osc.Cells(10, 12).Value2)
p75 = float(ws_osc.Cells(8,  12).Value2)

# 종목명 일괄 읽기
max_col = ws_forn.UsedRange.Columns.Count
raw = ws_forn.Range(ws_forn.Cells(9,2), ws_forn.Cells(9, max_col)).Value
stocks = [str(v).strip() for v in (raw[0] if raw else []) if v and isinstance(v, str)]

wb.Close(False)
xl.Quit()
time.sleep(2)

print(f"총 {len(stocks)}개 | A≤{p10*100:.3f}%  B≤{p25*100:.3f}%")
print()

# ── 단계2: C2 변경 → L12 읽기 (매크로 활성, 배치 100개) ────────────
results = []
errors  = []

for batch_start in range(0, len(stocks), BATCH):
    batch = stocks[batch_start:batch_start + BATCH]

    # 팝업 자동클릭 스레드 먼저 시작
    t = threading.Thread(target=auto_dismiss, args=(20,), daemon=True)
    t.start()

    xl = win32.Dispatch('Excel.Application')
    xl.Visible = True           # 팝업이 보여야 클릭 가능
    xl.DisplayAlerts = False
    xl.AskToUpdateLinks = False
    xl.AutomationSecurity = 1   # 매크로 활성 (VBA 필요)
    wb = xl.Workbooks.Open(XLSM_PATH, UpdateLinks=0)
    time.sleep(5)               # Workbook_Open + 팝업 클릭 대기
    xl.Visible = False          # 팝업 처리 후 숨기기

    ws = wb.Sheets('수급오실레이터')
    ws.Activate()

    for name in batch:
        try:
            ws.Cells(2, 3).Value = name
            for _ in range(20):
                try:
                    if xl.Ready: break
                except: pass
                time.sleep(0.1)
            time.sleep(1.0)

            val = None
            for _ in range(5):
                try:
                    v = ws.Cells(12, 12).Value2
                    if v is not None and abs(float(v)) < 1:
                        val = float(v); break
                except: pass
                time.sleep(0.3)

            if val is None:
                errors.append(name); continue

            g = 'A' if val<=p10 else 'B' if val<=p25 else 'D' if val>=p75 else 'C'
            results.append((val, name, g))
        except:
            errors.append(name)

    try: wb.Close(False)
    except: pass
    try: xl.Quit()
    except: pass
    time.sleep(2)

    a = sum(1 for _,_,g in results if g=='A')
    b = sum(1 for _,_,g in results if g=='B')
    print(f"  [{batch_start+len(batch)}/{len(stocks)}] 완료={len(results)} 오류={len(errors)} A={a} B={b}")

빈집_A = sorted([(v,n) for v,n,g in results if g=='A'])
빈집_B = sorted([(v,n) for v,n,g in results if g=='B'])

print(f"\n✅ {len(results)}종목 완료 | 오류:{len(errors)}")
print(f"빈집A:{len(빈집_A)}  빈집B:{len(빈집_B)}\n")
for v,n in 빈집_A: print(f"  {n}  {v*100:.4f}%")

out = {'date': str(date.today()),
       'thresholds': {'A': round(p10*100,4), 'B': round(p25*100,4)},
       'A': [(n,round(v*100,5)) for v,n in 빈집_A],
       'B': [(n,round(v*100,5)) for v,n in 빈집_B],
       'errors': errors}
Path('raw/oscillator_scan.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print("저장: raw/oscillator_scan.json")
