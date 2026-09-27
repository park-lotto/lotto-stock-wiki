# -*- coding: utf-8 -*-
"""장면 골라 지우기 화면 QA (2026-09-26) — serve_clean_pick_qa.py가 띄운 서버에서 실제 화면을 누른다.

순서: 자막제거 패널 열기 → '골라서 지우기' → 장면 카드 3개만 남기고 빼기 → 시작 → 끝날 때까지 기다림 →
전/후 비교에서 고른 장면은 '자막 제거됨', 안 고른 장면은 '안 지웠어요'인지 확인. 화면 캡처를 남긴다.
실행(트랙 폴더): py shopping_shorts/scripts/qa_clean_pick_ui.py --job bte60cb14b7d --out <폴더>
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--base", default="http://127.0.0.1:8769")
ap.add_argument("--out", required=True)
ap.add_argument("--keep", default="1,2,7", help="남길(지울) 장면 번호(0부터)")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
keep = [int(x) for x in a.keep.split(",")]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1600})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(a.base + "/produce", wait_until="networkidle")
    # 자막제거 패널이 있는 단계를 보이게 하고, 이 job으로 패널을 연다(고객이 3단계에 들어온 것과 같은 함수)
    pg.evaluate("""(job)=>{ MIX_JOB=job; STATE.subtitleRemoval=true;
        document.querySelectorAll('section.panel').forEach(s=>s.style.display='none');
        const sec=document.getElementById('cleanPreviewWrap').closest('section'); sec.style.display='block';
        const t=document.getElementById('subToggle'); if(t) t.checked=true;
        refreshSub(); }""", a.job)
    pg.wait_for_selector("#cleanPickWrap", state="visible", timeout=15000)
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "1_전체.png"))
    print("전체 모드 안내:", pg.inner_text("#cleanPickSum"))
    pg.click("#pickSome")
    pg.wait_for_selector(".pick-card", timeout=10000)
    cards = pg.locator(".pick-card")
    n = cards.count()
    print("장면 카드:", n)
    pg.click("text=모두 빼기")
    print("모두 뺀 뒤 안내:", pg.inner_text("#cleanPickSum"))
    for i in keep:
        pg.locator(".pick-card").nth(i).click()
    pg.wait_for_timeout(2500)          # 카드 그림(원본 프레임) 로딩
    on = pg.evaluate("()=>[...document.querySelectorAll('.pick-card')].map((c,i)=>c.classList.contains('on')?i:-1).filter(i=>i>=0)")
    imgs = pg.evaluate("()=>[...document.querySelectorAll('.pick-card img')].map(i=>i.naturalWidth)")
    print("고른 카드:", on, "| 그림 폭(0이면 안 뜸):", imgs)
    print("고른 뒤 안내:", pg.inner_text("#cleanPickSum"))
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "2_골라서.png"))
    # 시작 — 보내는 값을 가로채 기록
    sent = {}
    pg.on("request", lambda r: sent.update(body=r.post_data) if r.url.endswith("/api/produce/mix/clean") else None)
    pg.click("#btnCleanPreview")
    t0 = time.time()
    while time.time() - t0 < 600:
        st = pg.evaluate("(job)=>fetch('/api/mix/status/'+job).then(r=>r.json()).then(d=>d.clean_status)", a.job)
        if st in ("ready", "failed"):
            break
        pg.wait_for_timeout(3000)
    print("보낸 값:", sent.get("body"), "| 결과:", st, "| %.0f초" % (time.time() - t0))
    pg.wait_for_selector(".cp-compare .cp-cap", timeout=30000)
    pg.wait_for_timeout(1500)
    res = []
    for ci in range(n):
        pg.evaluate("(ci)=>cleanGo(0,0.5,ci)", ci)
        pg.wait_for_timeout(900)
        caps = pg.evaluate("()=>[...document.querySelectorAll('.cp-compare .cp-cap')].map(e=>e.innerText)")
        res.append((ci, caps[-1] if caps else None))
        if ci in (keep[0], 0):
            pg.locator("#cleanPreview").screenshot(path=str(out / ("3_비교_장면%d.png" % (ci + 1))))
    bad = [(ci, c) for ci, c in res if (ci in keep) != ("자막 제거됨" == c)]
    for ci, c in res:
        print("  장면%d: %s" % (ci + 1, c))
    print("비교 화면 문구 틀린 장면:", bad)
    print("페이지 오류:", errs)
    b.close()
