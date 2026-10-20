# -*- coding: utf-8 -*-
"""모션 자산 작업대(/mograph_bench, 관제 244)를 실제 브라우저로 열어 잰다 — 결과물로만 '됐다'.

사용:
  로컬  py tools/mograph/check_bench.py --base http://127.0.0.1:8898 --shot out/모션그래픽엔진/bench.png
  라이브 py tools/mograph/check_bench.py --live --shot …      (tools/live_admin 관리자 세션)
  --make  만들기 탭에서 작업물 1편을 조립해 미리보기 iframe 이 움직이는지 + (--render 면) 렌더까지 기다려 mp4·시트를 잰다
  --verdict <slug>  판정 버튼을 눌러 parts.jsonl 에 verdicts 가 1건 늘었는지 잰다(장부 파일을 전후 대조)

재는 것: 카드 수 = 장부 수 · overlay 캔버스 잉크 > 0 · scene iframe 타임라인 시각이 두 번 재서 달라짐(움직임) ·
  판정 저장 → 장부 verdicts +1 · 작업물 미리보기 타임라인 시각 변화 · 렌더 산출물(mp4 ffprobe 1080×1920 · sheet.png) · 콘솔 오류 0."""
import argparse, json, sys, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

JS_GALLERY = r"""async()=>{
  for(let i=0;i<80&&!window.__mographBenchReady;i++)await new Promise(r=>setTimeout(r,250));
  await new Promise(r=>setTimeout(r,1500));
  const cards=[...document.querySelectorAll('#grid .card')];
  const first=cards.find(c=>c.querySelector('.pv[data-scene]'));
  if(first){first.dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));}
  await new Promise(r=>setTimeout(r,2500));
  const mg=[...document.querySelectorAll('#grid [data-mg] canvas')].map(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n;});
  const shapes=[...document.querySelectorAll('#grid canvas.shape')].map(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n;});
  const f=first&&first.querySelector('iframe');
  let t1=null,t2=null,tlOk=false;
  if(f){t1=f.dataset.t;await new Promise(r=>setTimeout(r,900));t2=f.dataset.t;try{tlOk=!!(f.contentWindow.__timelines&&Object.keys(f.contentWindow.__timelines).length);}catch(e){}}
  return {cards:cards.length,iframes:document.querySelectorAll('#grid iframe').length,mg,shapes,sceneT1:t1,sceneT2:t2,tlOk,
          count:document.getElementById('count').textContent,filters:document.querySelectorAll('#filters .chip').length};
}"""

JS_VERDICT = r"""async(slug)=>{
  const c=document.querySelector(`#grid .card[data-slug="${slug}"]`);if(!c)return {err:'카드 없음'};c.click();
  await new Promise(r=>setTimeout(r,800));
  const tag=document.querySelector('#vtags .chip');if(tag)tag.click();
  document.querySelector('#vnote').value='check_bench 자동 판정';
  document.querySelector('#vgood').click();
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,250));const m=document.querySelector('#vmsg').textContent;
    if(/저장됨|실패/.test(m)){const c2=document.querySelector(`#grid .card[data-slug="${slug}"]`);return {msg:m,badge:!!(c2&&c2.querySelector('.bd.good'))};}}   // 카드는 다시 그려지므로 다시 찾는다
  return {err:'응답 없음'};
}"""

JS_MAKE = r"""async()=>{
  document.querySelector('.tab[data-tab="make"]').click();
  await new Promise(r=>setTimeout(r,300));
  document.getElementById('btnMake').click();
  for(let i=0;i<60;i++){await new Promise(r=>setTimeout(r,250));if(document.querySelector('#stage iframe'))break;}
  await new Promise(r=>setTimeout(r,2500));
  const a=document.getElementById('scrubT').textContent;await new Promise(r=>setTimeout(r,1000));const b=document.getElementById('scrubT').textContent;
  const f=document.querySelector('#stage iframe');let tl=false,scenes=0;try{tl=!!f.contentWindow.__timelines.main;scenes=f.contentDocument.querySelectorAll('.scene').length;}catch(e){}
  return {msg:document.getElementById('makeMsg').textContent,info:document.getElementById('pvInfo').textContent,t1:a,t2:b,tl,scenes,work:(document.getElementById('pvInfo').textContent.match(/work-[0-9a-f]+/)||[null])[0]};
}"""

