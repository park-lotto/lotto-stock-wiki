#!/usr/bin/env python3
"""
osc_chart2.py — 창의적 수급오실레이터 시각화 4종

사용법:
  python osc_chart2.py 한미반도체                    ← 4스타일 PNG 저장
  python osc_chart2.py 한미반도체 --style gauge --tg
  python osc_chart2.py 한미반도체 --style tank  --tg
  python osc_chart2.py 한미반도체 --style cal   --tg
  python osc_chart2.py 한미반도체 --style card  --tg
  python osc_chart2.py 한미반도체 --all --tg         ← 4개 모두 전송
"""
import sys, json, io, uuid
from pathlib import Path
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Arc, Circle
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.gridspec as gridspec
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

plt.rcParams["font.family"]        = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# ── 디자인 토큰 ─────────────────────────────────────────────────
BG      = "#0A0A0A"
CARD    = "#131313"
CARD2   = "#1A1A1A"
MINT    = "#00FFD0"
MINT2   = "#00BF9A"
MINT3   = "#004D3D"
WHITE   = "#FFFFFF"
GRAY    = "#888888"
DGRAY   = "#222222"
BORDER  = "#2A2A2A"
BEAR    = "#FF6B6B"
BEAR2   = "#FF3030"

# chart_card 전용 — 프리미엄 네이비 팔레트
_BG_NAV   = "#0A0C1E"
_CARD_NAV = "#0F1228"
_HEAD_NAV = "#070912"
_LINE_NAV = "#1B1F3A"
_SUB_NAV  = "#6B6E8A"

GRADE_COLOR = {
    "A 완전빈집": MINT,
    "B 반빈집":   "#60EEC0",
    "C 정상":     GRAY,
    "D 과매수":   BEAR,
}
GRADE_KOR = {
    "A 완전빈집": ("A", "완전빈집"),
    "B 반빈집":   ("B", "반빈집"),
    "C 정상":     ("C", "정상"),
    "D 과매수":   ("D", "과매수"),
}

TREND_NATURAL = {
    "↑ 재진입":   "외인·기관 재진입중",
    "↓ 빈집심화": "외인·기관 여전히 비우는중",
    "→ 횡보":     "외인·기관 횡보중",
}

def make_summary(g: str, trend: str, pct_val: float) -> list:
    """Returns list of (icon, text, icon_color) tuples — 3 lines."""
    M, W, B, G = MINT, WHITE, BEAR, GRAY
    GR = "#60EEC0"
    if g == "A 완전빈집":
        if "재진입" in trend:
            return [("●", "완전빈집 → 재진입 신호 포착", M),
                    ("▶", "이탈 극단 후 신규 수급 유입 감지", W),
                    ("◆", "테마 재점화 시 탄력 극대화 예상", M)]
        if "심화" in trend:
            return [("●", "완전빈집 — 이탈 가속 진행 중", B),
                    ("▶", "외인·기관 지속 매도세 진행", W),
                    ("◆", "촉매 확인 후 진입 대기 유리", G)]
        return [("●", "완전빈집 구간 — 횡보 유지 중", M),
                ("▶", "수급 이탈 후 정체 상태 지속", W),
                ("◆", "추세 전환 촉매 대기 중", G)]
    if g == "B 반빈집":
        if "재진입" in trend:
            return [("●", "반빈집 → 재진입 시작 감지", GR),
                    ("▶", "수급 유입 초기 신호 확인 중", W),
                    ("◆", "완전빈집 확인 후 진입 검토", GR)]
        if "심화" in trend:
            return [("●", "반빈집 — 이탈 진행 중", B),
                    ("▶", "수급 이탈 지속, 빈집 심화 가능", W),
                    ("◆", "완전빈집 도달 시 진입 기회", G)]
        return [("●", "반빈집 구간 — 횡보 중", GR),
                ("▶", "수급 방향 미결정 구간", W),
                ("◆", "추가 이탈 또는 반등 신호 주시", G)]
    if g == "C 정상":
        if "재진입" in trend:
            return [("●", "정상 구간 — 수급 유입 중", G),
                    ("▶", "외인·기관 점진적 진입 신호", W),
                    ("◆", "빈집 아님 — 추격 부담 있음", G)]
        if "심화" in trend:
            return [("●", "정상 구간 — 수급 이탈 중", B),
                    ("▶", "빈집 구간 진입 가능성 모니터링", W),
                    ("◆", "이탈 지속 시 매수 기회 접근", G)]
        return [("●", "정상 수급 구간 — 균형 상태", G),
                ("▶", "외인·기관 진출입 균형 유지", W),
                ("◆", "빈집 신호 없음 — 대기 유지", G)]
    if "재진입" in trend:
        return [("●", "과매수 — 수급 추가 유입 중", B),
                ("▶", "이미 많이 들어와 있는 상태", W),
                ("◆", "추격 부담 높음 — 신중 접근", B)]
    if "심화" in trend:
        return [("●", "과매수 — 이탈 시작", G),
                ("▶", "수급 과열 해소 진행 중", W),
                ("◆", "빈집 구간 도달까지 대기 유리", G)]
    return [("●", "과매수 — 수급 유지 중", B),
            ("▶", "외인·기관 이미 진입한 상태", W),
            ("◆", "신규 매수 탄력 제한적", G)]


