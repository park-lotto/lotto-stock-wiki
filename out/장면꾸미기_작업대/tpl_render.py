# -*- coding: utf-8 -*-
"""HTML 틀 + 문구 → 투명 PNG. 장면 여러 개를 한 번에 뽑는다.

왜(2026-09-05 사장님 "이걸 주면 너가 어떻게 할 수 있나"):
  코덱스/GPT가 만든 틀은 **한 장**이고 문구를 손으로 친다.
  이 파일이 하는 일 = 그 틀에 job의 문구를 넣어 **장면 수만큼 자동으로** 뽑는 것.
  디자인(CSS)은 그대로 두고 {{ }} 자리만 갈아끼운다 — 느낌이 안 죽는다.
"""
import os, re, tempfile
from playwright.sync_api import sync_playwright

TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tpl')


def list_templates():
    """tpl/ 에 HTML을 떨어뜨리면 그게 곧 틀 목록이 된다(등록 절차 없음)."""
    if not os.path.isdir(TPL_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(TPL_DIR) if f.endswith('.html'))


def fill(tpl_name, values):
    """{{KEY}} 를 값으로 바꾼 HTML 문자열. 안 채운 자리는 빈칸으로 둔다."""
    src = open(os.path.join(TPL_DIR, tpl_name + '.html'), encoding='utf-8').read()
    def sub(m):
        return str(values.get(m.group(1), ''))
    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', sub, src)


def render_many(tpl_name, scenes, out_dir, w=1080, h=1920):
    """scenes = [{LINE1:.., LINE2:.., SUB:..}, ...] → out_dir/000.png ...

    브라우저를 한 번만 띄우고 페이지만 갈아끼운다(12장에 브라우저 12번 띄우면 느리다).
    """
    os.makedirs(out_dir, exist_ok=True)
    made = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
        for i, sc in enumerate(scenes):
            html = fill(tpl_name, sc)
            fd, tmp = tempfile.mkstemp(suffix='.html', dir=TPL_DIR)
            os.close(fd)
            open(tmp, 'w', encoding='utf-8').write(html)
            try:
                pg.goto('file:///' + tmp.replace(os.sep, '/'))
                pg.wait_for_timeout(500)
                out = os.path.join(out_dir, '%03d.png' % i)
                pg.screenshot(path=out, omit_background=True)
                made.append(out)
            finally:
                os.remove(tmp)
        b.close()
    return made


if __name__ == '__main__':
    print('틀 목록:', list_templates())
