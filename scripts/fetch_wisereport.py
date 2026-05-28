"""
fetch_wisereport.py — 와이즈리포트 기업/산업 리포트 일일 수집

사용법:
  python scripts/fetch_wisereport.py              # 오늘 날짜
  python scripts/fetch_wisereport.py --date 2026-05-27
"""
import sys, re, argparse
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import date
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / 'wisereport'
SAVE_DIR.mkdir(exist_ok=True)

URL = 'https://comp.wisereport.co.kr/wiseReport/summary/ReportSummary.aspx?cn=&fmt=1'


def parse_xls(path: Path) -> list[dict]:
    """HTML-based XLS → 리스트"""
    content = path.read_bytes().decode('utf-8', errors='ignore')
    rows    = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
    result  = []
    for row in rows[2:]:   # 첫 2행(타이틀·헤더) 제외
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip().replace('\xa0','') for c in cells]
        cells = [c for c in cells if c]
        if cells:
            result.append(cells)
    return result


def download_tab(page, tab_text: str, date_val: str, save_path: Path):
    if tab_text != '기업':
        page.click(f'text={tab_text}')
        page.wait_for_timeout(1000)

    # 날짜 선택
    try:
        page.select_option('select', value=date_val)
    except:
        pass
    page.click('input[value="검색"], button:has-text("검색")')
    page.wait_for_timeout(1500)

    with page.expect_download(timeout=20000) as dl_info:
        page.click('a:has-text("Excel")')
    dl = dl_info.value
    dl.save_as(str(save_path))
    return save_path


def run(target_date: str):
    date_val = target_date.replace('-', '')   # 20260527
    print(f'[wisereport] {target_date} 수집 중...')

    corp_path = SAVE_DIR / f'{target_date}_기업.xls'
    ind_path  = SAVE_DIR / f'{target_date}_산업.xls'

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx  = browser.new_context(viewport={'width':1400,'height':900}, accept_downloads=True)
        page = ctx.new_page()

        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        download_tab(page, '기업', date_val, corp_path)
        print(f'  ✅ 기업 {corp_path.stat().st_size//1024}KB')

        download_tab(page, '산업', date_val, ind_path)
        print(f'  ✅ 산업 {ind_path.stat().st_size//1024}KB')

        ctx.close()
        browser.close()

    # 파싱 결과 저장 (JSON)
    import json
    corp_rows = parse_xls(corp_path)
    ind_rows  = parse_xls(ind_path)

    out = {
        'date': target_date,
        'corp': corp_rows,
        'industry': ind_rows,
    }
    json_path = SAVE_DIR / f'{target_date}_parsed.json'
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ✅ 파싱: 기업 {len(corp_rows)}건 / 산업 {len(ind_rows)}건 → {json_path.name}')

    return json_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=date.today().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    run(args.date)
