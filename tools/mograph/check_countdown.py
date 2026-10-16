# -*- coding: utf-8 -*-
"""모션그래픽팩 '3·2·1 카운트다운'(관제 222)이 편집기 → 완성본 → 썸네일 → 캡컷까지 레퍼런스와 같은 그림으로 나오는지 결과물에서 잰다.

편집기를 띄워 실제로 누른다: 스위치 꺼짐이면 '🎞 모션그래픽' 칸이 안 보이는지 → 켜고 효과 탭 → 모션그래픽 → 카운트다운.
완성본: 효과 없음/있음 두 번 렌더. 카운트다운을 넣은 장면 끝에 맞춰 끝나는 2.15초 동안 레퍼런스(같은 상대 시각)와 대조 —
  점 각도(±9°, 레퍼런스는 15fps 계단) · 원 중심·반지름(±4px) · 점 색 · 숫자 모양(겹침 ≥0.6)·높이(184±8) · 시작 전·장면 밖엔 없음.
썸네일: render_layer_one 한 장에 원·숫자 3. 캡컷: capcut_bake_spans 가 그 장면을 완성본에서 떠 오는지 + 뜬 영상에 원이 있는지.
사용: py tools/mograph/check_countdown.py --ref <레퍼런스.mp4> [--src <바탕영상>] [--work <폴더>] [--sheet 대조시트.png]
  레퍼런스 = youtube.com/shorts/xbyBPW8jIKw (yt-dlp 로 받는다). 바탕을 안 주면 레퍼런스 5~14초(카운트다운 없는 구간)를 쓴다.
"""
import argparse, json, math, os, subprocess, sys, tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

REF_T0 = 1.20          # 레퍼런스에서 카운트다운이 나타나는 시각
DUR = 2.15             # 레퍼런스에서 보이는 길이(motion-graphics-pack.js duration 과 같아야 한다)
CX, CY, R_DOT = 540, 1062, 200
TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 진짜 신기합니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "셋 둘 하나", "t0": 2.0, "dur": 3.0},
    {"beat_idx": 2, "role": "공개", "narration": "바로 이겁니다", "t0": 5.0, "dur": 2.5},
]
CHECK_AT = (0.10, 0.40, 0.70, 0.90, 1.10, 1.30, 1.50, 1.70, 1.90)   # 카운트다운 안 상대 시각(초). 레퍼런스는 2.0초부터 장면 전환에 같이 휩쓸려 대조 불가

