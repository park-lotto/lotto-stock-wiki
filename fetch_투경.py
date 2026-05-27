"""
투자경고·투자위험(단일가) 일일 모니터링 스크립트

데이터 소스:
  - KIND (Selenium, 매일): 투경/단일가 목록 + 실제 지정일
  - pykrx: 종가 데이터 (KRX 공식)
  - 로컬 stock_db.json: 지정일·코드 영구 캐시

실행:
  python fetch_투경.py        ← 매일 기본
  python fetch_투경.py --tg   ← + 텔레그램 전송

투경 해제 조건 (raw/투경해제 공식.xlsx 실증 검증 완료 2026-05-27):
  코스닥: 당일 < T-5×160% AND 당일 < T-15×200% AND 당일 ≠ 최근15일최고가
  코스피: 당일 < T-5×145% AND 당일 < T-15×175% AND 당일 ≠ 최근15일최고가
  ★ 3가지 모두(AND) 해소여야 해제. 하나라도 살아있으면 이연.
"""

import sys, time, os, json, argparse, urllib.request, urllib.parse, requests
from datetime import datetime, date, timedelta
from pathlib import Path
from pykrx import stock as pyk
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

sys.stdout.reconfigure(encoding='utf-8')

TODAY    = datetime.now().strftime('%Y-%m-%d')
TODAY_DT = date.today()
BASE_DIR = Path(__file__).parent

KIND_URL = ('https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
            '?method=investattentwarnriskyMain')

STOCK_DB_JSON    = "raw/투경/stock_db.json"
PREV_ACTIVE_JSON = "raw/투경/투경_활성_최신.json"
OUTPUT_RELEASE_MD = f"raw/투경/투경_해제분석_{TODAY}.md"

RELEASE_ELIGIBLE_BUSINESS_DAYS = 10

MARKET_THRESH = {
    'KOSDAQ': (1.60, 2.00),
    'KOSPI':  (1.45, 1.75),
    'KONEX':  (1.45, 1.75),
}

KRX_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://data.krx.co.kr/',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}

IMMINENT_GAP_PCT = 10.0
CLOSE_GAP_PCT    = 25.0

_code_cache:   dict[str, str] = {}
_market_cache: dict[str, str] = {}


# ── 영업일 계산 ───────────────────────────────────────────────────────────
def business_days_elapsed(start: date, end: date) -> int:
    """지정일 포함 inclusive 영업일 수. 5/14→5/27=10."""
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count


# ── 텔레그램 ──────────────────────────────────────────────────────────────
def _load_env() -> dict:
    cfg = {}
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


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


# ── 로컬 DB ───────────────────────────────────────────────────────────────
def load_stock_db() -> dict:
    if not os.path.exists(STOCK_DB_JSON):
        return {}
    with open(STOCK_DB_JSON, encoding='utf-8') as f:
        return json.load(f)


def save_stock_db(db: dict):
    os.makedirs('raw/투경', exist_ok=True)
    with open(STOCK_DB_JSON, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ── KRX 코드·시장 조회 ─────────────────────────────────────────────────────
def get_stock_code(name: str) -> str:
    if name in _code_cache:
        return _code_cache[name]
    try:
        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu',
                  'mktsel': 'ALL', 'searchText': name,
                  'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers=KRX_HEADERS, timeout=5)
        block = r.json().get('block1', [])
        if block:
            _code_cache[name] = block[0]['short_code']
            return _code_cache[name]
    except:
        pass
    return ''


def get_stock_market(code: str) -> str:
    if code in _market_cache:
        return _market_cache[code]
    try:
        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={'bld': 'dbms/comm/finder/finder_stkisu',
                  'mktsel': 'ALL', 'searchText': code,
                  'pagePath': '/contents/MDC/MDI/index.jsp'},
            headers=KRX_HEADERS, timeout=5)
        for item in r.json().get('block1', []):
            if item.get('short_code') == code:
                mkt = (item.get('mktId', '') or '').upper()
                result = ('KOSPI'  if 'KOSPI' in mkt or mkt in ('STK', 'JSE')
                          else 'KONEX' if 'KONEX' in mkt or mkt in ('NXT', 'KNX')
                          else 'KOSDAQ')
                _market_cache[code] = result
                return result
    except:
        pass
    return 'KOSDAQ'


