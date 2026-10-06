# -*- coding: utf-8 -*-
"""자동 배치(관제 124) — 효과 없는 영상으로 장면꾸미기를 열기만 하면(버튼 안 누름) 중요 장면마다 AUTO_FX 가 들어가고
완성본에 그대로 나오는지 잰다. 훅=0.5초 확대 · 문제=흑백 충격 · 제품 공개=쭉 당기기 · 고조=어둡게+큰 글자 · CTA=확대 후 돌아오기.

사용: py tools/scene_fx/verify_auto_fx.py --src <바탕영상> --work <폴더> [--movie 비교영상.mp4]
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from verify_scene_fx import make_base, frame, scale_between, luma  # noqa: E402
from verify_motion_fx import sat  # noqa: E402

TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 2.0},
    {"beat_idx": 2, "role": "공개", "narration": "이게 바로 그 태그건입니다", "t0": 4.0, "dur": 2.0},
    {"beat_idx": 3, "role": "고조1", "narration": "한 번에 딱 꽂혀요", "t0": 6.0, "dur": 1.5},
    {"beat_idx": 4, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 7.5, "dur": 2.5},
]

PAGE_JS = r"""
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true});
  try{
    const page=await browser.newPage();await page.setViewport({width:1600,height:1100});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setRequestInterception(true);
    page.on('request',r=>{const u=r.url();
      if(req.files[u])return r.respond({status:200,contentType:'image/jpeg',headers:{'access-control-allow-origin':'*'},body:fs.readFileSync(req.files[u])});
      if(u in req.boxes)return r.respond({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify({ok:true,box:req.boxes[u]})});
      r.continue();});
    // 파일(file://)로 열면 메시지 출처가 "null" 이라 편집기가 걸러 낸다(실측) — 라이브처럼 같은 주소(로컬 웹서버)로 연다
    await page.goto(req.page,{waitUntil:'networkidle0'});
    // 제작소가 편집기에 보내는 것과 같은 메시지(scene-style-context) — 저장된 효과 없음
    await page.evaluate(r=>window.postMessage({type:'scene-style-context',context:r.context,snapshot:{...r.snapshot,effects:{}}},location.origin),req);
    await new Promise(r=>setTimeout(r,4000));   // 자동 배치 + AI 위치 잡기
    const snap=await page.evaluate(()=>window.sceneStyle.snapshot());
    const autoLabel=await page.$eval('[data-ref-fx="auto"]',b=>b.textContent);
    fs.writeFileSync(req.out,JSON.stringify({snapshot:snap,autoLabel,errors}));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--work")
    ap.add_argument("--movie")
    a = ap.parse_args()
    from shopping_shorts import scene_style, video_analysis
    from pipeline.atoms import key_vault
    work = Path(a.work or tempfile.mkdtemp(prefix="scene_auto_"))
    work.mkdir(parents=True, exist_ok=True)
    base = work / "base.mp4"
    make_base(a.src, base, sec=10.0)
    fails = []
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    hc = {"text": "옷 정리\n끝판왕"}
    ctx = scene_style.context_for(TIMELINE, hc, snap0, "qa")
    ctx["jobId"] = "qa"
    scenes = ctx["scenes"]
    firsts = {sc["moment"]: i for i, sc in enumerate(scenes) if sc.get("moment") and (i == 0 or sc["beat_idx"] != scenes[i - 1]["beat_idx"])}
    print("장면:", [(i, sc["moment"], round(sc["start"], 2), round(sc["end"], 2)) for i, sc in enumerate(scenes)])
    key = key_vault.pick_paced_key(key_vault.get_live_keys("ingest")) if key_vault.get_live_keys("ingest") else None
    files, boxes = {}, {}
    for si, sc in enumerate(scenes):
        pts = []
        for k, t in enumerate((sc["start"] + .05, (sc["start"] + sc["end"]) / 2, sc["end"] - .05)):
            url = f"http://qa.local/api/produce/mix/beatframe/qa/{sc['beat_idx']}?at={t:.2f}"
            p = work / f"pt_{si}_{k}.jpg"
            cv2.imwrite(str(p), frame(base, round(t * 30)))
            files[url] = str(p); pts.append(url)
            if k == 1:
                boxes[url.replace("/beatframe/", "/scene_focus/")] = video_analysis.product_box(p.read_bytes(), sc["caption"], key=key) if key else None
        sc["media_points"] = pts
    import socket
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(ROOT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time; time.sleep(1.5)
    req = work / "req.json"
    req.write_text(json.dumps({"root": str(ROOT), "context": ctx, "snapshot": snap0, "files": files, "boxes": boxes,
                               "page": f"http://127.0.0.1:{port}/out/scene-style-ui-showcase.html?qa=1",
                               "out": str(work / "editor-out.json")}, ensure_ascii=False), encoding="utf-8")
    js = work / "editor.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    try:
        r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
        # 기존 영상(2026-10-06 사장님 "기존영상은 하지말고"): 서버가 autoNew=false 를 주면 열어도 장면 효과를 깔지 않는다
        req_old = work / "req_old.json"; d = json.loads(req.read_text(encoding="utf-8"))
        d["context"] = {**d["context"], "autoNew": False}; d["out"] = str(work / "editor-old.json")
        req_old.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        r_old = subprocess.run(["node", str(js), str(req_old)], capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        server.terminate()
    if r_old.returncode:
        raise SystemExit("편집기 실행 실패(기존 영상): " + r_old.stderr[-800:])
    old_eff = json.loads((work / "editor-old.json").read_text(encoding="utf-8"))["snapshot"].get("effects") or {}
    old_fx = {k: v for k, v in old_eff.items() if v and any(x in v for x in ("zoom", "zoomMove", "shock", "fxAuto")) or (v or {}).get("dim")}
    print("기존 영상(autoNew=false) 자동 효과:", old_fx or "없음")
    if old_fx:
        fails.append(f"기존 영상인데 장면 효과가 자동으로 깔렸다 {list(old_fx)}")
    if r.returncode:
        raise SystemExit("편집기 실행 실패: " + r.stderr[-800:])
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8"))
    eff = ed["snapshot"].get("effects") or {}
    print("편집기 오류:", ed["errors"], "| 버튼:", ed["autoLabel"])
    print("자동으로 들어간 효과:", {k: {kk: v[kk] for kk in ("zoom", "zoomMove", "shock", "dim", "fxFocusBy") if kk in v} for k, v in eff.items() if v})
    want = {"hook": ("zoom", None), "problem": ("shock", None), "reveal": ("zoom", "pull"), "peak": ("dim", None), "cta": ("zoom", "inout")}
    for m, (kind, way) in want.items():
        e = eff.get(str(firsts[m]), {})
        ok = (kind == "zoom" and e.get("fxAuto") == "emph" and e.get("zoomMove") == way) or (kind == "shock" and e.get("shock")) or (kind == "dim" and e.get("dim") and not e["dim"].get("sec"))
        if not ok:
            fails.append(f"{m} 장면 {firsts[m]} 자동 효과 {e} (기대 {kind} {way or ''})")
    others = [k for k, v in eff.items() if v and int(k) not in firsts.values()]
    if others:
        fails.append(f"중요 장면 첫 구절이 아닌 칸에도 효과가 들어갔다 {others}")
    snap = {**snap0, "effects": eff}
    out0, out1 = work / "plain.mp4", work / "fx.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(out0), work / "w0", hc)
    scene_style.compose(str(base), TIMELINE, snap, str(out1), work / "w1", hc)
    # 어둡게만 뺀 대조 — 어둡게 장면은 영상 칸이 자막 띠까지 넓어져(빈 띠 없앰) 효과 없음 영상과 같은 줄을 비교할 수 없다.
    #   대조도 같은 영상 칸이 되도록 dim 을 0.99(밝기 그대로, 강조 배치는 유지)로 둔다.
    snap_nodim = {**snap, "effects": {k: ({**v, "dim": {"level": .99, "sec": 0}} if v.get("dim") and not v["dim"].get("sec") else v) for k, v in eff.items()}}
    out2 = work / "nodim.mp4"
    scene_style.compose(str(base), TIMELINE, snap_nodim, str(out2), work / "w2", hc)
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))

    def box(i):
        _, h, top, *_ = scene_style.media_geometry(layers[i], eff.get(str(i)))
        return top + 8, top + h - 8
    for m in ("hook", "reveal", "cta"):
        i = firsts[m]; f0 = round(scenes[i]["start"] * 30); N = round(scenes[i]["end"] * 30) - f0
        z = [scale_between(frame(out0, f0 + k), frame(out1, f0 + k), box(i)) for k in (1, N // 2, N - 2)]
        print(f"{m} 장면 {i}: 시작·가운데·끝 배율 {[round(x, 2) if x else None for x in z]}")
        if z[1] is None or z[1] < .5:   # 2배 화면에서 특징점 맞추기 실패(0.014 같은 값) — 눈으로 확인할 몫, 실패로 안 센다
            print(f"   ⚠ 가운데 배율 측정 실패({z[1]}) — 비교 영상으로 눈 확인"); z[1] = None
            continue
        if not z[1] or z[1] < 1.05:   # 배율은 제품 크기로 자동(1.3~2) — 쭉 당기기는 가운데가 목표의 절반이다
            fails.append(f"{m} 장면 가운데 확대가 없다 {z}")
        if m == "cta" and (not z[2] or z[2] > 1.25):
            fails.append(f"CTA 끝에서 원본 크기로 안 돌아왔다 {z}")
    i = firsts["problem"]; f = round((scenes[i]["start"] + scenes[i]["end"]) / 2 * 30)
    s = sat(frame(out1, f), box(i))
    print(f"문제 장면 {i}: 채도 {s:.1f} (효과 없음 {sat(frame(out0, f), box(i)):.1f})")
    if s > 3:
        fails.append("문제 장면이 흑백이 아니다")
    i = firsts["peak"]; f = round((scenes[i]["start"] + scenes[i]["end"]) / 2 * 30)
    b0, b1 = box(i)
    rows = [(b0, b0 + int((b1 - b0) * .28)), (b0 + int((b1 - b0) * .72), b1)]
    ratio = sum(luma(frame(out1, f), rr) for rr in rows) / max(1, sum(luma(frame(out2, f), rr) for rr in rows))
    mid = (b0 + int((b1 - b0) * .3), b0 + int((b1 - b0) * .7))
    white = float((cv2.cvtColor(frame(out1, f)[mid[0]:mid[1]], cv2.COLOR_BGR2GRAY) > 235).mean())
    print(f"고조 장면 {i}: 어둡기 {ratio:.3f} · 가운데 흰 글자 비율 {white:.3f}")
    if not (.25 <= ratio <= .40) or white < .03:
        fails.append(f"고조 장면 어둡게+큰 글자가 아니다 ({ratio:.3f}, {white:.3f})")
    if a.movie:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out0), "-i", str(out1), "-filter_complex",
                        "[0:v]scale=540:960,drawtext=text='효과 없음':fontfile='C\\:/Windows/Fonts/malgunbd.ttf':fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.6:x=20:y=910[a];"
                        "[1:v]scale=540:960,drawtext=text='자동 배치':fontfile='C\\:/Windows/Fonts/malgunbd.ttf':fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.6:x=20:y=910[b];[a][b]hstack",
                        "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", a.movie], check=True)
        print("비교 영상:", a.movie)
    print("\n결과:", "통과" if not fails else "실패")
    for x in fails:
        print("  ✗", x)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
