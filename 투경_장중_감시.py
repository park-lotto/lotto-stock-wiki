"""
투경 지정 장중 감시 스크립트

목적: 오늘 장마감 시 투경 지정될 가능성이 있는 종목 조기 경보
      → 종가배팅 대상에서 제외 판단용

실행 시점: 오후 2:30 (마감 1시간 전)

투경 지정 조건 (KOSDAQ):
  현재가 > T-5종가(오늘기준 5일전) × 160%
  OR 현재가 > T-15종가(오늘기준 15일전) × 200%
  AND 현재가 = 오늘 일중 최고가(신고가)

경보 기준: 기준가의 80% 이상 도달 시 ⚠️ 경보

사용법:
  python 투경_장중_감시.py              # 터미널 출력
  python 투경_장중_감시.py --tg         # 텔레그램 전송
  python 투경_장중_감시.py --watchlist raw/투경/watchlist.txt --tg
"""

import sys, json, argparse, urllib.request, urllib.parse, requests
from datetime import date, timedelta, datetime
from pathlib import Path
from pykrx import stock as pyk

sys.stdout.reconfigure(encoding='utf-8')

TODAY    = date.today().strftime('%Y-%m-%d')
TODAY_DT = date.today()
BASE_DIR = Path(__file__).parent

MARKET_THRESH = {
    'KOSDAQ': (1.60, 2.00),
    'KOSPI':  (1.45, 1.75),
    'KONEX':  (1.45, 1.75),
}
WARN_RATIO = 0.80   # 기준가의 80% 이상 → ⚠️ 경보
ALERT_RATIO = 0.92  # 기준가의 92% 이상 → 🔴 위험


# ── 유틸 ──────────────────────────────────────────────────────────────────
def load_env() -> dict:
    cfg = {}
    env = BASE_DIR / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg

def send_telegram(text: str):
    cfg = load_env()
    token, chat_id = cfg.get('BOT_TOKEN', ''), cfg.get('CHAT_ID', '')
    if not token or not chat_id:
        print('텔레그램 설정 없음')
        return
    try:
        url  = f'https://api.telegram.org/bot{token}/sendMessage'
        data = urllib.parse.urlencode(
            {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}).encode()
        with urllib.request.urlopen(
                urllib.request.Request(url, data), timeout=10) as r:
            if json.loads(r.read()).get('ok'):
                print('텔레그램 전송 완료')
    except Exception as e:
        print(f'텔레그램 오류: {e}')


# ── 현재가 조회 (네이버 금융) ──────────────────────────────────────────────
_price_cache: dict[str, int] = {}

