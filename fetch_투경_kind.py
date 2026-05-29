"""
KIND 투자경고 현황 크롤러 (Playwright 브라우저 기반 — WAF 우회)

사용법:
  python fetch_투경_kind.py                  # 터미널 출력
  python fetch_투경_kind.py --save           # raw/투경/투경현황.json 갱신
  python fetch_투경_kind.py --save --tg      # 저장 + 텔레그램 전송
  python fetch_투경_kind.py --analysis --tg  # 저장 + 해제조건 분석 + 텔레그램
"""

import sys, json, argparse, urllib.request, urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
from pykrx import stock as pyk

sys.stdout.reconfigure(encoding='utf-8')

TODAY     = date.today().strftime('%Y-%m-%d')
TODAY_DT  = date.today()
BASE_DIR  = Path(__file__).parent
WARN_JSON    = BASE_DIR / 'raw' / '투경' / '투경현황.json'
TELEGRAM_DIR = BASE_DIR / 'raw' / 'telegram'
KIND_URL  = ('https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
             '?method=investattentwarnriskyMain')

MARKET_THRESH = {'KOSDAQ': (1.60, 2.00), 'KOSPI': (1.45, 1.75), 'KONEX': (1.45, 1.75)}


# ── 유틸 ──────────────────────────────────────────────────────────────────
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
        print('텔레그램 설정 없음 (.env)')
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

def business_days_elapsed(start_str: str, end_dt: date) -> int:
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
    except:
        return 0
    count, cur = 0, start
    while cur <= end_dt:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count


# ── KIND 크롤링 ───────────────────────────────────────────────────────────
def fetch_kind_warn_list() -> list[dict]:
    """KIND 투자경고종목 탭 → 현재 지정 중(해제일='-') 종목만 반환."""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'
        )

        print('KIND 접속 중...')
        page.goto(KIND_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=20000)

        # 투자경고종목 탭 — fnViewTab(1) 직접 호출 (click보다 확실)
        from_date = (TODAY_DT - timedelta(days=90)).strftime('%Y-%m-%d')

        page.evaluate(f'''() => {{
            document.getElementById("searchFromDate").value = "{from_date}";
            document.getElementById("currentPageSize").value = "100";
            var sel = document.querySelector('select[name="currentPageSize"]');
            if (sel) sel.value = "100";
        }}''')
        page.evaluate('fnViewTab(1)')    # 투자경고종목 탭 전환
        page.wait_for_timeout(4000)
        page.wait_for_load_state('networkidle', timeout=15000)

        # 실제 rows 수 확인
        rows = page.query_selector_all('table tbody tr')
        for row in rows:
            cells = row.query_selector_all('td')
            texts = [c.inner_text().strip() for c in cells]
            # 컬럼: 번호 | 종목명 | 공시일 | 지정일 | 해제일
            if len(texts) >= 5 and texts[0].isdigit():
                name     = texts[1].strip()
                pub_date = texts[2].strip()
                des_date = texts[3].strip()
                rel_date = texts[4].strip()
                if name and rel_date == '-':   # 해제일 없음 = 현재 활성
                    results.append({
                        'name':     name,
                        'pub_date': pub_date,
                        'des_date': des_date,
                    })

        browser.close()

    return results


# ── 종목코드 조회 ─────────────────────────────────────────────────────────
import requests as _req

_code_cache: dict[str, str]   = {}
_mkt_cache:  dict[str, str]   = {}
_KRX_HDR = {
    'User-Agent': 'Mozilla/5.0',
    'Referer':    'https://data.krx.co.kr/',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}

