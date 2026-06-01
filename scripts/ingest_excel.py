"""
ingest_excel.py — 매일 엑셀넣을것 → wiki 자동 반영

실행:
    python scripts/ingest_excel.py              # 전체 처리
    python scripts/ingest_excel.py --dry-run    # 실제 파일 수정 없이 리포트만 출력

출력:
    raw/ingest_report_{날짜}.md   — 처리 결과 요약
    wiki 파일 직접 수정           (--dry-run 아닐 때)
    wiki/log.md 자동 기록
"""

import sys
import os
import re
import glob
import argparse
from datetime import datetime, date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import openpyxl
except ImportError:
    print("openpyxl 없음. 설치: python -m pip install openpyxl")
    sys.exit(1)

# ─── 경로 설정 ────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
EXCEL_DIR = ROOT / "raw" / "매일 엑셀넣을것"
WIKI_DIR  = ROOT / "wiki"
LOG_FILE  = WIKI_DIR / "log.md"
TODAY     = datetime.today().strftime("%Y-%m-%d")

# ─── 헬퍼 ────────────────────────────────────────────────────

def load_wb(path: Path):
    """data_only=True로 캐시값 읽기 (수식 결과값)"""
    try:
        return openpyxl.load_workbook(str(path), read_only=True, keep_vba=False, data_only=True)
    except Exception as e:
        print(f"  ⚠️ {path.name} 열기 실패: {e}")
        return None

def find_excel(pattern: str) -> Path | None:
    """패턴 문자열로 EXCEL_DIR에서 파일 찾기"""
    for f in EXCEL_DIR.iterdir():
        if f.name.startswith("~$"): continue
        if pattern in f.name and f.suffix in (".xlsx", ".xlsm"):
            return f
    return None

def find_stock_page(name: str) -> Path | None:
    """종목명으로 wiki stock 페이지 경로 찾기"""
    name_clean = name.strip().replace(" ", "")
    for p in WIKI_DIR.rglob(f"stock_{name_clean}.md"):
        return p
    # 부분 매칭 시도
    for p in WIKI_DIR.rglob("stock_*.md"):
        stem = p.stem.replace("stock_", "").replace(" ", "")
        if name_clean in stem or stem in name_clean:
            return p
    return None

def rows_from_sheet(ws, max_row=500, max_col=20):
    """시트에서 값 있는 행만 추출"""
    result = []
    for row in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col, values_only=True):
        if any(v is not None for v in row):
            result.append(row)
    return result

def fmt_date(v) -> str:
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, float)):
        s = str(int(v))
        if len(s) == 8:
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return str(v) if v else ""

def fmt_pct(v) -> str:
    if v is None: return "—"
    if isinstance(v, (int, float)):
        return f"{v:+.1f}%"
    return str(v)

def fmt_num(v, unit="") -> str:
    if v is None: return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1e12: return f"{v/1e12:.1f}조{unit}"
        if abs(v) >= 1e8:  return f"{v/1e8:.0f}억{unit}"
        if abs(v) >= 1e4:  return f"{int(v):,}{unit}"
        return f"{v:.2f}{unit}"
    return str(v)

# ─── 파서 1: 추정이익변경 (Rating/TP 상향·하향) ────────────────

