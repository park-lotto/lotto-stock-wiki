#!/usr/bin/env python3
"""
osc_chart.py — 수급오실레이터 차트 이미지 생성 + 텔레그램 전송

사용법:
  python osc_chart.py 한미반도체              ← 3스타일 PNG 생성 (out/charts/)
  python osc_chart.py 한미반도체 --tg         ← bar 스타일 텔레그램 전송
  python osc_chart.py 한미반도체 --style area --tg
  python osc_chart.py 한미반도체 --style heat --tg
  python osc_chart.py 한미반도체 에스티아이 --tg  ← 여러 종목
"""
import sys, json, io
from pathlib import Path
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

from calc_oscillator import (
    find_xlsm, load_watchlist, load_bulk, compute_stock_bulk,
    grade, pct_from_thresholds, trend_str,
    DATA_ROW_START, DATA_ROW_END,
    STAT_ROW_P90, STAT_ROW_P75, STAT_ROW_P25, STAT_ROW_P10, STAT_COL,
    _load_env,
)

# ── 한글 폰트 ─────────────────────────────────────────────────────
plt.rcParams["font.family"]       = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# ── 디자인 토큰 ──────────────────────────────────────────────────
BG     = "#0A0A0A"
CARD   = "#111111"
MINT   = "#00FFD0"
MINT2  = "#00BF9A"
WHITE  = "#FFFFFF"
GRAY   = "#888888"
DGRAY  = "#1E1E1E"
BORDER = "#2A2A2A"
BULL   = "#00FFD0"          # 빈집 (음수)
BEAR   = "#FF6B6B"          # 과매수 (양수)
BULL_A = (0, 1, 0.82, 0.20)
BEAR_A = (1, 0.42, 0.42, 0.20)

OUT_DIR = Path(__file__).parent / "out" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── 영업일 날짜 역산 ─────────────────────────────────────────────
def get_trading_dates(n: int) -> list[date]:
    result, d = [], date.today()
    while len(result) < n:
        if d.weekday() < 5:
            result.append(d)
        d -= timedelta(days=1)
    return list(reversed(result))


# ── 등급 텍스트 ──────────────────────────────────────────────────
GRADE_LABEL = {
    "A 완전빈집": ("🔴 A 완전빈집", MINT),
    "B 반빈집":   ("🟠 B 반빈집",  "#FFB347"),
    "C 정상":     ("⚪ C 정상",    GRAY),
    "D 과매수":   ("🟡 D 과매수",  "#FFD700"),
}


# ════════════════════════════════════════════════════════════════
#  STYLE 1 — BAR 히스토그램 (MACD 스타일)
# ════════════════════════════════════════════════════════════════
def chart_bar(ax, series, dates, thresholds, stock_name, meta):
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend   = trend_str(series)
    gl, gc  = GRADE_LABEL.get(g, (g, GRAY))

    ax.set_facecolor(BG)

    # 바 색상: 음수=민트(빈집), 양수=코랄(과매수)
    colors = [BULL if v <= 0 else BEAR for v in series]
    x = np.arange(len(series))
    bars = ax.bar(x, series, color=colors, width=0.75, zorder=3)

    # 기준선: A/B 임계값
    ax.axhline(p10, color=MINT,  linewidth=1.0, linestyle="--", alpha=0.6, zorder=2)
    ax.axhline(p25, color=MINT2, linewidth=0.8, linestyle=":",  alpha=0.4, zorder=2)
    ax.axhline(0,   color=WHITE, linewidth=0.5,                 alpha=0.25, zorder=2)

    # 빈집존 배경 음영
    y_min = ax.get_ylim()[0] if ax.get_ylim()[0] < p10 else p10 * 1.5
    ax.axhspan(min(p10 * 1.5, min(series) * 1.1), p10, color=MINT, alpha=0.04, zorder=1)

    # x축 날짜 레이블 (5개)
    tick_idx = np.linspace(0, len(dates) - 1, 5, dtype=int)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([dates[i].strftime("%-m/%-d") if sys.platform != "win32"
                         else dates[i].strftime("%m/%d") for i in tick_idx],
                        color=GRAY, fontsize=9)

    ax.tick_params(axis="y", colors=GRAY, labelsize=9)
    ax.set_xlim(-1, len(series))
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter(useMathText=True))
    ax.ticklabel_format(style="sci", axis="y", scilimits=(-3, -3))
    ax.yaxis.get_offset_text().set_color(GRAY)
    ax.yaxis.get_offset_text().set_fontsize(8)

    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.grid(axis="y", color=DGRAY, linewidth=0.5, zorder=0)

    # 헤더 텍스트
    ax.set_title(f"  {stock_name}  수급오실레이터", color=WHITE, fontsize=14,
                 fontweight="bold", loc="left", pad=14)

    # 우측 상단: 등급 + 현재값
    ax.text(0.99, 0.97, gl, transform=ax.transAxes,
            color=gc, fontsize=11, fontweight="bold",
            ha="right", va="top")
    ax.text(0.99, 0.84, f"하위{pct_val:.0f}%  {trend}",
            transform=ax.transAxes, color=GRAY, fontsize=9, ha="right", va="top")

    # 임계값 레이블
    ax.text(len(series) - 0.5, p10 + abs(p10) * 0.08,
            "A기준", color=MINT, fontsize=7.5, alpha=0.7, ha="right")
    ax.text(len(series) - 0.5, p25 + abs(p25) * 0.08,
            "B기준", color=MINT2, fontsize=7.5, alpha=0.55, ha="right")

    # 현재값 callout
    ax.annotate(
        f"{latest:+.4f}",
        xy=(len(series) - 1, latest),
        xytext=(len(series) - 8, latest * 1.4),
        color=gc, fontsize=10, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=gc, lw=1.2),
    )


