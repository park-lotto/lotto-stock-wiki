"""
extract_유동성컨센.py
raw/유동성 컨센등등.xlsm -> raw/market/YYYYMMDD_유동성컨센_요약.md

실행: python extract_유동성컨센.py [--tg]

출력: raw/market/YYYYMMDD_유동성컨센_요약.md  <- Claude /ingest 대상
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

import win32com.client

BASE = Path(__file__).parent
XLSM_PATH = BASE / "raw" / "유동성 컨센등등.xlsm"
WLIST_JSON = BASE / "watchlist.json"
OUT_DIR = BASE / "raw" / "market"

# 빈집 등급 기준 (통합순위)
# 이 파일의 기관 추적 유니버스 = 약 546종목
# 통합순위 높을수록 = 기관이 안 사고 있음 = 빈집
TOTAL_UNIVERSE = 546
GRADE_A_THRESHOLD = TOTAL_UNIVERSE * 0.90  # ~491 하위 10% -> A 완전빈집
GRADE_B_THRESHOLD = TOTAL_UNIVERSE * 0.75  # ~410 하위 25% -> B 반빈집
GRADE_D_THRESHOLD = TOTAL_UNIVERSE * 0.25  # ~137 상위 25% -> D 과매수

DAILY_SECTORS = [
    "반도체", "방산", "조선", "LNG", "바이오", "우주", "로봇",
    "자동차", "이차전지", "전력", "원전", "신재생", "화장품", "미용", "철강", "엔터",
]


# ================================================================
# COM 헬퍼
# ================================================================
def open_wb(path: Path):
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.AutomationSecurity = 1
    wb = xl.Workbooks.Open(str(path.resolve()), ReadOnly=True, UpdateLinks=False)
    return xl, wb


def read_range(ws, r1: int, c1: int, r2: int, c2: int) -> list[list]:
    """범위 일괄 읽기 -> list[list]. 셀 수 < 2이면 단일값 보정."""
    if r2 < r1 or c2 < c1:
        return []
    try:
        val = ws.Range(ws.Cells(r1, c1), ws.Cells(r2, c2)).Value2
    except Exception:
        return []
    if val is None:
        return []
    # 단일 행 또는 단일 셀
    if not isinstance(val, tuple):
        return [[val]]
    if not isinstance(val[0], tuple):
        return [list(val)]
    return [list(row) for row in val]


def find_sheet(wb, *patterns: str):
    """시트명에 패턴이 포함되면 반환. None이면 없음."""
    for i in range(wb.Sheets.Count):
        name = wb.Sheets(i + 1).Name
        for pat in patterns:
            if pat.lower() in name.lower():
                return wb.Sheets(i + 1)
    return None


def find_유동성_sheet(wb):
    """'유동성 컨셉 YYYYMMDD' 중 가장 최신 시트 반환."""
    pat = re.compile(r"유동성\s*컨셉\s*(\d{6,8})", re.IGNORECASE)
    candidates = []
    for i in range(wb.Sheets.Count):
        name = wb.Sheets(i + 1).Name
        m = pat.search(name)
        if m:
            candidates.append((int(m.group(1)), name, wb.Sheets(i + 1)))
    if not candidates:
        raise ValueError("유동성 컨셉 시트 없음")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def excel_date_to_str(serial) -> str:
    """Excel 날짜 serial -> YYYY-MM-DD 문자열."""
    if serial is None:
        return ""
    try:
        n = int(float(serial))
        # Excel epoch: 1900-01-01 = 1, but has leap-year bug (day 60)
        base = date(1899, 12, 30)
        from datetime import timedelta
        d = base + timedelta(days=n)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(serial)


# ================================================================
# 1. 유동성 컨셉 — 통합순위 빈집 등급
# ================================================================
def grade_from_rank(rank: float) -> str:
    if rank >= GRADE_A_THRESHOLD:
        return "A"
    if rank >= GRADE_B_THRESHOLD:
        return "B"
    if rank > GRADE_D_THRESHOLD:
        return "C"
    return "D"


def grade_label(g: str) -> str:
    return {
        "A": "A 완전빈집",
        "B": "B 반빈집",
        "C": "C 정상",
        "D": "D 과매수",
    }.get(g, "?")


def extract_유동성컨셉(ws, watchlist: dict) -> dict:
    """
    R15+ 데이터 읽기
    C1=A코드(A005930 형식), C2=종목명, C18=통합순위(float)
    watchlist 종목만 필터링, 섹터별 정리.
    """
    print("  [유동성컨셉] 데이터 읽는 중...")
    last_row = ws.UsedRange.Rows.Count
    rows = read_range(ws, 15, 1, last_row, 18)

    # 전체 종목 맵: 6자리 코드 -> {name, rank, grade}
    code_map: dict[str, dict] = {}
    name_map: dict[str, dict] = {}  # 종목명으로도 검색
    for row in rows:
        if len(row) < 18:
            continue
        raw_code = row[0]  # C1: "A005930"
        name = str(row[1]).strip() if row[1] else ""
        rank_val = row[17]  # C18 (0-based index 17)
        if not raw_code or not name or rank_val is None:
            continue
        # "A005930" -> "005930"
        code6 = re.sub(r"^[A-Za-z]+", "", str(raw_code).strip()).zfill(6)
        try:
            rank_f = float(rank_val)
        except (TypeError, ValueError):
            continue
        g = grade_from_rank(rank_f)
        entry = {"name": name, "code": code6, "rank": rank_f, "grade": g}
        code_map[code6] = entry
        name_map[name] = entry

    print(f"     전체 {len(code_map)}종목 읽음")

    # watchlist 종목과 매칭 (섹터 내 중복 제거)
    sector_results: dict[str, list] = {}
    for sector, subs in watchlist.items():
        matched = []
        seen_codes: set[str] = set()  # 섹터 내 중복 방지
        for sub, stocks in subs.items():
            for s in stocks:
                code6 = str(s["code"]).zfill(6)
                if code6 in seen_codes:
                    continue
                nm = s["name"]
                entry = code_map.get(code6) or name_map.get(nm)
                if entry:
                    seen_codes.add(code6)
                    matched.append({
                        "name": nm,
                        "code": code6,
                        "sub": sub,
                        "rank": entry["rank"],
                        "grade": entry["grade"],
                    })
        if matched:
            # 통합순위 높은 순(빈집 심한 순)으로 정렬
            matched.sort(key=lambda x: -x["rank"])
            sector_results[sector] = matched

    빈집_count = sum(
        1 for stocks in sector_results.values()
        for s in stocks if s["grade"] in ("A", "B")
    )
    print(f"     빈집(A/B) 종목: {빈집_count}개")
    return {"total": len(code_map), "sectors": sector_results}


# ================================================================
# 2. 2027년 컨센 신고가
# ================================================================
def extract_컨센신고가(ws) -> list[dict]:
    """
    R2+ 데이터
    C2=종목명, C3=신고가여부(0=달성), C6=증권사, C8=2027AS OP
    """
    print("  [컨센신고가] 읽는 중...")
    last_row = ws.UsedRange.Rows.Count
    rows = read_range(ws, 2, 1, last_row, 10)
    result = []
    for row in rows:
        if len(row) < 8:
            continue
        name = str(row[1]).strip() if row[1] else ""
        flag = row[2]   # C3
        brokerage = str(row[5]).strip() if row[5] else ""
        op_2027 = row[7]  # C8
        if not name:
            continue
        try:
            flag_int = int(float(flag)) if flag is not None else 999
        except (TypeError, ValueError):
            continue
        if flag_int == 0:  # 0 = 신고가 달성
            result.append({
                "name": name,
                "brokerage": brokerage,
                "op_2027": op_2027,
            })
    print(f"     신고가 달성: {len(result)}종목")
    return result


# ================================================================
# 3. 가속화 모멘텀
# ================================================================
def extract_가속화모멘텀(ws) -> list[dict]:
    """
    R6+ 데이터 (추정이익 3개이상 섹션 기준)
    C2=종목명, C3=모멘텀스코어, C4=OP추정변화(2024), C5=OP추정변화(2025)
    """
    print("  [가속화모멘텀] 읽는 중...")
    last_row = ws.UsedRange.Rows.Count
    rows = read_range(ws, 6, 1, last_row, 10)
    result = []
    for row in rows:
        if len(row) < 3:
            continue
        name = str(row[1]).strip() if row[1] else ""
        score = row[2]  # C3
        op_2024 = row[3] if len(row) > 3 else None
        op_2025 = row[4] if len(row) > 4 else None
        if not name or name in ("종목명", "추정이익 3개이상"):
            continue
        try:
            score_f = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_f = 0.0
        result.append({
            "name": name,
            "score": score_f,
            "op_2024": op_2024,
            "op_2025": op_2025,
        })
    result.sort(key=lambda x: -x["score"])
    print(f"     모멘텀 종목: {len(result)}개")
    return result


# ================================================================
# 4. 업종 1개월 컨센
# ================================================================
def extract_업종컨센(ws) -> list[dict]:
    """
    R9+ 데이터
    C2=최종점수, C3=업종명
    """
    print("  [업종1개월컨센] 읽는 중...")
    last_row = ws.UsedRange.Rows.Count
    rows = read_range(ws, 9, 1, last_row, 8)
    result = []
    for row in rows:
        if len(row) < 3:
            continue
        score = row[1]  # C2
        업종 = str(row[2]).strip() if row[2] else ""
        if not 업종 or 업종 in ("업종", "Last Update"):
            continue
        try:
            score_f = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            continue
        result.append({"업종": 업종, "score": score_f})
    result.sort(key=lambda x: -x["score"])
    print(f"     업종: {len(result)}개")
    return result


# ================================================================
# 5. 주도주 찾기
# ================================================================
def extract_주도주(ws) -> list[dict]:
    """
    R5+ 데이터
    C1=종목명, C3=업종, C5=1개월수익률, C6=3개월수익률
    """
    print("  [주도주찾기] 읽는 중...")
    last_row = ws.UsedRange.Rows.Count
    rows = read_range(ws, 5, 1, last_row, 6)
    result = []
    for row in rows:
        if not row:
            continue
        name = str(row[0]).strip() if row[0] else ""
        업종 = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        ret_1m = row[4] if len(row) > 4 else None
        ret_3m = row[5] if len(row) > 5 else None
        if not name or name in ("Name", "종목명"):
            continue
        try:
            r1 = float(ret_1m) if ret_1m is not None else 0.0
        except (TypeError, ValueError):
            r1 = 0.0
        try:
            r3 = float(ret_3m) if ret_3m is not None else 0.0
        except (TypeError, ValueError):
            r3 = 0.0
        result.append({"name": name, "업종": 업종, "ret_1m": r1, "ret_3m": r3})
    result.sort(key=lambda x: -x["ret_1m"])
    print(f"     주도주: {len(result)}개")
    return result


# ================================================================
# 6. 50일 신고가
# ================================================================
def extract_50일신고가(ws) -> list[dict]:
    """
    R14+ 데이터 (R9-R13 = FnGuide DataGuide config headers)
    C2=종목코드(A-prefix), C3=종목명, C4=시장구분, C7=업종
    """
    print("  [50일신고가] 읽는 중...")
    last_row = min(ws.UsedRange.Rows.Count, 3000)
    if last_row < 14:
        return []
    rows = read_range(ws, 14, 1, last_row, 8)
    result = []
    for row in rows:
        if not row:
            continue
        code_raw = str(row[1]).strip() if row[1] else ""  # C2
        name = str(row[2]).strip() if len(row) > 2 and row[2] else ""   # C3
        market = str(row[3]).strip() if len(row) > 3 and row[3] else ""  # C4
        업종 = str(row[6]).strip() if len(row) > 6 and row[6] else ""    # C7
        if not name or name in ("Name", "종목명"):
            continue
        code6 = re.sub(r"^[A-Za-z]+", "", code_raw).zfill(6) if code_raw else ""
        result.append({"name": name, "code": code6, "market": market, "업종": 업종})
    print(f"     50일신고가 종목: {len(result)}개")
    return result


# ================================================================
# 7. 코스피/코스닥 최종 SIO
# ================================================================
def extract_sio(ws, label: str) -> dict:
    """
    R6+ 데이터. 마지막 비어있지 않은 행이 최신.
    C1=날짜(Excel serial), C2-C9=SIO 컬럼들
    """
    print(f"  [{label}] 읽는 중...")
    total_rows = ws.UsedRange.Rows.Count
    # R6부터 전체 읽기 (데이터가 어디서 끝나는지 미정)
    rows = read_range(ws, 6, 1, total_rows, 10)

    last_valid = None
    for row in rows:
        if row and any(v is not None for v in row[:3]):
            last_valid = row

    if not last_valid:
        return {}

    # 컬럼 구조 (R6 헤더 기준):
    # C1=DATE, C2=지수(KOSPI/KOSDAQ), C3=SIO(과매수/과매도 oscillator),
    # C4=상승비율(0~1), C5=하락비율(0~1),
    # C6=상승거래량, C7=하락거래량, C8=gained, C9=Lost
    def safe_float(row, idx, n_digits=4):
        try:
            if len(row) > idx and row[idx] is not None:
                return round(float(row[idx]), n_digits)
        except Exception:
            pass
        return None

    date_str = excel_date_to_str(last_valid[0]) if last_valid[0] else ""
    index_val = safe_float(last_valid, 1, 2)    # C2 = 지수
    sio = safe_float(last_valid, 2, 4)          # C3 = SIO oscillator (0~1)
    upside_r = safe_float(last_valid, 3, 4)     # C4 = 상승비율 (0~1)
    downside_r = safe_float(last_valid, 4, 4)   # C5 = 하락비율 (0~1)
    up_vol = safe_float(last_valid, 5, 0)       # C6 = 상승거래량
    dn_vol = safe_float(last_valid, 6, 0)       # C7 = 하락거래량

    # 비율 -> % 변환
    upside_pct = round(upside_r * 100, 1) if upside_r is not None else None
    downside_pct = round(downside_r * 100, 1) if downside_r is not None else None
    sio_pct = round(sio * 100, 1) if sio is not None else None

    result = {
        "date": date_str,
        "index": index_val,
        "sio": sio_pct,
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "up_vol": int(up_vol) if up_vol else None,
        "dn_vol": int(dn_vol) if dn_vol else None,
    }
    print(f"     {label} 최신: {date_str} 지수{index_val} SIO{sio_pct}% 상승{upside_pct}%")
    return result


# ================================================================
# 마크다운 보고서 생성
# ================================================================
def fmt_op(val) -> str:
    if val is None:
        return "—"
    try:
        return f"{int(float(val)):,}"
    except Exception:
        return str(val)


def fmt_pct(val) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):+.1f}%"
    except Exception:
        return str(val)


def build_markdown(
    today: str,
    유동성: dict,
    신고가: list,
    모멘텀: list,
    업종: list,
    주도주: list,
    코스피: dict,
    코스닥: dict,
    신고가50: list,
) -> str:
    lines = []
    lines.append(f"# 유동성컨센 요약 — {today}")
    lines.append(f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # ── 섹션1: 수급빈집 ──
    lines.append("## 섹션1 수급빈집 (유동성컨셉 통합순위)")
    lines.append("")
    a_thr = int(GRADE_A_THRESHOLD)
    b_thr = int(GRADE_B_THRESHOLD)
    lines.append(f"기관 추적 유니버스 {TOTAL_UNIVERSE}종목 기준. A≥{a_thr}(하위10%), B≥{b_thr}(하위25%)")
    lines.append("")

    for sector in DAILY_SECTORS:
        stocks = 유동성["sectors"].get(sector, [])
        빈집 = [s for s in stocks if s["grade"] in ("A", "B")]
        if not 빈집:
            continue
        lines.append(f"### {sector} — {len(빈집)}개 빈집")
        lines.append("| 종목 | 코드 | 통합순위 | 상위% | 빈집등급 |")
        lines.append("|------|------|---------|------|--------|")
        for s in 빈집:
            rank_f = s["rank"]
            pct_from_top = round((rank_f / TOTAL_UNIVERSE) * 100, 1)
            lines.append(
                f"| {s['name']} | {s['code']} | {rank_f:.1f} | 상위{pct_from_top}% | {grade_label(s['grade'])} |"
            )
        lines.append("")

    # 빈집 없는 섹터 요약
    empty_sectors = [s for s in DAILY_SECTORS if not any(
        x["grade"] in ("A", "B") for x in 유동성["sectors"].get(s, [])
    )]
    if empty_sectors:
        lines.append(f"> 빈집 없는 섹터: {', '.join(empty_sectors)}")
        lines.append("")

    # ── 섹션2: 컨센 신고가 ──
    lines.append("## 섹션2 2027년 컨센 신고가 종목")
    lines.append("")
    if 신고가:
        lines.append("| 종목 | 증권사 | 2027E (raw값, 단위불명) |")
        lines.append("|------|--------|----------------------|")
        for s in 신고가:
            lines.append(f"| {s['name']} | {s['brokerage']} | {fmt_op(s['op_2027'])} |")
    else:
        lines.append("(신고가 달성 종목 없음)")
    lines.append("")

    # ── 섹션3: 가속화모멘텀 ──
    lines.append("## 섹션3 가속화모멘텀 상위 20종목")
    lines.append("")
    if 모멘텀:
        lines.append("| 순위 | 종목 | 모멘텀스코어 | OP변화(24) | OP변화(25) |")
        lines.append("|-----|------|-----------|----------|----------|")
        for i, s in enumerate(모멘텀[:20], 1):
            lines.append(
                f"| {i} | {s['name']} | {s['score']:.3f} | "
                f"{fmt_pct(s['op_2024'])} | {fmt_pct(s['op_2025'])} |"
            )
    else:
        lines.append("(데이터 없음)")
    lines.append("")

    # ── 섹션4: 업종 1개월 컨센 ──
    lines.append("## 섹션4 업종 1개월 컨센서스 (상위 25위)")
    lines.append("")
    if 업종:
        lines.append("| 순위 | 업종 | 최종점수 |")
        lines.append("|-----|------|---------|")
        for i, s in enumerate(업종[:25], 1):
            lines.append(f"| {i} | {s['업종']} | {s['score']:.1f} |")
    else:
        lines.append("(데이터 없음)")
    lines.append("")

    # ── 섹션5: 주도주 찾기 ──
    lines.append("## 섹션5 주도주 찾기 (시총 상위600 / 수익률상위5% / MDD20%이내)")
    lines.append("")
    if 주도주:
        lines.append("| 종목 | 업종 | 1개월수익률 | 3개월수익률 |")
        lines.append("|------|------|-----------|-----------|")
        for s in 주도주[:20]:
            lines.append(
                f"| {s['name']} | {s['업종']} | {fmt_pct(s['ret_1m'])} | {fmt_pct(s['ret_3m'])} |"
            )
    else:
        lines.append("(데이터 없음)")
    lines.append("")

    # ── 섹션6: 코스피/코스닥 SIO ──
    lines.append("## 섹션6 코스피 / 코스닥 SIO (최신)")
    lines.append("")
    lines.append("| 시장 | 날짜 | 지수 | SIO(과매수/과매도) | 상승% | 하락% | 상승거래량 | 하락거래량 |")
    lines.append("|------|------|------|-----------------|------|------|---------|---------|")
    if 코스피:
        lines.append(
            f"| 코스피 | {코스피.get('date','')} | {코스피.get('index','')} | "
            f"{코스피.get('sio','')}% | {코스피.get('upside_pct','')}% | "
            f"{코스피.get('downside_pct','')}% | {코스피.get('up_vol','')} | {코스피.get('dn_vol','')} |"
        )
    if 코스닥:
        lines.append(
            f"| 코스닥 | {코스닥.get('date','')} | {코스닥.get('index','')} | "
            f"{코스닥.get('sio','')}% | {코스닥.get('upside_pct','')}% | "
            f"{코스닥.get('downside_pct','')}% | {코스닥.get('up_vol','')} | {코스닥.get('dn_vol','')} |"
        )
    lines.append("")

    # ── 섹션7: 50일 신고가 ──
    lines.append("## 섹션7 50일 신고가")
    lines.append("")
    if 신고가50:
        lines.append(f"총 {len(신고가50)}종목")
        lines.append("")
        lines.append("| 종목 | 코드 | 시장 | 업종 |")
        lines.append("|------|------|------|------|")
        for s in 신고가50[:50]:
            lines.append(f"| {s['name']} | {s['code']} | {s['market']} | {s['업종']} |")
    else:
        lines.append("(종목 없음)")
    lines.append("")

    return "\n".join(lines)


# ================================================================
# 텔레그램 전송
# ================================================================
def send_tg(text: str):
    try:
        import requests
    except ImportError:
        print("[TG] requests 없음 -> pip install requests")
        return
    token = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("[TG] TG_BOT_TOKEN / TG_CHAT_ID 환경변수 없음 -> 전송 건너뜀")
        return
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
            timeout=10,
        )
        if not r.ok:
            print(f"[TG] 오류: {r.status_code} {r.text[:200]}")


def build_tg_summary(today: str, 유동성: dict, 신고가: list, 주도주: list) -> str:
    lines = [f"<b>유동성컨센 {today}</b>", ""]
    for sector in DAILY_SECTORS:
        stocks = 유동성["sectors"].get(sector, [])
        빈집 = [s for s in stocks if s["grade"] in ("A", "B")]
        if 빈집:
            names = ", ".join(
                f"<code>{s['name']}</code>({grade_label(s['grade'])})"
                for s in 빈집[:4]
            )
            lines.append(f"<b>{sector}</b>: {names}")
    lines.append("")
    if 신고가:
        lines.append(f"<b>컨센신고가</b>: {', '.join(s['name'] for s in 신고가[:8])}")
    if 주도주:
        lines.append(f"<b>주도주</b>: {', '.join(s['name'] for s in 주도주[:8])}")
    return "\n".join(lines)


# ================================================================
# log.md 업데이트
# ================================================================
def update_log(today: str, 유동성: dict, 신고가: list, 모멘텀: list, out_path: Path):
    log_path = BASE / "wiki" / "log.md"
    if not log_path.exists():
        return
    content = log_path.read_text(encoding="utf-8")
    빈집_total = sum(
        1 for stocks in 유동성["sectors"].values()
        for s in stocks if s["grade"] in ("A", "B")
    )
    entry = (
        f"\n### {today} — 유동성컨센 추출\n"
        f"- 전체 {유동성['total']}종목 분석\n"
        f"- 수급빈집(A/B): {빈집_total}종목\n"
        f"- 컨센신고가: {len(신고가)}종목\n"
        f"- 가속화모멘텀 상위: {len(모멘텀)}종목\n"
        f"- 출력: {out_path.name}\n"
    )
    if "## 작업 이력" in content:
        idx = content.index("## 작업 이력") + len("## 작업 이력")
        content = content[:idx] + "\n" + entry + content[idx:]
    else:
        content = entry + content
    log_path.write_text(content, encoding="utf-8")
    print("  log.md 업데이트 완료")


# ================================================================
# main
# ================================================================
def main():
    parser = argparse.ArgumentParser(description="유동성컨센등등.xlsm 추출")
    parser.add_argument("--tg", action="store_true", help="텔레그램 요약 전송")
    args = parser.parse_args()

    if not XLSM_PATH.exists():
        print(f"파일 없음: {XLSM_PATH}")
        sys.exit(1)

    watchlist: dict = {}
    if WLIST_JSON.exists():
        watchlist = json.loads(WLIST_JSON.read_text(encoding="utf-8"))
    else:
        print("watchlist.json 없음 -> 먼저: python watchlist_parser.py")

    today = datetime.now().strftime("%Y%m%d")
    print(f"\n파일 열기: {XLSM_PATH.name}")
    xl, wb = open_wb(XLSM_PATH)

    try:
        # ── 1. 유동성컨셉 ──
        유동성_name, 유동성_ws = find_유동성_sheet(wb)
        print(f"[1/7] 유동성컨셉 시트: '{유동성_name}'")
        유동성_data = extract_유동성컨셉(유동성_ws, watchlist)

        # ── 2. 컨센신고가 (1) + (2) 합산 ──
        print("[2/7] 2027년 컨센 신고가")
        # 시트 (1) - 대형주 위주
        ws_신고가1 = find_sheet(wb, "2027년 컨센 신고가(2)")  # "(2)" 먼저 (substring match 방지)
        ws_신고가2 = None
        # exact "(1)" 시트 찾기
        for i in range(wb.Sheets.Count):
            nm = wb.Sheets(i + 1).Name
            if nm == "2027년 컨센 신고가":
                ws_신고가2 = wb.Sheets(i + 1)
                break
        신고가_data = []
        if ws_신고가2:
            신고가_data += extract_컨센신고가(ws_신고가2)
        if ws_신고가1:
            신고가_data += extract_컨센신고가(ws_신고가1)

        # ── 3. 가속화모멘텀 ──
        print("[3/7] 가속화모멘텀")
        ws_모멘텀 = find_sheet(wb, "가속화모멘텀", "가속화")
        모멘텀_data = extract_가속화모멘텀(ws_모멘텀) if ws_모멘텀 else []

        # ── 4. 업종1개월컨센 ──
        print("[4/7] 업종 1개월 컨센")
        ws_업종 = find_sheet(wb, "업종 1개월 컨센", "업종1개월컨센", "1개월 컨센")
        업종_data = extract_업종컨센(ws_업종) if ws_업종 else []

        # ── 5. 주도주찾기 ──
        print("[5/7] 주도주찾기")
        ws_주도주 = find_sheet(wb, "주도주찾기", "주도주")
        주도주_data = extract_주도주(ws_주도주) if ws_주도주 else []

        # ── 6. 코스피/코스닥 최종 ──
        print("[6/7] 코스피/코스닥 최종")
        ws_코스피 = find_sheet(wb, "코스피최종", "코스피 최종")
        ws_코스닥 = find_sheet(wb, "코스닥최종", "코스닥 최종")
        코스피_data = extract_sio(ws_코스피, "코스피최종") if ws_코스피 else {}
        코스닥_data = extract_sio(ws_코스닥, "코스닥최종") if ws_코스닥 else {}

        # ── 7. 50일 신고가 ──
        print("[7/7] 50일 신고가")
        ws_50 = find_sheet(wb, "50일 신고가", "50일신고가")
        신고가50_data = extract_50일신고가(ws_50) if ws_50 else []

    finally:
        wb.Close(SaveChanges=False)
        xl.Quit()

    # ── 마크다운 생성 ──
    md = build_markdown(
        today, 유동성_data, 신고가_data, 모멘텀_data,
        업종_data, 주도주_data, 코스피_data, 코스닥_data, 신고가50_data,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{today}_유동성컨센_요약.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"\n저장: {out_path}")
    print(f"  빈집종목: {sum(1 for s in 유동성_data['sectors'].values() for x in s if x['grade'] in ('A','B'))}개")
    print(f"  컨센신고가: {len(신고가_data)}개  |  주도주: {len(주도주_data)}개")

    if args.tg:
        tg_msg = build_tg_summary(today, 유동성_data, 신고가_data, 주도주_data)
        send_tg(tg_msg)
        print("[TG] 전송 완료")

    update_log(today, 유동성_data, 신고가_data, 모멘텀_data, out_path)

    print("\n완료. /ingest 명령어:")
    print(f"  /ingest raw/market/{today}_유동성컨센_요약.md")


if __name__ == "__main__":
    main()