# ── pykrx 종가 수집 ───────────────────────────────────────────────────────
def get_close_prices(code: str, n: int = 20) -> list[tuple[str, int]]:
    """최근 n개 영업일 종가 (newest-first). pykrx 사용."""
    if not code:
        return []
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
        print(f"    pykrx 오류 ({code}): {e}")
        return []


# ── KIND Selenium ─────────────────────────────────────────────────────────
def _make_driver():
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--log-level=3')
    return webdriver.Chrome(options=opts)


def _parse_kind_table(driver) -> list[dict]:
    rows = []
    for t in driver.find_elements(By.TAG_NAME, 'table'):
        trs = t.find_elements(By.TAG_NAME, 'tr')
        if len(trs) < 3:
            continue
        for tr in trs:
            tds = tr.find_elements(By.TAG_NAME, 'td')
            if len(tds) >= 4 and tds[1].text.strip():
                name     = tds[1].text.strip()
                pub_date = tds[2].text.strip() if len(tds) > 2 else ''
                des_date = tds[3].text.strip() if len(tds) > 3 else ''
                if name and des_date:
                    rows.append({'name': name, 'pub_date': pub_date,
                                 'des_date': des_date})
    return rows


def _scrape_tab(driver, tab_num: int) -> list[dict]:
    """KIND 특정 탭 전체 수집 (페이지네이션 처리)."""
    driver.execute_script(f'fnViewTab({tab_num});')
    time.sleep(4)

    start = (TODAY_DT - timedelta(days=90)).strftime('%Y-%m-%d')
    driver.execute_script(
        f"document.getElementById('startDate').value='{start}';"
        f"document.getElementById('endDate').value='{TODAY}';"
    )
    driver.execute_script('fnSearch();')
    time.sleep(4)

    seen, all_rows = set(), []
    page = 1
    while page <= 20:
        cur_rows = _parse_kind_table(driver)
        added = 0
        for r in cur_rows:
            k = (r['name'], r['des_date'])
            if k not in seen:
                seen.add(k)
                all_rows.append(r)
                added += 1
        if added == 0:
            break
        try:
            clicked = False
            for a in driver.find_elements(By.TAG_NAME, 'a'):
                if (a.text.strip() in ('다음', '>')
                        or (a.get_attribute('title') or '') == '다음'):
                    a.click()
                    time.sleep(3)
                    clicked = True
                    break
            if not clicked:
                driver.execute_script(f'goPage({page + 1});')
                time.sleep(3)
                check = _parse_kind_table(driver)
                if not any((r['name'], r['des_date']) not in seen
                           for r in check if r['name']):
                    break
        except:
            break
        page += 1

    return all_rows


def fetch_kind_all() -> dict:
    """KIND Selenium: 투경(tab1) + 단일가(tab2) 전체 수집."""
    driver = _make_driver()
    result = {'warning': [], 'risk': []}
    try:
        driver.get(KIND_URL)
        time.sleep(6)
        print('    투경 탭 수집...')
        result['warning'] = _scrape_tab(driver, 1)
        print(f'    → {len(result["warning"])}건')
        print('    단일가 탭 수집...')
        result['risk'] = _scrape_tab(driver, 2)
        print(f'    → {len(result["risk"])}건')
    except Exception as e:
        print(f"  KIND 오류: {e}")
    finally:
        driver.quit()
    return result


