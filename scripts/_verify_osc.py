import sys; sys.stdout.reconfigure(encoding='utf-8')
import sys; sys.path.insert(0, '.')
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 3
wb = xl.Workbooks.Open(str(path))
ws_size = wb.Sheets('시가총액')
ws_forn = wb.Sheets('외국인매수데이터')
ws_inst = wb.Sheets('기관매수데이터')
ws_osc  = wb.Sheets('수급오실레이터')

max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

K12, K26, K9 = 2/13, 2/27, 2/10

def ema(vals, k):
    r=[vals[0]]
    for v in vals[1:]: r.append(v*k+r[-1]*(1-k))
    return r

for name, col in [('LS ELECTRIC', 64), ('일진전기', 182), ('산일전기', 145), ('대한전선', 129)]:
    c = col - 1
    size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
    forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
    inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
    pairs = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
    raw = [net/sz for net,sz in pairs]
    e12=ema(raw,K12); e26=ema(raw,K26)
    macd=[a-b for a,b in zip(e12,e26)]
    sig=ema(macd,K9)
    osc=[m-s for m,s in zip(macd,sig)]
    print(f"{name} (col={col}):")
    print(f"  raw 최근5일: {[f'{v*100:.3f}%' for v in raw[-5:]]}")
    print(f"  MACD={macd[-1]*100:.3f}%  Signal={sig[-1]*100:.3f}%  Osc={osc[-1]*100:.3f}%")
    print(f"  시총={size_v[-1]:.1f}  외인={forn_v[-1]:.2f}  기관={inst_v[-1]:.2f}")
    print()