def get_stock_info(name: str) -> tuple[str, str]:
    if name in _code_cache:
        return _code_cache[name], _mkt_cache[name]
    try:
        r = _req.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu', 'mktsel': 'ALL',
                  'searchText': name, 'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers=_KRX_HDR, timeout=5)
        for item in r.json().get('block1', []):
            cname = item.get('codeName', '')
            if name in cname or cname in name:
                code = item.get('short_code', '')
                mkt  = item.get('marketEngName', '') or ''
                market = ('KOSPI'  if 'KOSPI' in mkt.upper() or mkt in ('STK',)
                          else 'KONEX' if 'KONEX' in mkt.upper()
                          else 'KOSDAQ')
                _code_cache[name] = code
                _mkt_cache[name]  = market
                return code, market
    except:
        pass
    return '', 'KOSDAQ'


# ── 해제 조건 분석 (고정 지정일 기준) ────────────────────────────────────
def get_prices(code: str, n: int = 22) -> list[tuple[str, int]]:
    """최근 n영업일 종가 (newest-first)."""
    start = (TODAY_DT - timedelta(days=90)).strftime('%Y%m%d')
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
    except:
        return []

def get_fixed_ref_price(code: str, des_date_str: str, n_days: int) -> tuple[str, int]:
    """지정일 기준 n영업일 전 종가 (고정값)."""
    try:
        des_dt = datetime.strptime(des_date_str, '%Y-%m-%d').date()
    except:
        return ('', 0)
    start = (des_dt - timedelta(days=60)).strftime('%Y%m%d')
    end   = (des_dt - timedelta(days=1)).strftime('%Y%m%d')
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return ('', 0)
        prices_before = []
        for idx in df.index[::-1]:
            c = int(df.loc[idx, '종가'])
            if c == 0:
                continue
            prices_before.append((idx.strftime('%Y-%m-%d'), c))
            if len(prices_before) >= n_days:
                break
        if len(prices_before) >= n_days:
            ref = prices_before[n_days - 1]
            return ref
    except:
        pass
    return ('', 0)

def analyze_release(name: str, code: str, market: str, des_date: str) -> dict:
    """고정 지정일 기준 해제 조건 분석."""
    result = {'name': name, 'code': code, 'market': market,
              'des_date': des_date, 'can_release': False, 'note': ''}

    elapsed_biz = business_days_elapsed(des_date, TODAY_DT)
    result['elapsed_biz'] = elapsed_biz

    if elapsed_biz < 10:
        result['note'] = f'10영업일 미경과 ({elapsed_biz}영업일)'
        return result

    if not code:
        result['note'] = '코드 미확인'
        return result

    t5_mult, t15_mult = MARKET_THRESH.get(market, MARKET_THRESH['KOSDAQ'])

    # 오늘 종가
    prices_today = get_prices(code, 22)
    if not prices_today:
        result['note'] = '가격 데이터 없음'
        return result
    today_close = prices_today[0][1]
    today_date  = prices_today[0][0]

    # 고정 기준가 (지정일 기준 T-5, T-15)
    t5_date,  t5_close  = get_fixed_ref_price(code, des_date, 5)
    t15_date, t15_close = get_fixed_ref_price(code, des_date, 15)

    if not t5_close or not t15_close:
        result['note'] = '기준가 조회 실패'
        return result

    tp5  = int(t5_close  * t5_mult)
    tp15 = int(t15_close * t15_mult)

    cond1 = today_close < tp5
    cond2 = today_close < tp15

    # ③ 최근 15영업일 최고가 ≠ 오늘
    high15 = max(p[1] for p in prices_today[:15]) if len(prices_today) >= 15 else today_close
    high15_date = max(prices_today[:15], key=lambda x: x[1])[0] if len(prices_today) >= 15 else today_date
    cond3 = today_close != high15

    can_release = cond1 and cond2 and cond3
    result.update({
        'today_close': today_close,
        'today_date':  today_date,
        't5_date':     t5_date,  't5_close':  t5_close,  'tp5':  tp5,
        't15_date':    t15_date, 't15_close': t15_close, 'tp15': tp15,
        'high15':      high15,   'high15_date': high15_date,
        'cond1': cond1, 'cond2': cond2, 'cond3': cond3,
        'can_release': can_release,
        't5_ratio':  round(today_close / t5_close  * 100, 1),
        't15_ratio': round(today_close / t15_close * 100, 1),
    })

    if can_release:
        result['note'] = f'3조건 충족 → 내일 해제 예정'
    elif cond1 and cond2 and not cond3:
        result['note'] = f'①② 충족, ③ 오늘 신고가({today_close:,}) → 내일 미경신 시 해제'
    else:
        parts = []
        if not cond1:
            need = round((tp5 / today_close - 1) * 100, 1)
            parts.append(f'① -{need}% 필요({tp5:,}원)')
        if not cond2:
            need = round((tp15 / today_close - 1) * 100, 1)
            parts.append(f'② -{need}% 필요({tp15:,}원)')
        if not cond3:
            parts.append(f'③ 오늘 신고가')
        result['note'] = ' / '.join(parts)

    return result