# ── 해제 조건 분석 ────────────────────────────────────────────────────────
def analyze_release(name: str, code: str, des_date_str: str,
                    market: str = '', elapsed_days: int = 0) -> dict:
    base = {
        'name': name, 'code': code, 'des_date': des_date_str,
        'market': market or 'KOSDAQ', 'elapsed_days': elapsed_days,
        'eligible': False, 'can_release': False, 'today_close': None,
        'cond1_ok': None, 'cond2_ok': None, 'cond3_ok': None,
        'thresh_t5': None, 'thresh_t15': None,
        'thresh_price_t5': None, 'thresh_price_t15': None,
        't5_ratio': None, 't15_ratio': None, 'note': '',
    }
    try:
        des_dt = datetime.strptime(des_date_str, '%Y-%m-%d').date()
    except:
        base['note'] = '날짜 파싱 실패'
        return base

    elapsed = elapsed_days or (TODAY_DT - des_dt).days
    base['elapsed_days'] = elapsed

    elapsed_biz = business_days_elapsed(des_dt, TODAY_DT)
    if elapsed_biz < RELEASE_ELIGIBLE_BUSINESS_DAYS:
        base['note'] = f'10영업일 미경과 ({elapsed_biz}영업일/{elapsed}일)'
        return base

    base['eligible'] = True
    if not market:
        market = get_stock_market(code)
        base['market'] = market
    t5_thresh, t15_thresh = MARKET_THRESH.get(market, MARKET_THRESH['KOSDAQ'])
    base['thresh_t5'], base['thresh_t15'] = t5_thresh, t15_thresh

    prices = get_close_prices(code, 20)
    if len(prices) < 16:
        base['note'] = f'주가 데이터 부족 ({len(prices)}건)'
        return base

    today_close = prices[0][1]
    t5_close    = prices[5][1]
    t15_close   = prices[15][1]
    high15      = max(p[1] for p in prices[:15])

    cond1_ok = today_close < t5_close  * t5_thresh
    cond2_ok = today_close < t15_close * t15_thresh
    cond3_ok = today_close != high15

    tp5, tp15   = int(t5_close * t5_thresh), int(t15_close * t15_thresh)
    pct5, pct15 = int((t5_thresh - 1) * 100), int((t15_thresh - 1) * 100)

    base.update({
        'today_close': today_close,
        't5_close': t5_close, 't15_close': t15_close, 'high15': high15,
        'cond1_ok': cond1_ok, 'cond2_ok': cond2_ok, 'cond3_ok': cond3_ok,
        'can_release': cond1_ok and cond2_ok and cond3_ok,
        'thresh_price_t5': tp5, 'thresh_price_t15': tp15,
        't5_ratio':  round(today_close / t5_close  * 100, 1) if t5_close  else 0,
        't15_ratio': round(today_close / t15_close * 100, 1) if t15_close else 0,
    })

    if base['can_release']:
        base['note'] = (f'3조건 모두 해소 → 내일 해제 예상 '
                        f'(①{base["t5_ratio"]}%<{pct5}% ②{base["t15_ratio"]}%<{pct15}% ③✅)')
    else:
        parts = []
        if not cond1_ok:
            gap = (today_close / tp5 - 1) * 100 if tp5 else 0
            parts.append(f'①T5 {base["t5_ratio"]}%≥{pct5}% (+{gap:.1f}%)')
        if not cond2_ok:
            gap = (today_close / tp15 - 1) * 100 if tp15 else 0
            parts.append(f'②T15 {base["t15_ratio"]}%≥{pct15}% (+{gap:.1f}%)')
        if not cond3_ok:
            parts.append(f'③최고가={today_close:,}')
        base['note'] = '유지: ' + ' | '.join(parts)

    return base


# ── 임박도 분류 ───────────────────────────────────────────────────────────
def classify_imminence(r: dict) -> str:
    if not r.get('eligible'):
        return 'ineligible'
    if r.get('can_release'):
        return 'release'
    unsolved = [not r.get('cond1_ok', True),
                not r.get('cond2_ok', True),
                not r.get('cond3_ok', True)]
    if sum(unsolved) >= 2:
        return 'maintain'
    if unsolved[2]:
        return 'imminent'
    tp = r.get('thresh_price_t5' if unsolved[0] else 'thresh_price_t15', 0)
    if not tp or not r.get('today_close'):
        return 'maintain'
    gap = (r['today_close'] / tp - 1) * 100
    return 'imminent' if gap <= IMMINENT_GAP_PCT else 'close' if gap <= CLOSE_GAP_PCT else 'maintain'


# ── 단일가 단계 ───────────────────────────────────────────────────────────
def get_risk_phase(des_date_str: str) -> dict:
    try:
        des = datetime.strptime(des_date_str, '%Y-%m-%d').date()
    except:
        return {'phase': 'unknown', 'msg': '날짜 확인 필요'}
    next_day  = des + timedelta(days=1)
    biz_after = business_days_elapsed(next_day, TODAY_DT) if next_day <= TODAY_DT else 0
    if   biz_after == 0: return {'phase': 'halt',    'msg': '⛔ 오늘 거래정지 → 내일부터 3거래일 단일가'}
    elif biz_after == 1: return {'phase': 'single1', 'msg': '📍 단일가 1/3일차 → 내일 2일차'}
    elif biz_after == 2: return {'phase': 'single2', 'msg': '📍 단일가 2/3일차 → 내일 3일차(마지막)'}
    elif biz_after == 3: return {'phase': 'single3', 'msg': '⚡ 단일가 3/3일차 → <b>내일 연속체결 복귀</b> 🟢'}
    else:                return {'phase': 'resumed', 'msg': f'단일가 종료({biz_after-3}일 경과) — 해제 공시 확인 필요'}


