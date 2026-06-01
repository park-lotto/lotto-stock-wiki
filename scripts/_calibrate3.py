"""
시기외12 = EMA12(시기외) 인지, 시기외26 = EMA26(시기외) 인지 검증
→ MACD 구조 역추적
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 3
wb = xl.Workbooks.Open(str(path))

ws_size = wb.Sheets('시가총액')
ws_forn = wb.Sheets('외국인매수데이터')
ws_inst = wb.Sheets('기관매수데이터')

def read_sheet_col(sheet_name, col, row_start=15, row_end=91):
    ws = wb.Sheets(sheet_name)
    return [float(ws.Cells(r, col).Value2) for r in range(row_start, row_end+1)
            if ws.Cells(r, col).Value2 is not None]

sig   = read_sheet_col('시기외', 3)
sig12 = read_sheet_col('시기외12', 3)
sig26 = read_sheet_col('시기외26', 3)

# 시그널 시트도 읽기
try:
    signal_sheet = read_sheet_col('시그널', 3)
    has_signal = True
except:
    has_signal = False

max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

# SK하이닉스 raw flows
c = 1
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
raw    = [net/sz for net,sz in pairs]

def ema(vals, k):
    r=[vals[0]]
    for v in vals[1:]: r.append(v*k+r[-1]*(1-k))
    return r

print("=== 가설1: 시기외12 = EMA12(시기외) ===")
e12_of_sig = ema(sig, 2/13)
err = abs(e12_of_sig[-1] - sig12[-1])
print(f"  EMA12(시기외) = {e12_of_sig[-1]*100:.5f}%")
print(f"  시기외12 실제  = {sig12[-1]*100:.5f}%")
print(f"  오차={err*100:.5f}%  {'✅ 일치!' if err<1e-6 else '❌'}")

print()
print("=== 가설2: 시기외26 = EMA26(시기외) ===")
e26_of_sig = ema(sig, 2/27)
err = abs(e26_of_sig[-1] - sig26[-1])
print(f"  EMA26(시기외) = {e26_of_sig[-1]*100:.5f}%")
print(f"  시기외26 실제  = {sig26[-1]*100:.5f}%")
print(f"  오차={err*100:.5f}%  {'✅ 일치!' if err<1e-6 else '❌'}")

print()
print("=== 가설3: 시기외 = EMA12(raw) - EMA26(raw) (MACD) ===")
e12_raw = ema(raw, 2/13)
e26_raw = ema(raw, 2/27)
macd_raw = [a-b for a,b in zip(e12_raw, e26_raw)]
err = abs(macd_raw[-1] - sig[-1])
print(f"  MACD(raw12-26) = {macd_raw[-1]*100:.5f}%")
print(f"  시기외 실제     = {sig[-1]*100:.5f}%")
print(f"  오차={err*100:.5f}%  {'✅ 일치!' if err<1e-5 else '❌'}")

print()
print("=== 가설4: 시기외 = raw 그 자체 ===")
err = abs(raw[-1] - sig[-1])
print(f"  raw 최신 = {raw[-1]*100:.5f}%, 시기외 = {sig[-1]*100:.5f}%, 오차={err*100:.5f}%")

print()
print("=== 가설5: 시기외 = 시기외12 - 시기외26 (MACD 히스토그램) ===")
macd_hist = sig12[-1] - sig26[-1]
err = abs(macd_hist - sig[-1])
print(f"  시기외12-시기외26 = {macd_hist*100:.5f}%, 시기외 = {sig[-1]*100:.5f}%, 오차={err*100:.5f}%")

print()
print("=== 모든 EMA 조합으로 시기외 맞추기 ===")
best = []
for n_short in range(2, 20):
    for n_long in range(n_short+1, 40):
        ks = 2/(n_short+1); kl = 2/(n_long+1)
        es = ema(raw, ks); el = ema(raw, kl)
        macd = [a-b for a,b in zip(es, el)]
        err = abs(macd[-1] - sig[-1])
        best.append((err, n_short, n_long, macd[-1]))

best.sort()
print(f"{'공식':<15} {'계산':>10} {'정답':>10} {'오차':>10}")
for err, ns, nl, val in best[:8]:
    mark = '✅' if err < 1e-5 else ('⚠️' if err < 5e-5 else '')
    print(f"  EMA{ns}-EMA{nl:<8} {val*100:>9.5f}% {sig[-1]*100:>9.5f}% {err*100:>9.5f}%  {mark}")
