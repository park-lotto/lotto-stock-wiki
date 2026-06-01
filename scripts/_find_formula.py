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
max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

# 차트에서 읽은 현재값 (육안 측정)
CHART = {
    'LS ELECTRIC': -0.070,   # -0.07%
    '일진전기':     -0.123,   # -0.12%
    '산일전기':     -0.200,   # -0.20%
    '대한전선':     -0.200,   # -0.20%
}
COLS = {'LS ELECTRIC': 64, '일진전기': 182, '산일전기': 145, '대한전선': 129}

def ema(vals, k):
    r = [vals[0]]
    for v in vals[1:]: r.append(v*k + r[-1]*(1-k))
    return r

def sma(vals, n):
    return sum(vals[-n:]) / n

def test_formula(name, col, formula_fn):
    c = col - 1
    size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
    forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
    inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
    pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
    raw    = [net/sz for net,sz in pairs]
    return formula_fn(raw) * 100  # → %

formulas = {
    'raw_1일':      lambda r: r[-1],
    'SMA_3일':      lambda r: sma(r, 3),
    'SMA_5일':      lambda r: sma(r, 5),
    'SMA_10일':     lambda r: sma(r, 10),
    'SMA_20일':     lambda r: sma(r, 20),
    'EMA12':        lambda r: ema(r, 2/13)[-1],
    'EMA26':        lambda r: ema(r, 2/27)[-1],
    'MACD(12-26)':  lambda r: ema(r,2/13)[-1] - ema(r,2/27)[-1],
    'MACD_Osc':     lambda r: (lambda m: [x-y for x,y in zip(m, ema(m, 2/10))])([a-b for a,b in zip(ema(r,2/13), ema(r,2/27))])[-1],
}

print(f"{'공식':<14}", end='')
for name in CHART: print(f"  {name[:8]:>10}", end='')
print(f"  {'오차합':>8}")
print('-'*80)

for fname, fn in formulas.items():
    vals = {}
    for name, col in COLS.items():
        try: vals[name] = test_formula(name, col, fn)
        except: vals[name] = None

    total_err = sum(abs(vals[n] - CHART[n]) for n in CHART if vals[n] is not None)
    print(f"{fname:<14}", end='')
    for name in CHART:
        v = vals[name]
        diff = v - CHART[name] if v is not None else 0
        mark = '✅' if abs(diff) < 0.03 else ('⚠️' if abs(diff) < 0.08 else '❌')
        print(f"  {v:>7.3f}%{mark}", end='')
    print(f"  {total_err:>7.3f}")
