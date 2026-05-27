#!/usr/bin/env python3
"""
calc_oscillator.py — 수급오실레이터 계산기
  공식: oscillator = EMA(12) - EMA(26) of [(기관+외인순매수)/시가총액]  →  MACD - Signal(EMA9)

사용법:
  python calc_oscillator.py --all --tg            ← 16개 섹터 전체 스캔 + 텔레그램
  python calc_oscillator.py --sector 반도체 조선  ← 지정 섹터만
  python calc_oscillator.py 삼성전자              ← 단일 종목
  python calc_oscillator.py 삼성전자 SK하이닉스 --tg

파일 자동 탐지: raw/매일 엑셀넣을것/외국인기관수급오실레이터*.xlsm (최신 수정일 우선)
watchlist.json: python watchlist_parser.py 로 생성
"""
import sys
import json
import os
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

# ── 경로 설정 ───────────────────────────────────────────────────
BASE       = Path(__file__).parent
XLSM_DIR   = BASE / "raw" / "매일 엑셀넣을것"
XLSM_PAT   = "외국인기관수급오실레이터*.xlsm"
WLIST_JSON = BASE / "watchlist.json"

DAILY_SECTORS = [
    "반도체", "방산", "조선", "LNG", "바이오", "우주", "로봇",
    "자동차", "이차전지", "전력", "원전", "신재생", "화장품", "미용", "철강", "엔터",
]

# ── EMA 계수 ───────────────────────────────────────────────────
K12 = 2 / 13
K26 = 2 / 27
K9  = 2 / 10
DATA_ROW_START = 15
DATA_ROW_END   = 91   # 77 거래일
STAT_ROW_P90  = 7
STAT_ROW_P75  = 8
STAT_ROW_P25  = 10
STAT_ROW_P10  = 11
STAT_COL      = 12

GRADE_ICON = {"A 완전빈집": "🔴", "B 반빈집": "🟠", "C 정상": "⚪", "D 과매수": "🟡"}


# ── 텔레그램 ─────────────────────────────────────────────────────
def _load_env():
    env_path = BASE / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def send_telegram(text: str):
    import urllib.request, urllib.parse
    cfg = _load_env()
    token = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("텔레그램 설정 없음 (.env BOT_TOKEN/CHAT_ID 확인)")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    if result.get("ok"):
        print("텔레그램 전송 완료")
    else:
        print(f"전송 실패: {result}")


# ── 파일 탐지 ─────────────────────────────────────────────────────
def find_xlsm() -> Path:
    files = sorted(XLSM_DIR.glob(XLSM_PAT), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"{XLSM_DIR}/{XLSM_PAT} 없음. 파일을 넣어주세요.")
    return files[0]


def load_watchlist() -> dict:
    if not WLIST_JSON.exists():
        raise FileNotFoundError("watchlist.json 없음. 먼저: python watchlist_parser.py")
    with open(WLIST_JSON, encoding="utf-8") as f:
        return json.load(f)


# ── 수급오실레이터 계산 ──────────────────────────────────────────
def ema_series(values: list[float], k: float) -> list[float]:
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def calc_osc(signal: list[float]) -> dict:
    ema12    = ema_series(signal, K12)
    ema26    = ema_series(signal, K26)
    macd     = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    sig_line = ema_series(macd, K9)
    osc      = [m - s for m, s in zip(macd, sig_line)]
    return {"series": osc, "latest": osc[-1], "macd_latest": macd[-1], "signal_latest": sig_line[-1]}


def load_bulk(ws_size, ws_forn, ws_inst, max_col: int):
    """3개 시트 일괄 읽기 (COM 3회)."""
    def to_matrix(ws):
        raw = ws.Range(ws.Cells(DATA_ROW_START, 1), ws.Cells(DATA_ROW_END, max_col)).Value
        return raw if raw else []
    return to_matrix(ws_size), to_matrix(ws_forn), to_matrix(ws_inst)


def compute_stock_bulk(col: int, mat_size, mat_forn, mat_inst) -> dict | None:
    c = col - 1
    size_v = [float(mat_size[r][c]) if mat_size[r][c] else None for r in range(len(mat_size))]
    forn_v = [float(mat_forn[r][c]) if mat_forn[r][c] else None for r in range(len(mat_forn))]
    inst_v = [float(mat_inst[r][c]) if mat_inst[r][c] else None for r in range(len(mat_inst))]
    pairs  = [((iv or 0) + (fv or 0), sv)
              for iv, fv, sv in zip(inst_v, forn_v, size_v) if sv and sv > 0]
    if len(pairs) < 27:
        return None
    return calc_osc([net / sz for net, sz in pairs])


