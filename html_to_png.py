"""
html_to_png.py — HTML 브리핑 → PNG 자동 변환 (Playwright 버전)

사용법:
  python html_to_png.py                  # 오늘 다크버전
  python html_to_png.py --white          # 화이트버전
  python html_to_png.py --both           # 둘 다
  python html_to_png.py --file path.html # 특정 파일
"""
import sys, argparse
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import date

TODAY = date.today().strftime('%Y-%m-%d')
BASE  = Path(__file__).parent
OUT   = BASE / 'out'


def html_to_png(html_path: Path, out_path: Path):
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path).resolve()
    if not html_path.exists():
        print(f'❌ 파일 없음: {html_path}')
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={'width': 800, 'height': 900},
            device_scale_factor=2          # 2x 고해상도
        )

        page.goto(f'file:///{html_path}')
        page.wait_for_timeout(1500)        # 폰트·렌더링 대기

        # 스크롤바 제거
        page.evaluate("""
            document.body.style.overflow = 'hidden';
            document.documentElement.style.overflow = 'hidden';
        """)

        # 실제 카드 높이만 정확히 측정
        card_bottom = page.evaluate("""
            () => {
                const el = document.body.firstElementChild;
                const rect = el.getBoundingClientRect();
                return Math.ceil(rect.bottom) + 20;
            }
        """)

        # 뷰포트를 카드 높이에 맞게 조정
        page.set_viewport_size({'width': 800, 'height': card_bottom})
        page.wait_for_timeout(300)

        # 카드 영역만 정확히 스크린샷
        page.screenshot(
            path=str(out_path),
            clip={'x': 0, 'y': 0, 'width': 800, 'height': card_bottom},
            scale='device'    # 2x device_scale_factor 반영 → 1680px wide
        )

        browser.close()

    from PIL import Image
    img = Image.open(out_path)
    print(f'✅ PNG 저장: {out_path}  ({img.size[0]}×{img.size[1]}px)')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file',  default=None)
    parser.add_argument('--white', action='store_true')
    parser.add_argument('--both',  action='store_true')
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)

    if args.file:
        p = Path(args.file)
        html_to_png(p, p.with_suffix('.png'))
        return

    dark_html  = OUT / f'morning_dark_{TODAY}.html'
    white_html = OUT / f'morning_white_{TODAY}.html'
    dark_png   = OUT / f'morning_dark_{TODAY}.png'
    white_png  = OUT / f'morning_white_{TODAY}.png'

    if args.both:
        html_to_png(dark_html,  dark_png)
        html_to_png(white_html, white_png)
    elif args.white:
        html_to_png(white_html, white_png)
    else:
        html_to_png(dark_html, dark_png)


if __name__ == '__main__':
    main()