# ── 텔레그램 메시지 ────────────────────────────────────────────────────────
def build_tg_message(new_warning: list, new_risk: list,
                     warn_analysis: list, risk_stocks: list) -> str:
    can_release   = [r for r in warn_analysis if r['can_release']]
    imminent_list = [r for r in warn_analysis
                     if not r['can_release'] and r.get('eligible')
                     and classify_imminence(r) in ('imminent', 'close')]
    maintain_list = [r for r in warn_analysis
                     if not r['can_release'] and r.get('eligible')
                     and classify_imminence(r) == 'maintain']

    lines = [
        f"🚨 <b>투경 브리핑</b>  {TODAY}",
        f"투경 <b>{len(warn_analysis)}종목</b>  |  단일가 <b>{len(risk_stocks)}종목</b>",
        "",
    ]

    if new_warning:
        lines.append("━━━ 🆕 오늘 신규 투경지정 ━━━")
        if len(new_warning) <= 5:
            for s in new_warning:
                lines.append(f"• <b>{s['name']}</b>  ({s.get('code', '-')})")
        else:
            sample = ', '.join(s['name'] for s in new_warning[:4])
            lines.append(f"• {len(new_warning)}종목: {sample} 외 {len(new_warning)-4}종목")
        lines.append("")

    if new_risk:
        lines.append("━━━ 🆕 오늘 신규 단일가 지정 ━━━")
        for s in new_risk:
            lines.append(
                f"• <b>{s['name']}</b> ({s.get('market', '-')})  "
                "오늘 거래정지 → 내일부터 3거래일 단일가"
            )
        lines.append("")

    if can_release:
        lines.append("━━━ 🟢 해제 가능 — 내일 해제 예상 ━━━")
        for r in can_release:
            pct5  = int((r.get('thresh_t5',  1.6) - 1) * 100)
            pct15 = int((r.get('thresh_t15', 2.0) - 1) * 100)
            lines.append(
                f"• <b>{r['name']}</b> ({r.get('market', '-')})  {r['des_date']} 지정"
            )
            lines.append(
                f"  ①{r.get('t5_ratio')}%&lt;{pct5}% ✅  "
                f"②{r.get('t15_ratio')}%&lt;{pct15}% ✅  ③✅"
            )
        lines.append("")

    if imminent_list:
        lines.append("━━━ 🔥 해제 임박 ━━━")
        for r in imminent_list:
            tag = '🔥임박' if classify_imminence(r) == 'imminent' else '📍근접'
            lines.append(
                f"• <b>{r['name']}</b> ({r.get('market', '-')})  "
                f"{r['des_date']} 지정  {tag}"
            )
            if not r.get('cond1_ok') and r.get('today_close'):
                tp5 = r.get('thresh_price_t5', 0)
                gap = (r['today_close'] / tp5 - 1) * 100 if tp5 else 0
                lines.append(f"  ❌① 기준가 {tp5:,}원 / 현재 {r['today_close']:,}원  (-{gap:.1f}% 하락시 해소)")
            if not r.get('cond2_ok') and r.get('today_close'):
                tp15 = r.get('thresh_price_t15', 0)
                gap  = (r['today_close'] / tp15 - 1) * 100 if tp15 else 0
                lines.append(f"  ❌② 기준가 {tp15:,}원 / 현재 {r['today_close']:,}원  (-{gap:.1f}% 하락시 해소)")
            if not r.get('cond3_ok') and r.get('today_close'):
                lines.append(f"  ❌③ 오늘 최고가 {r['today_close']:,}원  → 내일 신고가 미경신시 해소")
        lines.append("")

    if maintain_list:
        lines.append("━━━ 🔴 조건 미해소 유지 ━━━")
        for r in maintain_list:
            c1 = '✅' if r.get('cond1_ok') else '❌'
            c2 = '✅' if r.get('cond2_ok') else '❌'
            c3 = '✅' if r.get('cond3_ok') else '❌'
            lines.append(
                f"• {r['name']} ({r.get('market', '-')})  "
                f"①{c1}②{c2}③{c3}  {r.get('note', '')}"
            )
        lines.append("")

    if risk_stocks:
        lines.append("━━━ 🔴 단일가 현황 ━━━")
        for r in risk_stocks:
            phase = get_risk_phase(r.get('des_date_risk', TODAY))
            lines.append(
                f"• <b>{r['name']}</b> ({r.get('market', '-')})  {phase['msg']}"
            )
        lines.append("  ※ 단일가→연속체결 복귀 시 매수 대기 물량 한번에 터짐")
        lines.append("")

    return "\n".join(lines)


