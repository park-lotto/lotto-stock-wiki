# -*- coding: utf-8 -*-
"""레퍼런스 역설계 길(작업대 /mograph_bench 레퍼런스 카드 → 역설계 버튼 → 지시서 → 승인)을 실제 브라우저로 잰다(관제 244, 2026-10-20).

사용:
  py tools/mograph/check_reverse.py --base http://127.0.0.1:8898 --ref 2103918792845963545 --shot out/모션그래픽엔진/bench_reverse.png
  --click  역설계 버튼을 실제로 눌러(Opus 호출, 40초·구독) 끝날 때까지 기다린다 — 안 주면 이미 있는 지시서가 화면에 뜨는지만 잰다
  --approve  👍 승인 버튼을 눌러 refs.jsonl 의 status 가 approved 로 바뀌는지 잰다

재는 것: 레퍼런스 카드 수 = /api/admin/mograph/refs 수 · 프롬프트 없음 필터 · 카드 클릭 → 상세에 영상(video) + 역설계 버튼 ·
  (--click) 역설계 → 상태 running → done, 지시서 9칸이 화면에, [실측]/[추정] 표식 수 > 0, 장면 띠·시트 img 가 실제로 그려짐(naturalWidth>0) ·
  (--approve) 승인 → refs.jsonl status approved · 카드 배지 '승인' · 콘솔 오류 0."""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

JS_OPEN = r"""async(id)=>{
  for(let i=0;i<80&&!window.__mographBenchReady;i++)await new Promise(r=>setTimeout(r,250));
  await new Promise(r=>setTimeout(r,800));
  const allRef=document.querySelectorAll('#grid .card[data-slug^="ref-"]').length;   // 필터 전 전체 레퍼런스 카드 수
  const chip=[...document.querySelectorAll('#filters .chip')].find(c=>c.dataset.k==='prompt'&&c.dataset.v==='none');if(chip)chip.click();
  await new Promise(r=>setTimeout(r,300));
  const cards=[...document.querySelectorAll('#grid .card')];
  const c=document.querySelector(`#grid .card[data-slug="ref-${id}"]`);if(!c)return {err:'카드 없음',cards:cards.length};
  c.scrollIntoView();c.click();
  for(let i=0;i<40&&!document.querySelector('#detail #refbody h3');i++)await new Promise(r=>setTimeout(r,250));
  await new Promise(r=>setTimeout(r,500));
  const d=document.getElementById('detail');
  return {cards:cards.length,allRef,noPrompt:cards.length,video:!!d.querySelector('video'),
    btn:!!d.querySelector('#rvbtn'),hasBrief:!!d.querySelector('.brief'),sections:[...d.querySelectorAll('.brief h4')].map(h=>h.textContent),
    marks:{m:d.querySelectorAll('.brief .m').length,e:d.querySelectorAll('.brief .e').length},count:document.getElementById('count').textContent};
}"""

JS_CLICK = r"""async()=>{
  const d=document.getElementById('detail');const b=d.querySelector('#rvbtn');if(!b)return {err:'역설계 버튼 없음'};
  d.querySelector('#rvhint').value='check_reverse 자동 실행';b.click();
  let sawRunning=false;
  for(let i=0;i<600;i++){await new Promise(r=>setTimeout(r,1000));
    const badge=[...document.querySelectorAll('#grid .card .bd')].some(x=>x.textContent.includes('역설계 중'));if(badge)sawRunning=true;
    if(d.querySelector('.brief'))break;const e=d.querySelector('#refbody .err');if(e&&e.textContent.includes('실패'))return {err:e.textContent};}
  await new Promise(r=>setTimeout(r,1500));
  const imgs=[...d.querySelectorAll('.brief img')].map(i=>i.naturalWidth);
  return {sawRunning,hasBrief:!!d.querySelector('.brief'),sections:[...d.querySelectorAll('.brief h4')].map(h=>h.textContent),
    marks:{m:d.querySelectorAll('.brief .m').length,e:d.querySelectorAll('.brief .e').length},imgs};
}"""

JS_APPROVE = r"""async()=>{
  const d=document.getElementById('detail');const b=d.querySelector('#rvok');if(!b)return {err:'승인 버튼 없음'};b.click();
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,250));const m=document.querySelector('#detail #rvvmsg');if(m&&/저장됨|실패/.test(m.textContent))break;}
  const m=document.querySelector('#detail #rvvmsg');
  const badge=[...document.querySelectorAll('#grid .card.sel .bd')].map(x=>x.textContent);
  return {msg:m?m.textContent:'',badge};
}"""


def run(base, ref, shot=None, click=False, approve=False):
    from playwright.sync_api import sync_playwright
    fails, out = [], {}
    refs_path = ROOT / "shopping_shorts" / "mograph" / "data" / "refs.jsonl"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(viewport={"width": 1500, "height": 1000})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(base + "/mograph_bench", wait_until="domcontentloaded")
        api = page.evaluate("async()=>{const r=await fetch('/api/admin/mograph/refs');return await r.json();}")
        n_ref = len(api.get("refs") or [])
        out["open"] = o = page.evaluate(JS_OPEN, ref)
        if o.get("err"): fails.append("카드 열기 실패 %s" % o)
        else:
            if o["allRef"] != n_ref: fails.append(f"레퍼런스 카드 {o['allRef']} ≠ API {n_ref}")
            if not o["video"]: fails.append("상세에 영상이 없음")
            if not o["btn"]: fails.append("역설계 버튼이 없음")
        if shot:
            Path(shot).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=shot, full_page=False)
        if click and not o.get("err"):
            out["click"] = c = page.evaluate(JS_CLICK)
            if c.get("err") or not c.get("hasBrief"): fails.append(f"역설계 실패 {c}")
            else:
                if len(c["sections"]) < 9: fails.append(f"지시서 칸 {len(c['sections'])} < 9")
                if c["marks"]["m"] == 0 or c["marks"]["e"] == 0: fails.append(f"[실측]/[추정] 표식 {c['marks']}")
                if not c["imgs"] or min(c["imgs"]) == 0: fails.append(f"띠·시트 그림 안 그려짐 {c['imgs']}")
            if shot: page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_brief.png")), full_page=True)
        elif not o.get("err") and o.get("hasBrief"):
            if o["marks"]["m"] == 0 or o["marks"]["e"] == 0: fails.append(f"[실측]/[추정] 표식 {o['marks']}")
            if shot: page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_brief.png")), full_page=True)
        if approve:
            out["approve"] = a = page.evaluate(JS_APPROVE)
            if a.get("err") or "저장됨" not in (a.get("msg") or ""): fails.append(f"승인 실패 {a}")
            rec = next((json.loads(l) for l in refs_path.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l).get("id") == ref), None)
            if not rec or rec.get("status") != "approved": fails.append("refs.jsonl status 가 approved 가 아님")
            if not any("승인" in b for b in (a.get("badge") or [])): fails.append(f"카드 배지에 승인이 없음 {a.get('badge')}")
            if shot: page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_approve.png")))
        out["errors"] = errors[:10]
        if errors: fails.append(f"콘솔 오류 {len(errors)}: {errors[:3]}")
        br.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n".join("❌ " + f for f in fails) if fails else "✅ 역설계 길 검사 통과")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8898")
    ap.add_argument("--ref", default="2103918792845963545")
    ap.add_argument("--shot")
    ap.add_argument("--click", action="store_true")
    ap.add_argument("--approve", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.base, a.ref, a.shot, a.click, a.approve))
