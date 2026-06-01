"""
시기외 K12=2/27 = EMA26 계수.
시기외[1] 실제값을 초기값으로 삼고 EMA26 연산하면 일치하는지 검증.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 1
wb = xl.Workbooks.Open(str(path))

ws_size = wb.Sheets('시가총액'); ws_forn = wb.Sheets('외국인매수데이터'); ws_inst = wb.Sheets('기관매수데이터')
actual = [float(wb.Sheets('시기외').Cells(r, 3).Value2)
          for r in range(15, 92) if wb.Sheets('시기외').Cells(r, 3).Value2 is not None]
max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

c = 1
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
raw    = [net/sz for net,sz in pairs]
n = min(len(raw), len(actual))
raw_s = raw[:n]; act_s = actual[:n]

k = 2/27  # K12 상수 (EMA26)

print("=== EMA26(raw), 초기값=실제 첫번째값 ===")
pred = [act_s[0]]
for i in range(1, n):
    pred.append(k * raw_s[i] + (1-k) * pred[-1])

errs = [abs(p-a) for p,a in zip(pred, act_s)]
print(f"평균오차: {sum(errs)/len(errs)*100:.5f}%  최대오차: {max(errs)*100:.5f}%")
print()
print(f"{'일':>3} {'raw':>10} {'예측':>10} {'실제':>10} {'오차':>10}")
for i in range(n-12, n):
    mark = '✅' if errs[i]*100 < 0.005 else ''
    print(f"{i+1:>3} {raw_s[i]*100:>9.4f}% {pred[i]*100:>9.4f}% {act_s[i]*100:>9.4f}% {errs[i]*100:>9.4f}% {mark}")

# 만약 잘 맞으면: 다른 종목 적용 방법
print()
print("=== 초기값 변형 시도: 첫값 ±조정 ===")
for init_scale in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
    init = act_s[0] * init_scale
    p = [init]
    for i in range(1, n): p.append(k*raw_s[i]+(1-k)*p[-1])
    e = sum(abs(p[i]-act_s[i]) for i in range(n))/n
    print(f"  초기값×{init_scale}: 평균오차={e*100:.4f}%  최신={p[-1]*100:.4f}% vs 실제={act_s[-1]*100:.4f}%")
