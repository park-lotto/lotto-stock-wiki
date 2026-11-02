# -*- coding: utf-8 -*-
"""기사 캡처 + 구절 좌표 — render.py 의 article 샷 재료(assets/article/aNNN.png·json)를 만든다.
    py -X utf8 tools/calcopy/longform/article_capture.py <url> <작업폴더/assets/article/a004> "강조 구절" ["구절2" ...]
가로 화면으로 열어 본문을 찍고, 구절이 줄별로 어디 있는지 사각형을 재서 json 에 적는다(boxes = 구절별 [줄 사각형...]).
구절을 못 찾으면 빈 결과를 만들지 않고 멈춘다(동그라미가 엉뚱한 데 쳐지는 것보다 낫다).
세로 장면용 캡처는 ../article_shot.py 다.
"""
import json
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SCALE = 1.5
WIDTH = 1100
CLEAN = """() => { for (const s of ['iframe','ins','aside','nav','footer','[class*=ad-]','[class*=-ad]','[id*=google_ads]','[class*=popup]','[class*=banner]','[class*=recommend]','[class*=share]']) {
    document.querySelectorAll(s).forEach(e => { if (e.offsetHeight < 900) e.remove(); }); }
    document.querySelectorAll('*').forEach(e => { const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.style.position = 'static'; }); }"""
FIND = """(phrases) => {
    const norm = s => s.replace(/\\s+/g, '');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const map = []; let joined = '';
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const st = getComputedStyle(n.parentElement);
        if (st.display === 'none' || st.visibility === 'hidden' || ['SCRIPT','STYLE','NOSCRIPT'].includes(n.parentElement.tagName)) continue;
        const v = n.nodeValue;
        for (let i = 0; i < v.length; i++) if (!/\\s/.test(v[i])) { map.push([n, i]); joined += v[i]; }
    }
    return phrases.map(p => {
        const q = norm(p), at = joined.indexOf(q);
        if (at < 0) return null;
        const a = map[at], b = map[at + q.length - 1];
        const r = document.createRange(); r.setStart(a[0], a[1]); r.setEnd(b[0], b[1] + 1);
        const lines = [];
        for (const c of r.getClientRects()) {
            if (c.width < 2) continue;
            const y = c.top + scrollY, l = lines.find(x => Math.abs(x[1] - y) < c.height / 2);
            if (l) { l[0] = Math.min(l[0], c.left + scrollX); l[2] = Math.max(l[2], c.right + scrollX); l[3] = Math.max(l[3], c.bottom + scrollY); }
            else lines.push([c.left + scrollX, y, c.right + scrollX, c.bottom + scrollY]);
        }
        return lines;
    });
}"""
HEAD = """() => { const h = document.querySelector('h1, .headline, .article_title, h2.title'); if (!h) return null;
    const r = h.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY]; }"""


def capture(url, stem, phrases):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": WIDTH, "height": 1400}, device_scale_factor=SCALE)
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(2500)
        pg.evaluate(CLEAN)
        pg.wait_for_timeout(300)
        found = pg.evaluate(FIND, phrases)
        missing = [q for q, f in zip(phrases, found) if not f]
        if missing:
            b.close()
            sys.exit(f"구절을 못 찾음: {missing}")
        head = pg.evaluate(HEAD)
        ys = [y for f in found for r in f for y in (r[1], r[3])]
        top = max(0, min(ys + ([head[1]] if head else [])) - 120)
        bottom = max(ys) + 500
        pg.screenshot(path=stem + ".png", full_page=True, clip={"x": 0, "y": top, "width": WIDTH, "height": bottom - top})
        b.close()
    tr = lambda r: [round(r[0] * SCALE), round((r[1] - top) * SCALE), round(r[2] * SCALE), round((r[3] - top) * SCALE)]
    meta = {"url": url, "phrase": phrases, "boxes": [[tr(r) for r in f] for f in found]}
    if head:
        meta["headline_box"] = tr(head)
    json.dump(meta, open(stem + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(stem + ".png", [len(f) for f in found], "줄")


if __name__ == "__main__":
    capture(sys.argv[1], sys.argv[2], sys.argv[3:])
