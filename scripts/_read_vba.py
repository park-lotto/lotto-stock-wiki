import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calc_oscillator as co
import win32com.client as win32

path = co.find_xlsm()
xl = win32.Dispatch('Excel.Application')
xl.Visible = False; xl.AutomationSecurity = 3
wb = xl.Workbooks.Open(str(path))

try:
    vba = wb.VBProject.VBComponents
    for comp in vba:
        try:
            n = comp.CodeModule.CountOfLines
            if n == 0: continue
            code = comp.CodeModule.Lines(1, n)
            if any(kw in code for kw in ['오실레이터', 'EMA', 'ema', '수급', 'OSC', 'osc', 'Oscillator']):
                print(f"=== {comp.Name} ({n}줄) ===")
                print(code[:4000])
                print()
        except: pass
except Exception as e:
    print(f"VBA 접근 실패: {e}")

wb.Close(False); xl.Quit()
