# -*- coding: utf-8 -*-
"""구글 검색 결과(제목·주소)만 읽는다 — 로그인 크롬 프로필, 무료, 질의 사이 ≥3초 (관제 097, 2026-10-19).
    PYTHONUTF8=1 py tools/calcopy/shark/gsearch.py <out.json> "<질의1>" "<질의2>" …
"""
import json, sys, time, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.google_browser import google_page  # noqa: E402

def main():
    out, qs = Path(sys.argv[1]), sys.argv[2:]
    res = []
    with google_page() as pg:
        for q in qs:
            pg.goto("https://www.google.com/search?hl=en&num=10&q=" + urllib.parse.quote(q), wait_until="domcontentloaded")
            time.sleep(2.5)
            rows = pg.eval_on_selector_all("a:has(h3)", "as=>as.map(a=>[a.href,(a.querySelector('h3')||{}).innerText||''])")
            res.append({"q": q, "n": len(rows), "results": rows[:10], "captcha": "unusual traffic" in pg.content()[:5000].lower()})
            print(q, len(rows), flush=True)
            time.sleep(3)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
