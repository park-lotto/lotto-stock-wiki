"""HTML 키트 → PDF + 쪽별 미리보기 PNG. 넘친 쪽이 있으면 rc=1 로 멈춘다.

    py out/무료자료/_공용/build_pdf.py out/무료자료/숏템키트/kit.html
    → 같은 폴더에 kit.pdf · preview/p01.png …
"""
import os
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")


def build(html_path: str) -> int:
    html_path = os.path.abspath(html_path)
    d = os.path.dirname(html_path)
    stem = os.path.splitext(os.path.basename(html_path))[0]
    prev = os.path.join(d, "preview")
    os.makedirs(prev, exist_ok=True)
    for f in os.listdir(prev):
        if f.endswith(".png"):
            os.remove(os.path.join(prev, f))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=1.5)
        pg.goto("file:///" + html_path.replace("\\", "/"))
        pg.wait_for_timeout(1200)
        # 넘침 검사: .page 안 내용이 쪽 높이를 넘거나, 마지막 요소가 바닥글 영역을 침범하면 실패
        over = pg.evaluate("""() => [...document.querySelectorAll('.page')].map((el, i) => {
            const r = el.getBoundingClientRect();
            const foot = el.querySelector('.foot');
            const limit = foot ? foot.getBoundingClientRect().top - 2 : r.bottom;
            let maxB = 0;
            el.querySelectorAll('*').forEach(c => {
              if (c.closest('.foot') || c.classList.contains('foot')) return;
              const cr = c.getBoundingClientRect();
              if (cr.height > 0) maxB = Math.max(maxB, cr.bottom);
            });
            return {i: i + 1, over: Math.round(maxB - limit), scroll: el.scrollHeight - el.clientHeight};
          }).filter(x => x.over > 0 || x.scroll > 1)""")
        pages = pg.locator(".page")
        n = pages.count()
        for i in range(n):
            pages.nth(i).screenshot(path=os.path.join(prev, f"p{i + 1:02d}.png"))
        pdf = os.path.join(d, f"{stem}.pdf")
        pg.pdf(path=pdf, format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print(f"쪽 {n} · PDF {pdf} ({os.path.getsize(pdf) // 1024}KB)")
    if over:
        for o in over:
            print(f"  ✗ {o['i']}쪽 넘침 {o['over']}px (scroll {o['scroll']})")
        return 1
    print("  ✓ 넘친 쪽 없음")
    return 0


if __name__ == "__main__":
    sys.exit(build(sys.argv[1]))