# ── 출력 ─────────────────────────────────────────────────────────────────
def print_warn_list(stocks: list[dict]):
    print(f'\n투자경고 현황  {TODAY}  ({len(stocks)}종목)\n')
    print(f'{"종목명":<14} {"지정일":<12} {"경과"}')
    print('─' * 40)
    for s in stocks:
        biz = business_days_elapsed(s['des_date'], TODAY_DT)
        print(f'{s["name"]:<14} {s["des_date"]}  {biz}영업일')

def print_analysis(analyses: list[dict]):
    print(f'\n해제 조건 분석  {TODAY}\n')
    for a in sorted(analyses, key=lambda x: -x.get('elapsed_biz', 0)):
        code = a['code'] or '??????'
        print(f'{"─"*55}')
        print(f'  {a["name"]} ({code}) [{a["market"]}]  지정:{a["des_date"]}  {a.get("elapsed_biz","?")}영업일')
        if a.get('today_close'):
            c1 = '✅' if a['cond1'] else '❌'
            c2 = '✅' if a['cond2'] else '❌'
            c3 = '✅' if a['cond3'] else '❌'
            t5p  = int(a.get('t5_mult',  1.60) * 100) if 't5_mult'  not in a else int(MARKET_THRESH.get(a['market'], (1.60,))[0] * 100)
            t15p = int(a.get('t15_mult', 2.00) * 100) if 't15_mult' not in a else int(MARKET_THRESH.get(a['market'], (0, 2.00))[1] * 100)
            print(f'  현재가 {a["today_close"]:,}원  ({a["today_date"]})')
            print(f'  {c1} ① T-5  {a["t5_close"]:,}({a["t5_date"]}) × {t5p}% = {a["tp5"]:,}  ({a["t5_ratio"]}%)')
            print(f'  {c2} ② T-15 {a["t15_close"]:,}({a["t15_date"]}) × {t15p}% = {a["tp15"]:,}  ({a["t15_ratio"]}%)')
            print(f'  {c3} ③ 15일최고 {a["high15"]:,}({a["high15_date"]})')
            status = '🟢 해제예정' if a['can_release'] else ('🔥 임박' if a['cond1'] and a['cond2'] else '🔴 유지')
            print(f'  → {status}  {a["note"]}')
        else:
            print(f'  ⏳ {a["note"]}')