# ════════════════════════════════════════════════════════════════
#  STYLE 2 — AREA 그라데이션 에어리어
# ════════════════════════════════════════════════════════════════
def chart_area(ax, series, dates, thresholds, stock_name, meta):
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend   = trend_str(series)
    gl, gc  = GRADE_LABEL.get(g, (g, GRAY))

    ax.set_facecolor(BG)
    x = np.arange(len(series))

    # 메인 라인
    ax.plot(x, series, color=MINT, linewidth=1.5, zorder=4)

    # fill: 빈집(음수)와 과매수(양수) 분리 fill
    ax.fill_between(x, series, 0,
                    where=[v <= 0 for v in series],
                    color=BULL, alpha=0.20, zorder=3, label="빈집")
    ax.fill_between(x, series, 0,
                    where=[v > 0 for v in series],
                    color=BEAR, alpha=0.20, zorder=3, label="과매수")

    # 빈집 A/B 존 배경 밴드
    ax.axhspan(min(series) * 1.05, p10, color=MINT, alpha=0.06, zorder=1)
    ax.axhspan(p10, p25,            color=MINT, alpha=0.03, zorder=1)

    # 기준선
    ax.axhline(p10, color=MINT,  linewidth=1.0, linestyle="--", alpha=0.5)
    ax.axhline(p25, color=MINT2, linewidth=0.8, linestyle=":",  alpha=0.35)
    ax.axhline(0,   color=WHITE, linewidth=0.5,                 alpha=0.2)

    # 빈집존 레이블
    ax.text(2, p10 * 0.8, "A 완전빈집", color=MINT, fontsize=7.5, alpha=0.6)
    ax.text(2, p25 * 0.88, "B 반빈집",  color=MINT2, fontsize=7.5, alpha=0.5)

    # 최근값 도트
    ax.scatter([len(series) - 1], [latest], color=gc, s=55, zorder=6)

    # x축
    tick_idx = np.linspace(0, len(dates) - 1, 5, dtype=int)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([dates[i].strftime("%m/%d") for i in tick_idx],
                        color=GRAY, fontsize=9)
    ax.tick_params(axis="y", colors=GRAY, labelsize=9)
    ax.set_xlim(-1, len(series) + 1)
    ax.ticklabel_format(style="sci", axis="y", scilimits=(-3, -3))
    ax.yaxis.get_offset_text().set_color(GRAY)
    ax.yaxis.get_offset_text().set_fontsize(8)

    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.grid(axis="y", color=DGRAY, linewidth=0.5, zorder=0)

    ax.set_title(f"  {stock_name}  수급오실레이터", color=WHITE, fontsize=14,
                 fontweight="bold", loc="left", pad=14)
    ax.text(0.99, 0.97, gl,                    transform=ax.transAxes,
            color=gc, fontsize=11, fontweight="bold", ha="right", va="top")
    ax.text(0.99, 0.84, f"하위{pct_val:.0f}%  {trend}",
            transform=ax.transAxes, color=GRAY, fontsize=9, ha="right", va="top")


