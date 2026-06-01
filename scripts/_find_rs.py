"""RS 데이터 위치 탐색"""
import sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / '매일 엑셀넣을것'

# 받은 파일 전체 탐색
for path in sorted(SAVE_DIR.glob('*.xls*')):
    if path.name.startswith('~$'): continue
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)
        # RS 관련 시트 찾기
        rs_sheets = [s for s in wb.sheetnames if 'RS' in s.upper() or '주도주' in s or '상대강도' in s]
        if rs_sheets:
            print(f'\n✅ {path.name}')
            for s in rs_sheets:
                ws = wb[s]
                print(f'  [{s}] {ws.max_row}행 × {ws.max_column}열')
                # 1~3행 샘플
                for r in range(1, 4):
                    row = [ws.cell(r, c).value for c in range(1, 12)]
                    if any(v is not None for v in row):
                        print(f'    행{r}: {row}')
        # RS 컬럼 헤더 탐색 (시트명 무관)
        for sname in wb.sheetnames:
            ws = wb[sname]
            for r in range(1, 10):
                row = [str(ws.cell(r, c).value or '') for c in range(1, 20)]
                if any('RS_' in v or 'norm_RS' in v for v in row):
                    print(f'\n✅ {path.name} → [{sname}] 행{r}에서 RS 컬럼 발견')
                    print(f'   {row[:12]}')
                    break
        wb.close()
    except Exception as e:
        print(f'  ⚠️ {path.name}: {e}')
