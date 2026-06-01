"""
투자경고 해제 예측 검증기 — 2026-06-02 오전 10시 실행용

목적:
  어제(6/1) 예측한 "내일(6/2) 해제 예상 종목"이 실제로 해제됐는지 KIND로 확인
  → 공식(롤링 T-5/T-15 + 160%/200%)의 실전 정확도 검증

실행법:
  python 투경_검증_내일.py

검증 대상 (2026-06-01 예측):
  - 조이웍스앤코 (309930) : 3조건 충족
  - 제주반도체   (080220) : 3조건 충족
  - 코리아써키트  (007810) : ①② 충족, ③ 오늘 신고가(이연 가능)
  - 메디젠휴먼케어 (236340) : 3조건 충족
  - 사토시홀딩스  (223310) : 3조건 충족
  - 소룩스       (290690) : 3조건 충족
  - 에스에이엠티  (031330) : 3조건 충족
"""

import sys, json, subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from pykrx import stock as pyk
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR  = Path(__file__).parent
WARN_JSON = BASE_DIR / 'raw' / '투경' / '투경현황.json'
LOG_FILE  = BASE_DIR / 'raw' / '투경' / f'투경_검증_{date.today()}.md'

TODAY_DT  = date.today()
TODAY_STR = TODAY_DT.strftime('%Y-%m-%d')

# 어제 예측 목록
PREDICTED = [
    {'name': '조이웍스앤코',  'code': '309930', 'des': '2026-04-29', 'prediction': '3조건충족'},
    {'name': '제주반도체',    'code': '080220', 'des': '2026-05-14', 'prediction': '3조건충족'},
    {'name': '코리아써키트',  'code': '007810', 'des': '2026-05-14', 'prediction': '①②충족_③이연가능'},
    {'name': '메디젠휴먼케어','code': '236340', 'des': '2026-05-18', 'prediction': '3조건충족'},
    {'name': '사토시홀딩스',  'code': '223310', 'des': '2026-05-18', 'prediction': '3조건충족'},
    {'name': '소룩스',        'code': '290690', 'des': '2026-05-19', 'prediction': '3조건충족'},
    {'name': '에스에이엠티',  'code': '031330', 'des': '2026-05-19', 'prediction': '3조건충족'},
]

TYPE_THRESH = {
    'surge':  (1.60, 2.00),
    'unfair': (1.45, 1.75),
}
KNOWN_TYPES = {
    '080220': 'surge',   # 제주반도체 — 공시 원문 "주가급등" 확인
    '009155': 'unfair',  # 삼성전기우 — "소수계좌 거래집중" 확인
}

KIND_URL = ('https://kind.krx.co.kr/investwarn/investattentwarnrisky.do'
            '?method=investattentwarnriskyMain')


# ── 1. KIND 현재 활성 투경 목록 크롤링 ────────────────────────────────────
def fetch_active_stocks() -> set[str]:
    """KIND에서 현재 투경 중인 종목 코드 set 반환."""
    active = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        page.goto(KIND_URL, timeout=30000)
        page.wait_for_load_state('networkidle', timeout=20000)
        from_date = (TODAY_DT - timedelta(days=90)).strftime('%Y-%m-%d')
        page.evaluate(f'document.getElementById("searchFromDate").value = "{from_date}"; document.getElementById("currentPageSize").value = "100";')
        page.evaluate('fnViewTab(1)')
        page.wait_for_timeout(4000)
        page.wait_for_load_state('networkidle', timeout=15000)

        rows = page.query_selector_all('table tbody tr')
        for row in rows:
            cells = row.query_selector_all('td')
            texts = [c.inner_text().strip() for c in cells]
            if len(texts) >= 5 and texts[0].isdigit():
                name = texts[1].strip()
                active.add(name)

        browser.close()
    return active


# ── 2. 역산 검증: 어제 종가로 3조건 재계산 ──────────────────────────────
def backtest_yesterday(code: str, des_date: str, warn_type: str = 'surge') -> dict:
    """
    어제(6/1) 종가 기준으로 해제 조건 3개 계산.
    이것이 충족됐으면 → 오늘(6/2) 해제 예상이 맞았던 것.
    """
    yesterday = TODAY_DT - timedelta(days=1)
    # 주말이면 전 영업일
    while yesterday.weekday() >= 5:
        yesterday -= timedelta(days=1)

    start = (yesterday - timedelta(days=60)).strftime('%Y%m%d')
    end   = yesterday.strftime('%Y%m%d')
    try:
        df = pyk.get_market_ohlcv(start, end, code)
        if df is None or df.empty:
            return {'ok': False, 'note': '데이터 없음'}
        prices = []
        for idx in df.index[::-1]:
            c = int(df.loc[idx, '종가'])
            if c > 0:
                prices.append((idx.strftime('%Y-%m-%d'), c))
            if len(prices) >= 20:
                break
    except:
        return {'ok': False, 'note': '조회 오류'}

    if len(prices) < 16:
        return {'ok': False, 'note': f'데이터 부족({len(prices)})'}

    t5m, t15m = TYPE_THRESH.get(warn_type, TYPE_THRESH['surge'])
    today_c  = prices[0][1]
    t5_c     = prices[5][1]
    t15_c    = prices[15][1]
    tp5      = int(t5_c * t5m)
    tp15     = int(t15_c * t15m)
    high15   = max(p[1] for p in prices[:15])

    c1 = today_c < tp5
    c2 = today_c < tp15
    c3 = today_c != high15

    return {
        'ok':       c1 and c2 and c3,
        'date':     prices[0][0],
        'close':    today_c,
        't5_date':  prices[5][0],  't5_c':  t5_c,  'tp5':  tp5,  'c1': c1,
        't15_date': prices[15][0], 't15_c': t15_c, 'tp15': tp15, 'c2': c2,
        'high15':   high15, 'c3': c3,
        't5_ratio': round(today_c/t5_c*100,1),
        't15_ratio': round(today_c/t15_c*100,1),
    }