# ════════════════════════════════════════════════════════════════
#  STYLE 3 — HEAT 스파크라인 + 열지도
# ════════════════════════════════════════════════════════════════
def chart_heat(fig, gs_row, series, dates, thresholds, stock_name, meta, row_idx=0):
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend   = trend_str(series)
    gl, gc  = GRADE_LABEL.get(g, (g, GRAY))

    # 상단: 스파크라인
    ax_line = fig.add_subplot(gs_row[0])
    ax_heat = fig.add_subplot(gs_row[1])

    ax_line.set_facecolor(BG)
    ax_heat.set_facecolor(BG)

    x = np.arange(len(series))
    ax_line.plot(x, series, color=MINT, linewidth=1.2)
    ax_line.fill_between(x, series, 0,
                          where=[v <= 0 for v in series],
                          color=MINT, alpha=0.15)
    ax_line.fill_between(x, series, 0,
                          where=[v > 0 for v in series],
                          color=BEAR, alpha=0.15)
    ax_line.axhline(p10, color=MINT, linewidth=0.8, linestyle="--", alpha=0.5)
    ax_line.axhline(0,   color=WHITE, linewidth=0.4, alpha=0.2)
    ax_line.set_xlim(0, len(series) - 1)
    ax_line.axis("off")

    # 등급/정보 텍스트
    ax_line.text(0.01, 0.95, stock_name, transform=ax_line.transAxes,
                  color=WHITE, fontsize=13, fontweight="bold", va="top")
    ax_line.text(0.01, 0.58, gl, transform=ax_line.transAxes,
                  color=gc, fontsize=10, va="top")
    ax_line.text(0.01, 0.30, f"하위{pct_val:.0f}%  {trend}",
                  transform=ax_line.transAxes, color=GRAY, fontsize=8, va="top")

    # 열지도: 색상맵 — 음수(빈집)=민트, 양수=코랄
    cmap_colors = [(1, 0.42, 0.42, 1), (0.15, 0.15, 0.15, 1), (0, 1, 0.82, 1)]
    cmap = LinearSegmentedColormap.from_list("osc", cmap_colors, N=256)

    arr = np.array(series).reshape(1, -1)
    vabs = max(abs(min(series)), abs(max(series)))
    ax_heat.imshow(arr, aspect="auto", cmap=cmap, vmin=-vabs, vmax=vabs)
    ax_heat.set_yticks([])
    ax_heat.set_xticks([])

    # 하단 날짜 레이블 (5개)
    tick_idx = np.linspace(0, len(dates) - 1, 5, dtype=int)
    for ti in tick_idx:
        ax_heat.text(ti, 0.8, dates[ti].strftime("%m/%d"),
                      color=GRAY, fontsize=7.5, ha="center", transform=ax_heat.get_xaxis_transform())

    for spine in ax_heat.spines.values():
        spine.set_color(BORDER)

    return ax_line, ax_heat


# ════════════════════════════════════════════════════════════════
#  텔레그램 이미지 전송
# ════════════════════════════════════════════════════════════════
def send_telegram_photo(buf: io.BytesIO, caption: str = ""):
    import urllib.request, uuid
    cfg   = _load_env()
    token = cfg.get("BOT_TOKEN", "")
    chat  = cfg.get("CHAT_ID", "")
    if not token or not chat:
        print("텔레그램 설정 없음 (.env BOT_TOKEN/CHAT_ID)")
        return

    boundary = uuid.uuid4().hex
    buf.seek(0)
    img_data = buf.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="photo"; filename="chart.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read())
    if result.get("ok"):
        print("텔레그램 이미지 전송 완료")
    else:
        print(f"전송 실패: {result}")


# ════════════════════════════════════════════════════════════════
#  단일 종목 차트 생성
# ════════════════════════════════════════════════════════════════
def make_chart(stock_name: str, series: list, thresholds: tuple,
               style: str = "bar") -> io.BytesIO:
    dates = get_trading_dates(len(series))
    meta  = {}

    if style == "heat":
        fig = plt.figure(figsize=(11, 3.2), facecolor=BG)
        import matplotlib.gridspec as gridspec
        gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[3, 1],
                               hspace=0.05, left=0.03, right=0.97,
                               top=0.92, bottom=0.12)
        chart_heat(fig, gs, series, dates, thresholds, stock_name, meta)
        fig.suptitle("수급오실레이터", color=GRAY, fontsize=9, x=0.99, ha="right", y=0.99)
    else:
        fig, ax = plt.subplots(figsize=(11, 4.5), facecolor=BG)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.12)
        if style == "area":
            chart_area(ax, series, dates, thresholds, stock_name, meta)
        else:
            chart_bar(ax, series, dates, thresholds, stock_name, meta)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


