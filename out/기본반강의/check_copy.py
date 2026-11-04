# -*- coding: utf-8 -*-
"""강의 슬라이드 문장이 참고 자료(카페 강의 글) 문장을 그대로 옮겼나 — 글자 n개 연속 겹침으로 찾는다.
    py check_copy.py <슬라이드.html> <참고.txt> [참고2.txt ...] [--n 7]
슬라이드 글은 실제 브라우저로 연 화면 글(innerText)을 쓴다. 띄어쓰기·문장부호는 빼고 비교한다.
겹친 곳을 슬라이드 번호와 함께 보여 준다. rc=0 = 겹침 없음.
(사장님 11-04 "네이버 카페 그 자료 문장들 아니지? 문장들 동일하게 쓰면 안 된다")
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 7
if "--n" in sys.argv:
    args.remove(str(N))
html, refs = args[0], args[1:]
# 겹쳐도 되는 말(고유명사·일반 용어) — 문장이 아니라 낱말
ALLOW = ["재사용", "캡컷", "프리미어", "쇼핑태그", "AI생성", "채널", "유튜브"]


def norm(s):
    return re.sub(r"[\s\W_]+", "", s)


ref = "".join(norm(Path(r).read_text(encoding="utf-8")) for r in refs)
grams = {ref[i:i + N] for i in range(len(ref) - N + 1)}

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.goto("file:///" + str(Path(html).resolve()).replace("\\", "/"))
    texts = pg.evaluate("[...document.querySelectorAll('section.slide')].map(s=>s.innerText)")
    b.close()

bad = 0
for i, t in enumerate(texts, 1):
    for line in t.splitlines():
        s = norm(line)
        hits = [j for j in range(len(s) - N + 1) if s[j:j + N] in grams]
        if not hits:
            continue
        spans, a = [], hits[0]
        for x, y in zip(hits, hits[1:] + [None]):
            if y != x + 1:
                spans.append(s[a:x + N]); a = y
        spans = [sp for sp in spans if not any(sp == w or sp in w for w in ALLOW)]
        if spans:
            bad += 1
            print(f"[{i:02d}] {line.strip()[:70]}  ← 겹침: {', '.join(spans)}")
print(f"슬라이드 {len(texts)}장 · 겹친 줄 {bad}개 (기준: 띄어쓰기 뺀 {N}글자 연속)")
sys.exit(1 if bad else 0)