JS_RENDER = r"""async()=>{
  document.getElementById('btnRender').click();
  for(let i=0;i<400;i++){await new Promise(r=>setTimeout(r,1000));const m=document.getElementById('renderMsg').textContent;if(/완료|실패/.test(m))return {msg:m,video:!!document.querySelector('#result video'),sheet:!!document.querySelector('#result img')};}
  return {err:'렌더 시간 초과'};
}"""


def run(base, shot=None, make=False, render=False, verdict=None, live=False):
    from playwright.sync_api import sync_playwright
    fails, out = [], {}
    parts_path = ROOT / "shopping_shorts" / "mograph" / "data" / "parts.jsonl"
    before = parts_path.read_text(encoding="utf-8").count("\n") if parts_path.exists() else 0
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(viewport={"width": 1500, "height": 1000})
        if live:
            from tools.live_admin import admin_cookies   # noqa
            ctx.add_cookies(admin_cookies())
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(base + "/mograph_bench", wait_until="domcontentloaded")
        out["gallery"] = g = page.evaluate(JS_GALLERY)
        api = page.evaluate("async()=>{const r=await fetch('/api/admin/mograph/parts');return await r.json();}")
        refs = page.evaluate("async()=>{const r=await fetch('/api/admin/mograph/refs');return (await r.json()).refs.length;}")
        n = len(api.get("parts") or []) + refs        # 카드 = 부품 장부 + 레퍼런스(JasonZhu, 2026-10-20 추가)
        if g["cards"] != n: fails.append(f"카드 {g['cards']} ≠ 장부 {len(api.get('parts') or [])} + 레퍼런스 {refs}")
        if not g["mg"] or min(g["mg"]) == 0: fails.append(f"팩 캔버스 잉크 0 {g['mg']}")
        if not g["shapes"] or min(g["shapes"]) == 0: fails.append(f"도형 캔버스 잉크 0 {g['shapes']}")
        if api.get("ref_dir_ok"):
            if not g["tlOk"]: fails.append("scene iframe 에 타임라인 없음")
            if g["sceneT1"] == g["sceneT2"]: fails.append(f"scene 미리보기 안 움직임 {g['sceneT1']}→{g['sceneT2']}")
        if shot:
            Path(shot).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=shot, full_page=False)
        if verdict:
            out["verdict"] = v = page.evaluate(JS_VERDICT, verdict)
            if v.get("err") or "저장됨" not in (v.get("msg") or ""): fails.append(f"판정 저장 실패 {v}")
            rec = [json.loads(l) for l in parts_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            rec = next((r for r in rec if r["slug"] == verdict), None)
            if not rec or not rec.get("verdicts") or rec["verdicts"][-1].get("note") != "check_bench 자동 판정":
                fails.append("장부 parts.jsonl 에 판정이 안 남음")
            if not v.get("badge"): fails.append("카드 배지가 👍로 안 바뀜")
            if shot: page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_verdict.png")))
        if make:
            out["make"] = m = page.evaluate(JS_MAKE)
            if not m.get("tl"): fails.append(f"작업물 미리보기 타임라인 없음 {m}")
            if m.get("t1") == m.get("t2"): fails.append(f"작업물 미리보기 안 움직임 {m.get('t1')}→{m.get('t2')}")
            if not m.get("scenes"): fails.append("작업물 장면 0")
            if shot: page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_make.png")))
            if render:
                out["render"] = r = page.evaluate(JS_RENDER)
                if r.get("err") or "완료" not in (r.get("msg") or ""): fails.append(f"렌더 실패 {r}")
                if not r.get("video") or not r.get("sheet"): fails.append("렌더 결과(mp4·시트)가 화면에 없음")
                if "1080×1920" not in (r.get("msg") or ""): fails.append("렌더 규격이 1080×1920 이 아님")
                if shot:
                    page.wait_for_timeout(1500)
                    page.screenshot(path=str(Path(shot).with_name(Path(shot).stem + "_render.png")), full_page=True)
        after = parts_path.read_text(encoding="utf-8").count("\n") if parts_path.exists() else 0
        if after != before: fails.append(f"장부 줄 수가 바뀜 {before}→{after}(판정은 줄을 늘리지 않아야 한다)")
        out["errors"] = errors[:10]
        if errors: fails.append(f"콘솔 오류 {len(errors)}: {errors[:3]}")
        br.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("\n".join("❌ " + f for f in fails) if fails else "✅ 작업대 검사 통과")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8898")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--make", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--verdict")
    a = ap.parse_args()
    base = "https://shoppingshorts.duckdns.org" if a.live else a.base
    sys.exit(run(base, a.shot, a.make, a.render, a.verdict, a.live))