OUT_DIR = Path(__file__).parent / "out" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_trading_dates(n: int) -> list[date]:
    result, d = [], date.today()
    while len(result) < n:
        if d.weekday() < 5:
            result.append(d)
        d -= timedelta(days=1)
    return list(reversed(result))


# ════════════════════════════════════════════════════════════════
# STYLE 1 — GAUGE  속도계 게이지
# ════════════════════════════════════════════════════════════════
def chart_gauge(series, thresholds, stock_name) -> io.BytesIO:
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend   = trend_str(series)
    gc      = GRADE_COLOR.get(g, GRAY)
    gl, gs  = GRADE_KOR.get(g, (g, ""))

    fig, ax = plt.subplots(figsize=(7, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.axis("off")

    # ── 게이지 아크 (A→B→C→D 4개 존) ─────────────────────────
    #   pct_val=0 → 왼쪽(180°) = 완전빈집
    #   pct_val=100 → 오른쪽(0°) = 과매수
    zone_defs = [
        (0,  10, MINT,    "A"),
        (10, 25, "#50DDB0","B"),
        (25, 75, "#2A2A2A",""),
        (75, 90, "#FF9975",""),
        (90,100, BEAR,    "D"),
    ]
    R_OUT, R_IN = 1.0, 0.58

    for (s_pct, e_pct, color, lbl) in zone_defs:
        a1 = np.radians(180 - s_pct * 1.8)
        a2 = np.radians(180 - e_pct * 1.8)
        th = np.linspace(a1, a2, 80)
        xs = np.concatenate([np.cos(th)*R_OUT, np.cos(th[::-1])*R_IN])
        ys = np.concatenate([np.sin(th)*R_OUT, np.sin(th[::-1])*R_IN])
        ax.fill(xs, ys, color=color, zorder=2, linewidth=0)

    # 존 구분선
    for boundary_pct in [10, 25, 75, 90]:
        ba = np.radians(180 - boundary_pct * 1.8)
        ax.plot([np.cos(ba)*R_IN, np.cos(ba)*R_OUT],
                [np.sin(ba)*R_IN, np.sin(ba)*R_OUT],
                color=BG, linewidth=1.5, zorder=3)

    # 눈금 텍스트
    for pct_mark, label in [(5, "A"), (17, "B"), (50, "C"), (85, ""), (95, "D")]:
        ma = np.radians(180 - pct_mark * 1.8)
        r_text = 1.15
        ax.text(np.cos(ma)*r_text, np.sin(ma)*r_text, label,
                ha="center", va="center", color=WHITE, fontsize=9, fontweight="bold", zorder=4)

    # 바늘
    needle_a  = np.radians(180 - pct_val * 1.8)
    needle_len = 0.85
    nx, ny = np.cos(needle_a)*needle_len, np.sin(needle_a)*needle_len
    ax.annotate("", xy=(nx, ny), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color=WHITE,
                                lw=2.5, mutation_scale=12), zorder=6)

    # 중심 원
    center = Circle((0, 0), 0.07, color=WHITE, zorder=7)
    ax.add_patch(center)

    # 중앙 하단 수치
    ax.text(0, -0.15, f"하위 {pct_val:.0f}%", ha="center", va="center",
            color=gc, fontsize=15, fontweight="bold", zorder=8)

    # 제목 / 등급 / 트렌드
    ax.text(0,  1.30, stock_name, ha="center", color=WHITE,  fontsize=16, fontweight="bold")
    ax.text(0,  1.14, f"{gl}  {gs}",  ha="center", color=gc, fontsize=13)
    trend_c = MINT if "재진입" in trend else (BEAR if "심화" in trend else GRAY)
    ax.text(0, -0.32, trend,     ha="center", color=trend_c, fontsize=11)

    # 좌우 레이블
    ax.text(-1.18, 0.05, "빈집", ha="right", color=MINT, fontsize=10, fontweight="bold")
    ax.text( 1.18, 0.05, "과매수", ha="left", color=BEAR, fontsize=10, fontweight="bold")

    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-0.5, 1.5)
    fig.tight_layout(pad=0.5)

    return _to_buf(fig)


