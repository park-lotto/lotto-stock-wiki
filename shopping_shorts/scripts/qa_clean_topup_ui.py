# -*- coding: utf-8 -*-
"""덧지우기 화면 QA (2026-10-03, 관제 095) — serve_clean_pick_qa.py 서버에서 실제 화면을 누른다.

전제: clean_topup_e2e.py 를 먼저 돌려 그 job 이 '몇 장면 지운 상태'다.
순서: 자막제거 패널 → 이미 지운 장면에 '지움' 표시·아무것도 안 골라져 있음 → 이미 지운 장면만 고르면 안내만 뜨고
      요청이 안 나감 → 안 지운 장면 1개를 골라 시작 → 확인창(새로 지울 초만) → 끝난 뒤 지운 장면이 하나 늘고
      앞서 지운 장면은 그대로 '자막 제거됨'.
실행(트랙 폴더): py shopping_shorts/scripts/qa_clean_topup_ui.py --job bte60cb14b7d --out <폴더>
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--base", default="http://127.0.0.1:8769")
ap.add_argument("--out", required=True)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
FAILS = []


def check(ok, what):
    print(("  OK  " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1700})
    errs, dialogs, posts = [], [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.on("request", lambda r: posts.append(r.post_data) if (r.method == "POST" and r.url.endswith("/api/produce/mix/clean")) else None)
    pg.goto(a.base + "/produce", wait_until="networkidle")
    pg.evaluate("""(job)=>{ MIX_JOB=job; STATE.subtitleRemoval=true;
        document.querySelectorAll('section.panel').forEach(s=>s.style.display='none');
        const sec=document.getElementById('cleanPreviewWrap').closest('section'); sec.style.display='block';
        const t=document.getElementById('subToggle'); if(t) t.checked=true;
        refreshSub(); }""", a.job)
    pg.wait_for_selector("#cleanPickWrap", state="visible", timeout=15000)
    pg.evaluate("()=>setCleanTier('pro')")
    pg.wait_for_timeout(800)
    pg.evaluate("(job)=>{ CLEAN_PICK=null; return loadCleanPick(job); }", a.job)
    pg.wait_for_selector(".pick-card", timeout=10000)
    pg.wait_for_timeout(2500)
    st = lambda: pg.evaluate("""()=>[...document.querySelectorAll('.pick-card')].map(c=>({on:c.classList.contains('on'),
        kept:c.classList.contains('kept'), lbl:(c.querySelector('.pk-kept')||{}).innerText||''}))""")   # noqa: E731
    s0 = st()
    kept0 = [i for i, c in enumerate(s0) if c["kept"]]
    print("카드 %d장 · 지움 표시 %s · 문구 %s" % (len(s0), kept0, sorted({c["lbl"] for c in s0 if c["lbl"]})))
    check(len(kept0) >= 2 and all(s0[i]["lbl"].startswith("지움") for i in kept0), "이미 지운 장면에 '지움' 표시")
    check(not any(c["on"] for c in s0), "처음엔 아무 장면도 골라져 있지 않다(고르는 것 = 지금 지울 장면)")
    msg = pg.inner_text("#cleanPickSum")
    print("안내:", msg.replace("\n", " / "))
    check("그대로 유지" in msg, "안내: 이미 지운 장면은 그대로 유지")
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "1_처음.png"))

    done_pro = pg.evaluate("()=>CLEAN_PICK.cuts.map((c,i)=>c.done&&c.done.pro?i:-1).filter(i=>i>=0)")
    pg.locator(".pick-card").nth(done_pro[0]).click()
    msg = pg.inner_text("#cleanPickSum")
    print("이미 고급으로 지운 장면만 고름 →", msg.replace("\n", " / "))
    check("이미 고급 방식으로 지웠어요" in msg and "비용 0" in msg, "이미 지운 장면만 고르면 '결과가 같아 보내지 않아요' 안내")
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "2_이미지운장면만.png"))
    pg.click("#btnCleanPreview")
    pg.wait_for_timeout(1200)
    check(not posts and not dialogs, "시작을 눌러도 요청·확인창이 안 나간다(과금 0)")

    pg.locator(".pick-card").nth(done_pro[0]).click()                       # 뺀다
    fresh = [i for i, c in enumerate(s0) if not c["kept"]][0]
    dur = pg.evaluate("(i)=>CLEAN_PICK.cuts[i].dur", fresh)
    pg.locator(".pick-card").nth(fresh).click()
    msg = pg.inner_text("#cleanPickSum")
    print("안 지운 장면 %d 고름 →" % (fresh + 1), msg.replace("\n", " / "))
    check("고른 장면 1개" in msg and ("%.1f초" % dur) in msg, "새로 지울 1장면의 초·크레딧 안내")
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "3_새장면고름.png"))
    pg.click("#btnCleanPreview")
    t0 = time.time()
    stt = None
    while time.time() - t0 < 600:
        stt = pg.evaluate("(job)=>fetch('/api/mix/status/'+job).then(r=>r.json()).then(d=>d.clean_status)", a.job)
        if stt in ("ready", "failed") and time.time() - t0 > 4:
            break
        pg.wait_for_timeout(3000)
    print("확인창:", dialogs)
    print("보낸 값:", posts[-1] if posts else None, "| 결과:", stt, "| %.0f초" % (time.time() - t0))
    check(len(dialogs) == 1 and "이미 지운 장면은 그대로" in dialogs[0] and ("%.1f초" % dur) in dialogs[0], "확인창 = 새로 지울 초만")
    sent = json.loads(posts[-1]) if posts else {}
    check(len(sent.get("cuts") or []) == 1 and stt == "ready", "보낸 컷 1개 · 완료")
    pg.wait_for_selector(".cp-compare .cp-cap", timeout=30000)
    pg.wait_for_timeout(4000)
    s1 = st()
    kept1 = [i for i, c in enumerate(s1) if c["kept"]]
    print("끝난 뒤 지움 표시:", kept1)
    check(kept1 == sorted(kept0 + [fresh]), "끝난 뒤 지운 장면 = 앞의 것 전부 + 방금 것")
    check(not any(c["on"] for c in s1), "끝난 뒤 고른 것은 비워진다")
    pg.locator("#cleanPickWrap").screenshot(path=str(out / "4_끝난뒤.png"))
    res = []
    for ci in range(len(s1)):
        pg.evaluate("(ci)=>cleanGo(0,0.5,ci)", ci)
        pg.wait_for_timeout(900)
        caps = pg.evaluate("()=>[...document.querySelectorAll('.cp-compare .cp-cap')].map(e=>e.innerText)")
        res.append(caps[-1] if caps else None)
        if ci in (kept0[0], fresh):
            pg.locator("#cleanPreview").screenshot(path=str(out / ("5_비교_장면%d.png" % (ci + 1))))
    bad = [(ci + 1, c) for ci, c in enumerate(res) if (ci in kept1) != (c == "자막 제거됨")]
    print("비교 화면:", [(i + 1, c) for i, c in enumerate(res)])
    check(not bad, "비교 화면: 지운 장면 전부 '자막 제거됨', 나머지는 아님 (틀린 장면 %s)" % (bad or "없음"))
    check(not errs, "페이지 오류 없음 %s" % errs)
    b.close()
print("결과:", "FAIL %d건" % len(FAILS) if FAILS else "PASS")
sys.exit(1 if FAILS else 0)
