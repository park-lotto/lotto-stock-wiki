"""
check_투경_해제.py — 투자경고 종목 해제 조건 판단 → 다음날 시가베팅 알림

실행:
    python scripts/check_투경_해제.py          # 출력만
    python scripts/check_투경_해제.py --tg     # 텔레그램 발송

로직:
    1. raw/투경/투경_{TODAY}.json 읽기 (crawl_kind.py가 먼저 실행되어야 함)
    2. 각 종목 해제 조건 판단 (pykrx 가격 데이터)
    3. 3조건 모두 충족 → 내일 해제 예정 → 시가베팅 후보

해제 조건 (지정일로부터 10영업일 이후):
    급등형(KOSDAQ 투자경고):
        오늘 < T-5종가 × 1.60  AND
        오늘 < T-15종가 × 2.00 AND
        오늘 ≠ 최근15일최고가
    불건전형(KOSPI 또는 투자위험):
        오늘 < T-5종가 × 1.45  AND
        오늘 < T-15종가 × 1.75 AND
        오늘 ≠ 최근15일최고가
"""

import sys, json, argparse, urllib.request, urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT     = Path(__file__).parent.parent
TODAY_DT = date.today()
TODAY    = TODAY_DT.strftime("%Y-%m-%d")
TODAY_KR = TODAY_DT.strftime("%Y년 %m월 %d일")

try:
    from pykrx import stock as pyk
except ImportError:
    print("pip install pykrx 필요")
    sys.exit(1)


# ── 영업일 계산 ───────────────────────────────────────────────

def biz_days_ago(base: date, n: int) -> str:
    """base 기준 n 영업일 전 날짜 (YYYYMMDD)"""
    dt = base
    count = 0
    while count < n:
        dt -= timedelta(days=1)
        if dt.weekday() < 5:  # 평일만
            count += 1
    return dt.strftime("%Y%m%d")


def biz_days_since(dsgn_str: str) -> int:
    """지정일로부터 오늘까지 영업일 수"""
    try:
        dsgn = datetime.strptime(dsgn_str[:10], "%Y-%m-%d").date()
    except:
        return 0
    dt = dsgn
    count = 0
    while dt < TODAY_DT:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            count += 1
    return count


# ── 가격 데이터 ───────────────────────────────────────────────

def get_prices(code: str, from_date: str, to_date: str) -> dict:
    """종목 가격 OHLCV — code는 6자리 숫자"""
    try:
        df = pyk.get_market_ohlcv(from_date, to_date, code)
        if df is None or df.empty:
            return {}
        return {str(d.date()): row["종가"] for d, row in df.iterrows()}
    except Exception as e:
        print(f"    가격 조회 실패 ({code}): {e}")
        return {}


def get_market(code: str) -> str:
    """종목 시장 구분 (KOSPI/KOSDAQ)"""
    try:
        info = pyk.get_market_ticker_name(code)
        # pykrx ticker list로 시장 판단
        kospi = pyk.get_market_ticker_list(TODAY_DT.strftime("%Y%m%d"), market="KOSPI")
        return "KOSPI" if code in kospi else "KOSDAQ"
    except:
        return "KOSDAQ"


# ── 해제 조건 판단 ─────────────────────────────────────────────

def check_release(code: str, dsgn_dt: str, warn_code: str) -> dict:
    """
    해제 조건 3가지 체크.
    반환: {ok: bool, reason: str, t5: int, t15: int, today: int, max15: int}
    """
    # 최소 10영업일 경과 체크
    elapsed = biz_days_since(dsgn_dt)
    if elapsed < 10:
        return {"ok": False, "reason": f"지정 후 {elapsed}영업일 (최소 10일 필요)", "elapsed": elapsed}

    # 가격 데이터 수집
    from_str = biz_days_ago(TODAY_DT, 20)   # 넉넉하게 20영업일 전부터
    prices   = get_prices(code, from_str, TODAY_DT.strftime("%Y%m%d"))

    if not prices:
        return {"ok": False, "reason": "가격 데이터 없음", "elapsed": elapsed}

    dates_sorted = sorted(prices.keys())
    today_str    = TODAY

    if today_str not in prices:
        # 오늘 데이터 없으면 가장 최근 거래일
        today_str = dates_sorted[-1]

    today_price = prices[today_str]

    # 최근 15영업일 데이터
    recent15 = dates_sorted[-15:]
    if len(recent15) < 5:
        return {"ok": False, "reason": "최근 데이터 부족", "elapsed": elapsed}

    # T-5, T-15 종가 (지정일 기준이 아닌 최근 데이터 기준으로 근사)
    t5_price  = prices.get(recent15[-6], prices[recent15[0]])  # 5영업일 전
    t15_price = prices.get(recent15[0], prices[recent15[0]])   # 15영업일 전
    max15     = max(prices[d] for d in recent15)

    # 시장 구분 → 배수 결정
    mkt = get_market(code)
    if mkt == "KOSDAQ" and warn_code in ("0302", "0303"):
        mul5, mul15, label = 1.60, 2.00, "급등형"
    else:
        mul5, mul15, label = 1.45, 1.75, "불건전형"

    # 3조건 체크
    cond1 = today_price < t5_price  * mul5
    cond2 = today_price < t15_price * mul15
    cond3 = today_price < max15  # 최근15일 최고가 아님

    all_ok = cond1 and cond2 and cond3

    return {
        "ok":       all_ok,
        "type":     label,
        "market":   mkt,
        "elapsed":  elapsed,
        "today":    today_price,
        "t5":       t5_price,
        "t15":      t15_price,
        "max15":    max15,
        "cond1":    cond1,  # 오늘 < T5 × mul5
        "cond2":    cond2,  # 오늘 < T15 × mul15
        "cond3":    cond3,  # 오늘 ≠ 최고가
        "mul5":     mul5,
        "mul15":    mul15,
        "reason":   "✅ 3조건 충족" if all_ok else f"{'✅' if cond1 else '❌'}T5 {'✅' if cond2 else '❌'}T15 {'✅' if cond3 else '❌'}고가",
    }


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
        print("  ⚠️ .env 없음"); return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": "true"
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as r:
                if json.loads(r.read()).get("ok"):
                    print("  ✅ 텔레그램 발송")
        except Exception as e:
            print(f"  ❌ {e}")


