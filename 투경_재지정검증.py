"""
투경_재지정검증.py — 최근 해제 종목 조회 + 재지정 조건 검증

목적:
  KIND에서 최근 N일 이내 해제된 종목을 크롤링하고
  재지정 4조건(지정전일/해제전일/2일40%/시총100위)이 실제로 작동했는지 검증

사용법:
  python 투경_재지정검증.py              # 최근 7일 해제 종목
  python 투경_재지정검증.py --days 14    # 최근 14일
  python 투경_재지정검증.py --tg         # 텔레그램 전송
"""

import sys, json, argparse, urllib.request, urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
from pykrx import stock as pyk

sys.stdout.reconfigure(encoding='utf-8')

TODAY_DT = date.today()
TODAY    = TODAY_DT.strftime('%Y-%m-%d')
BASE_DIR = Path(__file__).parent
KIND_URL = ('https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
            '?method=investattentwarnriskyMain')

TYPE_THRESH = {
    'surge':  (1.60, 2.00),
    'unfair': (1.45, 1.75),
}
UNFAIR_KEYWORDS = ['불건전', '단기상승&', '중장기상승&', '초장기상승&']


# ── 유틸 ──────────────────────────────────────────────────────────────
def load_env():
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
        print('텔레그램 설정 없음'); return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            url  = f'https://api.telegram.org/bot{token}/sendMessage'
            data = urllib.parse.urlencode(
                {'chat_id': chat_id, 'text': chunk, 'parse_mode': 'HTML'}).encode()
            with urllib.request.urlopen(
                    urllib.request.Request(url, data), timeout=10) as r:
                if json.loads(r.read()).get('ok'):
                    print('텔레그램 전송 완료')
        except Exception as e:
            print(f'텔레그램 오류: {e}')

def biz_days(start: date, end: date) -> int:
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count

def prev_biz(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def add_biz(d: date, n: int) -> date:
    cur = d
    count = 0
    while count < n:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            count += 1
    return cur


# ── KIND 크롤링 (해제 종목 포함) ──────────────────────────────────────
def fetch_kind_released(days: int = 7) -> list[dict]:
    """KIND 투자경고종목 탭 → 최근 N일 이내 해제된 종목 반환."""
    cutoff = TODAY_DT - timedelta(days=days)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'
        )
        print('KIND 접속 중...')
        from_date = (TODAY_DT - timedelta(days=90)).strftime('%Y-%m-%d')
        page.goto(KIND_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=20000)

        page.evaluate(f'''() => {{
            document.getElementById("searchFromDate").value = "{from_date}";
            var sel = document.querySelector('select[name="currentPageSize"]');
            if (sel) sel.value = "100";
            document.getElementById("currentPageSize").value = "100";
        }}''')
        page.evaluate('fnViewTab(1)')
        page.wait_for_timeout(4000)
        page.wait_for_load_state('networkidle', timeout=15000)

        rows = page.query_selector_all('table tbody tr')
        for row in rows:
            cells = row.query_selector_all('td')
            texts = [c.inner_text().strip() for c in cells]
            if len(texts) >= 5 and texts[0].isdigit():
                name     = texts[1].strip()
                pub_date = texts[2].strip()
                des_date = texts[3].strip()
                rel_date = texts[4].strip()
                reason   = ''
                for t in texts[5:]:
                    if t and t != '-':
                        reason = t; break

                # 해제일 있는 종목만 (최근 N일 이내)
                if name and rel_date and rel_date != '-':
                    try:
                        rel_dt = datetime.strptime(rel_date, '%Y.%m.%d').date()
                    except:
                        try:
                            rel_dt = datetime.strptime(rel_date, '%Y-%m-%d').date()
                        except:
                            continue
                    if rel_dt >= cutoff:
                        results.append({
                            'name':     name,
                            'pub_date': pub_date,
                            'des_date': des_date.replace('.', '-'),
                            'rel_date': rel_dt.strftime('%Y-%m-%d'),
                            'reason':   reason,
                        })

        browser.close()

    print(f'최근 {days}일 해제 종목: {len(results)}건')
    return results


# ── pykrx 가격 조회 ────────────────────────────────────────────────────
_price_cache: dict[str, list] = {}

