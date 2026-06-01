"""
투자경고 지정유형 자동 확정기

KIND 공시 검색 API → 각 종목의 '투자경고종목지정' 공시 내용 긁기
→ 급등형(160/200%) vs 불건전형(145/175%) 자동 판별
→ 투경현황.json warn_type 갱신

사용법:
  python 투경_유형확정.py           # 전체 종목 유형 확정
  python 투경_유형확정.py --show    # 결과만 출력 (JSON 갱신 안 함)
"""

import sys, json, re, time, argparse, requests
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR  = Path(__file__).parent
WARN_JSON = BASE_DIR / 'raw' / '투경' / '투경현황.json'
TYPE_JSON = BASE_DIR / 'raw' / '투경' / '투경_유형.json'

# 불건전형 판별 키워드 (공시 본문에 포함 시)
UNFAIR_KEYWORDS = ['불건전', '소수계좌', '단기상승&', '중장기상승&', '초장기상승&',
                   '계좌 거래집중', '거래집중', '불건전거래']
SURGE_KEYWORDS  = ['초단기급등', '단기급등', '중장기급등', '투자주의반복']

KIND_SEARCH_URL = 'https://kind.krx.co.kr/disclosure/searchdisclosure.do'
KIND_DISC_BASE  = 'https://kind.krx.co.kr/common/disclsviewer.do'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer':    'https://kind.krx.co.kr/',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}


# ── KIND 공시 검색 (종목코드 + 기간 + 리포트유형) ─────────────────────────
def search_kind_disclosures(code: str, des_date: str) -> list[dict]:
    """
    KIND에서 특정 종목의 투자경고 공시 목록 반환.
    des_date 기준 ±30일 검색.
    """
    try:
        des_dt    = datetime.strptime(des_date, '%Y-%m-%d')
        start_dt  = (des_dt - timedelta(days=5)).strftime('%Y%m%d')
        end_dt    = (des_dt + timedelta(days=3)).strftime('%Y%m%d')

        # KIND 공시 검색 POST (비공개 내부 API — 브라우저 XHR 기반)
        payload = {
            'method':           'searchDisclosureMain',
            'currentPageSize':  '10',
            'currentPage':      '1',
            'marketType':       '',
            'orderMode':        '0',
            'searchText':       '',
            'repCode':          code,
            'startDate':        start_dt,
            'endDate':          end_dt,
            'reportType':       '시장경보',
        }
        r = requests.post(KIND_SEARCH_URL, data=payload, headers=HEADERS, timeout=10)
        data = r.json()
        return data.get('list', []) or data.get('result', []) or []
    except Exception as e:
        return []


