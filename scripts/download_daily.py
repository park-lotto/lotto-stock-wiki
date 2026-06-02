"""
download_daily.py — 마이박스 3폴더 8파일 + 유튜브 일일 수집
규칙: raw/다운로드규칙.md

사용법:
  python scripts/download_daily.py            # 전체
  python scripts/download_daily.py --ame      # 아메리카노만
  python scripts/download_daily.py --cafe     # 카페라떼만
  python scripts/download_daily.py --bingsu   # 눈꽃빙수만
  python scripts/download_daily.py --yt       # 유튜브만
  python scripts/download_daily.py --debug    # 브라우저 표시
"""
import sys, argparse, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import date
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / '매일 엑셀넣을것'
TODAY    = date.today()
MMDD     = TODAY.strftime('%m%d')

# ── 링크 (mybox_links.json에서 로드) ─────────────────
import json as _json
_links_path = Path(__file__).parent / 'mybox_links.json'
_links = _json.loads(_links_path.read_text(encoding='utf-8'))
URL = {
    'ame':    _links['ame'],
    'cafe':   _links['cafe'],
    'bingsu': _links['bingsu'],
}

# ── 파일 셀렉터 ──────────────────────────────────────
SEL_ITEM = 'li.class_name_for_init_check_photo_list'

# ── 다운로드 대상 ─────────────────────────────────────
# (인덱스, 이름패턴, 저장기본명, 확장자)
TARGETS_AME = [
    (1, '추정이익 변경', '추정이익 변경', '.xlsm'),
]

TARGETS_CAFE_ROOT = [
    (1, '종목피킹',  '유동성 체크, 가속화모멘텀, 신고가, 일정, 수주 데이터', '.xlsm'),
    (2, '일정',     '일정 및 수주잔고',    '.xlsx'),
    (5, '수출정리', '주요품목별수출정리',   '.xlsx'),
]

TARGETS_CAFE_FOLDER = [
    ('컨센관련데이터', 0, [
        (3, '투자픽업', '컨센움직임서프쇼크', '.xlsx'),
    ]),
]

TARGETS_BINGSU = [
    (2,  '(업종)',        '외국인기관수급오실레이터(업종)',      '.xlsm'),
    (3,  '(700-1400)',   '외국인기관수급오실레이터(700-1400)', '.xlsm'),
    (5,  '(700)',        '외국인기관수급오실레이터(700)',       '.xlsm'),
    (8,  '액티브ETF',    '액티브ETF관리',                     '.xlsx'),
    (11, '투자아이디어', '투자아이디어정리',                    '.xlsx'),
    (10, '특정업종 쏠림지수 국내', '특정업종쏠림지수국내',       '.xlsx'),  # 소라티노 — 주도업종 쏠림 감지
]


# ═══════════════════════════════════════════════════
# 유틸
# ═══════════════════════════════════════════════════

def log(msg): print(f'[{MMDD}] {msg}', flush=True)

def cleanup_all():
    """폴더 내 모든 파일 삭제 (다운로드 시작 전 초기화)"""
    deleted, skipped = [], []
    for f in SAVE_DIR.iterdir():
        if not f.is_file(): continue
        if f.name.startswith('~$'):   # 엑셀 열려있는 임시 파일
            skipped.append(f.name)
            continue
        try:
            f.unlink()
            deleted.append(f.name)
        except PermissionError:
            skipped.append(f.name)
    if deleted:
        log(f'🗑 기존 파일 {len(deleted)}개 삭제')
    if skipped:
        log(f'⚠️  {len(skipped)}개 건너뜀 (열려있음): {", ".join(skipped)}')

def clean_old(base_name: str):
    """같은 기본명 기존 파일 삭제 (개별 다운로드 직전)"""
    for f in SAVE_DIR.iterdir():
        if base_name in f.name and f.is_file() and not f.name.startswith('~$'):
            try:
                f.unlink()
            except PermissionError:
                pass

def dest_name(base: str, ext: str) -> str:
    return f'{base}{MMDD}{ext}'

def get_items(page):
    """마이박스 파일 아이템 목록"""
    page.wait_for_timeout(2000)
    return page.query_selector_all(SEL_ITEM)

def find_target(items, idx, pattern):
    """패턴 우선, 없으면 인덱스로 fallback"""
    for item in items:
        t = (item.inner_text() or '').strip()
        if pattern in t:
            return item, t.split('\n')[0]
    if idx < len(items):
        t = (items[idx].inner_text() or '').strip().split('\n')[0]
        log(f'  ⚠️ 패턴 "{pattern}" 미탐지 → [{idx}] {t} 사용')
        return items[idx], t
    return None, None


# ═══════════════════════════════════════════════════
# 핵심: 파일 1개 다운로드
# ═══════════════════════════════════════════════════

def download_one(page, idx, pattern, base_name, ext):
    items = get_items(page)
    log(f'  목록 {len(items)}개')

    item, fname = find_target(items, idx, pattern)
    if not item:
        log(f'  ❌ [{idx}] "{pattern}" 없음')
        return False

    log(f'  📥 {fname}')

    # 기존 파일 먼저 삭제 (다운로드 전에)
    clean_old(base_name)

    try:
        # 임시 저장 경로 (겹침 방지)
        tmp_path = SAVE_DIR / f'__tmp_{base_name}{MMDD}{ext}'

        with page.expect_download(timeout=180_000) as dl_info:
            item.hover()
            page.wait_for_timeout(500)

            more = item.query_selector(
                '[class*="btn_more"], [class*="more_btn"], '
                '[aria-label*="더보기"], button[title*="더보기"]'
            )
            if more:
                more.click()
                page.wait_for_timeout(500)
            else:
                item.click(button='right')
                page.wait_for_timeout(600)

            page.locator('text=내려받기').first.click()

        dl = dl_info.value
        dl.save_as(str(tmp_path))

        # 최종 이름으로 이동
        dst = SAVE_DIR / dest_name(base_name, ext)
        if dst.exists(): dst.unlink()
        tmp_path.rename(dst)
        log(f'  ✅ {dst.name}  ({dst.stat().st_size//1024}KB)')
        return True

    except Exception as e:
        log(f'  ❌ 실패: {e}')
        return False


