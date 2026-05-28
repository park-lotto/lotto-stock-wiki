"""
와이즈리포트 서머리 — 날짜 변경 + 기업/산업 둘 다 다운로드 테스트
"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from playwright.sync_api import sync_playwright

URL      = 'https://comp.wisereport.co.kr/wiseReport/summary/ReportSummary.aspx?cn=&fmt=1'
SAVE_DIR = Path(__file__).parent.parent / 'raw' / 'report'
TARGET_DATE = '2026-05-27'
SAVE_DIR.mkdir(exist_ok=True)

def download_excel(page, tab_name, date_str, save_path):
    """날짜 세팅 → 검색 → Excel 다운"""

    # 날짜 입력 필드 변경
    page.evaluate(f"""
        const sel = document.querySelector('select[name*="date"], select[id*="date"], input[type="text"]');
        if (sel) sel.value = '{date_str}';
    """)

    # 날짜 셀렉트박스 직접 조작
    date_selectors = ['select', 'input[type=text]']
    for sel in page.query_selector_all('select'):
        options = sel.query_selector_all('option')
        for opt in options:
            if date_str in (opt.get_attribute('value') or ''):
                sel.select_option(value=opt.get_attribute('value'))
                break

    # 검색 버튼 클릭
    page.click('input[type=button][value=검색], button:has-text("검색")')
    page.wait_for_timeout(1500)

    # Excel 다운로드
    with page.expect_download(timeout=20000) as dl_info:
        page.click('a:has-text("Excel")')
    dl = dl_info.value
    dl.save_as(str(save_path))
    size = save_path.stat().st_size // 1024
    print(f'  ✅ {save_path.name}  ({size}KB)')
    return True


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx  = browser.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
    page = ctx.new_page()

    print(f'접속 중...')
    page.goto(URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    # 날짜 셀렉트박스 옵션 목록 확인
    date_options = page.evaluate("""
        () => {
            const sel = document.querySelector('select');
            if (!sel) return [];
            return Array.from(sel.options).map(o => ({val: o.value, txt: o.text}));
        }
    """)
    print(f'날짜 옵션 ({len(date_options)}개):')
    for o in date_options[:10]:
        print(f'  {o["val"]} / {o["txt"]}')

    # 날짜 선택 (2026-05-27)
    target_val = None
    for o in date_options:
        if '2026-05-27' in o['val'] or '20260527' in o['val'] or '05/27' in o['val']:
            target_val = o['val']
            break

    if not target_val and date_options:
        # 날짜 포함된 value 찾기
        for o in date_options:
            if '27' in o['val']:
                target_val = o['val']
                print(f'  → 매칭: {o["val"]}')
                break

    if target_val:
        page.select_option('select', value=target_val)
        print(f'날짜 선택: {target_val}')
    else:
        print('⚠️  날짜 옵션 직접 매칭 안됨 — 첫번째 select에 입력 시도')
        page.evaluate(f"""
            const sel = document.querySelector('select');
            if (sel) {{
                for (let i=0; i<sel.options.length; i++) {{
                    if (sel.options[i].text.includes('27')) {{
                        sel.selectedIndex = i; break;
                    }}
                }}
            }}
        """)

    # 검색
    page.click('input[value="검색"], button:has-text("검색")')
    page.wait_for_timeout(1500)

    # ── 기업 탭 (현재 기본) ──
    print(f'\n[기업] 다운로드...')
    save1 = SAVE_DIR / f'wisereport_기업_{TARGET_DATE}.xls'
    with page.expect_download(timeout=20000) as dl_info:
        page.click('a:has-text("Excel")')
    dl = dl_info.value
    dl.save_as(str(save1))
    print(f'  ✅ {save1.name}  ({save1.stat().st_size//1024}KB)')

    # ── 산업 탭 ──
    print(f'\n[산업] 탭 클릭...')
    page.click('text=산업')
    page.wait_for_timeout(1500)

    # 날짜 다시 선택 (탭 전환 후 초기화될 수 있음)
    if target_val:
        try:
            page.select_option('select', value=target_val)
        except: pass
    page.click('input[value="검색"], button:has-text("검색")')
    page.wait_for_timeout(1500)

    save2 = SAVE_DIR / f'wisereport_산업_{TARGET_DATE}.xls'
    with page.expect_download(timeout=20000) as dl_info:
        page.click('a:has-text("Excel")')
    dl = dl_info.value
    dl.save_as(str(save2))
    print(f'  ✅ {save2.name}  ({save2.stat().st_size//1024}KB)')

    ctx.close()
    browser.close()

# 내용 미리보기
import re
print('\n─── 기업 내용 미리보기 ───')
for fname in [save1, save2]:
    content = fname.read_bytes().decode('utf-8', errors='ignore')
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
    label = '기업' if '기업' in fname.name else '산업'
    print(f'\n[{label}] 총 {len(rows)-2}건')
    for row in rows[2:7]:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells if c.strip()]
        cells = [c for c in cells if c]
        if cells:
            print('  ' + ' | '.join(cells[:5]))