# ── Playwright로 KIND 공시 직접 검색 ─────────────────────────────────────
def fetch_disclosure_content_playwright(code: str, des_date: str, name: str) -> str:
    """
    Playwright로 KIND 공시 검색 → 투자경고 지정 공시 HTM 내용 반환.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page(user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'))

        try:
            des_dt   = datetime.strptime(des_date, '%Y-%m-%d')
            start_dt = (des_dt - timedelta(days=3)).strftime('%Y%m%d')
            end_dt   = (des_dt + timedelta(days=2)).strftime('%Y%m%d')

            # KIND 공시 검색 페이지
            search_url = (
                f'https://kind.krx.co.kr/disclosure/searchdisclosure.do'
                f'?method=searchDisclosureMain'
                f'&repCode={code}'
                f'&startDate={start_dt}'
                f'&endDate={end_dt}'
                f'&reportTitle=투자경고'
            )
            page.goto(search_url, timeout=20000)
            page.wait_for_load_state('networkidle', timeout=10000)

            # 공시 목록에서 '투자경고종목지정' 링크 찾기
            links = page.query_selector_all('a')
            target_href = ''
            for link in links:
                text = link.inner_text().strip()
                href = link.get_attribute('href') or ''
                if '투자경고' in text and '지정' in text and 'acptno' in href.lower():
                    target_href = href
                    break

            if not target_href:
                # onclick에서 acptno 추출 시도
                for link in links:
                    onclick = link.get_attribute('onclick') or ''
                    text    = link.inner_text().strip()
                    if '투자경고' in text and 'acptno' in onclick.lower():
                        m = re.search(r'acptno[=,\s\'\"]+(\d{14,18})', onclick, re.I)
                        if m:
                            target_href = f'https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={m.group(1)}'
                            break

            if target_href:
                if not target_href.startswith('http'):
                    target_href = 'https://kind.krx.co.kr' + target_href
                page.goto(target_href, timeout=20000)
                page.wait_for_load_state('networkidle', timeout=10000)

                # iframe 내 내용 추출
                content = ''
                frames  = page.frames
                for frame in frames:
                    try:
                        txt = frame.inner_text('body')
                        if len(txt) > len(content):
                            content = txt
                    except:
                        pass
                if not content:
                    content = page.inner_text('body')
                return content

        except Exception as e:
            pass
        finally:
            browser.close()

    return ''


# ── KRX 데이터 공시 API 방식 ─────────────────────────────────────────────
def search_krx_api(code: str, des_date: str) -> list[dict]:
    """KRX 공시 API로 투자경고 지정 공시 목록 검색."""
    try:
        des_dt   = datetime.strptime(des_date, '%Y-%m-%d')
        start_dt = (des_dt - timedelta(days=3)).strftime('%Y%m%d')
        end_dt   = (des_dt + timedelta(days=2)).strftime('%Y%m%d')

        r = requests.post(
            'https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd',
            data={
                'bld':          'dbms/MDC/STAT/standard/MDCSTAT19001',
                'trdDd':        des_dt.strftime('%Y%m%d'),
                'strtDd':       start_dt,
                'endDd':        end_dt,
                'isuCd':        code,
                'searchText':   '투자경고',
                'pagePath':     '/contents/MDC/MDI/index.jsp',
            },
            headers={**HEADERS, 'Referer': 'https://data.krx.co.kr/'},
            timeout=8)
        return r.json().get('block1', [])
    except:
        return []


# ── 공시 내용에서 유형 판별 ───────────────────────────────────────────────
def classify_from_text(text: str) -> tuple[str, str]:
    """
    공시 텍스트 분석 → (warn_type, matched_keyword)
    급등형: 'surge' / 불건전형: 'unfair' / 미확인: 'unknown'
    """
    if not text:
        return 'unknown', ''

    text_lower = text

    # 불건전형 우선 체크
    for kw in UNFAIR_KEYWORDS:
        if kw in text_lower:
            return 'unfair', kw

    # 급등형 체크
    for kw in SURGE_KEYWORDS:
        if kw in text_lower:
            return 'surge', kw

    # 비율로 역추론 (공시에 수치 명시된 경우)
    if '45%' in text or '75%' in text:
        return 'unfair', '45%/75% 수치 감지'
    if '60%' in text or '100%' in text:
        return 'surge', '60%/100% 수치 감지'

    return 'unknown', ''


# ── KIND 오늘공시 전체 검색 (Playwright) ──────────────────────────────────
def get_acptno_via_search(page, code: str, des_date: str) -> str:
    """
    KIND 투자경고 목록 페이지에서 특정 종목의 acptno 탐색.
    공시일은 지정일 1~2일 전.
    """
    from datetime import datetime, timedelta
    des_dt  = datetime.strptime(des_date, '%Y-%m-%d')
    # 지정일 전후 3일 범위 검색
    for delta in range(-3, 2):
        pub_dt  = des_dt + timedelta(days=delta)
        trd_dd  = pub_dt.strftime('%Y%m%d')
        url     = (f'https://kind.krx.co.kr/disclosure/todaydisclosure.do'
                   f'?method=searchTodayDisclosureMain&trdDd={trd_dd}')
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state('networkidle', timeout=10000)
            page.wait_for_timeout(2000)

            rows = page.query_selector_all('table.list tbody tr')
            for row in rows:
                html = row.inner_html()
                txt  = row.inner_text()
                if '투자경고' in txt and '지정' in txt:
                    # acptno 추출 - onclick 패턴
                    m = re.search(r'acptno[=\s\"\']+(\d{14,18})', html, re.I)
                    if not m:
                        m = re.search(r'[\"\'(](\d{18})[\"\'.]', html)
                    if m:
                        return m.group(1)
        except:
            pass
    return ''


def fetch_doc_content_via_iframe(page, acptno: str) -> str:
    """
    KIND disclsviewer iframe에서 실제 공시 HTM 내용 추출.
    이 방식이 가장 신뢰성 높음 (제주반도체로 검증 완료).
    """
    url = f'https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acptno}'
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state('networkidle', timeout=15000)
        page.wait_for_timeout(3000)

        for frame in page.frames:
            if '/external/' in frame.url and '.htm' in frame.url:
                try:
                    return frame.inner_text('body')
                except:
                    pass
    except:
        pass
    return ''


def fetch_all_warn_disclosures_today(stocks: list[dict]) -> dict[str, str]:
    """
    KIND 공시 전체 검색으로 활성 종목들의 지정 공시 내용 수집.
    iframe 방식 사용 (제주반도체 검증 완료).
    {종목명: 공시내용} 반환.
    """
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'))
        page = context.new_page()

        for stock in stocks:
            code     = stock.get('code', '')
            name     = stock['name']
            des_date = stock['des_date']

            if not code:
                print(f'  ⚠️  {name}: 코드 없음')
                results[name] = ''
                continue

            print(f'  🔍 {name} ({code}) {des_date} ...', end=' ', flush=True)

            # 1단계: acptno 탐색
            acptno = get_acptno_via_search(page, code, des_date)

            if not acptno:
                print('acptno 미발견')
                results[name] = ''
                continue

            # 2단계: iframe으로 실제 문서 내용 추출
            content = fetch_doc_content_via_iframe(page, acptno)

            if content:
                # 첫 줄 미리보기
                first_line = content.split('\n')[0].strip()[:60]
                print(f'✅ acptno={acptno} | {first_line}')
            else:
                print(f'❌ acptno={acptno} 내용 없음')

            results[name] = content
            time.sleep(0.3)

        browser.close()

    return results


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', action='store_true', help='결과 출력만 (JSON 갱신 안 함)')
    args = parser.parse_args()

    # 현재 투경 목록 로드
    if not WARN_JSON.exists():
        print('투경현황.json 없음. 먼저 fetch_투경_kind.py --save 실행하세요.')
        return

    data   = json.loads(WARN_JSON.read_text(encoding='utf-8'))
    stocks = data.get('stocks', [])
    print(f'투경 유형 확정 시작  ({len(stocks)}종목)\n')

    # 공시 내용 수집
    print('KIND 공시 검색 중...')
    disc_contents = fetch_all_warn_disclosures_today(stocks)

    # 유형 판별 및 결과 정리
    print('\n\n── 유형 판별 결과 ──────────────────────────────────────')
    type_map = {}
    updated  = 0

    for stock in stocks:
        name     = stock['name']
        content  = disc_contents.get(name, '')
        wtype, keyword = classify_from_text(content)

        prev_type = stock.get('warn_type', 'surge')
        icon      = '🔸' if wtype == 'unfair' else ('⬜' if wtype == 'surge' else '❓')
        changed   = ' ← 변경!' if wtype != prev_type and wtype != 'unknown' else ''

        print(f'  {icon} {name} ({stock.get("code","")}) : {wtype}  [{keyword or "미감지"}]{changed}')

        if wtype != 'unknown':
            stock['warn_type'] = wtype
            stock['reason']    = keyword
            type_map[name]     = wtype
            if wtype != prev_type:
                updated += 1
        else:
            type_map[name] = prev_type  # 미확인이면 기존 유지

    # 요약
    surge_n  = sum(1 for v in type_map.values() if v == 'surge')
    unfair_n = sum(1 for v in type_map.values() if v == 'unfair')
    unkn_n   = sum(1 for v in type_map.values() if v == 'unknown')
    print(f'\n급등형: {surge_n}종목 / 불건전형: {unfair_n}종목 / 미확인: {unkn_n}종목')
    print(f'유형 변경: {updated}종목')

    # JSON 갱신
    if not args.show:
        WARN_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n✅ 투경현황.json 갱신 완료')

        # 유형 별도 저장
        TYPE_JSON.write_text(
            json.dumps({'updated': data['updated'], 'types': type_map},
                       ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'✅ 투경_유형.json 저장 완료')


if __name__ == '__main__':
    main()