# ════════════════════════════════════════════════════════════════
# STYLE 2 — TANK  욕조 수위계
# ════════════════════════════════════════════════════════════════
def chart_tank(series, thresholds, stock_name) -> io.BytesIO:
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend   = trend_str(series)
    gc      = GRADE_COLOR.get(g, GRAY)
    gl, gs  = GRADE_KOR.get(g, (g, ""))

    fig = plt.figure(figsize=(7, 6), facecolor=BG)
    ax  = fig.add_axes([0.05, 0.08, 0.90, 0.84])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    # ── 탱크 외곽 ──────────────────────────────────────────────
    tx, ty, tw, th_tank = 2.5, 0.8, 5.0, 7.5
    tank_rect = FancyBboxPatch((tx, ty), tw, th_tank,
                                boxstyle="round,pad=0.1",
                                linewidth=2, edgecolor=BORDER,
                                facecolor="#0D0D0D", zorder=2)
    ax.add_patch(tank_rect)

    # ── 수위 fill (아래→위, 빈집=바닥, 과매수=가득) ────────────
    fill_ratio = pct_val / 100          # 0(빈집)~1(과매수)
    fill_h     = th_tank * fill_ratio
    fill_y     = ty

    # 색상: 빈집=민트, 중간=어두운, 과매수=코랄
    if fill_ratio < 0.25:
        fill_col = MINT
    elif fill_ratio < 0.5:
        fill_col = "#00886A"
    elif fill_ratio < 0.75:
        fill_col = "#884444"
    else:
        fill_col = BEAR

    if fill_h > 0.05:
        fill_rect = FancyBboxPatch((tx + 0.08, fill_y + 0.08),
                                    tw - 0.16, fill_h - 0.08,
                                    boxstyle="round,pad=0.05",
                                    linewidth=0,
                                    facecolor=fill_col, alpha=0.75, zorder=3)
        ax.add_patch(fill_rect)

        # 수면 파형 (사인 곡선)
        wx = np.linspace(tx + 0.1, tx + tw - 0.1, 200)
        wave_y = fill_y + fill_h + 0.08 * np.sin((wx - tx) * 5)
        ax.plot(wx, wave_y, color=fill_col, linewidth=1.5, alpha=0.9, zorder=4)
        ax.fill_between(wx, wave_y, fill_y + fill_h,
                         color=fill_col, alpha=0.3, zorder=3)

    # ── A/B 임계 수위 표시선 ────────────────────────────────────
    p10_h = th_tank * 0.10 + ty
    p25_h = th_tank * 0.25 + ty
    for line_y, label, lc in [(p10_h, "A기준", MINT), (p25_h, "B기준", "#60EEC0")]:
        ax.plot([tx, tx + tw], [line_y, line_y],
                color=lc, linewidth=1.0, linestyle="--", alpha=0.5, zorder=5)
        ax.text(tx + tw + 0.15, line_y, label,
                color=lc, fontsize=8.5, va="center", alpha=0.7)

    # ── 눈금 (왼쪽) ──────────────────────────────────────────────
    for tick_pct in [0, 25, 50, 75, 100]:
        tick_y = ty + th_tank * tick_pct / 100
        ax.plot([tx - 0.2, tx], [tick_y, tick_y], color=BORDER, linewidth=1)
        ax.text(tx - 0.35, tick_y,
                "빈집" if tick_pct == 0 else ("가득" if tick_pct == 100 else f"{tick_pct}%"),
                ha="right", va="center", color=GRAY, fontsize=8)

    # ── 텍스트 정보 ──────────────────────────────────────────────
    # 종목명
    ax.text(5.0, 9.5, stock_name, ha="center", va="top",
            color=WHITE, fontsize=17, fontweight="bold")

    # 등급 배지 (탱크 우측)
    ax.text(8.8, 5.5, gl,  ha="center", color=gc, fontsize=36, fontweight="bold", va="center")
    ax.text(8.8, 4.5, gs,  ha="center", color=gc, fontsize=10, va="center")
    ax.text(8.8, 3.7, f"하위{pct_val:.0f}%", ha="center", color=GRAY, fontsize=9, va="center")

    # 트렌드 화살표 (탱크 아래)
    trend_c = MINT if "재진입" in trend else (BEAR if "심화" in trend else GRAY)
    arrow_sym = "↑" if "재진입" in trend else ("↓" if "심화" in trend else "→")
    trend_lbl = trend.replace("↑ ", "").replace("↓ ", "").replace("→ ", "")
    ax.text(5.0, 0.25, f"{arrow_sym}  {trend_lbl}",
            ha="center", color=trend_c, fontsize=13, fontweight="bold")

    # 날짜
    ax.text(9.8, 0.15, date.today().strftime("%m/%d"),
            ha="right", color=GRAY, fontsize=9)

    fig.tight_layout(pad=0.3)
    return _to_buf(fig)


