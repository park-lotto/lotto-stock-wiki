"""
매크로 활성화 상태로 Excel 열기 → 전체 종목 오실레이터 읽기 시도
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False
xl.AutomationSecurity = 1   # LOW: 매크로 허용
wb = xl.Workbooks.Open(str(path))
time.sleep(3)  # 매크로 초기화 대기

# 시트 목록
sheets = [wb.Sheets(i+1).Name for i in range(wb.Sheets.Count)]
print(f"시트 수: {len(sheets)}")
print(f"시트 목록: {sheets}")

# 수급오실레이터 시트 현재값 확인
ws_osc = wb.Sheets('수급오실레이터')
print(f"\n수급오실레이터 시트 현재 종목:")
print(f"  B2(종목코드): {ws_osc.Cells(2,2).Value2}")
print(f"  C2(종목명): {ws_osc.Cells(2,3).Value2}")

# 시기외 시트에 종목 코드 넣으면 자동 계산되는지 확인
ws_sig = wb.Sheets('시기외')
print(f"\n시기외 시트 현재 종목:")
print(f"  B8(코드): {ws_sig.Cells(8,2).Value2}")
print(f"  B9(이름): {ws_sig.Cells(9,2).Value2}")
print(f"  B77(최신값): {ws_sig.Cells(77,3).Value2}")

# VBA 매크로 목록 확인
try:
    vba_comps = wb.VBProject.VBComponents
    print(f"\nVBA 컴포넌트 ({vba_comps.Count}개):")
    for comp in vba_comps:
        n = comp.CodeModule.CountOfLines
        if n > 0:
            print(f"  {comp.Name}: {n}줄")
except Exception as e:
    print(f"\nVBA 접근: {e}")

wb.Close(False)
xl.Quit()
