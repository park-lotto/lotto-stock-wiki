# -*- coding: utf-8 -*-
"""HTML 틀 → 투명 배경 PNG.

왜(2026-09-05 사장님): GPT에 시키면 HTML/CSS 템플릿이 바로 나온다.
이미지 생성 API가 필요 없다 — 브라우저로 그려서 PNG로 뽑으면
영상 위에 그대로 얹을 수 있다. 디자인은 GPT가, 합성은 우리가.
"""
import os, sys
from playwright.sync_api import sync_playwright

def render(html_path, out_png, w=1080, h=1920):
    url = 'file:///' + os.path.abspath(html_path).replace(os.sep, '/')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
        pg.goto(url)
        pg.wait_for_timeout(900)          # 폰트 로딩 여유
        pg.screenshot(path=out_png, omit_background=True)
        b.close()
    return out_png

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'tpl_demo.html'
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.png'
    render(src, dst)
    print('%s → %s (%d 바이트)' % (src, dst, os.path.getsize(dst)))