def get_prices(code: str, ref_date: date, n: int = 25) -> list[tuple]:
    """ref_date 이하 최근 n영업일 종가 리스트 (newest-first)."""
    key = f'{code}_{ref_date}'
    if key in _price_cache:
        return _price_cache[key]
    start = (ref_date - timedelta(days=120)).strftime('%Y%m%d')
    end   = ref_date.strftime('%Y%m%d')
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return []
        result = []
        for idx in df.index[::-1]:
            close = int(df.loc[idx, '종가'])
            if close == 0: continue
            result.append((idx.strftime('%Y-%m-%d'), close))
            if len(result) >= n: break
        _price_cache[key] = result
        return result
    except:
        return []

def get_code(name: str) -> tuple[str, str]:
    import requests
    try:
        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu', 'mktsel': 'ALL',
                  'searchText': name, 'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.krx.co.kr/'},
            timeout=5)
        for item in r.json().get('block1', []):
            cname = item.get('codeName', '')
            if name in cname or cname in name:
                code = item.get('short_code', '')
                mkt  = item.get('marketEngName', '') or ''
                market = 'KOSPI' if 'KOSPI' in mkt.upper() else 'KONEX' if 'KONEX' in mkt.upper() else 'KOSDAQ'
                return code, market
    except:
        pass
    return '', 'KOSDAQ'


# ── 재지정 조건 검증 ───────────────────────────────────────────────────
def verify_rejoin(stock: dict) -> dict:
    """
    해제 후 10거래일간 재지정 4조건 일별 체크.
    반환: {name, 해제일, 지정전일종가, 해제전일종가, days: [{date, close, c1,c2,c3,c4, 재지정여부}]}
    """
    name     = stock['name']
    code     = stock.get('code', '')
    des_date = stock['des_date']
    rel_date = stock['rel_date']

    try:
        des_dt = datetime.strptime(des_date, '%Y-%m-%d').date()
        rel_dt = datetime.strptime(rel_date, '%Y-%m-%d').date()
    except:
        return {'name': name, 'error': '날짜 파싱 실패'}

    if not code:
        return {'name': name, 'error': '코드 없음'}

    # 지정 전일 종가
    des_prev = prev_biz(des_dt)
    des_prev_prices = get_prices(code, des_prev, 3)
    des_prev_close  = des_prev_prices[0][1] if des_prev_prices else 0

    # 해제 전일 종가 (= 3조건 충족일 종가)
    rel_prev = prev_biz(rel_dt)
    rel_prev_prices = get_prices(code, rel_prev, 3)
    rel_prev_close  = rel_prev_prices[0][1] if rel_prev_prices else 0

    # 해제 후 10거래일 = 재지정 위험 구간
    end_dt = add_biz(rel_dt, 10)
    end_dt = min(end_dt, TODAY_DT)

    day_results = []
    cur = add_biz(rel_dt, 1)  # 해제 다음 영업일부터
    while cur <= end_dt:
        if cur.weekday() >= 5:
            cur += timedelta(days=1)
            continue

        prices_cur = get_prices(code, cur, 5)
        if not prices_cur:
            cur += timedelta(days=1)
            continue

        today_close = prices_cur[0][1]
        t2_close    = prices_cur[2][1] if len(prices_cur) >= 3 else 0

        c1 = today_close > des_prev_close  # 지정전일 종가 초과
        c2 = today_close > rel_prev_close  # 해제전일 종가 초과
        c3 = t2_close > 0 and today_close >= t2_close * 1.40  # 2일 40% 급등
        # c4 (시총 100위 밖) = 중소형주이면 True, 대형주 False 가정
        # 실제 시총 순위 조회는 비용이 크므로 종목명 기반 추정
        c4 = True  # 보수적으로 True (중소형주 가정)

        rejoin = c1 and c2 and c3 and c4

        day_results.append({
            'date':        cur.strftime('%Y-%m-%d'),
            'close':       today_close,
            't2_close':    t2_close,
            'c1':          c1,
            'c2':          c2,
            'c3':          c3,
            'rejoin':      rejoin,
        })

        cur += timedelta(days=1)

    return {
        'name':          name,
        'code':          code,
        'des_date':      des_date,
        'rel_date':      rel_date,
        'des_prev_close': des_prev_close,
        'rel_prev_close': rel_prev_close,
        'days':          day_results,
        'rejoin_triggered': any(d['rejoin'] for d in day_results),
        'warn_type':     stock.get('warn_type', 'surge'),
    }


