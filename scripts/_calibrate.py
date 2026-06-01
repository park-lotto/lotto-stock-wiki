"""
SK하이닉스의 실제 오실레이터 값(시기외 시트)을 정답으로 삼아
어떤 공식이 일치하는지 역추적
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

# 시기외 시트: col1=SK시총, col2=SK오실레이터 실제값
ws_sig = wb.Sheets('시기외')
ws_size = wb.Sheets('시가총액')
ws_forn = wb.Sheets('외국인매수데이터')
ws_inst = wb.Sheets('기관매수데이터')

# SK하이닉스 실제 오실레이터 값 (정답)
actual_osc = []
for r in range(15, 92):
    v = ws_sig.Cells(r, 3).Value2   # col3 = SK오실레이터
    d = ws_sig.Cells(r, 1).Value2   # col1 = 날짜(또는 시총)
    if v is not None:
        actual_osc.append(float(v))

print(f"시기외 col3 최근5개: {[f'{v*100:.4f}%' for v in actual_osc[-5:]]}")
print(f"시기외 col3 최신값:  {actual_osc[-1]*100:.4f}%")
print()

# SK하이닉스 raw 플로우 데이터 (col=2 → index 1)
max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

SK_COL = 2  # SK하이닉스 = 외국인매수데이터 col2 → index 1
c = SK_COL - 1
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
raw    = [net/sz for net, sz in pairs]

print(f"raw 데이터 길이: {len(raw)}, 실제오실레이터 길이: {len(actual_osc)}")
print(f"raw 최근5일: {[f'{v*100:.4f}%' for v in raw[-5:]]}")

# 정답과 비교: 여러 공식 시도
def ema(vals, k):
    r=[vals[0]]
    for v in vals[1:]: r.append(v*k+r[-1]*(1-k))
    return r

def sma(vals, n):
    return [sum(vals[max(0,i-n+1):i+1])/min(i+1,n) for i in range(len(vals))]

target = actual_osc[-1]
print(f"\n정답(시기외 최신): {target*100:.4f}%")
print()

n = min(len(raw), len(actual_osc))
raw_s = raw[-n:]

candidates = {}
for k in [1,2,3,5,7,10,13,20,26]:
    ema_v = ema(raw_s, 2/(k+1))
    candidates[f'EMA{k}'] = ema_v[-1]
    sma_v = sma(raw_s, k)
    candidates[f'SMA{k}'] = sma_v[-1]

# MACD variants
for short, long in [(3,7),(5,13),(5,20),(8,17),(10,21),(12,26),(3,10)]:
    e_s = ema(raw_s, 2/(short+1))
    e_l = ema(raw_s, 2/(long+1))
    macd = [a-b for a,b in zip(e_s, e_l)]
    candidates[f'MACD{short}-{long}'] = macd[-1]
    for sig in [3,5,9]:
        osc = [m-s for m,s in zip(macd, ema(macd, 2/(sig+1)))]
        candidates[f'MACD{short}-{long}_sig{sig}'] = osc[-1]

print(f"{'공식':<22} {'계산값':>10} {'정답':>10} {'오차':>10}")
print('-'*55)
results = sorted(candidates.items(), key=lambda x: abs(x[1]-target))
for name, val in results[:15]:
    err = abs(val - target)
    mark = '✅' if err < 0.000010 else ('⚠️' if err < 0.000050 else '')
    print(f"{name:<22} {val*100:>9.5f}% {target*100:>9.5f}% {err*100:>9.5f}%  {mark}")