PAGE_JS = r"""
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true});
  const out={errors:[]};
  try{
    const page=await browser.newPage();await page.setViewport({width:1600,height:1100});
    page.on('pageerror',e=>out.errors.push(e.message));
    await page.setRequestInterception(true);
    page.on('request',r=>{const u=r.url();
      if(req.files[u])return r.respond({status:200,contentType:'image/jpeg',headers:{'access-control-allow-origin':'*'},body:fs.readFileSync(req.files[u])});
      r.continue();});
    const open=async on=>{
      await page.goto(pathToFileURL(path.resolve(req.root,'out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
      await page.evaluate((r,on)=>window.sceneStyle.load({...r.context,mographEnabled:on},r.snapshot),req,on);
      await page.click('[data-editor-tab="effects"]');
      await page.evaluate(i=>window.sceneStyle.show(i),req.index);await new Promise(r=>setTimeout(r,300));
    };
    await open(false);
    out.kitHiddenOff=await page.$eval('[data-dec-kit="mograph"]',b=>b.hidden).catch(()=>'없음');
    await open(true);
    out.kitHiddenOn=await page.$eval('[data-dec-kit="mograph"]',b=>b.hidden).catch(()=>'없음');
    out.kitVisible=await page.$eval('[data-dec-kit="mograph"]',b=>{const r=b.getBoundingClientRect();return {w:r.width,h:r.height,hidden:b.hidden,inDetails:b.closest('details')?.open}});
    await page.$eval('[data-dec-kit="mograph"]',b=>{b.scrollIntoView();b.click()});
    out.items=await page.$$eval('[data-add-mograph]',bs=>bs.map(b=>b.dataset.addMograph));
    await page.$eval('[data-add-mograph="countdown321"]',b=>{b.scrollIntoView();b.click()});await new Promise(r=>setTimeout(r,200));
    // 미리보기가 움직이나 — 효과 캔버스를 0.6초 간격으로 두 번 떠서 다른지
    const grab=()=>page.$eval('#a-live-preview .scene-decoration[data-mograph] canvas',c=>c.toDataURL());
    const a=await grab();await new Promise(r=>setTimeout(r,600));const b=await grab();
    out.previewMoves=a!==b;
    out.listLabel=await page.$eval('.dec-items',el=>el.textContent);
    await page.screenshot({path:req.shot,clip:await page.$eval('#a-live-preview',el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})});
    out.snapshot=await page.evaluate(()=>window.sceneStyle.snapshot());
  }finally{await browser.close();fs.writeFileSync(req.out,JSON.stringify(out));}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def frame_at(video, t, fps=None):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"{video} {t:.3f}초 프레임 없음")
    return f


def measure(img):
    """원·점·숫자 재기(BGR 1080×1920). 없으면 None."""
    b, g, r = (img[..., k].astype(int) for k in range(3))
    ys, xs = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    near = (abs(np.hypot(xs - CX, ys - CY) - R_DOT) < 70)
    cyan = (r < 120) & (g > 200) & (b > 200) & near
    if cyan.sum() < 2000:
        return None
    cy, cx = np.nonzero(cyan)
    ang = math.degrees(math.atan2(cx.mean() - CX, -(cy.mean() - CY))) % 360
    col = img[int(cy.mean()), int(cx.mean())][::-1].tolist()
    paint = (img.min(axis=2) > 238) | ((g > 225) & (b < 170) & (r > 150)) | ((r < 120) & (g > 200) & (b > 200))   # 흰 원 + 진행 막대 + 점
    ring = paint & (abs(np.hypot(xs - CX, ys - CY) - 202) < 18)
    ry, rx = np.nonzero(ring)
    inner = (img.min(axis=2) > 238) & (np.hypot(xs - CX, ys - CY) < 150)
    inner = cv2.morphologyEx(inner.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
    iy, ix = np.nonzero(inner)
    digit = inner[iy.min():iy.max() + 1, ix.min():ix.max() + 1] if len(iy) else None
    return {"ang": ang, "dot": col, "dotw": int(cx.max() - cx.min()),
            "ring": (int((rx.min() + rx.max()) / 2), int((ry.min() + ry.max()) / 2), int((rx.max() - rx.min()) / 2)) if len(rx) else None,
            "digit": digit, "dh": int(iy.max() - iy.min()) if len(iy) else 0}


def iou(a, b):
    if a is None or b is None:
        return 0.0
    H = 120
    a = cv2.resize(a.astype(np.uint8), (max(1, round(a.shape[1] * H / a.shape[0])), H)) > 0
    b = cv2.resize(b.astype(np.uint8), (max(1, round(b.shape[1] * H / b.shape[0])), H)) > 0
    W = max(a.shape[1], b.shape[1])
    pa = np.zeros((H, W), bool); pb = pa.copy(); pa[:, :a.shape[1]] = a; pb[:, :b.shape[1]] = b
    return float((pa & pb).sum() / max(1, (pa | pb).sum()))


def angdiff(x, y):
    return abs((x - y + 180) % 360 - 180)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--src")
    ap.add_argument("--work")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    from shopping_shorts import scene_style
    work = Path(a.work or tempfile.mkdtemp(prefix="mograph_"))
    work.mkdir(parents=True, exist_ok=True)
    base = work / "base.mp4"
    src_args = ["-i", a.src] if a.src else ["-ss", "5", "-i", a.ref]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *src_args, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "7.5",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(base)], check=True)
    fails = []
    snap0 = {"version": 1, "mode": "story", "presetId": "t11"}
    hc = {"text": "셋 둘 하나\n카운트다운"}
    ctx = scene_style.context_for(TIMELINE, hc, snap0, "qa")
    scenes = ctx["scenes"]
    index = max(i for i, sc in enumerate(scenes) if sc["beat_idx"] == 1)
    s0, s1 = float(scenes[index]["start"]), float(scenes[index]["end"])
    print("장면:", [(i, round(sc["start"], 2), round(sc["end"], 2)) for i, sc in enumerate(scenes)], "| 카운트다운 장면", index, (s0, s1))
    files = {}
    for si, sc in enumerate(scenes):
        pts = []
        for k, t in enumerate((sc["start"] + .05, (sc["start"] + sc["end"]) / 2, sc["end"] - .05)):
            url = f"http://qa.local/api/produce/mix/beatframe/qa/{sc['beat_idx']}?at={t:.2f}"
            p = work / f"pt_{si}_{k}.jpg"
            cv2.imwrite(str(p), frame_at(base, t))
            files[url] = str(p); pts.append(url)
        sc["media_points"] = pts
    req = work / "req.json"
    req.write_text(json.dumps({"root": str(ROOT), "context": ctx, "snapshot": snap0, "files": files, "index": index,
                               "out": str(work / "editor-out.json"), "shot": str(work / "editor.png")}, ensure_ascii=False), encoding="utf-8")
    js = work / "editor.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8")) if (work / "editor-out.json").exists() else {}
    if r.returncode or not ed.get("snapshot"):
        print("편집기 실행 실패:", (r.stderr or "")[-800:], ed.get("errors"))
        print("\n결과: 실패"); sys.exit(1)
    print("① 편집기: 스위치 꺼짐 칸 숨김", ed["kitHiddenOff"], "· 켜짐 칸 숨김", ed["kitHiddenOn"], "· 효과", ed["items"],
          "· 미리보기 움직임", ed["previewMoves"], "· 목록", ed["listLabel"].strip(), "· 오류", ed["errors"])
    if ed["kitHiddenOff"] is not True: fails.append("스위치 꺼진 계정에도 모션그래픽 칸이 보인다")
    if ed["kitHiddenOn"] is not False: fails.append("스위치 켠 계정에 모션그래픽 칸이 안 보인다")
    if "countdown321" not in ed["items"]: fails.append("카운트다운 버튼이 없다")
    if not ed["previewMoves"]: fails.append("편집기 미리보기가 안 움직인다")
    if ed["errors"]: fails.append(f"편집기 오류 {ed['errors']}")
    eff = ed["snapshot"].get("effects") or {}
    masks = (eff.get(str(index)) or {}).get("masks") or []
    if not any(m.get("kind") == "mograph" and m.get("mograph") == "countdown321" for m in masks):
        fails.append(f"저장값에 카운트다운이 없다: {masks}")
    snap = {**snap0, "effects": eff}
    v = scene_style.validate_snapshot(json.loads(json.dumps(snap)))
    kept = [m for m in ((v.get("effects") or {}).get(str(index)) or {}).get("masks") or [] if m.get("kind") == "mograph"]
    print("   서버 검사 뒤 남은 항목:", kept)
    if not kept: fails.append("서버 검사(validate_snapshot)가 모션그래픽 항목을 버렸다")

    out0, out1 = work / "plain.mp4", work / "mograph.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(out0), work / "w0", hc)
    scene_style.compose(str(base), TIMELINE, snap, str(out1), work / "w1", hc)
    start = s1 - min(DUR, s1 - s0)
    print(f"② 완성본: 카운트다운 {start:.2f}~{s1:.2f}초 (장면 끝에 맞춤) — 레퍼런스 {REF_T0}+τ 와 대조")
    rows = []
    for tau in CHECK_AT:
        mine, ref = measure(frame_at(out1, start + tau)), measure(frame_at(a.ref, REF_T0 + tau))
        if not mine or not ref:
            fails.append(f"τ={tau}: {'우리' if not mine else '레퍼런스'} 프레임에서 카운트다운을 못 찾음"); continue
        # 레퍼런스 진행은 15fps 계단(두 프레임씩 멈춤) — 앞뒤 프레임 각도 사이에 들어오면 같은 움직임으로 본다
        near_refs = [x["ang"] for x in (measure(frame_at(a.ref, REF_T0 + tau + k / 30)) for k in (-1, 0, 1, 2)) if x]
        lo, hi = min(near_refs), max(near_refs)
        d = 0.0 if lo - 3 <= mine["ang"] <= hi + 3 else min(angdiff(mine["ang"], lo), angdiff(mine["ang"], hi))
        ov = iou(mine["digit"], ref["digit"])
        rows.append((tau, round(mine["ang"], 1), round(ref["ang"], 1), round(d, 1), round(ov, 2), mine["dh"], ref["dh"], mine["ring"], mine["dot"]))
        if d > 0: fails.append(f"τ={tau}: 점 각도 {mine['ang']:.1f}° — 레퍼런스 앞뒤 프레임 {lo:.1f}~{hi:.1f}° 밖")
        if ov < .6: fails.append(f"τ={tau}: 숫자 모양 겹침 {ov:.2f}")
        if mine["ring"] and (abs(mine["ring"][0] - CX) > 4 or abs(mine["ring"][1] - CY) > 4 or abs(mine["ring"][2] - 217) > 4):
            fails.append(f"τ={tau}: 원 자리·크기 {mine['ring']} (기대 중심 {CX},{CY} 바깥 반지름 217)")
        if max(abs(c - e) for c, e in zip(mine["dot"], (56, 248, 236))) > 25: fails.append(f"τ={tau}: 점 색 {mine['dot']}")
    print("   τ | 우리 각도 | 레퍼런스 | 앞뒤 프레임 범위 밖 | 숫자 겹침 | 숫자 높이(우리/레퍼) | 원(중심x,y,바깥r) | 점 색")
    for row in rows:
        print("  ", " | ".join(map(str, row)))
    for t, what in ((start - .2, "시작 전"), (s1 + .2, "다음 장면")):
        if measure(frame_at(out1, t)):
            fails.append(f"{what}({t:.2f}초)에 카운트다운이 남아 있다")
    if measure(frame_at(out0, start + 1.0)):
        fails.append("효과 없음 영상에 카운트다운이 보인다(측정이 바탕을 잡는다)")

    thumb = Path(scene_style.render_layer_one(TIMELINE, snap, work / "thumb", index, hc))
    timg = cv2.imread(str(thumb), cv2.IMREAD_UNCHANGED)
    alpha = timg[..., 3] if timg.shape[2] == 4 else None
    ys, xs = np.mgrid[0:1920, 0:1080]
    ring_a = alpha[(abs(np.hypot(xs - CX, ys - CY) - 202) < 10)] if alpha is not None else np.array([0])
    print(f"③ 썸네일 {thumb.name}: 원 자리 불투명 비율 {float((ring_a > 200).mean()):.2f}")
    if float((ring_a > 200).mean()) < .8: fails.append("썸네일에 카운트다운 원이 없다")

    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))
    bakes = scene_style.capcut_bake_spans(scenes, snap, layers, work / "w1", out1)
    mine_bake = [b for b in bakes if b.get("scene") == index]
    print("④ 캡컷: 완성본에서 뜬 장면", [(b.get("scene"), Path(b["path"]).name, round(b["start"], 2), round(b["end"], 2)) for b in bakes])
    if not mine_bake:
        fails.append("캡컷이 카운트다운 장면을 완성본에서 떠 오지 않는다(정지 그림으로 멈춘다)")
    else:
        bk = mine_bake[0]
        got = measure(frame_at(bk["path"], (start + 1.0) - float(bk["start"])))
        want = measure(frame_at(out1, start + 1.0))
        print("   뜬 영상 τ=1.0 각도", got and round(got["ang"], 1), "· 완성본", want and round(want["ang"], 1))
        if not got or not want or angdiff(got["ang"], want["ang"]) > 4:
            fails.append("캡컷에 뜬 장면의 카운트다운이 완성본과 다르다")

    if a.sheet:
        tiles = []
        for tau in (0.10, 0.70, 0.79, 1.10, 1.60, 1.95):
            pair = [frame_at(a.ref, REF_T0 + tau), frame_at(out1, start + tau)]
            pair = [cv2.resize(p[812:1312, 290:790], (300, 300)) for p in pair]
            for p, lab in zip(pair, ("ref", "ours")):
                cv2.putText(p, f"{lab} {tau:.2f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 4)
                cv2.putText(p, f"{lab} {tau:.2f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
            tiles.append(np.vstack(pair))
        ed_shot = cv2.imread(str(work / "editor.png"))
        cv2.imwrite(a.sheet, np.hstack(tiles))
        print("대조 시트:", a.sheet, "· 편집기 화면:", work / "editor.png")
    print("\n결과:", "통과" if not fails else "실패")
    for f in fails:
        print("  ✗", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