def parse_추정이익변경(dry_run: bool) -> dict:
    path = find_excel("추정이익 변경")
    if not path:
        return {"error": "추정이익 변경 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}

    results = {
        "Rating_Up": [], "Rating_Down": [],
        "TP_Up": [],     "TP_Down": [],
        "New_KOSPI": [],  "New_KOSDAQ": [],
    }

    sheet_map = {
        "Rating_Up":   results["Rating_Up"],
        "Rating_Down": results["Rating_Down"],
        "TP_Up":       results["TP_Up"],
        "TP_Down":     results["TP_Down"],
        "New_KOSPI":   results["New_KOSPI"],
        "New_KOSDAQ":  results["New_KOSDAQ"],
    }

    for sheet_name, bucket in sheet_map.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        rows = rows_from_sheet(ws, max_row=200, max_col=15)

        # 헤더 행 찾기: '일자' 또는 '코드' 있는 행
        header_idx = None
        for i, r in enumerate(rows):
            vals = [str(v) for v in r if v is not None]
            if any(k in vals for k in ["일자", "코드", "From"]):
                header_idx = i
                break

        # 데이터 행 (헤더 다음 2행부터)
        if header_idx is None:
            continue

        for r in rows[header_idx + 2:]:
            # 날짜, 코드, 종목명 위치 탐색 (컬럼 1,2,3)
            vals = list(r)
            # 날짜가 datetime이고 코드가 'A'로 시작하는 행
            date_v = vals[1] if len(vals) > 1 else None
            code_v = vals[2] if len(vals) > 2 else None
            name_v = vals[3] if len(vals) > 3 else None

            if not isinstance(date_v, (datetime, date)): continue
            if not isinstance(code_v, str) or not code_v.startswith("A"): continue
            if not name_v: continue

            bucket.append({
                "date":      fmt_date(date_v),
                "code":      code_v,
                "name":      str(name_v).strip(),
                "brokerage": str(vals[5]).strip() if vals[5] else "—",
                "analyst":   str(vals[6]).strip() if vals[6] else "—",
                "op_old":    str(vals[11]).strip() if len(vals) > 11 and vals[11] else "—",
                "op_new":    str(vals[12]).strip() if len(vals) > 12 and vals[12] else "—",
                "tp_old":    int(vals[13]) if len(vals) > 13 and isinstance(vals[13], (int, float)) else None,
                "tp_new":    int(vals[14]) if len(vals) > 14 and isinstance(vals[14], (int, float)) else None,
            })

    wb.close()

    # wiki 업데이트
    updated = []
    if not dry_run:
        all_items = results["Rating_Up"] + results["TP_Up"] + results["Rating_Down"] + results["TP_Down"]
        for item in all_items:
            page = find_stock_page(item["name"])
            if not page: continue
            updated.append(_update_consensus(page, item))

    return {"file": path.name, "results": results, "updated": updated}


def _update_consensus(page: Path, item: dict) -> str:
    """stock 페이지의 증권사 컨센서스 섹션에 1행 덮어쓰기"""
    text = page.read_text(encoding="utf-8")

    tp_old_str = fmt_num(item["tp_old"], "원") if item["tp_old"] else "—"
    tp_new_str = fmt_num(item["tp_new"], "원") if item["tp_new"] else "—"

    if item["tp_old"] and item["tp_new"] and item["tp_old"] > 0:
        chg = (item["tp_new"] - item["tp_old"]) / item["tp_old"]
        direction = f"↑ {chg:+.0%}" if chg > 0 else f"↓ {chg:+.0%}"
    else:
        direction = "신규"

    new_row = f"| {item['brokerage']} | {tp_new_str} | {item['op_new']} | {item['date']} | {tp_old_str} | {direction} |"

    # 기존 해당 증권사 행 찾아 덮어쓰기
    pattern = re.compile(rf"^\| {re.escape(item['brokerage'])} \|.*$", re.MULTILINE)
    if pattern.search(text):
        new_text = pattern.sub(new_row, text)
    else:
        # 컨센서스 테이블 끝에 추가
        consensus_end = text.find("\n---", text.find("## 증권사 컨센서스"))
        if consensus_end > 0:
            new_text = text[:consensus_end] + "\n" + new_row + text[consensus_end:]
        else:
            new_text = text + f"\n{new_row}"

    if new_text != text:
        page.write_text(new_text, encoding="utf-8")
        return f"✅ {item['name']} — {item['brokerage']} TP {tp_old_str}→{tp_new_str}"
    return f"⏭ {item['name']} 변경 없음"


# ─── 파서 2: 컨센움직임서프쇼크 ─────────────────────────────────

def parse_컨센움직임(dry_run: bool) -> dict:
    path = find_excel("컨센움직임서프쇼크")
    if not path:
        return {"error": "컨센움직임 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}

    sheets = {
        "컨센상향": [], "컨센하향": [],
        "서프라이즈": [], "쇼크": [],
    }

    for sheet_name, bucket in sheets.items():
        if sheet_name not in wb.sheetnames: continue
        ws = wb[sheet_name]
        rows = rows_from_sheet(ws, max_row=300, max_col=20)

        # 종목코드 'A'로 시작하는 행이 실데이터
        for r in rows:
            code = r[1] if len(r) > 1 else None
            name = r[2] if len(r) > 2 else None
            if not isinstance(code, str) or not code.startswith("A"): continue
            if not name: continue

            entry = {
                "code":     code,
                "name":     str(name).strip(),
                "sector":   str(r[3]).strip() if r[3] else "—",
                "ret_1m":   r[4],   # 1개월 수익률
                "ret_3m":   r[5],   # 3개월 수익률
                "op_2026":  r[6],   # 2026년 영업이익 (십억원)
                "op_chg1m": r[7],   # 1개월 변화
            }

            if sheet_name in ("서프라이즈", "쇼크"):
                entry["surprise_rate"] = r[11] if len(r) > 11 else None

            bucket.append(entry)

    wb.close()
    return {"file": path.name, "results": sheets}


# ─── 파서 3: 핵심 수출 데이터 ────────────────────────────────────

EXPORT_KEY_SHEETS = {
    "디램":       ("반도체", ["삼성전자", "SK하이닉스"]),
    "낸드":       ("반도체", ["삼성전자", "SK하이닉스"]),
    "HBM":        ("반도체", ["SK하이닉스"]),
    "동박":       ("2차전지", ["롯데에너지머티리얼즈", "SKC"]),
    "양극재(NCM+NCA)": ("2차전지", ["에코프로비엠", "포스코퓨처엠"]),
    "MLCC":       ("반도체부품", ["삼성전기"]),
    "CCL":        ("기판", ["두산"]),
    "선박 엔진":  ("조선", ["HD현대중공업", "한화오션"]),
    "고용량변압기": ("전력기기", ["HD현대일렉트릭", "효성중공업"]),
}

def parse_수출정리(dry_run: bool) -> dict:
    path = find_excel("수출정리")
    if not path:
        return {"error": "수출정리 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}

    results = {}

    for sheet_name, (sector, stocks) in EXPORT_KEY_SHEETS.items():
        if sheet_name not in wb.sheetnames: continue
        ws = wb[sheet_name]
        rows = rows_from_sheet(ws, max_row=100, max_col=12)

        # 헤더 행 찾기 ('년월' 있는 행)
        data_start = None
        for i, r in enumerate(rows):
            if r[0] == "년월":
                data_start = i + 1
                break
        if data_start is None: continue

        # 최근 3개월 데이터
        data_rows = [r for r in rows[data_start:] if r[0] and str(r[0]).startswith("20")][-3:]

        monthly = []
        for r in data_rows:
            monthly.append({
                "month":     str(r[0]),
                "daily_avg": r[5],       # 일평균수출 (달러)
                "mom":       r[6],       # MoM
                "yoy_vol":   r[7],       # 물량 YoY
                "price_abs": r[8],       # 판가 절대값
                "price_yoy": r[9],       # 판가 YoY
            })

        # 신호 판단
        if monthly:
            latest = monthly[-1]
            yoy = latest["yoy_vol"]
            price_yoy = latest["price_yoy"]
            if isinstance(yoy, float) and isinstance(price_yoy, float):
                if yoy > 0.15 and price_yoy > 0.10:
                    signal = "🔴"
                elif yoy > 0 or price_yoy > 0:
                    signal = "🟠"
                else:
                    signal = "🟡"
            else:
                signal = "—"
        else:
            signal = "—"

        results[sheet_name] = {
            "sector": sector,
            "stocks": stocks,
            "monthly": monthly,
            "signal": signal,
        }

    wb.close()
    return {"file": path.name, "results": results}


# ─── 파서 4: 유동성체크 (컨센신고가 + 가속화모멘텀) ────────────────

def parse_유동성체크(dry_run: bool) -> dict:
    path = find_excel("유동성 체크")
    if not path:
        return {"error": "유동성 체크 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}

    results = {"컨센신고가": [], "가속화모멘텀": []}

    # 컨센신고가 시트
    for sheet_name in ["2027년 컨센 신고가", "2027년 컨센 신고가(2)"]:
        if sheet_name not in wb.sheetnames: continue
        ws = wb[sheet_name]
        for r in ws.iter_rows(min_row=2, max_row=100, max_col=10, values_only=True):
            rank = r[0]
            name = r[1]
            if not isinstance(rank, (int, float)): continue
            if not name: continue
            results["컨센신고가"].append({
                "rank":       int(rank),
                "name":       str(name).strip(),
                "latest_date": fmt_date(r[4]),
                "brokerage":  str(r[5]).strip() if r[5] else "—",
                "op_2027":    r[7],
            })

    # 가속화모멘텀 시트
    if "가속화모멘텀" in wb.sheetnames:
        ws = wb["가속화모멘텀"]
        rows = rows_from_sheet(ws, max_row=200, max_col=12)
        for r in rows:
            # 종목코드 형태 'A######' 있는 행
            for v in r:
                if isinstance(v, str) and re.match(r"A\d{6}", v):
                    name_idx = list(r).index(v) + 1
                    name = r[name_idx] if name_idx < len(r) else None
                    if name:
                        results["가속화모멘텀"].append(str(name).strip())
                    break

    wb.close()
    return {"file": path.name, "results": results}


# ─── 파서 5: 수급오실레이터 (COM 기반 EMA MACD 방식) ─────────────

def _run_osc_com(path: Path) -> dict:
    """COM으로 xlsm 열어 EMA MACD 오실레이터 계산 (대형주·중소형주 공용)"""
    try:
        import win32com.client as win32
    except ImportError:
        return {"error": "win32com 없음 — pip install pywin32"}

    K12, K26, K9 = 2/13, 2/27, 2/10
    DATA_START, DATA_END = 15, 91
    STAT_COL = 12

    def ema(vals, k):
        r = [vals[0]]
        for v in vals[1:]:
            r.append(v * k + r[-1] * (1 - k))
        return r

    def calc_osc(signal):
        e12 = ema(signal, K12); e26 = ema(signal, K26)
        macd = [a - b for a, b in zip(e12, e26)]
        sig  = ema(macd, K9)
        return [m - s for m, s in zip(macd, sig)]

    print("    [COM] Excel 열기...")
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.AutomationSecurity = 3
    wb_com = xl.Workbooks.Open(str(path))

    ws_size = wb_com.Sheets("시가총액")
    ws_forn = wb_com.Sheets("외국인매수데이터")
    ws_inst = wb_com.Sheets("기관매수데이터")

    # 기준값: 수급오실레이터 시트가 있으면 읽고, 없으면 계산값으로 대체
    p10 = p25 = p75 = p90 = None
    if "수급오실레이터" in [wb_com.Sheets(i+1).Name for i in range(wb_com.Sheets.Count)]:
        ws_osc = wb_com.Sheets("수급오실레이터")
        try:
            p10 = float(ws_osc.Cells(11, STAT_COL).Value2)
            p25 = float(ws_osc.Cells(10, STAT_COL).Value2)
            p75 = float(ws_osc.Cells(8,  STAT_COL).Value2)
            p90 = float(ws_osc.Cells(7,  STAT_COL).Value2)
        except (TypeError, ValueError):
            pass

    last_date = ws_forn.Cells(DATA_END, 1).Value2
    max_col = ws_forn.UsedRange.Columns.Count

    xl_stocks = {}
    for c in range(2, max_col + 1):
        name = ws_forn.Cells(9, c).Value2
        code = ws_forn.Cells(8, c).Value2
        if name:
            xl_stocks[str(name)] = {"col": c, "code": str(code or "").replace("A", "")}

    def to_matrix(ws):
        raw = ws.Range(ws.Cells(DATA_START, 1), ws.Cells(DATA_END, max_col)).Value
        return raw or []

    mat_size = to_matrix(ws_size)
    mat_forn = to_matrix(ws_forn)
    mat_inst = to_matrix(ws_inst)
    wb_com.Close(False); xl.Quit()
    print(f"    [COM] Excel 닫힘. {len(xl_stocks)}종목 계산 중...")

    results = []
    for name, info in xl_stocks.items():
        c = info["col"] - 1
        size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
        forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
        inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
        pairs  = [((fv or 0) + (iv or 0), sv)
                  for fv, iv, sv in zip(forn_v, inst_v, size_v) if sv and sv > 0]
        if len(pairs) < 27:
            continue
        series = calc_osc([net / sz for net, sz in pairs])
        osc = series[-1]
        trend = "↑ 재진입" if len(series) >= 5 and osc > sum(series[-5:-1])/4 * 1.05 else \
                "↓ 빈집심화" if len(series) >= 5 and osc < sum(series[-5:-1])/4 * 0.95 else "→ 횡보"
        results.append({"name": name, "code": info["code"], "osc": osc, "trend": trend})

    if not results:
        return {"file": path.name, "error": "계산 가능 종목 없음"}

    # 기준값이 없으면 계산값 기반으로 산출
    all_sorted = sorted(r["osc"] for r in results)
    n = len(all_sorted)
    if p10 is None: p10 = all_sorted[int(n * 0.10)]
    if p25 is None: p25 = all_sorted[int(n * 0.25)]
    if p75 is None: p75 = all_sorted[int(n * 0.75)]
    if p90 is None: p90 = all_sorted[int(n * 0.90)]

    def pct(v):
        if v <= p10: return 10 * (v / p10) if p10 else 5
        if v <= p25: return 10 + (v - p10) / (p25 - p10) * 15
        if v <= p75: return 25 + (v - p25) / (p75 - p25) * 50
        if v <= p90: return 75 + (v - p75) / (p90 - p75) * 15
        return min(90 + (v - p90) / abs(p90) * 5 if p90 else 95, 100)

    빈집_A = sorted([r for r in results if r["osc"] <= p10], key=lambda x: x["osc"])
    빈집_B = sorted([r for r in results if p10 < r["osc"] <= p25], key=lambda x: x["osc"])
    for r in results:
        r["pct"] = pct(r["osc"])

    if isinstance(last_date, datetime):
        last_date_str = last_date.strftime("%Y-%m-%d")
    else:
        last_date_str = TODAY

    return {
        "file": path.name,
        "date": last_date_str,
        "total": len(results),
        "빈집_A": [{"name": r["name"], "code": r["code"], "osc": r["osc"], "pct": r["pct"], "trend": r["trend"]} for r in 빈집_A],
        "빈집_B": [{"name": r["name"], "code": r["code"], "osc": r["osc"], "pct": r["pct"], "trend": r["trend"]} for r in 빈집_B],
        "note": f"전체 {len(results)}종목 | 빈집A: {len(빈집_A)}개 | 빈집B: {len(빈집_B)}개 | 기준A≤{p10:.6f} B≤{p25:.6f}",
    }


def parse_수급오실레이터(dry_run: bool) -> dict:
    path = find_excel("(700)")
    if not path:
        path = find_excel("수급오실레이터")
    if not path:
        return {"error": "수급오실레이터(700) 파일 없음"}
    return _run_osc_com(path)


# ─── 파서 6: 중소형주 오실레이터 (700-1400) ───────────────────────

def parse_중소형주오실레이터(dry_run: bool) -> dict:
    path = find_excel("(700-1400)")
    if not path:
        return {"error": "수급오실레이터(700-1400) 파일 없음"}
    return _run_osc_com(path)


# ─── 파서 7: 가속화모멘텀 ────────────────────────────────────────

def parse_가속화모멘텀(dry_run: bool) -> dict:
    path = find_excel("유동성 체크")
    if not path:
        path = find_excel("가속화모멘텀")
    if not path:
        return {"error": "유동성체크 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}
    if "가속화모멘텀" not in wb.sheetnames:
        wb.close(); return {"error": "가속화모멘텀 시트 없음"}

    ws = wb["가속화모멘텀"]

    # 4개 그룹: 각 그룹 = (순위col, 종목col, 스코어col, 변화24col, 변화25col)
    groups = {
        "추정이익3개+": (1, 2, 3, 4, 5),
        "추정이익1개+": (6, 7, 8, 9, 10),
        "시총상위300":  (11, 12, 13, 14, 15),
        "주당순이익1개+": (16, 17, 18, 19, 20),  # 태린이아빠 선호
    }

    result = {}
    for g_name, (c_rank, c_name, c_score, c_24, c_25) in groups.items():
        items = []
        for r in range(6, ws.max_row + 1):
            name = ws.cell(r, c_name).value
            score = ws.cell(r, c_score).value
            if not name or not isinstance(name, str): continue
            try: score = float(score)
            except (TypeError, ValueError): continue
            chg24 = ws.cell(r, c_24).value
            chg25 = ws.cell(r, c_25).value
            items.append({
                "name":   name.strip(),
                "score":  round(score, 4),
                "chg24":  float(chg24) if isinstance(chg24, (int, float)) else None,
                "chg25":  float(chg25) if isinstance(chg25, (int, float)) else None,
            })
        result[g_name] = items

    wb.close()
    return {"file": path.name, "results": result}


# ─── 파서 8: 상대강도 RS ─────────────────────────────────────────

def parse_rs(dry_run: bool) -> dict:
    path = find_excel("한국상대강도")
    if not path:
        return {"error": "한국상대강도 파일 없음"}

    wb = load_wb(path)
    if not wb: return {"error": "열기 실패"}
    if "종가" not in wb.sheetnames:
        wb.close(); return {"error": "종가 시트 없음"}

    ws = wb["종가"]

    # 헤더 읽기
    headers = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(1, c).value
        headers.append(str(v).strip() if v else None)

    # 가격 데이터 읽기
    prices = {h: [] for h in headers[1:] if h}
    dates = []
    for r in range(2, ws.max_row + 1):
        date_v = ws.cell(r, 1).value
        if date_v is None: continue
        dates.append(date_v)
        for c, h in enumerate(headers[1:], 2):
            if not h: continue
            v = ws.cell(r, c).value
            prices[h].append(float(v) if isinstance(v, (int, float)) else None)

    wb.close()
    if not dates:
        return {"error": "종가 데이터 없음"}

    kospi = prices.get("코스피", [])
    n = len(dates)

    # RS 계산: 각 기간 절대 수익률 (종목 - 코스피 상대)
    results = {}
    for stock, plist in prices.items():
        if stock == "코스피": continue
        row = {"name": stock}
        for period in [60, 120, 250]:
            if n > period:
                p_now = plist[-1]
                p_ago = next((plist[-(period + 1 + i)] for i in range(5)
                              if -(period + 1 + i) >= -n and plist[-(period + 1 + i)] is not None), None)
                k_now = kospi[-1]
                k_ago = next((kospi[-(period + 1 + i)] for i in range(5)
                              if -(period + 1 + i) >= -n and kospi[-(period + 1 + i)] is not None), None)
                if p_now and p_ago and k_now and k_ago:
                    s_ret = (p_now / p_ago - 1) * 100
                    k_ret = (k_now / k_ago - 1) * 100
                    row[f"RS_{period}d"] = round(s_ret - k_ret, 2)
        results[stock] = row

    # 정규화: 퍼센타일
    for period in [60, 120, 250]:
        key = f"RS_{period}d"
        vals = sorted(v[key] for v in results.values() if key in v)
        nv = len(vals)
        for v in results.values():
            if key in v:
                rank = sum(1 for x in vals if x <= v[key])
                v[f"norm_RS_{period}"] = round(rank / nv * 100, 2)

    # 평균 RS
    for v in results.values():
        rs_vals  = [v[f"RS_{p}d"]     for p in [60, 120, 250] if f"RS_{p}d"     in v]
        nr_vals  = [v[f"norm_RS_{p}"] for p in [60, 120, 250] if f"norm_RS_{p}" in v]
        if rs_vals:  v["RS_avg"]      = round(sum(rs_vals) / len(rs_vals), 2)
        if nr_vals:  v["norm_RS_avg"] = round(sum(nr_vals) / len(nr_vals), 2)

    sorted_r = sorted(
        [v for v in results.values() if "norm_RS_avg" in v],
        key=lambda x: x["norm_RS_avg"], reverse=True
    )

    last_date = str(dates[-1])[:10] if dates else TODAY
    return {
        "file":    path.name,
        "date":    last_date,
        "total":   len(sorted_r),
        "top30":   sorted_r[:30],
        "bottom10": sorted_r[-10:],
    }


# ─── 리포트 생성 ──────────────────────────────────────────────

def build_report(results: dict) -> str:
    lines = [
        f"# Excel Ingest 리포트 — {TODAY}",
        f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 소스: `raw/매일 엑셀넣을것/`",
        "",
    ]

    # 1. 추정이익변경
    r = results.get("추정이익변경", {})
    if "results" in r:
        lines += ["## 1. 추정이익변경 (Rating/TP)", ""]
        for sheet, label in [("Rating_Up","📈 레이팅 상향"), ("Rating_Down","📉 레이팅 하향"),
                              ("TP_Up","🎯 TP 상향"), ("TP_Down","⬇️ TP 하향")]:
            items = r["results"].get(sheet, [])
            if items:
                lines.append(f"### {label} ({len(items)}건)")
                lines.append("| 날짜 | 종목 | 증권사 | 의견변경 | TP변경 |")
                lines.append("|------|------|--------|---------|--------|")
                for it in items[:15]:
                    op = f"{it['op_old']}→{it['op_new']}" if it['op_old'] != it['op_new'] else it['op_new']
                    tp_old = fmt_num(it['tp_old'], "원") if it['tp_old'] else "—"
                    tp_new = fmt_num(it['tp_new'], "원") if it['tp_new'] else "—"
                    tp_str = f"{tp_old}→{tp_new}" if it['tp_old'] else tp_new
                    lines.append(f"| {it['date']} | {it['name']} | {it['brokerage']} | {op} | {tp_str} |")
                lines.append("")
        if r.get("updated"):
            lines += ["**wiki 업데이트:**"] + [f"- {u}" for u in r["updated"]] + [""]

    # 2. 컨센움직임
    r = results.get("컨센움직임", {})
    if "results" in r:
        lines += ["## 2. 컨센움직임 / 서프·쇼크", ""]
        for sheet, label in [("컨센상향","📈 컨센상향"), ("서프라이즈","🎉 어닝서프"),
                              ("컨센하향","📉 컨센하향"), ("쇼크","💥 어닝쇼크")]:
            items = r["results"].get(sheet, [])
            if items:
                lines.append(f"### {label} ({len(items)}종목)")
                lines.append("| 종목 | 섹터 | 1M수익률 | 2026E영업이익(억) | 1M변화 |")
                lines.append("|------|------|---------|----------------|--------|")
                for it in items[:10]:
                    op_str = fmt_num(it['op_2026'], "") if it['op_2026'] else "—"
                    lines.append(f"| {it['name']} | {it['sector']} | {fmt_pct(it['ret_1m'])} | {op_str} | {fmt_pct(it['op_chg1m'])} |")
                lines.append("")

    # 3. 수출
    r = results.get("수출", {})
    if "results" in r:
        lines += ["## 3. 핵심 수출 신호", ""]
        lines.append("| 품목 | 섹터 | 최근월 | 물량YoY | 판가YoY | 신호 |")
        lines.append("|------|------|--------|--------|--------|------|")
        for sheet_name, data in r["results"].items():
            if not data.get("monthly"): continue
            latest = data["monthly"][-1]
            lines.append(
                f"| {sheet_name} | {data['sector']} | {latest['month'][:7]} "
                f"| {fmt_pct(latest['yoy_vol'])} | {fmt_pct(latest['price_yoy'])} "
                f"| {data['signal']} |"
            )
        lines.append("")

    # 4. 유동성체크
    r = results.get("유동성", {})
    if "results" in r:
        lines += ["## 4. 컨센 신고가 TOP10", ""]
        items = r["results"].get("컨센신고가", [])[:10]
        if items:
            lines.append("| 순위 | 종목 | 최근발표일 | 증권사 |")
            lines.append("|------|------|-----------|--------|")
            for it in items:
                lines.append(f"| {it['rank']} | {it['name']} | {it['latest_date']} | {it['brokerage']} |")
        lines.append("")

    def _빈집_섹션(lines, r, title_prefix, sec_num):
        if not (r.get("빈집_A") or r.get("빈집_B")):
            return
        lines += [f"## {sec_num}. {title_prefix} 수급 빈집 탐지", ""]
        if r.get("date"):
            lines.append(f"> 기준일: {r['date']} | {r.get('note', '')}")
            lines.append("")
        for grade, label in [("빈집_A", "🏚️ 빈집A — 완전빈집 (하위 10%)"),
                              ("빈집_B", "🏠 빈집B — 반빈집 (하위 10~25%)")]:
            items = r.get(grade, [])
            if not items: continue
            lines.append(f"### {label} {len(items)}종목")
            lines.append("| 종목 | 오실레이터 | 퍼센타일 | 방향 |")
            lines.append("|------|----------|---------|------|")
            for it in items[:20]:
                lines.append(f"| {it['name']} | {it['osc']:+.6f} | 하위{it['pct']:.1f}% | {it.get('trend','')} |")
            lines.append("")

    _빈집_섹션(lines, results.get("수급", {}),       "대형주(700)",       "5")
    _빈집_섹션(lines, results.get("중소형주수급", {}), "중소형주(700-1400)", "6")

    # 7. 가속화모멘텀 (Q열 — 주당순이익 1개+)
    r = results.get("가속화모멘텀", {})
    if "results" in r:
        q_items = r["results"].get("주당순이익1개+", [])
        if q_items:
            lines += ["## 7. 가속화모멘텀 TOP30 (주당순이익 1개+)", ""]
            lines.append("| 순위 | 종목 | 모멘텀스코어 | 이익변화24 | 이익변화25 |")
            lines.append("|------|------|------------|---------|---------|")
            for i, it in enumerate(q_items[:30], 1):
                c24 = f"{it['chg24']:+.0%}" if it['chg24'] is not None else "—"
                c25 = f"{it['chg25']:+.0%}" if it['chg25'] is not None else "—"
                lines.append(f"| {i} | {it['name']} | {it['score']:.2f} | {c24} | {c25} |")
            lines.append("")

    # 8. RS 상대강도 TOP30
    r = results.get("RS", {})
    if r.get("top30"):
        lines += [f"## 8. RS 상대강도 TOP30 — {r.get('date','')}", ""]
        lines.append("| 종목 | RS_60d | RS_120d | RS_250d | norm평균 |")
        lines.append("|------|--------|---------|---------|---------|")
        for it in r["top30"]:
            r60  = f"{it.get('RS_60d',0):+.1f}%"  if 'RS_60d'  in it else "—"
            r120 = f"{it.get('RS_120d',0):+.1f}%" if 'RS_120d' in it else "—"
            r250 = f"{it.get('RS_250d',0):+.1f}%" if 'RS_250d' in it else "—"
            nav  = f"{it.get('norm_RS_avg',0):.1f}"
            lines.append(f"| {it['name']} | {r60} | {r120} | {r250} | {nav} |")
        lines.append("")

    return "\n".join(lines)


# ─── 텔레그램 발송 ────────────────────────────────────────────────

def _load_env() -> dict:
    env_path = ROOT / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def send_telegram(text: str) -> bool:
    import json as _json, urllib.request as _req, urllib.parse as _parse
    cfg     = _load_env()
    token   = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("  ⚠️ .env BOT_TOKEN/CHAT_ID 없음 — 텔레그램 스킵")
        return False
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for idx, chunk in enumerate(chunks, 1):
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _parse.urlencode({
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": "true",
        }).encode()
        try:
            with _req.urlopen(_req.Request(url, data=data), timeout=10) as r:
                res = _json.loads(r.read())
                if not res.get("ok"):
                    print(f"  ❌ TG 오류: {res}")
                    return False
        except Exception as e:
            print(f"  ❌ TG 실패: {e}")
            return False
    print(f"  ✅ 텔레그램 발송 ({len(chunks)}건)")
    return True


def _빈집_tg_블록(a_list: list) -> list:
    """빈집A 리스트 → 심화중 / 유턴중 분리 라인 반환"""
    심화 = [it for it in a_list if '심화' in it.get('trend', '')]
    유턴 = [it for it in a_list if '재진입' in it.get('trend', '')]
    lines = []
    if 심화:
        lines.append(f"<b>📉 빈집 심화중 — {len(심화)}종목</b>")
        for it in 심화:
            lines.append(f"  {it['name']}  <code>{it['osc']:+.6f}</code>  하위{it.get('pct',0):.0f}%")
        lines.append("")
    if 유턴:
        lines.append(f"<b>↩️ 빈집 유턴중 — {len(유턴)}종목</b>")
        for it in 유턴:
            lines.append(f"  {it['name']}  <code>{it['osc']:+.6f}</code>  하위{it.get('pct',0):.0f}%")
        lines.append("")
    return lines


def _build_중소형주_tg(r: dict) -> str:
    date_str = r.get("date", TODAY)
    total    = r.get("total", 0)
    a_list   = r.get("빈집_A", [])
    심화 = [it for it in a_list if '심화' in it.get('trend', '')]
    유턴 = [it for it in a_list if '재진입' in it.get('trend', '')]
    lines = [
        f"🏚️ <b>중소형주(700-1400) 수급 빈집</b> — {date_str}",
        f"전체 {total}종목 | 심화중: {len(심화)}개  유턴중: {len(유턴)}개",
        "",
    ]
    lines += _빈집_tg_블록(a_list)
    return "\n".join(lines)


def build_빈집_tg(r: dict, results: dict) -> str:
    date_str = r.get("date", TODAY)
    total    = r.get("total", 0)
    a_list   = r.get("빈집_A", [])
    심화 = [it for it in a_list if '심화' in it.get('trend', '')]
    유턴 = [it for it in a_list if '재진입' in it.get('trend', '')]
    lines = [
        f"🏚️ <b>대형주(700) 수급 빈집</b> — {date_str}",
        f"전체 {total}종목 | 심화중: {len(심화)}개  유턴중: {len(유턴)}개",
        "",
    ]
    lines += _빈집_tg_블록(a_list)

    # ── 레이팅 상향 TOP5
    rating_up = results.get("추정이익변경", {}).get("results", {}).get("Rating_Up", [])
    if rating_up:
        lines.append("<b>📈 레이팅 상향 TOP5</b>")
        for it in rating_up[:5]:
            op = f"{it['op_old']}→{it['op_new']}"
            tp = fmt_num(it['tp_new'], "원") if it['tp_new'] else "—"
            lines.append(f"  · {it['name']} ({it['brokerage']}) {op} TP {tp}")
        lines.append("")

    # ── 컨센 신고가 TOP5
    high_list = results.get("유동성", {}).get("results", {}).get("컨센신고가", [])
    if high_list:
        lines.append("<b>🎯 컨센 신고가 TOP5</b>")
        for it in high_list[:5]:
            lines.append(f"  {it['rank']}. {it['name']} ({it['brokerage']})")
        lines.append("")

    return "\n".join(lines)


# ─── log.md 기록 ───────────────────────────────────────────────

def append_log(summary: str):
    if not LOG_FILE.exists(): return
    existing = LOG_FILE.read_text(encoding="utf-8")
    entry = f"- {TODAY} — Excel ingest 완료: {summary}\n"
    LOG_FILE.write_text(entry + existing, encoding="utf-8")


# ─── 메인 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="wiki 수정 없이 리포트만 생성")
    parser.add_argument("--only", help="특정 파서만 실행 (추정이익|컨센|수출|유동성|수급)")
    args = parser.parse_args()

    dry_run = args.dry_run
    only = args.only

    print(f"{'[DRY-RUN] ' if dry_run else ''}Excel Ingest 시작 — {TODAY}")
    print(f"소스 폴더: {EXCEL_DIR}")
    print()

    results = {}

    parsers = {
        "추정이익": ("추정이익변경", lambda: parse_추정이익변경(dry_run)),
        "컨센":     ("컨센움직임",   lambda: parse_컨센움직임(dry_run)),
        "수출":     ("수출",         lambda: parse_수출정리(dry_run)),
        "유동성":   ("유동성",       lambda: parse_유동성체크(dry_run)),
        "수급":     ("수급",         lambda: parse_수급오실레이터(dry_run)),
        "중소형주":  ("중소형주수급",  lambda: parse_중소형주오실레이터(dry_run)),
        "가속화":    ("가속화모멘텀",  lambda: parse_가속화모멘텀(dry_run)),
        "RS":        ("RS",           lambda: parse_rs(dry_run)),
    }

    for key, (label, fn) in parsers.items():
        if only and only not in key: continue
        print(f"  처리 중: {label}...")
        try:
            results[label] = fn()
            if "error" in results[label]:
                print(f"    ⚠️ {results[label]['error']}")
            else:
                print(f"    ✅ 완료")
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            results[label] = {"error": str(e)}

    # 리포트 저장
    report = build_report(results)
    report_path = ROOT / "raw" / f"ingest_report_{TODAY}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📄 리포트: {report_path}")

    # log.md 기록 + 텔레그램 발송
    if not dry_run:
        summary_parts = []
        for label, data in results.items():
            if "error" not in data:
                summary_parts.append(label)
        append_log("·".join(summary_parts) + f" → {report_path.name}")

        # 대형주 수급빈집 텔레그램 발송
        r_수급 = results.get("수급", {})
        if r_수급.get("빈집_A") or r_수급.get("빈집_B"):
            print("\n📲 [대형주] 텔레그램 발송 중...")
            msg = build_빈집_tg(r_수급, results)
            send_telegram(msg)

        # 중소형주 빈집A 텔레그램 발송
        r_중소 = results.get("중소형주수급", {})
        if r_중소.get("빈집_A"):
            print("\n📲 [중소형주] 텔레그램 발송 중...")
            send_telegram(_build_중소형주_tg(r_중소))

    print("\n" + "="*50)
    print(report[:2000])

if __name__ == "__main__":
    main()
