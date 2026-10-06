# -*- coding: utf-8 -*-
"""효과 여러 개 같이(관제 124, 사장님 "중복으로 선택 효과되게") + 확대→복귀 끝 상태(사장님 "복귀되고 다시 확대로 간다") 검사.

편집기(로컬 웹서버): 장면 하나에서 [쭉 당기기]→[어둡게+글자]→[흑백 충격] 을 차례로 눌러 셋 다 켜지는지, 같은 확대를 다시 누르면 꺼지는지,
  [확대→복귀] 미리보기 움직임이 끝난 뒤 원래 크기(scale 1)에 머무는지.
완성본: 그 장면에 확대(가운데·끝 배율)·흑백(채도 0)·어둡게(밝기↓)가 같이 나오는지 / 캡컷: 한 조각에 크기·채도 키프레임이 같이 있는지.
사용: py tools/scene_fx/verify_multi_fx.py --src <바탕영상> --work <폴더>
"""
import argparse, json, os, socket, subprocess, sys, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
import cv2  # noqa: E402
from verify_scene_fx import make_base, frame, scale_between, luma  # noqa: E402
from verify_motion_fx import sat  # noqa: E402

TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 3.0},
]
PAGE_JS = r"""
const fs=require('fs'),puppeteer=require('puppeteer');
(async()=>{const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const b=await puppeteer.launch({headless:true});
try{const p=await b.newPage();await p.setViewport({width:1500,height:1100});const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(req.page,{waitUntil:'networkidle0'});
await p.evaluate(r=>window.postMessage({type:'scene-style-context',context:r.context,snapshot:{...r.snapshot,effects:{}}},location.origin),req);
await new Promise(r=>setTimeout(r,1500));
await p.click('[data-editor-tab="effects"]');
await p.evaluate(()=>window.sceneStyle.autoPlace(false));
await p.evaluate(i=>window.sceneStyle.show(i),req.scene);await new Promise(r=>setTimeout(r,200));
const steps={};
await p.click('[data-scene-fx="pull"]');steps.pull=await p.evaluate(i=>window.sceneStyle.sceneFx(i),req.scene);
await p.click('[data-scene-fx="dim"]');steps.dim=await p.evaluate(i=>window.sceneStyle.sceneFx(i),req.scene);
await p.click('[data-scene-fx="shock"]');steps.shock=await p.evaluate(i=>window.sceneStyle.sceneFx(i),req.scene);
const active=await p.$$eval('[data-scene-fx].active',bs=>bs.map(b=>b.dataset.sceneFx));
const snap=await p.evaluate(()=>window.sceneStyle.snapshot());
await p.click('[data-scene-fx="pull"]');steps.pullOff=await p.evaluate(i=>window.sceneStyle.sceneFx(i),req.scene);
await p.click('[data-scene-fx="pull"]');
// 확대→복귀: 다른 장면(0)에서 누르고 움직임이 끝난 뒤 미리보기 크기
await p.evaluate(()=>window.sceneStyle.show(0));await new Promise(r=>setTimeout(r,200));
await p.click('[data-scene-fx="inout"]');await new Promise(r=>setTimeout(r,req.inoutWait));
const endScale=await p.$eval('#a-live-preview .precision-media',m=>getComputedStyle(m).transform);
fs.writeFileSync(req.out,JSON.stringify({steps,active,snap,endScale,errors}));}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    from shopping_shorts import scene_style, capcut_draft
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    base = work / "base.mp4"
    make_base(a.src, base, sec=5.0)
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    hc = {"text": "옷 정리\n끝판왕"}
    ctx = scene_style.context_for(TIMELINE, hc, snap0, "qa"); ctx["jobId"] = "qa"
    scenes = ctx["scenes"]
    target = next(i for i, sc in enumerate(scenes) if sc["beat_idx"] == 1)
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(ROOT)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    sc0 = scenes[0]
    req = work / "req.json"
    req.write_text(json.dumps({"page": f"http://127.0.0.1:{port}/out/scene-style-ui-showcase.html?qa=1", "context": ctx, "snapshot": snap0,
                               "scene": target, "inoutWait": int((sc0["end"] - sc0["start"]) * 1000) + 700,
                               "out": str(work / "out.json")}, ensure_ascii=False), encoding="utf-8")
    js = work / "page.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    try:
        r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        srv.terminate()
    if r.returncode:
        raise SystemExit("편집기 실행 실패: " + r.stderr[-600:])
    ed = json.loads((work / "out.json").read_text(encoding="utf-8"))
    fails = []
    print("누를 때마다 켜진 것:", ed["steps"], "| 켜짐 표시:", ed["active"], "| 오류:", ed["errors"])
    print("확대→복귀 끝난 뒤 미리보기 transform:", ed["endScale"])
    if ed["steps"]["shock"] != ["pull", "dim", "shock"] or sorted(ed["active"]) != ["dim", "pull", "shock"]:
        fails.append("쭉 당기기·어둡게·흑백이 같이 안 켜진다")
    if ed["steps"]["pullOff"] != ["dim", "shock"]:
        fails.append("같은 확대를 다시 누르면 꺼져야 한다")
    if ed["endScale"] not in ("none", "matrix(1, 0, 0, 1, 0, 0)"):
        fails.append(f"확대→복귀가 끝난 뒤 원래 크기가 아니다 ({ed['endScale']})")
    eff = ed["snap"]["effects"]
    snap = {**snap0, "effects": {str(target): eff[str(target)]}}
    out0, out1 = work / "plain.mp4", work / "fx.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(out0), work / "w0", hc)
    scene_style.compose(str(base), TIMELINE, snap, str(out1), work / "w1", hc)
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))
    _, h, top, *_ = scene_style.media_geometry(layers[target], eff[str(target)])
    box = (top + 8, top + h - 8)
    f0 = round(scenes[target]["start"] * 30); N = round(scenes[target]["end"] * 30) - f0
    fm, fe = f0 + N // 2, f0 + N - 3
    s = sat(frame(out1, fm), box)
    print(f"완성본 장면 {target}: 채도 {s:.1f} · 가운데 밝기 {luma(frame(out1, fm), box):.0f} (효과 없음 {luma(frame(out0, fm), box):.0f})")
    if s > 3:
        fails.append("완성본이 흑백이 아니다")
    if luma(frame(out1, fm), box) > .6 * luma(frame(out0, fm), box):
        fails.append("완성본이 어둡지 않다")
    spans = scene_style.capcut_fx_spans(scenes, snap, layers)
    piece = next(sp for sp in spans if abs(sp["start"] - scenes[target]["start"]) < 1e-6)
    kfs = capcut_draft._scene_fx_keyframes(capcut_draft._us(piece["start"]), capcut_draft._us(piece["end"]) - capcut_draft._us(piece["start"]), piece)
    props = {k["property_type"]: k["keyframe_list"] for k in kfs}
    sc = props.get("UNIFORM_SCALE", [])
    print("캡컷 키프레임:", sorted(props), "| 크기 처음·끝:", round(sc[0]["values"][0], 3) if sc else None, round(sc[-1]["values"][0], 3) if sc else None)
    if not {"UNIFORM_SCALE", "KFTypeSaturation", "KFTypePositionX"} <= set(props) or not sc or sc[-1]["values"][0] < 1.2:
        fails.append("캡컷 한 조각에 확대·흑백 키프레임이 같이 없다")
    print("\n결과:", "통과" if not fails else "실패")
    for x in fails:
        print("  ✗", x)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
