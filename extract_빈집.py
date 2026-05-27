# -*- coding: utf-8 -*-
"""
extract_빈집.py — 수급오실레이터 전종목 스캔 → 빈집 일괄 추출
오실레이터_종목별.xlsm × watchlist.json → raw/market/YYYYMMDD_빈집_요약.md

실행: python extract_빈집.py
     python extract_빈집.py --tg
"""
import sys, os, json, re, argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# calc_oscillator.py 의 핵심 함수 재사용
from calc_oscillator import (
    find_xlsm, load_watchlist,
    load_bulk, compute_stock_bulk,
    grade, pct_from_thresholds, trend_str,
    STAT_ROW_P90, STAT_ROW_P75, STAT_ROW_P25, STAT_ROW_P10, STAT_COL,
    DAILY_SECTORS, GRADE_ICON,
)

import win32com.client as win32
import requests

BASE    = Path(__file__).parent
OUT_DIR = BASE / "raw" / "market"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Excel 열기 ────────────────────────────────────────────────────
def open_xlsm(path: Path):
    xl = win32.Dispatch("Excel.Application")
    xl.AutomationSecurity = 3
    wb = xl.Workbooks.Open(str(path))
    return xl, wb


# ── 전종목 스캔 ───────────────────────────────────────────────────
def scan_all(wb, watchlist: dict) -> tuple[list, dict]:
    """
    반환: (results_list, thresholds)
    results_list: [{name, code, sector, sub, osc, pct, grade, trend}]
    thresholds:   {p10, p25, p75, p90}
    """
    ws_osc  = wb.Sheets("수급오실레이터")
    ws_forn = wb.Sheets("외국인매수데이터")
    ws_inst = wb.Sheets("기관매수데이터")
    ws_size = wb.Sheets("시가총액")

    p90 = ws_osc.Cells(STAT_ROW_P90, STAT_COL).Value2
    p75 = ws_osc.Cells(STAT_ROW_P75, STAT_COL).Value2
    p25 = ws_osc.Cells(STAT_ROW_P25, STAT_COL).Value2
    p10 = ws_osc.Cells(STAT_ROW_P10, STAT_COL).Value2

    # 종목→컬럼 맵
    max_col = ws_forn.UsedRange.Columns.Count
    xl_stocks = {}
    for c in range(2, max_col + 1):
        name = ws_forn.Cells(9, c).Value2
        code = ws_forn.Cells(8, c).Value2
        if name:
            xl_stocks[name] = {
                "col": c,
                "code": str(code).replace("A", "") if code else "",
            }

    print(f"  xlsm 종목: {len(xl_stocks)}개")
    print("  데이터 일괄 로딩 중...")
    mat_size, mat_forn, mat_inst = load_bulk(ws_size, ws_forn, ws_inst, max_col)

    results = []
    seen = set()

    for sector in DAILY_SECTORS:
        if sector not in watchlist:
            continue
        for sub, stock_list in watchlist[sector].items():
            for st in stock_list:
                name = st["name"]
                if name in seen or name not in xl_stocks:
                    continue
                seen.add(name)
                info = xl_stocks[name]
                r = compute_stock_bulk(info["col"], mat_size, mat_forn, mat_inst)
                if r is None:
                    continue
                osc = r["latest"]
                results.append({
                    "name":   name,
                    "code":   info["code"],
                    "sector": sector,
                    "sub":    sub,
                    "osc":    osc,
                    "pct":    pct_from_thresholds(osc, p10, p25, p75, p90),
                    "grade":  grade(osc, p10, p25, p75),
                    "trend":  trend_str(r["series"]),
                    "series": r["series"],
                })

    return results, {"p10": p10, "p25": p25, "p75": p75, "p90": p90}


