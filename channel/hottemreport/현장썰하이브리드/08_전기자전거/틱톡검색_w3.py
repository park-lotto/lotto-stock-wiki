# -*- coding: utf-8 -*-
"""08 전기자전거 워커3 — 틱톡 웹 검색 / 구글 검색에서 영상 링크만 뽑는다(워커 전용 프로필 .lens_profile_w3).
    PYTHONUTF8=1 py 틱톡검색_w3.py <out.json> tiktok|google "<검색어>" …"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tools.calcopy.lens as L  # noqa: E402
L.PROFILE = str(ROOT / ".lens_profile_w3")

out, how, qs = sys.argv[1], sys.argv[2], sys.argv[3:]
res = {}
with L.lens_page() as pg:
    for q in qs:
        url = (f"https://www.tiktok.com/search/video?q={quote(q)}" if how == "tiktok"
               else f"https://www.google.com/search?q={quote(q)}&tbm=vid&hl=ko")
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        for _ in range(4):
            pg.mouse.wheel(0, 2000)
            pg.wait_for_timeout(1200)
        raw = pg.content()
        links = sorted(set(re.findall(r"https?://(?:www\.)?tiktok\.com/@[\w.\-]+/video/\d+", raw)
                           + re.findall(r"/@[\w.\-]+/video/\d+", raw)
                           + re.findall(r"https?://(?:www\.)?youtube\.com/(?:shorts/|watch\?v=)[\w-]{11}", raw)
                           + re.findall(r"https?://(?:www\.)?instagram\.com/(?:reel|p)/[\w-]+", raw)))
        res[q] = links
        pg.screenshot(path=str(HERE / f"검색_{how}.png"))
        print(q, len(links))
        for l in links[:40]:
            print("  ", l)
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
