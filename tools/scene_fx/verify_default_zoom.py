# -*- coding: utf-8 -*-
"""강조 확대 3종의 기본 크기(관제 178, 사장님 2026-10-11 "쭉 당기기 확대 크기를 1.3배를 기본으로 / 0.5초 확대랑 확대→복귀도 모두").

편집기(로컬 웹서버)에서 [0.5초 확대]·[쭉 당기기]·[확대→복귀] 를 실제로 눌러
  ① 저장값(snapshot effects.zoom) ② [확대 크기] 슬라이더 글자 ③ 제품 쪽 자동 맞춤(AI 상자 응답을 가로채 작은 제품을 준다) 뒤 값
이 전부 WANT 배인지, 그리고 그 저장값으로 캡컷 조각 크기(scene_style.capcut_fx_spans)가 같은 배율인지 본다.
자동 배치(버튼 안 누름)로 깔린 확대 장면도 같은 배율이어야 한다.

사용: py tools/scene_fx/verify_default_zoom.py [--want 1.3]     실패하면 rc=1 과 이유.
"""
import argparse, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 3.0},
    {"beat_idx": 2, "role": "공개", "narration": "이 택건 하나면 끝나요", "t0": 5.0, "dur": 3.0},
    {"beat_idx": 3, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 8.0, "dur": 1.5},
]