# ═══════════════════════════════════════════════════
# 폴더별 함수
# ═══════════════════════════════════════════════════

def run_ame(page):
    log('▶ 아메리카노 접속...')
    page.goto(URL['ame'], wait_until='networkidle', timeout=30000)
    for idx, pat, base, ext in TARGETS_AME:
        download_one(page, idx, pat, base, ext)


def run_cafe(page):
    log('▶ 카페라떼 접속...')
    page.goto(URL['cafe'], wait_until='networkidle', timeout=30000)

    # 루트 파일들
    for idx, pat, base, ext in TARGETS_CAFE_ROOT:
        download_one(page, idx, pat, base, ext)

    # 서브폴더 진입
    for folder_name, folder_idx, targets in TARGETS_CAFE_FOLDER:
        log(f'  📁 {folder_name} 폴더 진입...')
        page.goto(URL['cafe'], wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        items = get_items(page)
        if folder_idx < len(items):
            items[folder_idx].click()
            page.wait_for_timeout(2500)
            for idx, pat, base, ext in targets:
                download_one(page, idx, pat, base, ext)
        else:
            log(f'  ❌ 폴더 [{folder_idx}] 없음')


def run_bingsu(page):
    log('▶ 눈꽃빙수 접속...')
    page.goto(URL['bingsu'], wait_until='networkidle', timeout=30000)
    for idx, pat, base, ext in TARGETS_BINGSU:
        download_one(page, idx, pat, base, ext)

    # 서브폴더: 다양한 코드 → 한국 개별종목 상대강도
    log('  📁 다양한 코드 → 한국 개별종목 상대강도...')
    page.goto(URL['bingsu'], wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)
    items = get_items(page)
    if 1 < len(items):
        items[1].click()          # 다양한 코드
        page.wait_for_timeout(2500)
        items2 = get_items(page)
        if 1 < len(items2):
            items2[1].click()     # 한국 개별종목 상대강도
            page.wait_for_timeout(2500)
            download_one(page, 0, '종목상대강도', '한국상대강도', '.xlsx')

    # 서브폴더: 다양한 코드 → 한국 ETF 상대강도 (소라티노 ETF RS)
    log('  📁 다양한 코드 → 한국 ETF 활용한 상대강도...')
    page.goto(URL['bingsu'], wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)
    items = get_items(page)
    if 1 < len(items):
        items[1].click()          # 다양한 코드
        page.wait_for_timeout(2500)
        items2 = get_items(page)
        if 2 < len(items2):
            items2[2].click()     # 한국 etf 활용한 상대강도 추출
            page.wait_for_timeout(2500)
            download_one(page, 0, 'ETF', '한국ETF상대강도', '.xlsx')


# ═══════════════════════════════════════════════════
# 유튜브 게시물 수집
# ═══════════════════════════════════════════════════

def run_youtube(page):
    log('▶ 유튜브 게시물 수집...')
    try:
        page.goto('https://www.youtube.com/@Taerins_Dad/posts',
                  wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(3000)

        posts = page.query_selector_all(
            'ytd-post-renderer #content-text, '
            'ytd-backstage-post-renderer #content-text'
        )
        texts = [p.inner_text().strip() for p in posts[:3] if p.inner_text().strip()]

        if texts:
            out_dir = BASE / 'raw' / 'telegram'
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f'{TODAY}_태린이아빠_유튜브.md'
            out_path.write_text('\n\n---\n\n'.join(texts), encoding='utf-8')
            log(f'  ✅ {out_path.name} ({len(texts)}건)')
        else:
            log('  ⚠️ 게시물 텍스트 없음')
    except Exception as e:
        log(f'  ❌ 유튜브 오류: {e}')


# ═══════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yt',     action='store_true')
    parser.add_argument('--ame',    action='store_true')
    parser.add_argument('--cafe',   action='store_true')
    parser.add_argument('--bingsu', action='store_true')
    parser.add_argument('--debug',  action='store_true')
    args = parser.parse_args()

    run_all = not any([args.yt, args.ame, args.cafe, args.bingsu])
    SAVE_DIR.mkdir(exist_ok=True)

    log(f'저장: {SAVE_DIR}')

    # 전체 실행 시에만 폴더 초기화 (개별 실행 시는 유지)
    if run_all:
        cleanup_all()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not args.debug,
            args=['--no-sandbox', '--lang=ko-KR'],
        )
        ctx = browser.new_context(
            accept_downloads=True,
            viewport={'width': 1280, 'height': 800},
            locale='ko-KR',
        )
        ctx.set_default_timeout(60000)
        page = ctx.new_page()

        try:
            if run_all or args.yt:     run_youtube(page)
            if run_all or args.ame:    run_ame(page)
            if run_all or args.cafe:   run_cafe(page)
            if run_all or args.bingsu: run_bingsu(page)
        finally:
            ctx.close()
            browser.close()

    # 결과
    log('')
    log('─' * 55)
    log('📋 최종 파일 목록:')
    for f in sorted(SAVE_DIR.iterdir()):
        if f.is_file():
            log(f'  {f.name}  ({f.stat().st_size//1024}KB)')
    log('─' * 55)


if __name__ == '__main__':
    main()
