"""
시기외[n] = α × raw[n] + β × 시기외[n-1] 회귀분석
SK하이닉스 77일치 정답 데이터로 공식 도출
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

ws_size = wb.Sheets('시가총액')
ws_forn = wb.Sheets('외국인매수데이터')
ws_inst = wb.Sheets('기관매수데이터')

actual = [float(wb.Sheets('시기외').Cells(r, 3).Value2)
          for r in range(15, 92) if wb.Sheets('시기외').Cells(r, 3).Value2 is not None]

max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

c = 1  # SK하이닉스
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
pairs  = [((fv or 0)+(iv or 0), sv) for fv,iv,sv in zip(forn_v,inst_v,size_v) if sv and sv>0]
raw    = [net/sz for net,sz in pairs]

n = min(len(raw), len(actual))
raw_s = raw[:n]; act_s = actual[:n]

# OLS: 시기외[t] = α·raw[t] + β·시기외[t-1]
# y = [시기외[1..n-1]], X = [[raw[1..n-1]], [시기외[0..n-2]]]
y  = act_s[1:]
x1 = raw_s[1:]          # raw[t]
x2 = act_s[:-1]         # 시기외[t-1]

# OLS 공식: (X'X)^-1 X'y
n2 = len(y)
s11 = sum(a*a for a in x1)
s12 = sum(a*b for a,b in zip(x1,x2))
s22 = sum(a*a for a in x2)
s1y = sum(a*b for a,b in zip(x1,y))
s2y = sum(a*b for a,b in zip(x2,y))

det = s11*s22 - s12*s12
alpha = (s22*s1y - s12*s2y) / det
beta  = (s11*s2y - s12*s1y) / det

print(f"회귀 결과: 시기외[t] = {alpha:.4f} × raw[t] + {beta:.4f} × 시기외[t-1]")
print()

# 검증: 이 공식으로 시기외 재현
pred = [act_s[0]]  # 초기값 = 실제 첫번째 값
for i in range(1, n):
    pred.append(alpha * raw_s[i] + beta * pred[-1])

errors = [abs(p - a) for p, a in zip(pred, act_s)]
print(f"평균 절대오차: {sum(errors)/len(errors)*100:.5f}%")
print(f"최대 오차:     {max(errors)*100:.5f}%")
print()
print(f"{'일':>3} {'raw':>10} {'예측':>10} {'실제':>10} {'오차':>10}")
for i in range(n-10, n):
    print(f"{i+1:>3} {raw_s[i]*100:>9.4f}% {pred[i]*100:>9.4f}% {act_s[i]*100:>9.4f}% {errors[i]*100:>9.4f}%")

print()
print(f"α={alpha:.6f}, β={beta:.6f}")
print(f"해석: β≈{beta:.3f} → EMA 감쇠계수. 대응 EMA기간 = 2/α_ema - 1 = {2/(1-beta)-1:.1f}일")