# ════════════════════════════════════════════════════════════════
#  Excel 데이터 로딩
# ════════════════════════════════════════════════════════════════
def load_series_from_excel(stock_names: list[str]) -> dict:
    import win32com.client as win32

    xlsm_path = find_xlsm()
    print(f"파일: {xlsm_path.name}")
    print("Excel 열기 중...")

    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.AutomationSecurity = 3
    wb = xl.Workbooks.Open(str(xlsm_path))

    try:
        ws_osc  = wb.Sheets("수급오실레이터")
        ws_size = wb.Sheets("시가총액")
        ws_forn = wb.Sheets("외국인매수데이터")
        ws_inst = wb.Sheets("기관매수데이터")

        p90 = ws_osc.Cells(STAT_ROW_P90, STAT_COL).Value2
        p75 = ws_osc.Cells(STAT_ROW_P75, STAT_COL).Value2
        p25 = ws_osc.Cells(STAT_ROW_P25, STAT_COL).Value2
        p10 = ws_osc.Cells(STAT_ROW_P10, STAT_COL).Value2
        thresholds = (p10, p25, p75, p90)

        print("종목 목록 로딩 중...")
        max_col = ws_forn.UsedRange.Columns.Count
        xl_stocks: dict[str, int] = {}
        for c in range(2, max_col + 1):
            name = ws_forn.Cells(9, c).Value2
            if name:
                xl_stocks[name] = c
        print(f"총 {len(xl_stocks)}개 종목\n")

        print("데이터 일괄 로딩 중...")
        mat_size, mat_forn, mat_inst = load_bulk(ws_size, ws_forn, ws_inst, max_col)

    finally:
        wb.Close(False)
        xl.Quit()

    print("Excel 닫힘. 계산 시작...\n")

    results = {}
    for name in stock_names:
        col = xl_stocks.get(name)
        if not col:
            # 부분 일치 시도
            for k, v in xl_stocks.items():
                if name in k or k in name:
                    col = v
                    break
        if not col:
            print(f"  ❌ {name} — xlsm에서 찾지 못함")
            continue
        res = compute_stock_bulk(col, mat_size, mat_forn, mat_inst)
        if not res:
            print(f"  ❌ {name} — 데이터 부족")
            continue
        print(f"  ✅ {name} — 시리즈 {len(res['series'])}일, 최신값 {res['latest']:+.6f}")
        results[name] = {"series": res["series"], "thresholds": thresholds}

    return results


# ════════════════════════════════════════════════════════════════
#  main
# ════════════════════════════════════════════════════════════════
def main():
    args      = sys.argv[1:]
    send_tg   = "--tg" in args;   args = [a for a in args if a != "--tg"]
    style     = "bar"
    if "--style" in args:
        idx   = args.index("--style")
        style = args[idx + 1] if idx + 1 < len(args) else "bar"
        args  = args[:idx] + args[idx + 2:]

    stock_names = [a for a in args if not a.startswith("--")]
    if not stock_names:
        print("사용법: python osc_chart.py 종목명 [--style bar|area|heat] [--tg]")
        sys.exit(1)

    data = load_series_from_excel(stock_names)
    if not data:
        print("처리 가능한 종목이 없습니다.")
        sys.exit(1)

    for name, d in data.items():
        series     = d["series"]
        thresholds = d["thresholds"]

        if send_tg:
            # 지정 스타일 1개 전송
            buf     = make_chart(name, series, thresholds, style)
            caption = f"📊 {name}  수급오실레이터 ({date.today().strftime('%m/%d')})"
            print(f"  텔레그램 전송 ({style})...")
            send_telegram_photo(buf, caption)
        else:
            # 3스타일 모두 파일 저장
            for s in ["bar", "area", "heat"]:
                buf  = make_chart(name, series, thresholds, s)
                path = OUT_DIR / f"osc_{name}_{s}.png"
                path.write_bytes(buf.read())
                print(f"  저장: {path}")
            print(f"  → out/charts/ 폴더에서 미리보기 후 --style 지정해서 --tg 전송하세요")


if __name__ == "__main__":
    import matplotlib.ticker
    main()