def get_current_price(code: str) -> int:
    """네이버 금융에서 현재가 조회."""
    if code in _price_cache:
        return _price_cache[code]
    try:
        r = requests.get(
            f'https://finance.naver.com/item/main.naver?code={code}',
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        import re
        # 현재가 패턴
        m = re.search(r'<strong[^>]*id="_nowVal"[^>]*>([\d,]+)</strong>', r.text)
        if m:
            price = int(m.group(1).replace(',', ''))
            _price_cache[code] = price
            return price
    except:
        pass
    # 실패 시 pykrx 당일 종가 대체
    try:
        df = pyk.get_market_ohlcv(TODAY_DT.strftime('%Y%m%d'), TODAY_DT.strftime('%Y%m%d'), code)
        if not df.empty:
            close = int(df.iloc[-1]['종가'])
            if close > 0:
                _price_cache[code] = close
                return close
    except:
        pass
    return 0


# ── 기준가 계산 (rolling T-5, T-15 from TODAY) ────────────────────────────
def get_rolling_ref(code: str) -> dict:
    """오늘 기준 T-5, T-15 종가 및 15일 최고가."""
    start = (TODAY_DT - timedelta(days=60)).strftime('%Y%m%d')
    end   = (TODAY_DT - timedelta(days=1)).strftime('%Y%m%d')  # 전날까지
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return {}
        prices = []
        for idx in df.index[::-1]:
            c = int(df.loc[idx, '종가'])
            if c > 0:
                prices.append((idx.strftime('%Y-%m-%d'), c))
            if len(prices) >= 16:
                break
        if len(prices) < 16:
            return {}
        return {
            't5_date':  prices[4][0], 't5_close':  prices[4][1],
            't15_date': prices[14][0], 't15_close': prices[14][1],
            'high15': max(p[1] for p in prices[:15]),
            'high15_date': max(prices[:15], key=lambda x: x[1])[0],
        }
    except:
        return {}


# ── 종목 코드·시장 조회 ────────────────────────────────────────────────────
_KRX_HDR = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.krx.co.kr/',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
_mkt_cache: dict[str, str] = {}

def get_market(code: str) -> str:
    if code in _mkt_cache:
        return _mkt_cache[code]
    try:
        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu', 'mktsel': 'ALL',
                  'searchText': code, 'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers=_KRX_HDR, timeout=5)
        for item in r.json().get('block1', []):
            if item.get('short_code') == code:
                mkt = (item.get('marketEngName', '') or '').upper()
                market = 'KOSPI' if 'KOSPI' in mkt else 'KONEX' if 'KONEX' in mkt else 'KOSDAQ'
                _mkt_cache[code] = market
                return market
    except:
        pass
    return 'KOSDAQ'


# ── 핵심 분석 ─────────────────────────────────────────────────────────────
def analyze_warn_risk(code: str, name: str) -> dict | None:
    """현재가 기준 투경 지정 위험도 분석."""
    market = get_market(code)
    t5_mult, t15_mult = MARKET_THRESH.get(market, MARKET_THRESH['KOSDAQ'])

    refs = get_rolling_ref(code)
    if not refs:
        return None

    cur = get_current_price(code)
    if not cur:
        return None

    t5_close  = refs['t5_close']
    t15_close = refs['t15_close']
    high15    = refs['high15']

    tp5  = int(t5_close  * t5_mult)
    tp15 = int(t15_close * t15_mult)

    # 기준가 대비 현재가 비율
    r5  = cur / tp5  if tp5  else 0
    r15 = cur / tp15 if tp15 else 0
    max_ratio = max(r5, r15)

    # 신고가 여부 (현재가 > 15일 최고가)
    is_high15 = cur >= high15

    if max_ratio < WARN_RATIO:
        return None  # 위험 없음

    return {
        'code':   code,
        'name':   name,
        'market': market,
        'cur':    cur,
        't5_close': t5_close, 't5_date': refs['t5_date'],
        't15_close': t15_close, 't15_date': refs['t15_date'],
        'tp5': tp5, 'tp15': tp15,
        'r5': round(r5 * 100, 1), 'r15': round(r15 * 100, 1),
        'max_ratio': max_ratio,
        'high15': high15, 'high15_date': refs['high15_date'],
        'is_high15': is_high15,
        't5_pct':  int(t5_mult  * 100),
        't15_pct': int(t15_mult * 100),
    }


# ── 워치리스트 로드 ──────────────────────────────────────────────────────
def load_watchlist(path: str | None) -> list[tuple[str, str]]:
    """(코드, 이름) 목록 반환."""
    stocks = []

    # 기본: 투경현황.json의 현재 투경 종목 (이미 지정된 것 = 제외 대상 확인용이 아님)
    # + wiki의 탑픽 종목 리스트
    # 여기서는 raw/투경/watchlist.txt 또는 wiki stock/ 파일에서 코드 추출

    if path and Path(path).exists():
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                stocks.append((parts[0], parts[1]))
            elif len(parts) == 1 and parts[0].isdigit():
                stocks.append((parts[0], parts[0]))
        return stocks

    # 기본 워치리스트: wiki stock 파일들에서 코드 추출
    stock_files = list(BASE_DIR.glob('wiki/L5_섹터/*/stock/stock_*.md'))
    for f in stock_files:
        try:
            header = f.read_text(encoding='utf-8', errors='ignore')[:500]
            import re
            # # 종목명 (코드) 패턴
            m = re.search(r'^# (.+?) \((\d{6})\)', header, re.MULTILINE)
            if m:
                stocks.append((m.group(2), m.group(1)))
        except:
            pass

    return stocks


# ── 텔레그램 메시지 ──────────────────────────────────────────────────────
def build_warn_message(results: list[dict]) -> str:
    now_str = datetime.now().strftime('%H:%M')
    lines   = [f'⚠️ <b>투경 지정 장중 경보</b>  {TODAY} {now_str}', '']

    danger = [r for r in results if r['max_ratio'] >= ALERT_RATIO]
    warn   = [r for r in results if WARN_RATIO <= r['max_ratio'] < ALERT_RATIO]

    if danger:
        lines.append(f'🔴 <b>위험 (기준가 {int(ALERT_RATIO*100)}%↑) — 종가배팅 제외</b>')
        for r in sorted(danger, key=lambda x: -x['max_ratio']):
            icon = '🆕 신고가!' if r['is_high15'] else '📈'
            dominant = 'T-5' if r['r5'] >= r['r15'] else 'T-15'
            ratio    = r['r5'] if r['r5'] >= r['r15'] else r['r15']
            thresh   = r['tp5'] if r['r5'] >= r['r15'] else r['tp15']
            lines.append(
                f'  {icon} <b>{r["name"]}</b> ({r["code"]}) [{r["market"]}]\n'
                f'  현재가 {r["cur"]:,}원  |  {dominant} 기준가 {thresh:,}원  ({ratio:.1f}%)\n'
                f'  T-5: {r["t5_close"]:,}×{r["t5_pct"]}%={r["tp5"]:,}({r["r5"]:.1f}%)  '
                f'T-15: {r["t15_close"]:,}×{r["t15_pct"]}%={r["tp15"]:,}({r["r15"]:.1f}%)'
            )
        lines.append('')

    if warn:
        lines.append(f'🟡 <b>주의 (기준가 {int(WARN_RATIO*100)}~{int(ALERT_RATIO*100)}%) — 모니터링</b>')
        for r in sorted(warn, key=lambda x: -x['max_ratio']):
            icon = '🆕' if r['is_high15'] else '  '
            dominant = 'T-5' if r['r5'] >= r['r15'] else 'T-15'
            ratio    = r['r5'] if r['r5'] >= r['r15'] else r['r15']
            thresh   = r['tp5'] if r['r5'] >= r['r15'] else r['tp15']
            lines.append(
                f'  {icon} <b>{r["name"]}</b> ({r["code"]}) — '
                f'{dominant} {ratio:.1f}%  현재가 {r["cur"]:,}원 / 기준 {thresh:,}원'
            )
        lines.append('')

    if not danger and not warn:
        lines.append('이상 없음')

    lines.append(f'총 {len(results)}종목 감시 중')
    return '\n'.join(lines)


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='투경 지정 장중 감시')
    parser.add_argument('--watchlist', default=None, help='워치리스트 파일 경로')
    parser.add_argument('--tg', action='store_true', help='텔레그램 전송')
    args = parser.parse_args()

    stocks = load_watchlist(args.watchlist)
    if not stocks:
        print('워치리스트 비어있음. wiki/L5_섹터/*/stock/stock_*.md 파일 확인.')
        return

    print(f'[{TODAY}] 투경 지정 장중 감시  ({len(stocks)}종목)')
    print(f'경보 기준: T-5×{int(MARKET_THRESH["KOSDAQ"][0]*100)}% 또는 T-15×{int(MARKET_THRESH["KOSDAQ"][1]*100)}% 의 {int(WARN_RATIO*100)}% 이상\n')

    results = []
    for code, name in stocks:
        r = analyze_warn_risk(code, name)
        if r:
            flag = '🔴' if r['max_ratio'] >= ALERT_RATIO else '🟡'
            nh   = ' ★신고가' if r['is_high15'] else ''
            print(f'  {flag} {name} ({code}) — T5:{r["r5"]}% / T15:{r["r15"]}%{nh}')
            results.append(r)
        else:
            print(f'     {name} ({code}) — 이상 없음')

    print(f'\n경보 종목: {len(results)}개')

    if args.tg and results:
        msg = build_warn_message(results)
        send_telegram(msg)
    elif args.tg:
        # 이상 없을 때도 간단히 전송 (확인용)
        now_str = datetime.now().strftime('%H:%M')
        send_telegram(f'✅ 투경 장중 감시  {TODAY} {now_str}\n이상 없음 ({len(stocks)}종목 감시)')


if __name__ == '__main__':
    main()
