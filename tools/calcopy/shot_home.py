# -*- coding: utf-8 -*-
"""칼카피 홈(/admin/calcopy) 탭 5개 스크린샷 + 탭마다 내용이 실제로 채워졌나 점검(관제 097).

    PYTHONUTF8=1 py tools/calcopy/shot_home.py --base http://127.0.0.1:8853 --out out/calcopy_board
판정: 탭마다 '채워짐' 기준(행 수·타일 수·iframe 안 글자)이 0 이면 실패(rc=1) — 빈 화면을 찍고 됐다고 하지 않게.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CHECKS = {   # 탭 → (셀렉터, 최소 개수) — 데이터가 그려졌다는 표식
    "창고": ("iframe#fr-topics", 1),
    "채널프리셋": ("#packs .card", 1),
    "엔진": ("#kpi .tile", 5),
    "작업기록": ("#ledger tr", 5),
    "결과물": ("#results tr", 10),
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8853")
    ap.add_argument("--out", default="out/calcopy_board")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    rep, bad = {}, []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for i, (tab, (sel, need)) in enumerate(CHECKS.items(), 1):
            pg.goto(f"{a.base}/admin/calcopy#{tab}", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            n = pg.locator(sel).count()
            extra = {}
            if tab == "창고":
                fr = pg.frame_locator("iframe#fr-topics")
                extra["iframe_text_len"] = len(fr.locator("body").inner_text(timeout=20000))
                n = n if extra["iframe_text_len"] > 200 else 0
            err_box = pg.locator("#err").inner_text()
            f = out / f"{i}_{tab}.png"
            pg.screenshot(path=str(f), full_page=tab != "창고")
            rep[tab] = {"shot": str(f.resolve()), "count": n, "need": need, "err": err_box, **extra}
            if n < need or err_box:
                bad.append(tab)
        rep["_pageerrors"] = errs
        b.close()
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 1 if bad or rep["_pageerrors"] else 0


if __name__ == "__main__":
    sys.exit(main())