def build_tg_message(stocks: list[dict], analyses: list[dict],
                     new_stocks: list[dict], released_stocks: list[dict]) -> str:
    """3섹션 텔레그램 메시지 — 종가배팅 트레이딩 관점."""
    next_biz = TODAY_DT + timedelta(days=1)
    while next_biz.weekday() >= 5:
        next_biz += timedelta(days=1)
    next_biz_str = next_biz.strftime('%m/%d(%a)')

    lines = [f'📊 <b>투경 브리핑</b>  {TODAY}', '']

    # ── 섹션 1: 오늘 투경 해제 확정 ────────────────────────────────────────
    # → "오늘 해제됐으니 어제 종가배팅이 맞았다/틀렸다" 참고용
    lines.append(f'🟢 <b>오늘 해제 확정</b>  ({len(released_stocks)}종목)')
    if released_stocks:
        for s in released_stocks:
            biz = business_days_elapsed(s['des_date'], TODAY_DT)
            lines.append(f'  • <b>{s["name"]}</b> ({s.get("code","")})  {s["des_date"]} 지정 → {biz}영업일 만에 해제')
    else:
        lines.append('  없음')
    lines.append('')

    # ── 섹션 2: 신규 투경 지정 ─────────────────────────────────────────────
    # → 종가배팅 제외 대상 신규 추가
    lines.append(f'🔴 <b>신규 투경 지정</b>  ({len(new_stocks)}종목)  ← 종가배팅 제외')
    if new_stocks:
        for s in new_stocks:
            lines.append(f'  • <b>{s["name"]}</b> ({s.get("code","")})  지정:{s["des_date"]}')
    else:
        lines.append('  없음')
    lines.append('')

    # ── 섹션 3: 오늘 종가배팅 후보 (내일 해제 예상) ─────────────────────────
    # 조건: ①② 이미 충족 + ③ 오늘 신고가 안 찍으면 내일 해제
    can_release = [a for a in analyses if a.get('can_release') and a.get('today_close')]
    cond12_ok   = [a for a in analyses if not a.get('can_release')
                   and a.get('cond1') and a.get('cond2') and a.get('today_close')]
    bet_candidates = can_release + cond12_ok

    lines.append(f'💰 <b>오늘 종가배팅 후보</b>  ({len(bet_candidates)}종목)  → 내일({next_biz_str}) 해제 예상')

    if can_release:
        lines.append('  <b>[3조건 모두 충족 — 내일 해제 확실]</b>')
        for a in can_release:
            mkt  = a['market']
            t5p  = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[0] * 100)
            t15p = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[1] * 100)
            lines.append(
                f'  • <b>{a["name"]}</b> ({a["code"]})  지정:{a["des_date"]}  {a.get("elapsed_biz","")}영업일\n'
                f'    현재가 <b>{a["today_close"]:,}원</b>\n'
                f'    ① {a["t5_close"]:,}×{t5p}%={a["tp5"]:,} ✅  '
                f'② {a["t15_close"]:,}×{t15p}%={a["tp15"]:,} ✅  '
                f'③ 신고가 아님 ✅'
            )

    if cond12_ok:
        lines.append('  <b>[①② 충족 — 오늘 신고가만 안 찍으면 내일 해제]</b>')
        for a in cond12_ok:
            mkt  = a['market']
            t5p  = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[0] * 100)
            t15p = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[1] * 100)
            watch_price = a.get('high15', 0)
            lines.append(
                f'  • <b>{a["name"]}</b> ({a["code"]})  지정:{a["des_date"]}  {a.get("elapsed_biz","")}영업일\n'
                f'    현재가 <b>{a["today_close"]:,}원</b>  |  15일 최고가: {watch_price:,}원\n'
                f'    ① {a["t5_close"]:,}×{t5p}%={a["tp5"]:,} ✅  '
                f'② {a["t15_close"]:,}×{t15p}%={a["tp15"]:,} ✅\n'
                f'    ③ 오늘 <b>{watch_price:,}원 미경신</b> 유지 필요 → 경신 시 이연'
            )

    if not bet_candidates:
        # 가장 가까운 종목 1개 힌트
        eligible = [a for a in analyses if a.get('today_close')]
        if eligible:
            closest = min(eligible, key=lambda a: (
                max(a['today_close'] / a['tp5'] if a['tp5'] else 99,
                    a['today_close'] / a['tp15'] if a['tp15'] else 99)))
            need_drop1 = round((1 - closest['tp5']  / closest['today_close']) * 100, 1) if closest['tp5'] < closest['today_close'] else 0
            need_drop2 = round((1 - closest['tp15'] / closest['today_close']) * 100, 1) if closest['tp15'] < closest['today_close'] else 0
            lines.append(f'  없음  (가장 가까운 종목: {closest["name"]}')
            if need_drop1 > 0 or need_drop2 > 0:
                lines.append(f'   ① -{need_drop1}%  ② -{need_drop2}% 추가 하락 필요)')
            else:
                lines.append('   ③ 신고가 경신 중)')
        else:
            lines.append('  없음 (10영업일 이상 경과 종목 없음)')

    lines.append('')
    lines.append(f'━━  전체 투경 {len(stocks)}종목  |  신규 {len(new_stocks)}  |  해제 {len(released_stocks)}  ━━')

    return '\n'.join(lines)


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='KIND 투자경고 일일 브리핑')
    parser.add_argument('--save', action='store_true', help='투경현황.json 저장')
    parser.add_argument('--tg',   action='store_true', help='텔레그램 전송')
    args = parser.parse_args()

    # 1. 전날 목록 로드 (신규/해제 비교용)
    prev_names: set[str] = set()
    prev_stocks: dict[str, dict] = {}
    if WARN_JSON.exists():
        try:
            old = json.loads(WARN_JSON.read_text(encoding='utf-8'))
            for s in old.get('stocks', []):
                prev_names.add(s['name'])
                prev_stocks[s['name']] = s
        except:
            pass

    # 2. KIND 크롤링
    print(f'[{TODAY}] KIND 투자경고 크롤링...')
    stocks = fetch_kind_warn_list()

    if not stocks:
        print('결과 없음. 페이지 구조 변경 가능성.')
        return

    today_names = {s['name'] for s in stocks}

    # 신규 지정 = 오늘 목록에 있고 전날 목록에 없는 것
    new_stocks = [s for s in stocks if s['name'] not in prev_names]

    # 해제 = 전날 목록에 있었고 오늘 목록에 없는 것
    released_stocks = [prev_stocks[n] for n in prev_names if n not in today_names]

    print(f'전체 {len(stocks)}종목  |  신규 {len(new_stocks)}  |  해제 {len(released_stocks)}')
    print_warn_list(stocks)

    # 3. 종목코드 enrichment
    enriched = []
    for s in stocks:
        code, market = get_stock_info(s['name'])
        enriched.append({
            'name':     s['name'],
            'code':     code or prev_stocks.get(s['name'], {}).get('code', ''),
            'des_date': s['des_date'],
            'type':     'warning',
        })

    # 신규/해제에도 코드 보완
    for s in new_stocks:
        if 'code' not in s or not s.get('code'):
            code, _ = get_stock_info(s['name'])
            s['code'] = code
    for s in released_stocks:
        if 'code' not in s or not s.get('code'):
            code, _ = get_stock_info(s['name'])
            s['code'] = code

    # 4. JSON 저장
    if args.save:
        WARN_JSON.parent.mkdir(parents=True, exist_ok=True)
        out = {'updated': TODAY, 'stocks': enriched}
        WARN_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'저장: {WARN_JSON}')

        # raw/telegram/ MD 저장
        TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
        md_path = TELEGRAM_DIR / f'{TODAY}_투경현황.md'
        md_lines = [f'# 투자경고 현황  {TODAY}  ({len(enriched)}종목)',
                    f'> 신규: {len(new_stocks)}  해제: {len(released_stocks)}\n',
                    '| 종목명 | 코드 | 지정일 | 경과 |',
                    '|--------|------|--------|------|']
        for e in enriched:
            biz = business_days_elapsed(e['des_date'], TODAY_DT)
            md_lines.append(f'| {e["name"]} | {e["code"]} | {e["des_date"]} | {biz}영업일 |')
        md_path.write_text('\n'.join(md_lines), encoding='utf-8')
        print(f'MD 저장: {md_path}')

    # 5. 해제 조건 분석 (10영업일 이상 경과 종목만)
    print('\n해제 조건 분석 중...')
    analyses = []
    for e in enriched:
        if business_days_elapsed(e['des_date'], TODAY_DT) < 10:
            continue
        a = analyze_release(e['name'], e['code'],
                            _mkt_cache.get(e['name'], 'KOSDAQ'), e['des_date'])
        analyses.append(a)
        print(f'  {e["name"]} ({e["code"]}): {a["note"]}')

    print_analysis(analyses)

    # 6. 대시보드 HTML 생성 (항상)
    generate_dashboard(enriched, analyses, new_stocks, released_stocks)

    # 7. 텔레그램
    if args.tg:
        msg = build_tg_message(stocks, analyses, new_stocks, released_stocks)
        send_telegram(msg)
        print('텔레그램 전송 완료')


