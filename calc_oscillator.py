#!/usr/bin/env python3
"""
calc_oscillator.py — 수급오실레이터 계산기
  원본: 외국인기관수급오실레이터 (눈)0526.xlsm
  공식: oscillator = EMA(12) - EMA(26) of [(기관+외인순매수)/거래대금]  →  MACD - Signal(EMA9)

사용법:
  python calc_oscillator.py                              ← 전체 종목 통계 + 상위/하위 20개
  python calc_oscillator.py 삼성전자                    ← 단일 종목
  python calc_oscillator.py 반도체                      ← 키워드 포함 종목 전체
  python calc_oscillator.py 삼성전자 SK하이닉스 한미반도체  ← 여러 종목 비교표
  python calc_oscillator.py 삼성전자 SK하이닉스 --tg    ← 결과를 텔레그램으로 전송

단일/소수 종목: xlsm 내 사전계산 통계 사용 → 빠름 (수초)
전체 스캔:      700개 직접 계산 → 수분 소요
"""
import sys
import math
import os
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

# ── 텔레그램 설정 (.env에서 로드) ─────────────────────────────
def _load_env():
    env_path = Path(__file__).parent / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def send_telegram(text: str):
    import urllib.request, urllib.parse, json
    cfg = _load_env()
    token = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  텔레그램 설정 없음 (.env BOT_TOKEN/CHAT_ID 확인)")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    if result.get("ok"):
        print("✅ 텔레그램 전송 완료")
    else:
        print(f"❌ 전송 실패: {result}")

FILE = Path(r"C:\Users\TheRose\Desktop\로또의 주식\raw\매일 엑셀넣을것\외국인기관수급오실레이터 (눈)0526.xlsm")

# ── EMA 계수 ───────────────────────────────────────────────────
K12 = 2 / 13        # EMA12
K26 = 2 / 27        # EMA26
K9  = 2 / 10        # Signal (EMA9 of MACD)
DATA_ROW_START = 15
DATA_ROW_END   = 91   # 77 trading days

# 수급오실레이터 시트 내 사전계산 백분위 기준값 위치
STAT_ROW_P90  = 7   # 상위10% (= 하위90% 기준)
STAT_ROW_P75  = 8   # 상위25%
STAT_ROW_AVG  = 9   # 평균
STAT_ROW_P25  = 10  # 하위25%
STAT_ROW_P10  = 11  # 하위10%
STAT_COL      = 12  # C12


def ema_series(values: list[float], k: float) -> list[float]:
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def calc_osc(signal: list[float]) -> dict:
    ema12 = ema_series(signal, K12)
    ema26 = ema_series(signal, K26)
    macd  = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    sig_line = ema_series(macd, K9)
    osc = [m - s for m, s in zip(macd, sig_line)]
    return {
        "series": osc,
        "latest": osc[-1],
        "macd_latest": macd[-1],
        "signal_latest": sig_line[-1],
    }


def read_sheet_column(ws, col: int, row_start: int, row_end: int) -> list:
    vals = []
    for r in range(row_start, row_end + 1):
        v = ws.Cells(r, col).Value2
        vals.append(float(v) if v is not None else None)
    return vals


def compute_stock(name, col, ws_size, ws_forn, ws_inst) -> dict | None:
    size_vals = read_sheet_column(ws_size, col, DATA_ROW_START, DATA_ROW_END)
    forn_vals = read_sheet_column(ws_forn, col, DATA_ROW_START, DATA_ROW_END)
    inst_vals = read_sheet_column(ws_inst, col, DATA_ROW_START, DATA_ROW_END)

    pairs = [
        ((inst or 0) + (forn or 0), size)
        for inst, forn, size in zip(inst_vals, forn_vals, size_vals)
        if size and size > 0
    ]
    if len(pairs) < 27:
        return None

    signal_series = [(net / sz) for net, sz in pairs]
    r = calc_osc(signal_series)
    return r


def grade(v, p10, p25, p75):
    if v <= p10:  return "A 완전빈집"
    if v <= p25:  return "B 반빈집"
    if v <= p75:  return "C 정상"
    return "D 과매수"


def pct_from_thresholds(v, p10, p25, p75, p90):
    """임계값 기반 대략 백분위 (xlsm 사전계산값 사용)."""
    if v <= p10:  return (v / p10) * 10 if p10 != 0 else 5.0
    if v <= p25:  return 10 + (v - p10) / (p25 - p10) * 15
    if v <= p75:  return 25 + (v - p25) / (p75 - p25) * 50
    if v <= p90:  return 75 + (v - p75) / (p90 - p75) * 15
    return 90 + min((v - p90) / abs(p90) * 5 if p90 != 0 else 5, 10)