# ── 메인 ─────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tg", action="store_true")
    args = ap.parse_args()

    # 오늘 투경 JSON 읽기
    json_path = ROOT / "raw" / "투경" / f"투경_{TODAY}.json"
    if not json_path.exists():
        print(f"⚠️ {json_path.name} 없음 — crawl_kind.py 먼저 실행 필요")
        sys.exit(0)

    warn_data: dict = json.loads(json_path.read_text(encoding="utf-8"))

    WARN_TYPES = [
        ("투자위험", "0301"),
        ("투자경고", "0302"),
        ("투자주의", "0303"),
    ]

    release_candidates = []   # 3조건 충족 → 내일 해제 예정
    near_release       = []   # 2조건 충족 → 관찰

    for label, code in WARN_TYPES:
        items = warn_data.get(code, [])
        for it in items:
            name    = it.get("name", "")
            ticker  = it.get("code", "").replace("A", "").strip()
            dsgn_dt = it.get("dsgn_dt", "")
            if not ticker or len(ticker) != 6:
                continue

            print(f"  검사: {name} ({ticker})  지정일: {dsgn_dt}")
            result = check_release(ticker, dsgn_dt, code)
            result["name"]    = name
            result["ticker"]  = ticker
            result["warn"]    = label
            result["dsgn_dt"] = dsgn_dt

            if result["ok"]:
                release_candidates.append(result)
                print(f"    → ✅ 내일 해제 예정!")
            else:
                conds_met = sum([result.get("cond1",False), result.get("cond2",False), result.get("cond3",False)])
                if conds_met >= 2:
                    near_release.append(result)
                print(f"    → {result.get('reason','')}")

    # 결과 출력
    print(f"\n{'='*55}")
    print(f"📋 투경 해제 판단 결과 — {TODAY}")
    print(f"  내일 해제 예정: {len(release_candidates)}종목")
    print(f"  2조건 충족(관찰): {len(near_release)}종목")

    for r in release_candidates:
        print(f"\n  ✅ {r['name']} ({r['ticker']}) — {r['warn']} [{r['type']}]")
        print(f"     지정일: {r['dsgn_dt']}  경과: {r['elapsed']}영업일")
        print(f"     오늘: {r['today']:,}  T5×{r['mul5']}: {r['t5']*r['mul5']:,.0f}  T15×{r['mul15']}: {r['t15']*r['mul15']:,.0f}")

    if not args.tg:
        return

    # 텔레 메시지
    if not release_candidates and not near_release:
        lines = [
            f"📋 <b>투경 해제 판단</b> — {TODAY_KR}",
            "",
            "오늘 해제 조건 충족 종목 없음",
        ]
    else:
        lines = [
            f"🚨 <b>투경 해제 예정 — 내일 시가베팅 후보</b>",
            f"<i>{TODAY_KR} 장 마감 후 판단</i>",
            "",
        ]

        if release_candidates:
            lines.append(f"<b>✅ 내일 해제 예정 ({len(release_candidates)}종목)</b>")
            for r in release_candidates:
                pct_from_t5  = (r['today'] / r['t5']  - 1) * 100 if r['t5'] else 0
                lines.append(
                    f"  <b>{r['name']}</b>  [{r['warn']} / {r['type']}]"
                )
                lines.append(
                    f"   지정 {r['dsgn_dt']} ({r['elapsed']}영업일)"
                    f"  오늘 {r['today']:,}원"
                )
                lines.append(
                    f"   T5기준 {pct_from_t5:+.1f}%  조건 {r['reason']}"
                )
            lines.append("")

        if near_release:
            lines.append(f"<b>🟡 2조건 충족 관찰 ({len(near_release)}종목)</b>")
            for r in near_release[:5]:
                lines.append(f"  {r['name']}  {r['reason']}")

    send_tg("\n".join(lines))


if __name__ == "__main__":
    main()