# ════════════════════════════════════════════════════════════════
# STYLE 3 — CALENDAR  달력 히트맵
# ════════════════════════════════════════════════════════════════
def chart_calendar(series, thresholds, stock_name) -> io.BytesIO:
    p10, p25, p75, p90 = thresholds
    latest  = series[-1]
    g       = grade(latest, p10, p25, p75)
    pct_val = pct_from_thresholds(latest, p10, p25, p75, p90)
    gc      = GRADE_COLOR.get(g, GRAY)
    dates   = get_trading_dates(len(series))

    # 색상맵: 민트(빈집/음수) → 회색(중립) → 코랄(과매수/양수)
    cmap = LinearSegmentedColormap.from_list(
        "osc", [(0, 1, 0.82), (0.1, 0.1, 0.1), (1, 0.42, 0.42)], N=256
    )
    vabs = max(abs(min(series)), abs(max(series)), 1e-9)

    # 주별 그룹핑 (월요일 기준)
    weeks: list[list[tuple]] = []
    week: list[tuple] = []
    for d, v in zip(dates, series):
        if d.weekday() == 0 and week:
            weeks.append(week)
            week = []
        week.append((d, v))
    if week:
        weeks.append(week)

    n_weeks = len(weeks)
    fig, ax  = plt.subplots(figsize=(max(10, n_weeks * 0.62 + 2), 5.5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    cell_w, cell_h = 0.85, 0.85
    gap            = 0.12
    day_labels     = ["월", "화", "수", "목", "금"]

    # 요일 레이블 (y축 왼쪽)
    for di, dl in enumerate(day_labels):
        ax.text(-0.6, -(di * (cell_h + gap)), dl,
                ha="right", va="center", color=GRAY, fontsize=9)

    month_marked: set[int] = set()

    for wi, wk in enumerate(weeks):
        for (d, v) in wk:
            di = d.weekday()   # 0=월 ~ 4=금
            cx = wi * (cell_w + gap)
            cy = -(di * (cell_h + gap))
            norm_v = (v + vabs) / (2 * vabs)
            color  = cmap(norm_v)

            # 셀
            rect = FancyBboxPatch(
                (cx, cy - cell_h * 0.5), cell_w, cell_h,
                boxstyle="round,pad=0.04",
                facecolor=color, edgecolor="none", zorder=2
            )
            ax.add_patch(rect)

            # 오늘 강조
            if d == date.today():
                hl = FancyBboxPatch(
                    (cx, cy - cell_h * 0.5), cell_w, cell_h,
                    boxstyle="round,pad=0.04",
                    facecolor="none", edgecolor=WHITE, linewidth=2, zorder=3
                )
                ax.add_patch(hl)

            # 날짜 숫자
            ax.text(cx + cell_w * 0.5, cy, str(d.day),
                    ha="center", va="center", color=WHITE, fontsize=7.5,
                    alpha=0.85, zorder=4)

            # 월 레이블 (주의 첫 번째 날이 새로운 월이면)
            if d.month not in month_marked and di == 0:
                ax.text(cx + cell_w * 0.5, 0.72,
                        f"{d.month}월", ha="center", color=GRAY, fontsize=8.5)
                month_marked.add(d.month)

    # 범례
    legend_x = n_weeks * (cell_w + gap) + 0.3
    ax.text(legend_x, 0.4, "빈집", color=MINT, fontsize=9, fontweight="bold")
    ax.text(legend_x, 0.4 - (cell_h + gap) * 2.5, "중립", color=GRAY, fontsize=9)
    ax.text(legend_x, -(di * (cell_h + gap)) - 0.1, "과매수", color=BEAR, fontsize=9)

    # 제목 + 등급
    ax.set_title(f"{stock_name}  수급오실레이터 달력",
                  color=WHITE, fontsize=14, fontweight="bold",
                  loc="left", pad=18)
    ax.text(1.0, 1.04, f"{g}  하위{pct_val:.0f}%",
            transform=ax.transAxes, ha="right", color=gc, fontsize=11, fontweight="bold")

    max_x = n_weeks * (cell_w + gap) + 0.6
    ax.set_xlim(-1.2, max_x)
    ax.set_ylim(-(4 * (cell_h + gap)) - 0.5, 1.0)
    fig.tight_layout(pad=0.5)
    return _to_buf(fig)


# ════════════════════════════════════════════════════════════════
# STYLE 4 — CARD  프리미엄 스코어카드 (정사각형 6×6)
# ════════════════════════════════════════════════════════════════
INSIGHT_COPY = {
    ("A 완전빈집", "재진입"): ("완전빈집 → 재진입 시작",  "외인·기관 이탈 극단, 신규 유입 감지"),
    ("A 완전빈집", "심화"):   ("완전빈집 — 이탈 가속",    "촉매 확인 후 진입 대기 유리"),
    ("A 완전빈집", "횡보"):   ("완전빈집 — 횡보 유지",    "추세 전환 촉매 대기 중"),
    ("B 반빈집",   "재진입"): ("반빈집 → 재진입 감지",    "수급 유입 초기 신호 포착"),
    ("B 반빈집",   "심화"):   ("반빈집 — 이탈 진행 중",   "빈집 심화 가능, 완전빈집 모니터링"),
    ("B 반빈집",   "횡보"):   ("반빈집 — 횡보 중",        "수급 방향 미결정, 신호 대기"),
    ("C 정상",     "재진입"): ("정상 → 수급 유입 중",     "추격 부담 있음, 빈집 아님"),
    ("C 정상",     "심화"):   ("정상 → 이탈 시작",        "빈집 구간 접근, 모니터링"),
    ("C 정상",     "횡보"):   ("정상 수급 — 균형",        "빈집 신호 없음, 대기"),
    ("D 과매수",   "재진입"): ("과매수 — 추가 유입 중",   "추격 부담 높음, 신중 접근"),
    ("D 과매수",   "심화"):   ("과매수 → 이탈 시작",      "수급 과열 해소, 빈집 대기"),
    ("D 과매수",   "횡보"):   ("과매수 — 수급 유지",      "신규 매수 탄력 제한적"),
}

def _trend_key(trend: str) -> str:
    if "재진입" in trend: return "재진입"
    if "심화"   in trend: return "심화"
    return "횡보"


def chart_card(series, thresholds, stock_name) -> io.BytesIO:
    p10, p25, p75, p90 = thresholds
    latest    = series[-1]
    g         = grade(latest, p10, p25, p75)
    pct_val   = pct_from_thresholds(latest, p10, p25, p75, p90)
    trend     = trend_str(series)
    gc        = GRADE_COLOR.get(g, GRAY)
    trend_c   = MINT if "재진입" in trend else (BEAR if "심화" in trend else GRAY)
    arrow_ch  = "▲" if "재진입" in trend else ("▼" if "심화" in trend else "▶")
    trend_nat = TREND_NATURAL.get(trend, trend)
    headline, subtitle = INSIGHT_COPY.get((g, _trend_key(trend)), ("—", "—"))

    # ── 정사각형 6×6 피겨 ─────────────────────────────────────
    fig = plt.figure(figsize=(6, 6), facecolor=_BG_NAV)

    # 스파크라인 axes — 하단 27%, 배경으로 깔기
    ax_s = fig.add_axes([0.0, 0.0, 1.0, 0.27])
    ax_s.set_facecolor(_CARD_NAV)
    ax_s.axis("off")

    # 메인 컨텐츠 axes — 상단 73%
    ax = fig.add_axes([0.0, 0.27, 1.0, 0.73])
    ax.set_facecolor(_BG_NAV)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── 스파크라인 (배경으로 깔기) ────────────────────────────
    sx = np.arange(len(series))
    ax_s.plot(sx, series, color=gc, linewidth=2.0, zorder=3)
    ax_s.fill_between(sx, series, min(series),
                       color=gc, alpha=0.14, zorder=2)
    ax_s.axhline(p10, color=gc, linewidth=0.8, linestyle="--", alpha=0.28)
    ax_s.axhline(0,   color=WHITE, linewidth=0.4, alpha=0.08)
    ax_s.scatter([len(series)-1], [latest], color=gc, s=50, zorder=5)
    ax_s.set_xlim(0, len(series)-1)

    # 화살표 (우상단)
    ax_s.text(0.97, 0.88, arrow_ch, transform=ax_s.transAxes,
               ha="right", va="top", color=trend_c,
               fontsize=24, fontweight="bold", zorder=6)

    # 날짜 레이블
    dates_arr = get_trading_dates(len(series))
    ax_s.text(0.03, 0.07, dates_arr[0].strftime("%m/%d"),
               transform=ax_s.transAxes, color=_SUB_NAV, fontsize=7.5)
    ax_s.text(0.97, 0.07, dates_arr[-1].strftime("%m/%d"),
               transform=ax_s.transAxes, ha="right", color=_SUB_NAV, fontsize=7.5)

    # ── 헤더 (STOCK BRAIN 로고) ──────────────────────────────
    ax.add_patch(patches.Rectangle(
        (0, 0.89), 1, 0.11, transform=ax.transAxes,
        facecolor=_HEAD_NAV, zorder=3
    ))
    ax.add_patch(patches.Rectangle(
        (0, 0.884), 1, 0.007, transform=ax.transAxes,
        facecolor=gc, zorder=4
    ))
    ax.text(0.06, 0.941, "◈  STOCK BRAIN",
             transform=ax.transAxes, ha="left", va="center",
             color=MINT, fontsize=10, fontweight="bold", zorder=5)
    ax.text(0.94, 0.941, date.today().strftime("%Y.%m.%d"),
             transform=ax.transAxes, ha="right", va="center",
             color=_SUB_NAV, fontsize=8.5, zorder=5)

    # ── 종목명 ───────────────────────────────────────────────
    ax.text(0.5, 0.765, stock_name,
             transform=ax.transAxes, ha="center", va="center",
             color=WHITE, fontsize=30, fontweight="bold", zorder=5)

    # ── 구분선 ───────────────────────────────────────────────
    ax.plot([0.06, 0.94], [0.648, 0.648], color=_LINE_NAV, linewidth=0.8,
             transform=ax.transAxes)

    # ── 수급 인사이트 (한 문장 큰 글씨 + 서브타이틀) ─────────
    ax.text(0.5, 0.557, headline,
             transform=ax.transAxes, ha="center", va="center",
             color=gc, fontsize=20, fontweight="bold", zorder=5)
    ax.text(0.5, 0.466, subtitle,
             transform=ax.transAxes, ha="center", va="center",
             color=BEAR, fontsize=11, alpha=0.92, zorder=5)

    # ── 구분선 ───────────────────────────────────────────────
    ax.plot([0.06, 0.94], [0.385, 0.385], color=_LINE_NAV, linewidth=0.8,
             transform=ax.transAxes)

    # ── 수급위치 | 수급방향 (2열) ─────────────────────────────
    ax.plot([0.5, 0.5], [0.150, 0.365], color=_LINE_NAV, linewidth=0.8,
             transform=ax.transAxes)

    ax.text(0.25, 0.322, "수급위치",
             transform=ax.transAxes, ha="center", va="center",
             color=_SUB_NAV, fontsize=9, zorder=5)
    ax.text(0.25, 0.210, f"하위  {pct_val:.0f}%",
             transform=ax.transAxes, ha="center", va="center",
             color=WHITE, fontsize=21, fontweight="bold", zorder=5)

    ax.text(0.75, 0.322, "수급방향",
             transform=ax.transAxes, ha="center", va="center",
             color=_SUB_NAV, fontsize=9, zorder=5)
    ax.text(0.75, 0.210, trend_nat,
             transform=ax.transAxes, ha="center", va="center",
             color=trend_c, fontsize=13, fontweight="bold", zorder=5)

    # ── 하단 경계 구분선 ──────────────────────────────────────
    ax.plot([0.0, 1.0], [0.080, 0.080], color=_LINE_NAV, linewidth=0.8,
             transform=ax.transAxes)

    return _to_buf(fig)


# ════════════════════════════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════════════════════════════
def _to_buf(fig) -> io.BytesIO:
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


def send_telegram_photo(buf: io.BytesIO, caption: str = ""):
    cfg   = _load_env()
    token = cfg.get("BOT_TOKEN", "")
    chat  = cfg.get("CHAT_ID", "")
    if not token or not chat:
        print("텔레그램 설정 없음"); return

    import urllib.request
    boundary = uuid.uuid4().hex
    buf.seek(0)
    img_data = buf.read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"chart.png\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        r = json.loads(resp.read())
    print("전송 완료" if r.get("ok") else f"전송 실패: {r}")


# ════════════════════════════════════════════════════════════════
# Excel 데이터 로딩
# ════════════════════════════════════════════════════════════════
def load_series(stock_names: list[str]) -> dict:
    import win32com.client as win32
    xlsm_path = find_xlsm()
    print(f"파일: {xlsm_path.name}")
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
        max_col = ws_forn.UsedRange.Columns.Count
        xl_stocks = {}
        for c in range(2, max_col + 1):
            name = ws_forn.Cells(9, c).Value2
            if name:
                xl_stocks[name] = c
        mat_size, mat_forn, mat_inst = load_bulk(ws_size, ws_forn, ws_inst, max_col)
    finally:
        wb.Close(False); xl.Quit()

    results = {}
    for name in stock_names:
        col = xl_stocks.get(name)
        if not col:
            for k, v in xl_stocks.items():
                if name in k:
                    col = v; break
        if not col:
            print(f"  X {name} — 찾을 수 없음"); continue
        res = compute_stock_bulk(col, mat_size, mat_forn, mat_inst)
        if not res:
            print(f"  X {name} — 데이터 부족"); continue
        results[name] = {"series": res["series"], "thresholds": (p10, p25, p75, p90)}
        print(f"  OK {name}  최신값 {res['latest']:+.6f}")
    return results


STYLE_FUNCS = {
    "gauge": chart_gauge,
    "tank":  chart_tank,
    "cal":   chart_calendar,
    "card":  chart_card,
}


# ════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════
def main():
    args    = sys.argv[1:]
    send_tg = "--tg"  in args; args = [a for a in args if a != "--tg"]
    do_all  = "--all" in args; args = [a for a in args if a != "--all"]

    style = "gauge"
    if "--style" in args:
        idx   = args.index("--style")
        style = args[idx+1] if idx+1 < len(args) else "gauge"
        args  = args[:idx] + args[idx+2:]

    stocks = [a for a in args if not a.startswith("--")]
    if not stocks:
        print("사용법: python osc_chart2.py 종목명 [--style gauge|tank|cal|card] [--all] [--tg]")
        sys.exit(1)

    data = load_series(stocks)
    if not data:
        sys.exit(1)

    styles_to_run = list(STYLE_FUNCS.keys()) if do_all else [style]

    for name, d in data.items():
        series     = d["series"]
        thresholds = d["thresholds"]
        today_str  = date.today().strftime("%m/%d")

        for s in styles_to_run:
            fn  = STYLE_FUNCS[s]
            buf = fn(series, thresholds, name)

            if send_tg:
                caption = f"📊 {name}  {s.upper()}  ({today_str})"
                print(f"  텔레그램 전송 ({s})...")
                send_telegram_photo(buf, caption)
            else:
                path = OUT_DIR / f"osc2_{name}_{s}.png"
                path.write_bytes(buf.read())
                print(f"  저장: {path.name}")


if __name__ == "__main__":
    main()