# ── 대시보드 HTML 생성 ────────────────────────────────────────────────────
def generate_dashboard(stocks: list[dict], analyses: list[dict],
                       new_stocks: list[dict], released_stocks: list[dict]):
    out_dir = BASE_DIR / 'out'
    out_dir.mkdir(exist_ok=True)
    path = out_dir / '투경_대시보드.html'

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    next_biz = TODAY_DT + timedelta(days=1)
    while next_biz.weekday() >= 5:
        next_biz += timedelta(days=1)
    next_biz_str = next_biz.strftime('%m/%d')

    can_release = [a for a in analyses if a.get('can_release') and a.get('today_close')]
    cond12_ok   = [a for a in analyses if not a.get('can_release')
                   and a.get('cond1') and a.get('cond2') and a.get('today_close')]
    bet_candidates = can_release + cond12_ok

    def cond_badge(ok: bool, label: str) -> str:
        cls = 'ok' if ok else 'ng'
        return f'<span class="cond {cls}">{"✅" if ok else "❌"} {label}</span>'

    def stock_row(e: dict) -> str:
        biz = business_days_elapsed(e['des_date'], TODAY_DT)
        a   = next((x for x in analyses if x['name'] == e['name']), None)
        code = e.get('code', '')
        kind_url = f'https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage&searchCorpCode={code}'

        if biz < 10:
            status_html = f'<span class="badge wait">⏳ {biz}영업일 (해제검토 전)</span>'
            conds_html  = ''
        elif a and a.get('today_close'):
            if a.get('can_release'):
                status_html = f'<span class="badge green">🟢 내일({next_biz_str}) 해제 예상</span>'
            elif a.get('cond1') and a.get('cond2'):
                status_html = f'<span class="badge orange">🔥 신고가만 안 찍으면 해제</span>'
            else:
                status_html = f'<span class="badge red">🔴 {biz}영업일 유지 중</span>'
            mkt = a['market']
            t5p  = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[0] * 100)
            t15p = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[1] * 100)
            l1 = f'T-5 {a["t5_close"]:,}x{t5p}%={a["tp5"]:,}'
            l2 = f'T-15 {a["t15_close"]:,}x{t15p}%={a["tp15"]:,}'
            conds_html = (
                cond_badge(a['cond1'], l1) + ' '
                + cond_badge(a['cond2'], l2) + ' '
                + cond_badge(a['cond3'], '신고가 아님')
                + f'<br><small>현재가 {a["today_close"]:,}원</small>'
            )
        else:
            status_html = f'<span class="badge gray">— {biz}영업일</span>'
            conds_html  = ''

        return f'''
        <tr>
          <td><a href="{kind_url}" target="_blank" class="stock-link">{e["name"]}</a></td>
          <td class="code">{code}</td>
          <td>{e["des_date"]}</td>
          <td class="biz">{biz}</td>
          <td>{status_html}</td>
          <td class="conds">{conds_html}</td>
        </tr>'''

    rows_html = '\n'.join(stock_row(e) for e in stocks)

    def bet_card(a: dict) -> str:
        mkt  = a['market']
        t5p  = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[0] * 100)
        t15p = int(MARKET_THRESH.get(mkt, (1.60, 2.00))[1] * 100)
        if a.get('can_release'):
            verdict = f'<div class="verdict green">✅ 3조건 모두 충족 — 내일({next_biz_str}) 해제 확실</div>'
        else:
            verdict = f'<div class="verdict orange">⚠️ ①② 충족 — 오늘 {a.get("high15",0):,}원 미경신 시 내일 해제</div>'
        return f'''
        <div class="bet-card">
          <div class="bet-name">{a["name"]} <span class="bet-code">({a["code"]})</span>
            <span class="bet-mkt">{mkt}</span></div>
          <div class="bet-price">현재가 <b>{a["today_close"]:,}원</b>  |  지정일 {a["des_date"]}  |  {a.get("elapsed_biz",0)}영업일</div>
          <div class="bet-conds">
            {cond_badge(a["cond1"], "T-5 " + str(a['t5_close']) + "x" + str(t5p) + "%=" + str(a['tp5']))}
            {cond_badge(a["cond2"], "T-15 " + str(a['t15_close']) + "x" + str(t15p) + "%=" + str(a['tp15']))}
            {cond_badge(a["cond3"], "15일최고가 " + str(a.get("high15", 0)))}
          </div>
          {verdict}
        </div>'''

    bets_html = ''.join(bet_card(a) for a in bet_candidates) if bet_candidates else '<p class="none-text">없음</p>'

    def event_chip(s: dict, color: str) -> str:
        biz = business_days_elapsed(s['des_date'], TODAY_DT)
        label = f'{biz}영업일 만에 해제' if color == 'green' else f'지정:{s["des_date"]}'
        return f'<div class="chip {color}"><b>{s["name"]}</b> ({s.get("code","")}) {label}</div>'

    released_html = ''.join(event_chip(s, 'green') for s in released_stocks) or '<span class="none-text">없음</span>'
    new_html      = ''.join(event_chip(s, 'red')   for s in new_stocks)       or '<span class="none-text">없음</span>'

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>투경 대시보드 {TODAY}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', sans-serif; font-size: 14px; padding: 20px; }}
  h1 {{ font-size: 20px; color: #58a6ff; margin-bottom: 4px; }}
  .meta {{ color: #8b949e; font-size: 12px; margin-bottom: 24px; }}
  .meta b {{ color: #f0f6fc; }}

  /* 상단 요약 카드 */
  .summary {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
  .sum-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
               padding: 14px 20px; flex: 1; min-width: 130px; }}
  .sum-card .num {{ font-size: 32px; font-weight: 700; line-height: 1; }}
  .sum-card .lbl {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}
  .sum-card.red   .num {{ color: #f85149; }}
  .sum-card.green .num {{ color: #3fb950; }}
  .sum-card.orange .num {{ color: #d29922; }}
  .sum-card.blue  .num {{ color: #58a6ff; }}

  /* 섹션 */
  .section {{ margin-bottom: 28px; }}
  .section-title {{ font-size: 15px; font-weight: 600; margin-bottom: 12px;
                    padding-bottom: 6px; border-bottom: 1px solid #21262d; }}
  .section-title.green {{ color: #3fb950; }}
  .section-title.red   {{ color: #f85149; }}
  .section-title.gold  {{ color: #d29922; }}
  .section-title.blue  {{ color: #58a6ff; }}

  /* 이벤트 칩 */
  .chip {{ display: inline-block; padding: 5px 12px; border-radius: 20px;
           font-size: 13px; margin: 3px; }}
  .chip.green {{ background: #0d4429; border: 1px solid #3fb950; color: #3fb950; }}
  .chip.red   {{ background: #3d0914; border: 1px solid #f85149; color: #f85149; }}
  .none-text  {{ color: #8b949e; font-size: 13px; }}

  /* 종가배팅 카드 */
  .bet-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
               padding: 14px 16px; margin-bottom: 10px; }}
  .bet-name {{ font-size: 16px; font-weight: 700; color: #f0f6fc; }}
  .bet-code {{ font-size: 12px; color: #8b949e; font-weight: 400; }}
  .bet-mkt  {{ font-size: 11px; background: #21262d; padding: 2px 6px; border-radius: 4px;
               color: #8b949e; margin-left: 6px; }}
  .bet-price {{ margin: 6px 0; color: #8b949e; font-size: 13px; }}
  .bet-price b {{ color: #f0f6fc; font-size: 15px; }}
  .bet-conds {{ margin: 8px 0; display: flex; gap: 6px; flex-wrap: wrap; }}
  .verdict {{ padding: 8px 12px; border-radius: 6px; font-size: 13px; margin-top: 8px; font-weight: 600; }}
  .verdict.green  {{ background: #0d4429; color: #3fb950; }}
  .verdict.orange {{ background: #3d2e00; color: #d29922; }}

  /* 조건 뱃지 */
  .cond {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; margin: 2px; display: inline-block; }}
  .cond.ok {{ background: #0d4429; color: #3fb950; }}
  .cond.ng {{ background: #3d0914; color: #f85149; }}

  /* 전체 목록 테이블 */
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #161b22; color: #8b949e; font-size: 12px; font-weight: 600;
        padding: 8px 10px; text-align: left; border-bottom: 1px solid #30363d; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }}
  tr:hover td {{ background: #161b22; }}
  .stock-link {{ color: #58a6ff; text-decoration: none; font-weight: 600; }}
  .stock-link:hover {{ text-decoration: underline; }}
  .code {{ color: #8b949e; font-size: 12px; }}
  .biz  {{ color: #8b949e; font-size: 12px; text-align: center; }}
  .conds {{ font-size: 11px; }}
  .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .badge.green  {{ background: #0d4429; color: #3fb950; }}
  .badge.orange {{ background: #3d2e00; color: #d29922; }}
  .badge.red    {{ background: #3d0914; color: #f85149; }}
  .badge.wait   {{ background: #21262d; color: #8b949e; }}
  .badge.gray   {{ background: #21262d; color: #6e7681; }}
</style>
<script>
  // 10초마다 자동 새로고침
  setTimeout(() => location.reload(), 60000);
</script>
</head>
<body>

<h1>📊 투경 대시보드</h1>
<p class="meta">업데이트: <b>{now_str}</b>  |  기준: KIND 공식 데이터  |  매 7:00 / 14:30 자동 갱신</p>

<!-- 요약 카드 -->
<div class="summary">
  <div class="sum-card blue">
    <div class="num">{len(stocks)}</div>
    <div class="lbl">전체 투경 중</div>
  </div>
  <div class="sum-card red">
    <div class="num">{len(new_stocks)}</div>
    <div class="lbl">오늘 신규 지정</div>
  </div>
  <div class="sum-card green">
    <div class="num">{len(released_stocks)}</div>
    <div class="lbl">오늘 해제</div>
  </div>
  <div class="sum-card orange">
    <div class="num">{len(bet_candidates)}</div>
    <div class="lbl">종가배팅 후보<br><small>({next_biz_str} 해제 예상)</small></div>
  </div>
</div>

<!-- 섹션 1: 종가배팅 후보 -->
<div class="section">
  <div class="section-title gold">💰 오늘 종가배팅 후보 — 내일({next_biz_str}) 해제 예상</div>
  {bets_html}
</div>

<!-- 섹션 2: 오늘 이벤트 -->
<div class="section">
  <div class="section-title green">🟢 오늘 해제 확정</div>
  {released_html}
</div>
<div class="section">
  <div class="section-title red">🔴 오늘 신규 지정 — 종가배팅 제외</div>
  {new_html}
</div>

<!-- 섹션 3: 전체 목록 -->
<div class="section">
  <div class="section-title blue">📋 전체 투경 목록 ({len(stocks)}종목)</div>
  <table>
    <thead>
      <tr>
        <th>종목명</th><th>코드</th><th>지정일</th><th style="text-align:center">영업일</th>
        <th>상태</th><th>해제 조건 (T-5·T-15·신고가 — 고정 지정일 기준)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>

</body>
</html>'''

    path.write_text(html, encoding='utf-8')
    print(f'대시보드: {path}')


from datetime import datetime as _DT_CLS
datetime = _DT_CLS


if __name__ == '__main__':
    main()