PAGE_JS = r"""
const fs=require('fs'),puppeteer=require('puppeteer');
(async()=>{const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const b=await puppeteer.launch({headless:true});
try{const p=await b.newPage();await p.setViewport({width:1500,height:1100});const errors=[];p.on('pageerror',e=>errors.push(e.message));
// 제품 상자 요청(AI)을 가로채 화면의 20%짜리 작은 제품을 준다 — 예전 식(제품이 칸의 85%를 채우게, 최대 emphZoom)이면 여기서 배율이 커진다
await p.setRequestInterception(true);let boxCalls=0;
p.on('request',r=>{const u=r.url();
  if(u.includes('/scene_focus/')){boxCalls++;return r.respond({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify({ok:true,box:[.4,.4,.6,.6]})});}
  if(u.includes('/beatframe/'))return r.respond({status:200,contentType:'image/jpeg',headers:{'access-control-allow-origin':'*'},body:fs.readFileSync(req.frame)});
  r.continue();});
await p.goto(req.page,{waitUntil:'networkidle0'});
await p.evaluate(r=>window.postMessage({type:'scene-style-context',context:r.context,snapshot:{...r.snapshot,effects:{}}},location.origin),req);
await new Promise(r=>setTimeout(r,1500));
await p.click('[data-editor-tab="effects"]');
const read=async i=>p.evaluate(i=>({zoom:window.sceneStyle.snapshot().effects[String(i)]?.zoom,fx:window.sceneStyle.sceneFx(i),
  slider:document.querySelector('[data-zoom-amt] input').value,label:document.querySelector('[data-zoom-amt] output').textContent,
  by:window.sceneStyle.snapshot().effects[String(i)]?.fxFocusBy||null}),i);
// 자동 배치로 깔린 확대 장면(버튼 안 누름)
await p.evaluate(()=>{window.sceneStyle.autoPlace(false);window.sceneStyle.autoPlace(true)});
const auto=await p.evaluate(()=>Object.entries(window.sceneStyle.snapshot().effects).filter(([,e])=>e.fxAuto==='emph').map(([k,e])=>[k,e.zoom,e.zoomMove||'in']));
await p.evaluate(()=>window.sceneStyle.autoPlace(false));
const out={};
for(const kind of ['in','pull','inout']){
  await p.evaluate(i=>{window.sceneStyle.sceneFx(i,'none');window.sceneStyle.show(i)},req.scene);await new Promise(r=>setTimeout(r,200));
  await p.click(`[data-scene-fx="${kind}"]`);await new Promise(r=>setTimeout(r,150));
  const now=await read(req.scene);await new Promise(r=>setTimeout(r,1800));   // 제품 쪽 자동 맞춤(aimEmphasis)이 끝난 뒤
  out[kind]={now,settled:await read(req.scene)};
}
const refFx=await p.evaluate(()=>window.sceneStyle.refFx.emphZoom);
fs.writeFileSync(req.out,JSON.stringify({out,auto,refFx,boxCalls,snap:await p.evaluate(()=>window.sceneStyle.snapshot()),errors}));}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--want", type=float, default=1.3)
    a = ap.parse_args()
    from shopping_shorts import scene_style
    work = Path(tempfile.mkdtemp(prefix="default_zoom_"))
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    ctx = scene_style.context_for(TIMELINE, {"text": "옷 정리\n끝판왕"}, snap0, "qa"); ctx["jobId"] = "qa"
    scenes = ctx["scenes"]
    target = next(i for i, sc in enumerate(scenes) if sc["beat_idx"] == 1)
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(ROOT)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    from PIL import Image
    Image.new("RGB", (1080, 1920), (120, 140, 160)).save(work / "frame.jpg")
    for i, sc in enumerate(scenes):   # 장면 그림 주소(가짜) — 편집기가 이 주소로 제품 상자(scene_focus)를 묻는다
        sc["media"] = f"http://127.0.0.1:{port}/api/mix/qa/beatframe/{i}.jpg"; sc["media_points"] = [sc["media"]]
    req = work / "req.json"
    req.write_text(json.dumps({"page": f"http://127.0.0.1:{port}/out/scene-style-ui-showcase.html?qa=1", "context": ctx, "snapshot": snap0,
                               "scene": target, "frame": str(work / "frame.jpg"), "out": str(work / "out.json")}, ensure_ascii=False), encoding="utf-8")
    js = work / "page.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    try:
        r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        srv.terminate()
    if r.returncode:
        raise SystemExit("편집기 실행 실패: " + r.stderr[-600:])
    ed = json.loads((work / "out.json").read_text(encoding="utf-8"))
    fails, want = [], a.want
    label = f"{want:.2f}배"
    print(f"편집기 기본값(refFx.emphZoom): {ed['refFx']} | 제품 상자 요청 가로챔: {ed['boxCalls']}회 | 화면 오류: {ed['errors']}")
    if not ed["boxCalls"]:
        fails.append("제품 상자 요청이 한 번도 안 갔다 — 자동 맞춤 뒤 배율을 못 잰다")
    if ed["errors"]:
        fails.append(f"편집기 화면 오류 {ed['errors']}")
    for kind, name in (("in", "0.5초 확대"), ("pull", "쭉 당기기"), ("inout", "확대→복귀")):
        for when, key in (("누른 직후", "now"), ("자동 맞춤 뒤", "settled")):
            v = ed["out"][kind][key]
            print(f"  [{name}] {when}: 저장값 {v['zoom']} · 슬라이더 {v['slider']} · 글자 {v['label']} · 켜진 것 {v['fx']} · 맞춤 {v['by']}")
            if kind not in v["fx"]:
                fails.append(f"[{name}] {when}: 효과가 안 켜졌다 {v['fx']}")
            if v["zoom"] is None or abs(v["zoom"] - want) > 1e-6 or abs(float(v["slider"]) - want) > 1e-6 or v["label"] != label:
                fails.append(f"[{name}] {when}: 확대 크기 {v['zoom']} / 슬라이더 {v['slider']} / 글자 {v['label']} (기대 {label})")
    print("  자동 배치로 깔린 확대 장면(장면, 배율, 방식):", ed["auto"])
    if not ed["auto"]:
        fails.append("자동 배치가 확대 장면을 하나도 안 깔았다 — 이 검사가 자동 배치를 못 잰다")
    for k, z, way in ed["auto"]:
        if abs(z - want) > 1e-6:
            fails.append(f"자동 배치 장면 {k}({way}) 확대 {z} (기대 {want})")
    # 캡컷: 마지막으로 누른 확대→복귀 저장값이 그대로 조각 크기로
    snap = {**snap0, "effects": {str(target): ed["snap"]["effects"][str(target)]}}
    zs = [z for z in scene_style.zoom_spans(scenes, snap) if abs(z["start"] - scenes[target]["start"]) < 1e-6]
    print("  렌더·캡컷이 읽는 확대 구간(scene_style.zoom_spans):", [(round(z["start"], 2), z.get("zoom"), z.get("move")) for z in zs])
    if not zs or abs(float(zs[0].get("zoom") or 0) - want) > 1e-6:
        fails.append(f"확대 구간 배율 {zs[0].get('zoom') if zs else None} (기대 {want})")
    print("\n결과:", "통과" if not fails else "실패")
    for x in fails:
        print("  ✗", x)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