# ── 3. 결과 출력 ─────────────────────────────────────────────────────────
def run():
    print(f'\n{"═"*60}')
    print(f'  투자경고 해제 예측 검증  {TODAY_STR}')
    print(f'  검증 대상: 2026-06-01 예측 7종목')
    print(f'{"═"*60}\n')

    # KIND 현재 활성 목록 가져오기
    print('1. KIND 현재 투경 목록 조회 중...')
    try:
        active = fetch_active_stocks()
        print(f'   현재 활성 종목: {len(active)}개\n')
    except Exception as e:
        print(f'   KIND 조회 실패: {e}')
        active = set()

    results = []

    print('2. 종목별 검증\n')
    for p in PREDICTED:
        name    = p['name']
        code    = p['code']
        pred    = p['prediction']
        wtype   = KNOWN_TYPES.get(code, 'surge')

        # 실제 해제 여부 (KIND 목록에 없으면 해제됨)
        released = name not in active
        released_str = '🟢 해제 확인' if released else '🔴 여전히 투경 중'

        # 어제 조건 역산
        bt = backtest_yesterday(code, p['des'], wtype)

        # 예측 vs 실제 일치 여부
        pred_was_release = '이연가능' not in pred  # 코리아써키트 제외
        match = '✅ 일치' if (released == pred_was_release) else '❌ 불일치'
        if '이연가능' in pred:
            match = f'🔸 이연케이스 — {"해제됨" if released else "이연됨"}'

        print(f'  {"─"*52}')
        print(f'  {name} ({code}) [{wtype}]')
        print(f'  예측: {pred}')
        print(f'  실제: {released_str}  {match}')

        if bt.get('ok') is not None:
            c1s = '✅' if bt.get('c1') else '❌'
            c2s = '✅' if bt.get('c2') else '❌'
            c3s = '✅' if bt.get('c3') else '❌'
            t5p  = int(TYPE_THRESH[wtype][0]*100)
            t15p = int(TYPE_THRESH[wtype][1]*100)
            print(f'  역산({bt.get("date","")}) 종가:{bt.get("close",0):,}원')
            print(f'  {c1s}① T-5  {bt.get("t5_c",0):,}×{t5p}%={bt.get("tp5",0):,} ({bt.get("t5_ratio",0)}%)')
            print(f'  {c2s}② T-15 {bt.get("t15_c",0):,}×{t15p}%={bt.get("tp15",0):,} ({bt.get("t15_ratio",0)}%)')
            print(f'  {c3s}③ 15일최고 {bt.get("high15",0):,}')

        results.append({
            'name': name, 'code': code, 'pred': pred,
            'released': released, 'match': match,
            'backtest': bt,
        })
        print()

    # 요약
    print(f'{"═"*60}')
    total    = len(PREDICTED)
    rel_pred = sum(1 for r in results if '이연' not in r['pred'])
    rel_act  = sum(1 for r in results if r['released'])
    matched  = sum(1 for r in results if '일치' in r['match'])

    print(f'  예측 해제: {rel_pred}종목  실제 해제: {rel_act}종목  일치: {matched}/{total}')

    # 불일치 분석
    wrong = [r for r in results if '불일치' in r['match']]
    if wrong:
        print(f'\n  ⚠️  불일치 {len(wrong)}건:')
        for r in wrong:
            bt = r['backtest']
            fails = []
            if not bt.get('c1'): fails.append(f'① T-5 {bt.get("t5_ratio",0)}%>{int(TYPE_THRESH.get(KNOWN_TYPES.get(r["code"],"surge"))[0]*100)}%')
            if not bt.get('c2'): fails.append(f'② T-15 {bt.get("t15_ratio",0)}%>{int(TYPE_THRESH.get(KNOWN_TYPES.get(r["code"],"surge"))[1]*100)}%')
            if not bt.get('c3'): fails.append('③ 신고가')
            print(f'    {r["name"]}: 미충족={fails or "없음(KIND오류?)"} → 해제={r["released"]}')

    accuracy = matched / total * 100
    print(f'\n  공식 정확도: {accuracy:.0f}% ({matched}/{total})')
    if accuracy == 100:
        print('  → 공식 완전 검증 완료 ✅')
    elif accuracy >= 70:
        print('  → 공식 대체로 유효. 불일치 케이스 추가 분석 필요.')
    else:
        print('  → 공식 재검토 필요. 원인 분석 후 업데이트.')

    # 로그 저장
    lines = [f'# 투경 해제 예측 검증  {TODAY_STR}',
             f'예측 {total}종목 중 실제 해제 {rel_act}종목, 일치 {matched}건, 정확도 {accuracy:.0f}%', '']
    for r in results:
        lines.append(f'- {r["name"]} ({r["code"]}): 예측={r["pred"]} | 실제={r["released"]} | {r["match"]}')
    LOG_FILE.write_text('\n'.join(lines), encoding='utf-8')
    print(f'\n  로그: {LOG_FILE}')

    # fetch_투경_kind.py --save 도 함께 실행
    print('\n3. 투경 현황 업데이트 중...')
    subprocess.run(
        ['python', str(BASE_DIR / 'fetch_투경_kind.py'), '--save'],
        cwd=str(BASE_DIR), timeout=180
    )
    print('   완료.')


if __name__ == '__main__':
    run()
