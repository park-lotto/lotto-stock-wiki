"""
scan_sortino.py — 소라티노 ETF 랭킹 계산 + 텔레그램 전송

사용법:
    python scripts/scan_sortino.py          # 계산 + 출력
    python scripts/scan_sortino.py --tg     # 텔레그램 전송
    python scripts/scan_sortino.py --days 5 # 최근 5일

출력:
    1) Sortino Top 20 (10주선=50일 이상 / 3-6-12M 평균)  ← 이미지와 동일
    2) Mansfield RS ≥ 70 ETF 목록
"""

import sys, argparse, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pandas as pd
    import numpy as np
    import openpyxl
except ImportError as e:
    print(f"pip install pandas numpy openpyxl 필요: {e}")
    sys.exit(1)

ROOT      = Path(__file__).parent.parent
EXCEL_DIR = ROOT / "raw" / "매일 엑셀넣을것"
TODAY     = datetime.today().strftime("%Y-%m-%d")
TODAY_KR  = datetime.today().strftime("%Y년 %m월 %d일")


# ── 파일 찾기 ─────────────────────────────────────────────────

def find_excel(pattern: str) -> Path | None:
    for f in EXCEL_DIR.iterdir():
        if f.name.startswith("~$"): continue
        if pattern in f.name and f.suffix in (".xlsx", ".xlsm"):
            return f
    return None


# ── 데이터 로드 ───────────────────────────────────────────────

def load_etf_data() -> pd.DataFrame:
    path = (find_excel("소라티노ETF상대강도")
            or EXCEL_DIR / "etf상대강도데이터.xlsx"
            if (EXCEL_DIR / "etf상대강도데이터.xlsx").exists()
            else find_excel("etf상대강도데이터"))
    if not path:
        print("❌ 소라티노ETF상대강도 / etf상대강도데이터 파일 없음")
        sys.exit(1)
    print(f"📂 {path.name} 로딩...")
    df = pd.read_excel(str(path), sheet_name="데이터", engine="openpyxl")
    df = df.dropna(subset=["DATE"])
    df["DATE"] = pd.to_datetime(df["DATE"])
    df.set_index("DATE", inplace=True)
    df = df.sort_index()
    print(f"   {len(df)}일 데이터, ETF {len(df.columns)}개")
    return df


# ── Sortino 계산 함수 (태린이아빠 로직 그대로) ───────────────────

def _sortino_from_returns(ret: pd.Series, mar: float = 0.0, ppy: int = 252) -> float:
    ret = ret.dropna()
    if len(ret) < 5:
        return np.nan
    mar_d = (1 + mar) ** (1 / ppy) - 1
    excess = ret - mar_d
    down = excess[excess < 0]
    if len(down) < 5:
        return np.nan
    down_dev = down.std(ddof=1) * np.sqrt(ppy)
    if down_dev == 0 or np.isnan(down_dev):
        return np.nan
    return float(excess.mean() * ppy / down_dev)


def _ma_ok(series: pd.Series, end_idx: int, ma_days: int) -> bool:
    s = series.iloc[:end_idx + 1].dropna()
    if len(s) < ma_days:
        return False
    return bool(s.iloc[-1] >= s.rolling(ma_days).mean().iloc[-1])


def rank_sortino(
    data: pd.DataFrame,
    last_n_days: int = 10,
    ma_filter_days: int = 50,   # 10주선
    top_n: int = 20,
    periods: tuple = (63, 126, 252),  # 3M, 6M, 12M
) -> pd.DataFrame:
    """최근 last_n_days 동안 Sortino Top top_n ETF 랭킹"""
    trading_days = data.dropna(how="all").index[-last_n_days:]
    daily_top = {}

    for day in trading_days:
        end_idx = data.index.get_indexer_for([day])[0]
        scores = {}
        for col in data.columns:
            if not _ma_ok(data[col], end_idx, ma_filter_days):
                continue
            vals = []
            for win in periods:
                s_idx = max(0, end_idx - (win - 1))
                prices = data[col].iloc[s_idx:end_idx + 1].dropna()
                if len(prices) < max(20, int(win * 0.8)):
                    continue
                ret = prices.pct_change(fill_method=None).dropna()
                v = _sortino_from_returns(ret)
                if pd.notna(v):
                    vals.append(v)
            if vals:
                scores[col] = float(np.mean(vals))

        ranked = (pd.Series(scores).sort_values(ascending=False)
                  .head(top_n).index.tolist())
        while len(ranked) < top_n:
            ranked.append(None)
        daily_top[day] = ranked

    return pd.DataFrame.from_dict(
        daily_top, orient="index",
        columns=[f"Top {i+1}" for i in range(top_n)]
    )


# ── Mansfield RS 계산 ─────────────────────────────────────────

def compute_mansfield_rs(etf: pd.Series, kospi: pd.Series, ma: int) -> pd.Series:
    rel = etf / kospi
    ma_s = rel.rolling(window=ma, min_periods=ma).mean()
    return ((rel / ma_s) - 1) * 100

def norm_sigmoid(x, scale=12) -> float:
    return float(100 / (1 + np.exp(-x / scale)))