# ── 등급/백분위/방향 ──────────────────────────────────────────────
def grade(v, p10, p25, p75) -> str:
    if v <= p10: return "A 완전빈집"
    if v <= p25: return "B 반빈집"
    if v <= p75: return "C 정상"
    return "D 과매수"


def pct_from_thresholds(v, p10, p25, p75, p90) -> float:
    if v <= p10: return (v / p10) * 10 if p10 != 0 else 5.0
    if v <= p25: return 10 + (v - p10) / (p25 - p10) * 15
    if v <= p75: return 25 + (v - p25) / (p75 - p25) * 50
    if v <= p90: return 75 + (v - p75) / (p90 - p75) * 15
    return 90 + min((v - p90) / abs(p90) * 5 if p90 != 0 else 5, 10)


def trend_str(series: list[float]) -> str:
    if len(series) < 5: return "—"
    avg = sum(series[-5:-1]) / 4
    latest = series[-1]
    if avg == 0:
        return "→ 횡보"
    if latest > avg * 1.05: return "↑ 재진입"
    if latest < avg * 0.95: return "↓ 빈집심화"
    return "→ 횡보"


# ── 섹터 스캔 텔레그램 메시지 생성 ──────────────────────────────
def make_sector_message(sector: str, sector_data: dict, xl_stocks: dict,
                        mat_size, mat_forn, mat_inst,
                        p10, p25, p75, p90) -> str:
    """
    sector_data: {서브섹터: [{name, code}]}
    xl_stocks:   {종목명: {"col": int, "code": str}}  — xlsm 내 컬럼
    반환: Telegram HTML 메시지 (4000자 이내 보장용으로 sub-sector 없는 섹터 생략)
    """
    today  = date.today().strftime("%Y-%m-%d")
    header = f"<b>[ {sector} ] 수급오실레이터 {today}</b>\n"

    # 서브섹터별 결과 수집 (섹터 내 중복 종목은 첫 번째 서브섹터에만 표시)
    sub_summaries = []  # (sub_name, [(결과dict)])
    total = 0
    cnt_a = cnt_b = 0
    seen_names: set[str] = set()

    for sub, stock_list in sector_data.items():
        sub_results = []
        for st in stock_list:
            name = st["name"]
            if name not in xl_stocks or name in seen_names:
                continue
            info = xl_stocks[name]
            r = compute_stock_bulk(info["col"], mat_size, mat_forn, mat_inst)
            if r is None:
                continue
            seen_names.add(name)
            osc = r["latest"]
            pct = pct_from_thresholds(osc, p10, p25, p75, p90)
            g   = grade(osc, p10, p25, p75)
            tr  = trend_str(r["series"])
            total += 1
            if g == "A 완전빈집": cnt_a += 1
            elif g == "B 반빈집":  cnt_b += 1
            sub_results.append({"name": name, "code": info["code"],
                                 "osc": osc, "pct": pct, "grade": g, "trend": tr})

        empties = sorted(
            [r for r in sub_results if r["grade"] in ("A 완전빈집", "B 반빈집")],
            key=lambda x: x["osc"]
        )
        if empties:
            sub_summaries.append((sub, empties))

    # 요약 줄
    if total == 0:
        return header + "xlsm 내 종목 없음\n"

    summary = f"총 {total}종목 | 🔴A:{cnt_a} 🟠B:{cnt_b} 빈집{cnt_a+cnt_b}"
    if cnt_a + cnt_b == 0:
        summary += " (빈집 없음)"
    summary += "\n"

    lines = [header, summary]

    for sub, empties in sub_summaries:
        lines.append(f"\n<b>[{sub}]</b>")
        for r in empties:
            icon = GRADE_ICON[r["grade"]]
            lines.append(
                f"{icon} {r['name']}  "
                f"<code>{r['osc']:+.6f}</code>  "
                f"하위{r['pct']:.0f}%  {r['trend']}"
            )

    msg = "\n".join(lines)
    # Telegram 4096자 제한 — 초과 시 끝에 안내
    if len(msg) > 3900:
        msg = msg[:3890] + "\n...(이하 생략)"
    return msg


