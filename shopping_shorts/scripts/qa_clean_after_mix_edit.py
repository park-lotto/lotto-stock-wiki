# -*- coding: utf-8 -*-
"""관제 211 검사 — 영상대본MIX에서 장면을 바꾼 뒤 자막제거 단계에 다시 들어오면 화면이 **새 편성**을 보여주나.

실행(트랙 폴더):
  py tools/mirror_live_job.py <관리자 job>      # 서버 읽기만
  py tools/serve_local_mirror.py               # 127.0.0.1:8772 (별도 창)
  py shopping_shorts/scripts/qa_clean_after_mix_edit.py <job> [--html 옛produce.html]
--html 을 주면 그 화면 파일로 같은 시험을 돈다(고치기 전 화면에서 실패가 뜨는지 = 검사가 무엇을 재는지 확인).
재는 것: ①전/후 비교 화면이 서버의 지금 컷 목록과 같은가 ②장면 카드 그림 주소가 지금 장면 키를 담나.
편성은 mirror.db 에서만 바꾸고 끝나면 되돌린다(서버는 안 건드린다).
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / ".tmp" / "local-mirror" / "mirror.db"
ap = argparse.ArgumentParser()
ap.add_argument("job")
ap.add_argument("--base", default="http://127.0.0.1:8772")
ap.add_argument("--html", default=None)
a = ap.parse_args()


def plan_get():
    c = sqlite3.connect(DB)
    return c.execute("select edit_plan_json from mix_jobs where job_id=?", (a.job,)).fetchone()[0]


def plan_set(txt):
    c = sqlite3.connect(DB)
    c.execute("update mix_jobs set edit_plan_json=? where job_id=?", (txt, a.job))
    c.commit()


ENTER = """async (job)=>{ MIX_JOB=job; STATE.subtitleRemoval=true;
  document.querySelectorAll('section.panel').forEach(s=>s.style.display='none');
  const sec=document.getElementById('cleanPreviewWrap').closest('section'); sec.style.display='block';
  const t=document.getElementById('subToggle'); if(t) t.checked=true;
  refreshSub(); await restoreCleanPreview(); }"""
SNAP = """async (job)=>{
  const srv=await (await fetch('/api/produce/mix/clean_clips/'+job)).json();
  const pk=await (await fetch('/api/produce/mix/clean_pick/'+job)).json();
  return {screen:(CLEAN_CLIPS||[]).map(c=>c.beat_idx+':'+c.dur), server:(srv.clips||[]).map(c=>c.beat_idx+':'+c.dur),
          stale:srv.stale, keys:(pk.cuts||[]).map(c=>c.key),
          imgs:[...document.querySelectorAll('.pick-card img')].map(i=>decodeURIComponent(i.getAttribute('src')))}; }"""

orig = plan_get()
ok = True
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 1600})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        if a.html:
            body = Path(a.html).read_text(encoding="utf-8")
            pg.route("**/produce*", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=body))
        pg.goto(a.base + "/produce", wait_until="load"); pg.wait_for_timeout(3000)
        pg.evaluate(ENTER, a.job)
        pg.wait_for_timeout(2500)
        pg.evaluate("()=>{ const b=document.getElementById('pickSome'); if(b) b.click(); }")
        pg.wait_for_timeout(1500)
        before = pg.evaluate(SNAP, a.job)
        print("전: 화면 컷", len(before["screen"]), "/ 서버 컷", len(before["server"]), "/ 카드", len(before["imgs"]))

        # 영상대본MIX에서 장면을 바꾼 것과 같은 상태: 첫 칸 장면을 대체 후보로, 마지막 칸을 빼서 칸 수도 바꾼다
        plan = json.loads(orig)
        b0 = plan["beats"][0]
        alt = (b0.get("alternates") or [None])[0]
        if alt:
            b0["primary"], b0["alternates"][0] = alt, b0["primary"]
            for k in ("src_seg_applied", "pinned"):
                b0.pop(k, None)
        plan["beats"] = plan["beats"][:-1]
        plan_set(json.dumps(plan, ensure_ascii=False))

        # 다른 단계(MIX)로 갔다가 자막제거로 돌아온다 — 같은 페이지, 같은 진입 함수
        pg.evaluate("()=>{ document.querySelectorAll('section.panel').forEach(s=>s.style.display='none'); }")
        pg.evaluate(ENTER, a.job)
        pg.wait_for_timeout(3000)
        pg.evaluate("()=>{ const b=document.getElementById('pickSome'); if(b) b.click(); }")
        pg.wait_for_timeout(1500)
        after = pg.evaluate(SNAP, a.job)
        print("후: 화면 컷", len(after["screen"]), "/ 서버 컷", len(after["server"]), "/ 카드", len(after["imgs"]), "/ stale", after["stale"])

        c1 = after["screen"] == after["server"]
        c2 = len(after["imgs"]) == len(after["keys"]) and all(("k=" + k) in u for k, u in zip(after["keys"], after["imgs"]))
        c3 = before["keys"] != after["keys"]
        print("①비교 화면 = 서버 지금 목록:", "통과" if c1 else "실패", "" if c1 else (after["screen"][:4], after["server"][:4]))
        print("②카드 그림 주소 = 지금 장면 키:", "통과" if c2 else "실패")
        print("(편성이 실제로 바뀌었나:", c3, ")")
        print("페이지 오류:", errs)
        ok = c1 and c2 and c3 and not errs
        b.close()
finally:
    plan_set(orig)
print("결과:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
