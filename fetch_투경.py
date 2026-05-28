"""
투자경고 해제 조건 분석기

투경인지 여부는 네이버에서 확인 → 이 스크립트는 "얼마나 남았냐" 분석만 함

사용법:
  python fetch_투경.py 종목코드 지정일 [종목코드 지정일 ...]
  python fetch_투경.py 080220 2026-05-14
  python fetch_투경.py 080220 2026-05-14 007810 2026-05-14 --tg

해제 조건 (KRX 규정, raw/투경해제 공식.xlsx 실증 검증 완료):
  코스닥: 당일 < T-5×160% AND 당일 < T-15×200% AND 당일 ≠ 최근15일최고가
  코스피: 당일 < T-5×145% AND 당일 < T-15×175% AND 당일 ≠ 최근15일최고가
  ★ 3가지 모두(AND) 해소여야 해제. 하나라도 살아있으면 이연.
"""

import sys, os, json, argparse, urllib.request, urllib.parse, requests
from datetime import datetime, date, timedelta
from pathlib import Path
from pykrx import stock as pyk

sys.stdout.reconfigure(encoding='utf-8')

TODAY    = datetime.now().strftime('%Y-%m-%d')
TODAY_DT = date.today()
BASE_DIR = Path(__file__).parent

MARKET_THRESH = {
    'KOSDAQ': (1.60, 2.00),
    'KOSPI':  (1.45, 1.75),
    'KONEX':  (1.45, 1.75),
}
RELEASE_ELIGIBLE_BUSINESS_DAYS = 10

KRX_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://data.krx.co.kr/',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}

_name_cache:   dict[str, str] = {}
_market_cache: dict[str, str] = {}


# ── 유틸 ──────────────────────────────────────────────────────────────────
def business_days_elapsed(start: date, end: date) -> int:
    """지정일 포함 영업일 수."""
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count


def _load_env() -> dict:
    cfg = {}
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


# ── 텔레그램 ──────────────────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    cfg = _load_env()
    token, chat_id = cfg.get("BOT_TOKEN", ""), cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("텔레그램 설정 없음 (.env)")
        return False
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        with urllib.request.urlopen(
                urllib.request.Request(url, data), timeout=10) as resp:
            if json.loads(resp.read()).get("ok"):
                print("텔레그램 전송 완료")
                return True
    except Exception as e:
        print(f"텔레그램 오류: {e}")
    return False


# ── KRX 종목 정보 ─────────────────────────────────────────────────────────
def get_stock_info(code: str) -> tuple[str, str]:
    """종목코드 → (종목명, 시장)."""
    if code in _market_cache:
        return _name_cache.get(code, code), _market_cache[code]
    try:
        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu',
                  'mktsel': 'ALL', 'searchText': code,
                  'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers=KRX_HEADERS, timeout=5)
        for item in r.json().get('block1', []):
            if item.get('short_code') == code:
                name   = item.get('codeName', code)
                mkt    = (item.get('marketEngName', '') or item.get('marketCode', '') or '').upper()
                market = ('KOSPI'  if 'KOSPI' in mkt or mkt in ('STK',)
                          else 'KONEX' if 'KONEX' in mkt or mkt in ('KNX',)
                          else 'KOSDAQ')
                _name_cache[code]   = name
                _market_cache[code] = market
                return name, market
    except:
        pass
    return code, 'KOSDAQ'


# ── 종가 수집 (pykrx) ─────────────────────────────────────────────────────
def get_close_prices(code: str, n: int = 20) -> list[tuple[str, int]]:
    """최근 n영업일 종가 (newest-first)."""
    start = (TODAY_DT - timedelta(days=60)).strftime('%Y%m%d')
    end   = TODAY_DT.strftime('%Y%m%d')
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return []
        result = []
        for idx in df.index[::-1]:
            close = int(df.loc[idx, '종가'])
            if close == 0:
                continue
            result.append((idx.strftime('%Y-%m-%d'), close))
            if len(result) >= n:
                break
        return result
    except Exception as e:
        print(f"  pykrx 오류 ({code}): {e}")
        return []