def main():
    import win32com.client as win32

    args = sys.argv[1:]
    send_tg = "--tg" in args
    args = [a for a in args if a != "--tg"]
    queries = [q.strip() for q in args if q.strip()]
    full_scan = not queries
    multi_mode = len(queries) > 1

    print(f"\n{'━'*56}")
    print(f"  수급오실레이터 계산기  (EMA12-EMA26 / Signal EMA9)")
    print(f"{'━'*56}\n")
    print("Excel 파일 열기 중...")

    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.AutomationSecurity = 3
    wb = xl.Workbooks.Open(str(FILE))

    ws_osc  = wb.Sheets("수급오실레이터")
    ws_size = wb.Sheets("시가총액")
    ws_forn = wb.Sheets("외국인매수데이터")
    ws_inst = wb.Sheets("기관매수데이터")

    # ── xlsm 사전계산 백분위 기준값 읽기 ──────────────────────
    p90 = ws_osc.Cells(STAT_ROW_P90, STAT_COL).Value2   # 상위10%
    p75 = ws_osc.Cells(STAT_ROW_P75, STAT_COL).Value2   # 상위25%
    p25 = ws_osc.Cells(STAT_ROW_P25, STAT_COL).Value2   # 하위25%
    p10 = ws_osc.Cells(STAT_ROW_P10, STAT_COL).Value2   # 하위10%

    # ── 종목 목록 읽기 ─────────────────────────────────────────
    print("종목 목록 로딩 중...")
    stocks = {}
    codes  = {}
    max_col = ws_forn.UsedRange.Columns.Count
    for c in range(2, max_col + 1):
        name = ws_forn.Cells(9, c).Value2
        code = ws_forn.Cells(8, c).Value2
        if name:
            stocks[name] = c
            codes[name]  = str(code).replace("A", "") if code else ""

    print(f"총 {len(stocks)}개 종목 로드 완료\n")

    # ── 대상 종목 결정 ─────────────────────────────────────────
    if full_scan:
        targets = list(stocks.keys())
        print(f"전체 {len(targets)}개 종목 계산 중... (수분 소요)")
    else:
        targets = []
        not_found = []
        for q in queries:
            matched = [n for n in stocks if q in n]
            if matched:
                targets.extend(matched)
            else:
                not_found.append(q)
        # 중복 제거 (순서 유지)
        seen = set(); targets = [n for n in targets if not (n in seen or seen.add(n))]
        if not_found:
            print(f"⚠️  찾지 못한 종목: {', '.join(not_found)}")
        if not targets:
            wb.Close(False); xl.Quit()
            print("❌ 조회할 종목 없음"); return
        print(f"{len(targets)}개 종목 계산 중...")

    # ── 오실레이터 계산 ────────────────────────────────────────
    results = []
    for name in targets:
        col = stocks[name]
        r = compute_stock(name, col, ws_size, ws_forn, ws_inst)
        if r is None:
            continue
        results.append({
            "name":   name,
            "code":   codes[name],
            "osc":    r["latest"],
            "macd":   r["macd_latest"],
            "sig":    r["signal_latest"],
            "series": r["series"],
        })

    wb.Close(False)
    xl.Quit()

    if not results:
        print("계산 가능한 종목 없음")
        return

    # ── 백분위/등급 부여 ────────────────────────────────────────
    if full_scan:
        # 전체 스캔: 직접 계산한 분포 사용
        all_sorted = sorted(r["osc"] for r in results)
        n = len(all_sorted)
        p10_calc = all_sorted[int(n * 0.10)]
        p25_calc = all_sorted[int(n * 0.25)]
        p75_calc = all_sorted[int(n * 0.75)]
        p90_calc = all_sorted[int(n * 0.90)]
        def get_pct(v):
            idx = sum(1 for x in all_sorted if x <= v)
            return idx / n * 100
        for r in results:
            r["pct"]   = get_pct(r["osc"])
            r["grade"] = grade(r["osc"], p10_calc, p25_calc, p75_calc)
        p10, p25, p75, p90 = p10_calc, p25_calc, p75_calc, p90_calc
        n_label = n
    else:
        # 단일/소수 종목: xlsm 사전계산 임계값으로 빠르게 등급 판정
        for r in results:
            r["pct"]   = pct_from_thresholds(r["osc"], p10, p25, p75, p90)
            r["grade"] = grade(r["osc"], p10, p25, p75)
        n_label = len(stocks)

    # 방향 계산 헬퍼
    def trend(r):
        if len(r["series"]) < 5: return "—"
        avg = sum(r["series"][-5:-1]) / 4
        if r["osc"] > avg * 1.05:   return "↑ 재진입"
        elif r["osc"] < avg * 0.95: return "↓ 빈집심화"
        else:                       return "→ 횡보"

    # ── 출력 ────────────────────────────────────────────────────
    if not full_scan and len(results) == 1:
        # 단일 종목: 상세 박스
        r = results[0]
        print(f"┌{'─'*50}")
        print(f"│ {r['name']} ({r['code']})")
        print(f"│ 오실레이터: {r['osc']:.6f}")
        print(f"│ MACD:       {r['macd']:.6f}")
        print(f"│ 시그널:     {r['sig']:.6f}")
        print(f"│ 백분위:     하위{r['pct']:.1f}%  (전체 {n_label}개 기준)")
        print(f"│ 등급:       {r['grade']}")
        print(f"│ 방향:       {trend(r)}")
        print(f"└{'─'*50}\n")
        print(f"  [기준값] 하위10%(A):{p10:.6f}  하위25%(B):{p25:.6f}  상위25%(D):{p75:.6f}")

    elif not full_scan and len(results) <= 20:
        # 다수 종목: 비교표 (오실레이터 낮은 순 정렬)
        sorted_r = sorted(results, key=lambda x: x["osc"])
        print(f"{'종목':<16} {'코드':<8} {'오실레이터':>12} {'백분위':>8} {'등급':<12} {'방향'}")
        print(f"{'─'*16} {'─'*8} {'─'*12} {'─'*8} {'─'*12} {'─'*10}")
        for r in sorted_r:
            print(f"{r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']:<12} {trend(r)}")
        print(f"\n  [기준값] 하위10%(A):{p10:.6f}  하위25%(B):{p25:.6f}  상위25%(D):{p75:.6f}")

    else:
        sorted_results = sorted(results, key=lambda x: x["osc"])

        print(f"📊 전체 통계 (대상 {n_label}개 종목)")
        print(f"  하위10%(A): {p10:.6f}  하위25%(B): {p25:.6f}")
        print(f"  상위25%(D): {p75:.6f}  상위10%:    {p90:.6f}")
        print()

        top20 = sorted_results[:20]
        print(f"🔴 빈집 상위 {len(top20)} (오실레이터 낮을수록 빈집):")
        print(f"  {'종목':<16} {'코드':<8} {'오실레이터':>12} {'백분위':>8} {'등급'}")
        print(f"  {'─'*16} {'─'*8} {'─'*12} {'─'*8} {'─'*10}")
        for r in top20:
            print(f"  {r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']}")

        print()
        bot10 = sorted_results[-10:]
        print(f"🟡 과매수 상위 {len(bot10)}:")
        print(f"  {'종목':<16} {'코드':<8} {'오실레이터':>12} {'백분위':>8} {'등급'}")
        for r in bot10:
            print(f"  {r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']}")

    # ── 텔레그램 전송 ────────────────────────────────────────────
    if send_tg:
        today = date.today().strftime("%Y-%m-%d")
        grade_icon = {"A 완전빈집": "🔴", "B 반빈집": "🟠", "C 정상": "⚪", "D 과매수": "🟡"}

        if not full_scan and len(results) == 1:
            r = results[0]
            icon = grade_icon.get(r["grade"], "")
            msg = (
                f"<b>📊 수급오실레이터 {today}</b>\n\n"
                f"{icon} <b>{r['name']}</b> ({r['code']})\n"
                f"오실레이터: <code>{r['osc']:.6f}</code>\n"
                f"등급: {r['grade']}  방향: {trend(r)}\n"
                f"백분위: 하위{r['pct']:.1f}% (전체 {n_label}개)\n\n"
                f"기준 A≤{p10:.6f}  B≤{p25:.6f}"
            )
        else:
            target_r = sorted(results, key=lambda x: x["osc"]) if not full_scan else sorted(results, key=lambda x: x["osc"])[:20]
            lines = [f"<b>📊 수급오실레이터 {today}</b>\n"]
            for r in target_r:
                icon = grade_icon.get(r["grade"], "")
                lines.append(f"{icon} <b>{r['name']}</b>  {r['osc']:.6f}  하위{r['pct']:.1f}%  {trend(r)}")
            lines.append(f"\n기준 A≤{p10:.6f}  B≤{p25:.6f}")
            msg = "\n".join(lines)

        send_telegram(msg)


if __name__ == "__main__":
    main()