# ── main ─────────────────────────────────────────────────────────
def main():
    import win32com.client as win32

    raw_args = sys.argv[1:]
    send_tg  = "--tg" in raw_args
    raw_args = [a for a in raw_args if a != "--tg"]

    # --all 또는 --sector 파싱
    do_all = "--all" in raw_args
    raw_args = [a for a in raw_args if a != "--all"]

    sectors_to_scan: list[str] = []
    if "--sector" in raw_args:
        idx = raw_args.index("--sector")
        i = idx + 1
        while i < len(raw_args) and not raw_args[i].startswith("--"):
            sectors_to_scan.append(raw_args[i])
            i += 1
        raw_args = raw_args[:idx] + raw_args[i:]

    if do_all:
        sectors_to_scan = list(DAILY_SECTORS)

    sector_mode = bool(sectors_to_scan)
    queries = [q.strip() for q in raw_args if q.strip()]

    # ── Excel 열기 ─────────────────────────────────────────────
    xlsm_path = find_xlsm()
    print(f"\n{'━'*56}")
    if sector_mode:
        print(f"  섹터 수급스캔: {', '.join(sectors_to_scan)}")
    else:
        print(f"  수급오실레이터 계산기")
    print(f"  파일: {xlsm_path.name}")
    print(f"{'━'*56}\n")
    print("Excel 열기 중...")

    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.AutomationSecurity = 3
    wb = xl.Workbooks.Open(str(xlsm_path))

    ws_osc  = wb.Sheets("수급오실레이터")
    ws_size = wb.Sheets("시가총액")
    ws_forn = wb.Sheets("외국인매수데이터")
    ws_inst = wb.Sheets("기관매수데이터")

    p90 = ws_osc.Cells(STAT_ROW_P90, STAT_COL).Value2
    p75 = ws_osc.Cells(STAT_ROW_P75, STAT_COL).Value2
    p25 = ws_osc.Cells(STAT_ROW_P25, STAT_COL).Value2
    p10 = ws_osc.Cells(STAT_ROW_P10, STAT_COL).Value2

    print("종목 목록 로딩 중...")
    xl_stocks: dict[str, dict] = {}
    max_col = ws_forn.UsedRange.Columns.Count
    for c in range(2, max_col + 1):
        name = ws_forn.Cells(9, c).Value2
        code = ws_forn.Cells(8, c).Value2
        if name:
            xl_stocks[name] = {
                "col": c,
                "code": str(code).replace("A", "") if code else "",
            }
    print(f"총 {len(xl_stocks)}개 종목 로드 완료\n")

    print("데이터 일괄 로딩 중 (COM 3회)...")
    mat_size, mat_forn, mat_inst = load_bulk(ws_size, ws_forn, ws_inst, max_col)
    wb.Close(False)
    xl.Quit()
    print("Excel 닫힘. 계산 시작...\n")

    # ════════════════════════════════════════════════════════════
    #  섹터 스캔 모드 (--all / --sector X Y)
    # ════════════════════════════════════════════════════════════
    if sector_mode:
        watchlist = load_watchlist()
        tg_messages = []

        for sector in sectors_to_scan:
            if sector not in watchlist:
                print(f"  [SKIP] {sector} — watchlist.json에 없음")
                continue

            sector_data = watchlist[sector]

            # 콘솔 출력
            total_s = sum(len(v) for v in sector_data.values())
            print(f"▶ {sector} ({total_s}종목 처리 중)...")

            msg = make_sector_message(
                sector, sector_data, xl_stocks,
                mat_size, mat_forn, mat_inst,
                p10, p25, p75, p90,
            )
            print(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
            print()

            if send_tg:
                tg_messages.append(msg)

        if send_tg:
            print(f"텔레그램 전송 ({len(tg_messages)}개 메시지)...")
            for msg in tg_messages:
                send_telegram(msg)
        return

    # ════════════════════════════════════════════════════════════
    #  기존 모드 (단일/다수 종목 / 전체 스캔)
    # ════════════════════════════════════════════════════════════
    full_scan = not queries

    if full_scan:
        targets = list(xl_stocks.keys())
        print(f"전체 {len(targets)}개 종목 계산 중...")
    else:
        targets = []
        not_found = []
        for q in queries:
            matched = [n for n in xl_stocks if q in n]
            if matched:
                targets.extend(matched)
            else:
                not_found.append(q)
        seen = set()
        targets = [n for n in targets if not (n in seen or seen.add(n))]
        if not_found:
            print(f"찾지 못한 종목: {', '.join(not_found)}")
        if not targets:
            print("조회할 종목 없음")
            return
        print(f"{len(targets)}개 종목 계산 중...")

    results = []
    for name in targets:
        info = xl_stocks[name]
        r = compute_stock_bulk(info["col"], mat_size, mat_forn, mat_inst)
        if r is None:
            continue
        results.append({
            "name": name, "code": info["code"],
            "osc": r["latest"], "macd": r["macd_latest"],
            "sig": r["signal_latest"], "series": r["series"],
        })

    if not results:
        print("계산 가능한 종목 없음")
        return

    # 백분위/등급
    if full_scan:
        all_sorted = sorted(r["osc"] for r in results)
        n = len(all_sorted)
        p10_c = all_sorted[int(n * 0.10)]
        p25_c = all_sorted[int(n * 0.25)]
        p75_c = all_sorted[int(n * 0.75)]
        p90_c = all_sorted[int(n * 0.90)]
        def get_pct(v):
            return sum(1 for x in all_sorted if x <= v) / n * 100
        for r in results:
            r["pct"]   = get_pct(r["osc"])
            r["grade"] = grade(r["osc"], p10_c, p25_c, p75_c)
        p10, p25, p75, p90 = p10_c, p25_c, p75_c, p90_c
        n_label = n
    else:
        for r in results:
            r["pct"]   = pct_from_thresholds(r["osc"], p10, p25, p75, p90)
            r["grade"] = grade(r["osc"], p10, p25, p75)
        n_label = len(xl_stocks)

    def trend(r):
        return trend_str(r["series"])

    # 콘솔 출력
    if not full_scan and len(results) == 1:
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
        print(f"  [기준값] A≤{p10:.6f}  B≤{p25:.6f}  D>{p75:.6f}")

    elif not full_scan and len(results) <= 20:
        sorted_r = sorted(results, key=lambda x: x["osc"])
        print(f"{'종목':<16} {'코드':<8} {'오실레이터':>12} {'백분위':>8} {'등급':<12} {'방향'}")
        print(f"{'─'*16} {'─'*8} {'─'*12} {'─'*8} {'─'*12} {'─'*10}")
        for r in sorted_r:
            print(f"{r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']:<12} {trend(r)}")
        print(f"\n  [기준값] A≤{p10:.6f}  B≤{p25:.6f}  D>{p75:.6f}")

    else:
        sorted_results = sorted(results, key=lambda x: x["osc"])
        print(f"전체 통계 ({n_label}개)")
        print(f"  A(하위10%)≤{p10:.6f}  B(하위25%)≤{p25:.6f}  D(상위25%)>{p75:.6f}\n")
        top20 = sorted_results[:20]
        print(f"빈집 상위 {len(top20)}:")
        print(f"  {'종목':<16} {'코드':<8} {'오실레이터':>12} {'백분위':>8} {'등급'}")
        for r in top20:
            print(f"  {r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']}")
        bot10 = sorted_results[-10:]
        print(f"\n과매수 상위 {len(bot10)}:")
        for r in bot10:
            print(f"  {r['name']:<16} {r['code']:<8} {r['osc']:>12.6f} 하위{r['pct']:>4.1f}% {r['grade']}")

    # 텔레그램 (기존 모드)
    if send_tg:
        today = date.today().strftime("%Y-%m-%d")
        if not full_scan and len(results) == 1:
            r = results[0]
            msg = (
                f"<b>수급오실레이터 {today}</b>\n\n"
                f"{GRADE_ICON.get(r['grade'], '')} <b>{r['name']}</b> ({r['code']})\n"
                f"오실레이터: <code>{r['osc']:.6f}</code>\n"
                f"등급: {r['grade']}  방향: {trend(r)}\n"
                f"백분위: 하위{r['pct']:.1f}% (전체 {n_label}개)\n"
                f"A≤{p10:.6f}  B≤{p25:.6f}"
            )
        else:
            target_r = sorted(results, key=lambda x: x["osc"])
            if full_scan:
                target_r = target_r[:20]
            lines = [f"<b>수급오실레이터 {today}</b>\n"]
            for r in target_r:
                icon = GRADE_ICON.get(r["grade"], "")
                lines.append(
                    f"{icon} <b>{r['name']}</b>  "
                    f"<code>{r['osc']:.6f}</code>  하위{r['pct']:.1f}%  {trend(r)}"
                )
            lines.append(f"\nA≤{p10:.6f}  B≤{p25:.6f}")
            msg = "\n".join(lines)
        send_telegram(msg)


if __name__ == "__main__":
    main()