# ── 핵심 분석 ─────────────────────────────────────────────────────────────
def analyze(code: str, des_date_str: str) -> dict:
    """해제 조건 3개 계산 + 해소까지 필요한 하락폭."""
    name, market = get_stock_info(code)
    base = {
        'name': name, 'code': code, 'market': market,
        'des_date': des_date_str, 'eligible': False,
        'can_release': False, 'note': '',
    }

    try:
        des_dt = datetime.strptime(des_date_str, '%Y-%m-%d').date()
    except ValueError:
        base['note'] = '날짜 형식 오류 (YYYY-MM-DD 로 입력)'
        return base

    elapsed_days = (TODAY_DT - des_dt).days
    elapsed_biz  = business_days_elapsed(des_dt, TODAY_DT)
    base['elapsed_days'] = elapsed_days
    base['elapsed_biz']  = elapsed_biz

    if elapsed_biz < RELEASE_ELIGIBLE_BUSINESS_DAYS:
        remaining = RELEASE_ELIGIBLE_BUSINESS_DAYS - elapsed_biz
        base['note'] = (f'10영업일 미경과 '
                        f'({elapsed_biz}영업일 경과, {remaining}영업일 남음)')
        return base

    base['eligible'] = True
    t5_mult, t15_mult = MARKET_THRESH.get(market, MARKET_THRESH['KOSDAQ'])

    prices = get_close_prices(code, 20)
    if len(prices) < 16:
        base['note'] = f'주가 데이터 부족 ({len(prices)}건)'
        return base

    today_close = prices[0][1]
    t5_close    = prices[5][1]
    t15_close   = prices[15][1]
    high15      = max(p[1] for p in prices[:15])
    high15_date = max(prices[:15], key=lambda x: x[1])[0]

    tp5  = int(t5_close  * t5_mult)
    tp15 = int(t15_close * t15_mult)

    cond1_ok = today_close < tp5
    cond2_ok = today_close < tp15
    cond3_ok = today_close != high15

    gap1 = (today_close / tp5  - 1) * 100 if not cond1_ok and tp5  else 0.0
    gap2 = (today_close / tp15 - 1) * 100 if not cond2_ok and tp15 else 0.0

    can_release = cond1_ok and cond2_ok and cond3_ok
    binding = min(tp5, tp15)

    if can_release:
        verdict = f"오늘 종가 {today_close:,}원으로 3조건 충족"
        condition_line = f"해제 기준 {binding:,}원 이하 + 신고가 미경신 → 오늘 충족"
    elif cond1_ok and cond2_ok and not cond3_ok:
        verdict = f"①② 해소. 신고가({high15:,}원) 미경신 유지 중"
        condition_line = f"해제 기준 {binding:,}원 이하 ✅ + 신고가 미경신 → 오늘 최고가이면 내일로 이연"
    else:
        parts = []
        if not cond1_ok: parts.append(f"T-5 기준 {tp5:,}원 이하 (-{gap1:.1f}%)")
        if not cond2_ok: parts.append(f"T-15 기준 {tp15:,}원 이하 (-{gap2:.1f}%)")
        if not cond3_ok: parts.append("신고가 미경신")
        verdict = f"미충족: {' / '.join(parts)}"
        condition_line = f"해제 기준 {binding:,}원 이하 + 신고가 미경신 → 현재 {today_close:,}원 / 미달"

    base.update({
        'today_close': today_close, 'today_date': prices[0][0],
        't5_close':  t5_close,  't5_date':  prices[5][0],
        't15_close': t15_close, 't15_date': prices[15][0],
        'high15': high15, 'high15_date': high15_date,
        'tp5': tp5, 'tp15': tp15,
        't5_mult': t5_mult, 't15_mult': t15_mult,
        't5_ratio':  round(today_close / t5_close  * 100, 1),
        't15_ratio': round(today_close / t15_close * 100, 1),
        'cond1_ok': cond1_ok, 'cond2_ok': cond2_ok, 'cond3_ok': cond3_ok,
        'can_release': can_release,
        'gap1': round(gap1, 1), 'gap2': round(gap2, 1),
        'verdict': verdict,
        'condition_line': condition_line,
    })
    return base