def calc_mansfield(data: pd.DataFrame) -> pd.DataFrame:
    if "코스피" not in data.columns:
        return pd.DataFrame()
    kospi = data["코스피"].dropna()
    etf_cols = [c for c in data.columns if c != "코스피"]
    rows = []
    for col in etf_cols:
        s = data[col].dropna()
        ci = s.index.intersection(kospi.index)
        if len(ci) < 63:
            continue
        e, k = s.loc[ci], kospi.loc[ci]
        row = {"ETF": col}
        rs_vals, nrs_vals = [], []
        for win in [60, 120, 250]:
            if len(e) >= win:
                rs = compute_mansfield_rs(e, k, win).dropna()
                if not rs.empty:
                    raw = float(rs.iloc[-1])
                    nr  = norm_sigmoid(raw)
                    row[f"RS_{win}d"]    = round(raw, 2)
                    row[f"Norm_{win}d"]  = round(nr, 2)
                    rs_vals.append(raw); nrs_vals.append(nr)
        if rs_vals:
            row["RS_avg"]   = round(sum(rs_vals)/len(rs_vals), 2)
            row["Norm_avg"] = round(norm_sigmoid(row["RS_avg"]), 2)
            rows.append(row)
    return pd.DataFrame(rows).sort_values("Norm_avg", ascending=False)


# ── 텔레그램 ──────────────────────────────────────────────────

def send_tg(text: str):
    env = {}
    ep = ROOT / ".env"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    token, chat_id = env.get("BOT_TOKEN",""), env.get("CHAT_ID","")
    if not token or not chat_id:
        print("  ⚠️  .env BOT_TOKEN/CHAT_ID 없음"); return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": "true"
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as r:
                res = json.loads(r.read())
                if res.get("ok"):
                    print("  ✅ 텔레그램 발송")
                else:
                    print(f"  ❌ {res}")
        except Exception as e:
            print(f"  ❌ 발송 실패: {e}")


def fetch_etf_holdings(etf_name: str) -> str:
    """ETF 구성종목 상위 5개를 웹서치로 가져와 1줄 요약."""
    import urllib.request, urllib.parse, json as _json
    env = {}
    ep = ROOT / ".env"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    api_key = env.get("BRAVE_API_KEY") or env.get("SEARCH_API_KEY", "")
    if not api_key:
        return ""

    query = urllib.parse.quote(f"{etf_name} ETF 구성종목 상위 비중 2026")
    url = f"https://api.search.brave.com/res/v1/web/search?q={query}&count=3"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = _json.loads(r.read())
        snippets = [item.get("description", "") for item in data.get("web", {}).get("results", [])[:2]]
        return " / ".join(s[:80] for s in snippets if s)
    except Exception:
        return ""


def build_tg_message(sortino_df: pd.DataFrame, rs_df: pd.DataFrame, with_holdings: bool = False) -> str:
    lines = [
        f"📊 <b>소라티노 ETF 랭킹</b> — {TODAY_KR}",
        f"<i>Sortino Top 20 (10주선=50일↑ / 3-6-12M 평균)</i>",
        "",
    ]

    # 최신일 Top 10
    last_day = sortino_df.index[-1]
    lines.append(f"<b>▶ {str(last_day)[:10]} Sortino Top 10</b>")
    for i in range(10):
        etf = sortino_df.loc[last_day, f"Top {i+1}"]
        if etf:
            line = f"  {i+1:2d}. {etf}"
            if with_holdings:
                holdings = fetch_etf_holdings(etf)
                if holdings:
                    line += f"\n      └ {holdings}"
            lines.append(line)
    lines.append("")

    # Mansfield RS ≥ 70
    rs_filtered = rs_df[rs_df["Norm_avg"] >= 70] if not rs_df.empty else rs_df
    if not rs_filtered.empty:
        lines.append(f"<b>▶ Mansfield RS ≥ 70 ({len(rs_filtered)}개)</b>")
        for _, row in rs_filtered.iterrows():
            lines.append(f"  • {row['ETF']}  <code>{row['Norm_avg']:.1f}</code>")

    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tg",       action="store_true")
    ap.add_argument("--holdings", action="store_true", help="ETF 구성종목 서칭 포함")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--ma",   type=int, default=50, help="MA 필터 (기본 50=10주선)")
    args = ap.parse_args()

    df = load_etf_data()

    # 코스피 제외한 ETF 데이터
    etf_data = df.drop(columns=["코스피"], errors="ignore")

    print(f"\n⏳ Sortino Top 20 계산 중 (최근 {args.days}일, MA{args.ma})...")
    sortino_df = rank_sortino(etf_data, last_n_days=args.days, ma_filter_days=args.ma)

    print(f"\n⏳ Mansfield RS 계산 중...")
    rs_df = calc_mansfield(df)

    # ── 출력 ──
    print(f"\n{'='*60}")
    print(f"📊 소라티노 Sortino Top 20 (MA{args.ma} 이상 / 3-6-12M 평균)")
    print(f"{'='*60}")
    print(sortino_df.to_string())

    print(f"\n{'='*60}")
    print("📈 Mansfield RS Top (Norm_avg 내림차순)")
    print(f"{'='*60}")
    if not rs_df.empty:
        top_rs = rs_df.head(10)[["ETF","RS_avg","Norm_avg"]]
        print(top_rs.to_string(index=False))

    filtered = rs_df[rs_df["Norm_avg"] >= 70] if not rs_df.empty else rs_df
    print(f"\n  Norm_avg ≥ 70: {len(filtered)}개")
    if not filtered.empty:
        for _, row in filtered.iterrows():
            print(f"    • {row['ETF']}  RS_avg={row['RS_avg']:+.1f}  Norm={row['Norm_avg']:.1f}")

    if args.tg:
        msg = build_tg_message(sortino_df, rs_df, with_holdings=args.holdings)
        print("\n텔레그램 발송 중...")
        send_tg(msg)


if __name__ == "__main__":
    main()