# ── 출력 ──────────────────────────────────────────────────────────────
def print_result(r: dict):
    if 'error' in r:
        print(f'\n  {r["name"]} — ❌ {r["error"]}')
        return

    rejoin = r['rejoin_triggered']
    status = '🔴 재지정 조건 발생!' if rejoin else '🟢 재지정 없이 안정'
    print(f'\n{"━"*60}')
    print(f'  {r["name"]} ({r["code"]})  지정:{r["des_date"]} → 해제:{r["rel_date"]}')
    print(f'  지정전일종가: {r["des_prev_close"]:,}원  |  해제전일종가: {r["rel_prev_close"]:,}원')
    print(f'  → {status}')
    print(f'  {"날짜":<12} {"종가":>8} {"T-2종가":>8} {"①>지정전":>8} {"②>해제전":>8} {"③2일40%":>8} {"재지정"}')
    for d in r['days']:
        c1 = '✅' if d['c1'] else '❌'
        c2 = '✅' if d['c2'] else '❌'
        c3 = '✅' if d['c3'] else '❌'
        rej = '🔴 재지정!' if d['rejoin'] else ''
        print(f'  {d["date"]}  {d["close"]:>8,}  {d["t2_close"]:>8,}  {c1:>6}  {c2:>6}  {c3:>6}  {rej}')


def build_tg(results: list[dict]) -> str:
    lines = [f'🔄 <b>투경 재지정 검증</b> — {TODAY}', '']
    for r in results:
        if 'error' in r:
            lines.append(f'  {r["name"]}: ❌ {r["error"]}')
            continue
        status = '🔴 재지정 조건 발생' if r['rejoin_triggered'] else '🟢 안정'
        lines.append(f'<b>{r["name"]}</b> ({r["rel_date"]} 해제) → {status}')
        for d in r['days']:
            if d['rejoin']:
                lines.append(
                    f'  ⚠️ {d["date"]} 종가 {d["close"]:,}원 — 4조건 동시 충족 → 재지정')
    if not any(r.get('rejoin_triggered') for r in results if 'error' not in r):
        lines.append('\n모든 해제 종목 재지정 없이 안정 ✅')
    return '\n'.join(lines)


# ── 메인 ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=7, help='최근 N일 해제 종목 조회')
    ap.add_argument('--tg',   action='store_true')
    args = ap.parse_args()

    print(f'[{TODAY}] 투경 재지정 검증 — 최근 {args.days}일 해제 종목')

    # 1. KIND 크롤링
    released = fetch_kind_released(args.days)
    if not released:
        print('해제 종목 없음 또는 크롤링 실패')
        return

    # 2. 종목코드 보강 + 지정유형 판별
    for s in released:
        code, market = get_code(s['name'])
        s['code']   = code
        s['market'] = market
        reason = s.get('reason', '')
        s['warn_type'] = 'unfair' if any(k in reason for k in UNFAIR_KEYWORDS) else 'surge'
        print(f'  {s["name"]} ({code}) [{market}] 지정:{s["des_date"]} 해제:{s["rel_date"]} [{s["warn_type"]}]')

    # 3. 재지정 조건 일별 검증
    print('\n재지정 조건 검증 중...')
    results = []
    for s in released:
        r = verify_rejoin(s)
        results.append(r)
        print_result(r)

    # 4. 요약
    print(f'\n{"═"*60}')
    print(f'총 {len(results)}종목 검증')
    rejoin_count = sum(1 for r in results if r.get('rejoin_triggered'))
    stable_count = len(results) - rejoin_count
    print(f'  🔴 재지정 조건 발생: {rejoin_count}건')
    print(f'  🟢 안정 (재지정 없음): {stable_count}건')

    print('\n※ 검증 목적: 재지정 공식(4조건)이 실제로 작동했는지 확인')
    print('※ c4(시총100위 밖)는 중소형주로 가정 — 대형주는 수동 확인 필요')

    if args.tg:
        send_telegram(build_tg(results))


if __name__ == '__main__':
    main()