# ── 터미널 출력 ───────────────────────────────────────────────────────────
def print_result(r: dict):
    name   = r['name']
    code   = r['code']
    market = r['market']
    biz    = r.get('elapsed_biz', '-')
    days   = r.get('elapsed_days', '-')

    print(f"\n{'━'*52}")
    print(f"  {name} ({code})  [{market}]")
    print(f"  지정일: {r['des_date']}  경과: {days}일 / {biz}영업일")
    print(f"{'━'*52}")

    if not r.get('eligible'):
        print(f"  ⏳ {r['note']}")
        return

    today    = r['today_close']
    tp5      = r['tp5']
    tp15     = r['tp15']
    t5_pct   = int(r['t5_mult']  * 100)
    t15_pct  = int(r['t15_mult'] * 100)
    c1 = '✅' if r['cond1_ok'] else '❌'
    c2 = '✅' if r['cond2_ok'] else '❌'
    c3 = '✅' if r['cond3_ok'] else '❌'

    print(f"  현재가: {today:,}원  ({r['today_date']})")
    print()

    # 조건 ①
    print(f"  {c1} ① T-5  기준가 {tp5:,}원"
          f"  (T-5종가 {r['t5_close']:,}원 × {t5_pct}%  [{r['t5_date']}])")
    if not r['cond1_ok']:
        print(f"       현재 {r['t5_ratio']}%  →  {t5_pct}% 초과 중"
              f"  |  -{r['gap1']:.1f}% 하락 시 해소")
    print()

    # 조건 ②
    print(f"  {c2} ② T-15 기준가 {tp15:,}원"
          f"  (T-15종가 {r['t15_close']:,}원 × {t15_pct}%  [{r['t15_date']}])")
    if not r['cond2_ok']:
        print(f"       현재 {r['t15_ratio']}%  →  {t15_pct}% 초과 중"
              f"  |  -{r['gap2']:.1f}% 하락 시 해소")
    print()

    # 조건 ③
    if r['cond3_ok']:
        print(f"  {c3} ③ 15일 최고가 {r['high15']:,}원  [{r['high15_date']}]  "
              f"→ 오늘이 최고가 아님 ✅")
    else:
        print(f"  {c3} ③ 15일 최고가 = 오늘 종가 {today:,}원"
              f"  →  내일 신고가 미경신 시 해소")
    print()

    # 해제 조건 한줄
    print(f"  📌 {r['condition_line']}")
    print()

    # 판정
    if r['can_release']:
        print(f"  🟢  해제 임박 — {r['verdict']}")
    elif r['cond1_ok'] and r['cond2_ok'] and not r['cond3_ok']:
        print(f"  🔥  해제 임박 — {r['verdict']}")
    else:
        print(f"  🔴  {r['verdict']}")


# ── 텔레그램 메시지 ────────────────────────────────────────────────────────
def build_tg(results: list[dict]) -> str:
    lines = [f"📊 <b>투경 해제 분석</b>  {TODAY}", ""]

    for r in results:
        biz = r.get('elapsed_biz', '-')
        lines.append(
            f"<b>{r['name']}</b> ({r['code']}) [{r['market']}]  "
            f"지정 {r['des_date']}  {biz}영업일"
        )

        if not r.get('eligible'):
            lines.append(f"  ⏳ {r['note']}")
            lines.append("")
            continue

        today   = r['today_close']
        tp5     = r['tp5']
        tp15    = r['tp15']
        t5_pct  = int(r['t5_mult']  * 100)
        t15_pct = int(r['t15_mult'] * 100)
        c1 = '✅' if r['cond1_ok'] else '❌'
        c2 = '✅' if r['cond2_ok'] else '❌'
        c3 = '✅' if r['cond3_ok'] else '❌'

        lines.append(f"  현재가 {today:,}원")
        if r['cond1_ok']:
            lines.append(f"  {c1} ①T-5: {r['t5_ratio']}% &lt; {t5_pct}%")
        else:
            lines.append(f"  {c1} ①T-5: 기준 {tp5:,}원  "
                         f"(-{r['gap1']:.1f}% 필요)")
        if r['cond2_ok']:
            lines.append(f"  {c2} ②T-15: {r['t15_ratio']}% &lt; {t15_pct}%")
        else:
            lines.append(f"  {c2} ②T-15: 기준 {tp15:,}원  "
                         f"(-{r['gap2']:.1f}% 필요)")
        if r['cond3_ok']:
            lines.append(f"  {c3} ③최고가: 아님")
        else:
            lines.append(f"  {c3} ③최고가: 내일 미경신 시 해소")

        lines.append(f"  📌 {r['condition_line']}")
        if r['can_release']:
            lines.append(f"  → 🟢 <b>해제 임박</b> — {r['verdict']}")
        elif r['cond1_ok'] and r['cond2_ok']:
            lines.append(f"  → 🔥 <b>해제 임박</b> — {r['verdict']}")
        else:
            lines.append(f"  → 🔴 {r['verdict']}")
        lines.append("")

    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='투경 해제 조건 분석기',
        epilog='예) python fetch_투경.py 080220 2026-05-14 007810 2026-05-14'
    )
    parser.add_argument(
        'stocks', nargs='+',
        help='종목코드 지정일 쌍  예: 080220 2026-05-14 007810 2026-05-14'
    )
    parser.add_argument('--tg', action='store_true', help='텔레그램 전송')
    args = parser.parse_args()

    tokens = args.stocks
    if len(tokens) % 2 != 0:
        print("오류: 종목코드와 지정일을 쌍으로 입력하세요.")
        print("예) python fetch_투경.py 080220 2026-05-14 007810 2026-05-14")
        sys.exit(1)

    targets = [(tokens[i], tokens[i + 1]) for i in range(0, len(tokens), 2)]

    print(f"[{TODAY}] 투경 해제 조건 분석  ({len(targets)}종목)")

    results = []
    for code, des_date in targets:
        print(f"  {code} ({des_date}) 분석 중...")
        results.append(analyze(code, des_date))

    for r in results:
        print_result(r)

    if args.tg:
        print()
        send_telegram(build_tg(results))


if __name__ == '__main__':
    main()