# ── 분석 결과 저장 ────────────────────────────────────────────────────────
def save_release_md(warn_analysis: list, risk_stocks: list):
    can_release   = [r for r in warn_analysis if r['can_release']]
    imminent_list = [r for r in warn_analysis
                     if not r['can_release'] and r.get('eligible')
                     and classify_imminence(r) in ('imminent', 'close')]
    maintain_list = [r for r in warn_analysis
                     if not r['can_release'] and r.get('eligible')
                     and classify_imminence(r) == 'maintain']
    ineligible    = [r for r in warn_analysis if not r.get('eligible')]

    lines = [
        f'# 투경 해제 조건 분석  {TODAY}',
        f'> 투경 {len(warn_analysis)}종목  |  단일가 {len(risk_stocks)}종목',
        f'> 🟢 해제가능 {len(can_release)}  🔶 임박 {len(imminent_list)}  🔴 유지 {len(maintain_list)}',
        '', '### 해제 판단 기준', '```',
        '코스닥: T<T-5×160% AND T<T-15×200% AND T≠최근15일최고가',
        '코스피: T<T-5×145% AND T<T-15×175% AND T≠최근15일최고가',
        '★ 3가지 모두(AND) 해소여야 해제', '```', '',
    ]

    if can_release:
        lines += ['## 🟢 해제 가능', '',
                  '| 종목 | 시장 | 지정일 | 경과 | 현재가 | T5비율 | T15비율 |',
                  '|------|------|--------|------|--------|--------|--------|']
        for r in can_release:
            close = f"{r['today_close']:,}" if r.get('today_close') else '-'
            lines.append(f"| **{r['name']}** | {r.get('market','-')} | {r['des_date']} "
                         f"| {r.get('elapsed_days','-')}일 | {close} "
                         f"| {r.get('t5_ratio','-')}% | {r.get('t15_ratio','-')}% |")
        lines.append('')

    if imminent_list:
        lines += ['## 🔶 해제 임박', '',
                  '| 종목 | 시장 | 경과 | 미해소 조건 | 임박도 |',
                  '|------|------|------|-----------|-------|']
        for r in imminent_list:
            tag = '🔥임박' if classify_imminence(r) == 'imminent' else '📍근접'
            parts = []
            if not r.get('cond1_ok'):
                tp5  = r.get('thresh_price_t5', 0)
                gap  = (r['today_close'] / tp5 - 1) * 100 if tp5 else 0
                parts.append(f'①T5(-{gap:.1f}%)')
            if not r.get('cond2_ok'):
                tp15 = r.get('thresh_price_t15', 0)
                gap  = (r['today_close'] / tp15 - 1) * 100 if tp15 else 0
                parts.append(f'②T15(-{gap:.1f}%)')
            if not r.get('cond3_ok'):
                parts.append('③최고가(내일무갱신)')
            lines.append(f"| **{r['name']}** | {r.get('market','-')} "
                         f"| {r.get('elapsed_days','-')}일 | {', '.join(parts)} | {tag} |")
        lines.append('')

    if maintain_list:
        lines += ['## 🔴 유지 중', '',
                  '| 종목 | 시장 | 현재가 | T5비율 | T15비율 | 조건 |',
                  '|------|------|--------|--------|--------|------|']
        for r in maintain_list:
            c1 = '✅' if r.get('cond1_ok') else '❌'
            c2 = '✅' if r.get('cond2_ok') else '❌'
            c3 = '✅' if r.get('cond3_ok') else '❌'
            close = f"{r['today_close']:,}" if r.get('today_close') else r.get('note', '-')
            lines.append(f"| {r['name']} | {r.get('market','-')} | {close} "
                         f"| {r.get('t5_ratio','-')}% | {r.get('t15_ratio','-')}% | ①{c1}②{c2}③{c3} |")
        lines.append('')

    if ineligible:
        lines += ['## ⏳ 미경과', '',
                  '| 종목 | 지정일 | 경과 | 비고 |',
                  '|------|--------|------|------|']
        for r in ineligible:
            lines.append(f"| {r['name']} | {r['des_date']} "
                         f"| {r.get('elapsed_days','-')}일 | {r['note']} |")
        lines.append('')

    if risk_stocks:
        lines += ['## 🔴 투자위험(단일가)', '',
                  '| 종목 | 시장 | 단일가지정일 | 경과 | 단계 |',
                  '|------|------|------------|------|------|']
        for r in risk_stocks:
            phase = get_risk_phase(r.get('des_date_risk', TODAY))
            lines.append(f"| {r['name']} | {r.get('market','-')} "
                         f"| {r.get('des_date_risk','?')} "
                         f"| {r.get('elapsed_risk','-')}일 | {phase['msg']} |")

    os.makedirs('raw/투경', exist_ok=True)
    with open(OUTPUT_RELEASE_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return OUTPUT_RELEASE_MD


# ── 메인 루틴 ─────────────────────────────────────────────────────────────
def run_daily(send_tg: bool = False):
    print(f'[{TODAY}] 투경 일일 브리핑 시작')

    # 1. KIND Selenium — 투경 + 단일가 동시 수집
    print('  KIND 목록 수집 중...')
    kind_data   = fetch_kind_all()
    warning_now = kind_data['warning']
    risk_now    = kind_data['risk']
    print(f'  투경 {len(warning_now)}종목 / 단일가 {len(risk_now)}종목')

    # 2. 로컬 DB 로드 + 캐시 복구
    db = load_stock_db()
    for code, entry in db.items():
        if entry.get('name'):
            _code_cache[entry['name']] = code
        if entry.get('market'):
            _market_cache[code] = entry['market']

    # 3. 이전 목록 로드 (신규 감지용)
    prev_warning_codes, prev_risk_codes = set(), set()
    if os.path.exists(PREV_ACTIVE_JSON):
        try:
            with open(PREV_ACTIVE_JSON, encoding='utf-8') as f:
                prev = json.load(f)
            for r in prev.get('data', []):
                c = r.get('code', '')
                if c:
                    (prev_risk_codes if r.get('type') == 'risk'
                     else prev_warning_codes).add(c)
        except:
            pass

    # 4. DB 업데이트 + 신규 감지
    new_warning, new_risk = [], []

    def _update(s: dict, field_date: str, field_type: str,
                prev_codes: set, new_list: list):
        name     = s['name']
        des_date = s.get('des_date', '')
        code     = get_stock_code(name)
        if not code:
            print(f"    코드 조회 실패: {name}")
            return
        s['code'] = code

        if code not in db:
            db[code] = {}
        entry = db[code]
        entry['name'] = name
        entry['code'] = code
        if not entry.get('market'):
            entry['market'] = get_stock_market(code)
            _market_cache[code] = entry['market']
        entry[f'last_seen_{field_type}'] = TODAY

        if des_date:
            # KIND 실제 지정일 → approx 불필요
            if not entry.get(field_date) or des_date < entry[field_date]:
                entry[field_date] = des_date
                entry.pop(f'date_approx_{field_type}', None)
        elif not entry.get(field_date):
            entry[field_date] = TODAY
            entry[f'date_approx_{field_type}'] = True

        if code not in prev_codes:
            new_list.append(s)

    print('  DB 업데이트 중...')
    for s in warning_now:
        _update(s, 'des_date_warning', 'warning', prev_warning_codes, new_warning)

    for s in risk_now:
        code = get_stock_code(s['name'])
        if code:
            market = db.get(code, {}).get('market', '') or get_stock_market(code)
            if market == 'KONEX':
                print(f"    {s['name']} ({code}) [KONEX] — 단일가 제외")
                continue
        _update(s, 'des_date_risk', 'risk', prev_risk_codes, new_risk)

    if new_warning:
        print(f'  🆕 신규 투경: {[s["name"] for s in new_warning]}')
    if new_risk:
        print(f'  🆕 신규 단일가: {[s["name"] for s in new_risk]}')

    # 5. 투경 해제 조건 분석
    print('  해제 조건 분석 중...')
    warn_analysis = []
    for s in warning_now:
        code = s.get('code', '')
        if not code:
            continue
        entry    = db.get(code, {})
        des_date = entry.get('des_date_warning', TODAY)
        market   = entry.get('market', 'KOSDAQ')
        elapsed  = (TODAY_DT - datetime.strptime(des_date, '%Y-%m-%d').date()).days

        result = analyze_release(s['name'], code, des_date, market, elapsed)
        warn_analysis.append(result)

        tag = {'release': '🟢해제가능', 'imminent': '🔥임박',
               'close':   '📍근접',    'maintain': '🔴유지',
               'ineligible': '⏳미경과'}.get(classify_imminence(result), '')
        print(f"    {s['name'][:12]:12s} ({code}) [{market}] {tag}")
        time.sleep(0.1)

    # 6. 단일가 경과 계산 (KONEX 제외)
    risk_stocks_info = []
    for s in risk_now:
        code = s.get('code', '')
        if not code:
            continue
        entry  = db.get(code, {})
        market = entry.get('market', 'KOSDAQ')
        if market == 'KONEX':
            continue

        des          = entry.get('des_date_risk', TODAY)
        elapsed_risk = (TODAY_DT - datetime.strptime(des, '%Y-%m-%d').date()).days
        risk_stocks_info.append({
            'name': s['name'], 'code': code, 'market': market,
            'des_date_risk': des, 'elapsed_risk': elapsed_risk,
        })
    risk_stocks_info.sort(key=lambda r: r['elapsed_risk'], reverse=True)

    if risk_stocks_info:
        for r in risk_stocks_info:
            phase = get_risk_phase(r['des_date_risk'])
            print(f"    {r['name']} ({r['code']}) [{r['market']}]  {phase['msg']}")

    # 7. 파일 저장
    md = save_release_md(warn_analysis, risk_stocks_info)
    print(f'  분석 저장: {md}')

    # PREV_ACTIVE_JSON 갱신
    prev_data  = [{'name': s['name'], 'code': s.get('code',''),
                   'des_date': db.get(s.get('code',''),{}).get('des_date_warning', TODAY),
                   'type': 'warning'} for s in warning_now if s.get('code')]
    prev_data += [{'name': s['name'], 'code': s.get('code',''),
                   'des_date': db.get(s.get('code',''),{}).get('des_date_risk', TODAY),
                   'type': 'risk'} for s in risk_now if s.get('code')]
    os.makedirs('raw/투경', exist_ok=True)
    with open(PREV_ACTIVE_JSON, 'w', encoding='utf-8') as f:
        json.dump({'date': TODAY, 'data': prev_data}, f, ensure_ascii=False, indent=2)

    save_stock_db(db)

    # 8. 요약 출력
    can = [r for r in warn_analysis if r['can_release']]
    imm = [r for r in warn_analysis if not r['can_release'] and r.get('eligible')
           and classify_imminence(r) in ('imminent', 'close')]
    print()
    if can:
        print(f'  🟢 해제 가능 {len(can)}종목: {[r["name"] for r in can]}')
    if imm:
        print(f'  🔶 해제 임박/근접 {len(imm)}종목: {[r["name"] for r in imm]}')
    for r in risk_stocks_info:
        phase = get_risk_phase(r['des_date_risk'])
        print(f'  🔴 단일가: {r["name"]} — {phase["msg"]}')

    # 9. 텔레그램
    if send_tg:
        msg = build_tg_message(new_warning, new_risk, warn_analysis, risk_stocks_info)
        print()
        send_telegram(msg)


def main():
    parser = argparse.ArgumentParser(description='투자경고/단일가 일일 모니터링')
    parser.add_argument('--tg', action='store_true', help='텔레그램 전송')
    args = parser.parse_args()
    run_daily(send_tg=args.tg)


if __name__ == '__main__':
    main()
