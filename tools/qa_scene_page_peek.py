# -*- coding: utf-8 -*-
"""장면꾸미기 페이지 그림 화면 검사 (관제 101·104) — 실제 편집기를 헤드리스 크롬으로 열어 누른다.

재는 것:
  ① 각 페이지 그림 주소가 그 페이지 시각(?at=)이고 페이지마다 다르다
  ② 페이지를 넘기는 순간: 그림 주소가 바뀌면 새 그림이 뜰 때까지 영상 칸이 숨겨진다(앞 페이지 그림이 가림막 없이 보이는 순간 0)
  ③ [앞·가운데·뒤] 버튼이 그 페이지의 세 시각 그림으로 바꾸고, 페이지를 넘기면 가운데로 돌아간다
전제: 서버가 떠 있다(예: py shopping_shorts/scripts/serve_clean_pick_qa.py --db <LAB DB> --port 8769).
실행: py tools/qa_scene_page_peek.py --job <job_id> [--base http://127.0.0.1:8769] [--out <폴더>]
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--base", default="http://127.0.0.1:8769")
ap.add_argument("--out", default="")
a = ap.parse_args()
FAILS = []


def check(ok, what):
    print(("  OK   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1700, "height": 1100})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(a.base + "/produce", wait_until="networkidle")
    ctx = pg.evaluate("(job)=>fetch('/api/produce/scene-style/context/'+job).then(r=>r.json())", a.job)
    scenes = (ctx.get("context") or {}).get("scenes") or []
    check(len(scenes) > 2, "편집기 페이지 %d개" % len(scenes))
    check(all("?at=" in (s.get("media") or "") for s in scenes) and len({s["media"] for s in scenes}) == len(scenes),
          "페이지마다 그 페이지 시각의 그림 주소(전부 다름)")
    check(all(len(s.get("media_points") or []) == 3 and s["media_points"][1] == s["media"] for s in scenes),
          "페이지마다 앞·가운데·뒤 주소 3개(가운데 = 기본 그림)")
    pg.evaluate("""(job)=>{ MIX_JOB=job; return openSceneStyleEditor(); }""", a.job)
    pg.wait_for_selector("iframe[title='문구와 효과 편집기']", timeout=20000)
    fr = pg.frame_locator("iframe[title='문구와 효과 편집기']")
    frame = next(f for f in pg.frames if "scene-style-ui-showcase" in f.url)
    frame.wait_for_function("()=>document.querySelector('[data-scene-total]') && Number(document.querySelector('[data-scene-total]').textContent)>2", timeout=30000)
    frame.wait_for_timeout(1500)
    if frame.evaluate("()=>document.body.classList.contains('no-template')"):
        print("  (템플릿 없음 상태 — 첫 템플릿을 고른다)")
        frame.evaluate("()=>document.querySelector('[data-p20]')?.click()")
        frame.wait_for_timeout(1200)
    state = """()=>{const m=document.querySelector('.precision-media');const w=document.querySelector('[data-scene-peek]');
      return {src:(m.getAttribute('src')||''),vis:getComputedStyle(m).visibility,complete:m.complete&&m.naturalWidth>0,
              cur:document.querySelector('[data-scene-current]')?.textContent,peekHidden:w?w.hidden:null,
              on:w?[...w.querySelectorAll('[data-peek]')].findIndex(x=>x.classList.contains('on')):null};}"""
    step = """(d)=>{const bs=[...document.querySelectorAll('[data-scene-step]')];const b=bs.find(x=>Number(x.dataset.sceneStep)===d)||bs[d>0?bs.length-1:0];b.click();}"""
    frame.wait_for_function("()=>{const m=document.querySelector('.precision-media');return m.complete&&m.naturalWidth>0&&getComputedStyle(m).visibility!=='hidden'}", timeout=20000)
    s0 = frame.evaluate(state)
    print("  처음:", s0)
    exposed = 0
    for n in range(1, min(6, len(scenes))):
        # 넘기는 그 순간(같은 틱)에 재서, 그림 주소가 바뀌었는데 아직 안 뜬 그림이 '보이는' 상태인지 본다
        now = frame.evaluate("(d)=>{(%s)(d); return (%s)();}" % (step, state), 1)
        idx = int(now["cur"]) - 1
        want = scenes[idx]["media"]
        changed = now["src"] != s0["src"]
        if changed and now["vis"] != "hidden" and not now["complete"]:
            exposed += 1
        frame.wait_for_function("()=>{const m=document.querySelector('.precision-media');return m.complete&&m.naturalWidth>0&&getComputedStyle(m).visibility!=='hidden'}", timeout=20000)
        aft = frame.evaluate(state)
        check(aft["src"] == want and aft["on"] == 1, "%d쪽: 넘긴 뒤 그림 = 그 페이지 가운데 시각(%s), 직후 상태 %s" % (idx + 1, want.split("?")[-1], now["vis"]))
        s0 = aft
    check(exposed == 0, "넘기는 순간 '아직 안 뜬 새 그림이 보이는' 경우 %d회(0이어야 — 뜰 때까지 숨김)" % exposed)
    check(s0["peekHidden"] is False, "[앞·가운데·뒤] 버튼이 보인다")
    idx = int(s0["cur"]) - 1
    for k, nm in ((0, "앞"), (2, "뒤"), (1, "가운데")):
        frame.click("[data-scene-peek] [data-peek='%d']" % k)
        frame.wait_for_function("()=>{const m=document.querySelector('.precision-media');return m.complete&&m.naturalWidth>0&&getComputedStyle(m).visibility!=='hidden'}", timeout=20000)
        st = frame.evaluate(state)
        check(st["src"] == scenes[idx]["media_points"][k] and st["on"] == k, "[%s] → 그 시각 그림(%s)" % (nm, scenes[idx]["media_points"][k].split("?")[-1]))
    frame.click("[data-scene-peek] [data-peek='0']")
    frame.evaluate("(d)=>{(%s)(d)}" % step, 1)
    frame.wait_for_timeout(1500)
    st = frame.evaluate(state)
    check(st["on"] == 1 and st["src"] == scenes[int(st["cur"]) - 1]["media"], "페이지를 넘기면 가운데로 돌아간다")
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(a.out) / "scene_page_peek.png"))
    check(not errs, "페이지 오류 없음 %s" % errs[:3])
    b.close()
print("결과:", "FAIL %d건" % len(FAILS) if FAILS else "PASS")
sys.exit(1 if FAILS else 0)