# ── 마크다운 생성 ─────────────────────────────────────────────────
def build_markdown(results: list, thresholds: dict, today_str: str) -> str:
    p10, p25 = thresholds["p10"], thresholds["p25"]

    빈집A = [r for r in results if r["grade"] == "A 완전빈집"]
    빈집B = [r for r in results if r["grade"] == "B 반빈집"]
    재진입 = [r for r in (빈집A + 빈집B) if "재진입" in r["trend"]]

    빈집A.sort(key=lambda x: x["osc"])
    빈집B.sort(key=lambda x: x["osc"])
    재진입.sort(key=lambda x: x["osc"])

    lines = [
        f"# 수급오실레이터 빈집 분석 — {today_str}",
        f"> 기준: A≤{p10:.6f} (하위10%)  B≤{p25:.6f} (하위25%)",
        f"> 스캔: {len(results)}종목 / A빈집 {len(빈집A)}개 / B빈집 {len(빈집B)}개",
        "",
    ]

    # ── 핵심: 빈집 + 재진입 교집합 ──────────────────────────────
    if 재진입:
        lines += [
            "## 🔴 오늘의 핵심 — 빈집 + 재진입 초기",
            "> 빈집 상태에서 오실레이터가 바닥을 치고 올라오는 중 — 매수 트리거 구간",
            "",
            "| 종목 | 섹터 | 오실레이터 | 방향 | 등급 |",
            "|------|------|---------|------|------|",
        ]
        for r in 재진입:
            icon = GRADE_ICON[r["grade"]]
            lines.append(
                f"| {r['name']} | {r['sector']} | `{r['osc']:+.6f}` | {r['trend']} | {icon} {r['grade']} |"
            )
        lines.append("")
    else:
        lines += ["## 🔴 오늘의 핵심 — 빈집 + 재진입 초기", "> 현재 재진입 신호 없음", ""]

    # ── A 완전빈집 ────────────────────────────────────────────────
    lines += [
        f"## 섹션1 — A 완전빈집 ({len(빈집A)}종목, 하위10%)",
        "",
        "| 종목 | 섹터 | 오실레이터 | 백분위 | 방향 |",
        "|------|------|---------|-------|------|",
    ]
    for r in 빈집A:
        lines.append(
            f"| {r['name']} | {r['sector']} | `{r['osc']:+.6f}` | 하위{r['pct']:.0f}% | {r['trend']} |"
        )
    lines.append("")

    # ── B 반빈집 ──────────────────────────────────────────────────
    lines += [
        f"## 섹션2 — B 반빈집 ({len(빈집B)}종목, 하위25%)",
        "",
        "| 종목 | 섹터 | 오실레이터 | 백분위 | 방향 |",
        "|------|------|---------|-------|------|",
    ]
    for r in 빈집B:
        lines.append(
            f"| {r['name']} | {r['sector']} | `{r['osc']:+.6f}` | 하위{r['pct']:.0f}% | {r['trend']} |"
        )
    lines.append("")

    # ── 섹터별 요약 ───────────────────────────────────────────────
    lines += ["## 섹터별 빈집 현황", ""]
    lines += ["| 섹터 | A빈집 | B빈집 | 합계 |", "|------|-------|-------|------|"]
    for sector in DAILY_SECTORS:
        a = len([r for r in 빈집A if r["sector"] == sector])
        b = len([r for r in 빈집B if r["sector"] == sector])
        if a + b > 0:
            lines.append(f"| {sector} | {a} | {b} | {a+b} |")
    lines.append("")

    return "\n".join(lines)


def send_tg(text: str):
    env = {}
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    token   = env.get("BOT_TOKEN") or env.get("TG_BOT_TOKEN", "")
    chat_id = env.get("CHAT_ID")   or env.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("TG 환경변수 없음 — 전송 스킵")
        return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
            timeout=10,
        )


def update_log(today_str: str, cnt_a: int, cnt_b: int, cnt_reentry: int):
    log_path = BASE / "wiki" / "log.md"
    if not log_path.exists():
        return
    content = log_path.read_text(encoding="utf-8")
    line = f"- {today_str} — 수급빈집 ingest: A={cnt_a} B={cnt_b} 재진입={cnt_reentry}\n"
    if "## 작업 이력" in content:
        content = content.replace("## 작업 이력\n", f"## 작업 이력\n{line}")
    else:
        content = line + content
    log_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tg", action="store_true")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y%m%d")
    today_str = f"{today[:4]}-{today[4:6]}-{today[6:]}"

    xlsm_path = find_xlsm()
    print(f"\n파일: {xlsm_path.name}")

    watchlist = load_watchlist()
    print(f"watchlist: {sum(len(v) for s in watchlist.values() for v in s.values())}종목")

    print("Excel 열기...")
    xl, wb = open_xlsm(xlsm_path)
    try:
        results, thresholds = scan_all(wb, watchlist)
    finally:
        wb.Close(False)
        xl.Quit()

    빈집A = [r for r in results if r["grade"] == "A 완전빈집"]
    빈집B = [r for r in results if r["grade"] == "B 반빈집"]
    재진입 = [r for r in (빈집A + 빈집B) if "재진입" in r["trend"]]

    print(f"\n결과: 전체 {len(results)}종목 / A빈집 {len(빈집A)} / B빈집 {len(빈집B)} / 재진입 {len(재진입)}")

    md = build_markdown(results, thresholds, today_str)
    out_path = OUT_DIR / f"{today}_빈집_요약.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"저장: {out_path.name}")

    if 재진입:
        print("\n🔴 재진입 신호:")
        for r in 재진입:
            print(f"  {r['name']} ({r['sector']})  {r['osc']:+.6f}  {r['trend']}")

    if args.tg:
        핵심 = [r for r in 재진입]
        if 핵심:
            msg = f"<b>수급빈집 + 재진입 {today_str}</b>\n\n"
            for r in 핵심[:15]:
                msg += f"🔴 <b>{r['name']}</b> ({r['sector']})  <code>{r['osc']:+.6f}</code>  {r['trend']}\n"
            msg += f"\nA빈집:{len(빈집A)} B빈집:{len(빈집B)} 전체:{len(results)}"
        else:
            msg = f"<b>수급빈집 {today_str}</b>\nA:{len(빈집A)} B:{len(빈집B)} / 재진입 없음"
        send_tg(msg)
        print("텔레그램 전송 완료")

    update_log(today_str, len(빈집A), len(빈집B), len(재진입))


if __name__ == "__main__":
    main()
