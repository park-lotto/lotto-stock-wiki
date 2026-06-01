"""
시기외 = 누적 순매수 / 시총 가설 검증
시기외 전체 시계열과 비교
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

actual = []
for r in range(15, 92):
    v = wb.Sheets('시기외').Cells(r, 3).Value2
    if v is not None: actual.append(float(v))

max_col = ws_forn.UsedRange.Columns.Count
mat_size, mat_forn, mat_inst = co.load_bulk(ws_size, ws_forn, ws_inst, max_col)
wb.Close(False); xl.Quit()

c = 1  # SK하이닉스 index
size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
raw    = [(fv or 0) + (iv or 0) for fv, iv in zip(forn_v, inst_v)]  # KRW bil 순매수
sizes  = [sv for sv in size_v if sv]

n = min(len(raw), len(actual), len(sizes))

# 가설1: 누적합 / 현재시총 (×10 단위변환)
cum = 0
hyp1 = []
for i in range(n):
    cum += raw[i]         # KRW bil 누적
    v = cum * 10 / sizes[i]   # 억원 환산 / 시총(억)
    hyp1.append(v)

# 가설2: 누적합 / 최초시총 (×10)
cum = 0; first_size = sizes[0]
hyp2 = []
for i in range(n):
    cum += raw[i]
    hyp2.append(cum * 10 / first_size)

# 가설3: 누적합 / 평균시총 (×10)
avg_size = sum(sizes[:n]) / n
cum = 0; hyp3 = []
for i in range(n):
    cum += raw[i]
    hyp3.append(cum * 10 / avg_size)

# 가설4: 시계열 원본이 서로 다른 시작점 가짐 — offset 보정
# actual이 다른 초기값을 가질 수 있음 → raw와의 차이로 오프셋 추정

err1 = sum(abs(hyp1[i]-actual[i]) for i in range(n)) / n
err2 = sum(abs(hyp2[i]-actual[i]) for i in range(n)) / n
err3 = sum(abs(hyp3[i]-actual[i]) for i in range(n)) / n

print(f"평균 오차 비교:")
print(f"  가설1(누적/현재시총): {err1*100:.5f}%")
print(f"  가설2(누적/최초시총): {err2*100:.5f}%")
print(f"  가설3(누적/평균시총): {err3*100:.5f}%")

print()
print(f"{'일':>3} {'raw(KRWbil)':>12} {'가설1':>10} {'실제':>10} {'오차1':>10}")
for i in range(n-10, n):
    print(f"{i+1:>3} {raw[i]:>11.2f} {hyp1[i]*100:>9.4f}% {actual[i]*100:>9.4f}% {abs(hyp1[i]-actual[i])*100:>9.4f}%")

# 오프셋 보정 시도: actual과 hyp1의 차이
offset = actual[0] - hyp1[0]
print(f"\n오프셋 보정: {offset*100:.5f}%")
hyp1_adj = [v + offset for v in hyp1]
err_adj = sum(abs(hyp1_adj[i]-actual[i]) for i in range(n)) / n
print(f"오프셋 보정 후 평균 오차: {err_adj*100:.5f}%")
print(f"보정 후 최신값: {hyp1_adj[-1]*100:.5f}% vs 실제: {actual[-1]*100:.5f}%")
