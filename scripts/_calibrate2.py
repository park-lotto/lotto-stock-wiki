"""
시기외 / 시기외12 / 시기외26 시트의 실제값을 비교해
공식 역추적 (SK하이닉스 기준)
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

# 각 시트에서 SK하이닉스(col3) 값 읽기
def read_col3(sheet_name):
    ws = wb.Sheets(sheet_name)
    vals = []
    for r in range(15, 92):
        v = ws.Cells(r, 3).Value2
        if v is not None:
            vals.append(float(v))
    return vals

sig    = read_col3('시기외')    # MACD Osc 또는 EMA?
sig12  = read_col3('시기외12')  # EMA12?
sig26  = read_col3('시기외26')  # EMA26?

max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

# SK하이닉스 raw
c = 1  # col2 → index 1
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
raw    = [net/sz for net,sz in pairs]

print(f"데이터 길이: raw={len(raw)}, 시기외={len(sig)}, 시기외12={len(sig12)}, 시기외26={len(sig26)}")
print()
print(f"{'날짜순':>4} {'raw':>10} {'시기외':>10} {'시기외12':>10} {'시기외26':>10}  시기외=12-26?")
n = min(len(raw), len(sig), len(sig12), len(sig26))
for i in range(n-10, n):
    r = raw[i]
    s = sig[i]
    s12 = sig12[i]
    s26 = sig26[i]
    diff = abs(s - (s12 - s26))
    match = '✅' if diff < 1e-8 else f'err={diff:.2e}'
    print(f"{i+1:>4} {r*100:>9.4f}% {s*100:>9.4f}% {s12*100:>9.4f}% {s26*100:>9.4f}%  {match}")

print()
print(f"시기외 최신: {sig[-1]*100:.5f}%")
print(f"시기외12-시기외26: {(sig12[-1]-sig26[-1])*100:.5f}%")
print()

# 어떤 EMA가 시기외12, 시기외26인지 찾기
def ema(vals, k):
    r=[vals[0]]
    for v in vals[1:]: r.append(v*k+r[-1]*(1-k))
    return r

print("=== EMA 후보 vs 시기외12 ===")
for n_period in range(3, 30):
    k = 2/(n_period+1)
    e = ema(raw[:len(sig12)], k)
    err = abs(e[-1] - sig12[-1])
    if err < 0.00005:
        print(f"  EMA{n_period} (k={k:.4f}): {e[-1]*100:.5f}% vs {sig12[-1]*100:.5f}%  오차={err*100:.5f}%  ✅")
    elif err < 0.0002:
        print(f"  EMA{n_period}: {e[-1]*100:.5f}%  오차={err*100:.5f}%")

print()
print("=== EMA 후보 vs 시기외26 ===")
for n_period in range(3, 50):
    k = 2/(n_period+1)
    e = ema(raw[:len(sig26)], k)
    err = abs(e[-1] - sig26[-1])
    if err < 0.00005:
        print(f"  EMA{n_period} (k={k:.4f}): {e[-1]*100:.5f}% vs {sig26[-1]*100:.5f}%  오차={err*100:.5f}%  ✅")
    elif err < 0.0002:
        print(f"  EMA{n_period}: {e[-1]*100:.5f}%  오차={err*100:.5f}%")
