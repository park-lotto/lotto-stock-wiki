# -*- coding: utf-8 -*-
"""확대 방식 3가지(0.5초 확대·쭉 당기기·확대 후 돌아오기)와 흑백 충격(흑백·지지직·흔들림)이 편집기 → 완성본까지
같은 모양으로 나오는지 결과물에서 잰다 (관제 124, 사장님 2026-10-05).

편집기를 띄워 실제로 누른다: 중요 장면 한 번에 강조 확대 → 문제 장면 [흑백 충격] → 제품 공개 [쭉 당기기] → CTA [확대 후 돌아오기].
완성본: 효과 없음/있음 두 번 렌더 → 장면별 배율 곡선(scene_style.zoom_move_vf 식과 대조) · 흑백(채도) · 흔들림(프레임 간 이동).
비교 영상: --movie 경로에 나란히(왼쪽 없음·오른쪽 있음).
사용: py tools/scene_fx/verify_motion_fx.py --src <바탕영상> --work <폴더> [--movie 바탕화면.mp4]
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
from verify_scene_fx import make_base, frame, scale_between  # noqa: E402

TIMELINE = [   # 역할 이름은 실제 고객 대본에서 많이 쓰는 것
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 2.0},
    {"beat_idx": 2, "role": "공개", "narration": "이게 바로 그 태그건입니다", "t0": 4.0, "dur": 2.5},
    {"beat_idx": 3, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 6.5, "dur": 2.5},
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
    await page.goto(pathToFileURL(path.resolve(req.root,'out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
    await page.evaluate(r=>window.sceneStyle.load(r.context,r.snapshot),req);
    await page.click('[data-editor-tab="effects"]');
    // 문제 장면은 확대 대신 흑백 충격만 — '중요 장면 한 번에'에서 문제 칩을 끄고 강조 확대
    await page.click('[data-ref-moment-pick="problem"]');
    await page.click('[data-ref-fx="all-zoom"]');
    await new Promise(r=>setTimeout(r,2500));
    const show=async i=>{await page.evaluate(i=>window.sceneStyle.show(i),i);await new Promise(r=>setTimeout(r,150));};
    await show(req.at.problem);await page.click('[data-ref-fx="shock"]');
    const shockFilter=await page.$eval('#a-live-preview .scene-media-clip',m=>m.style.filter);
    await show(req.at.reveal);await page.click('[data-zoom-way="pull"]');
    await show(req.at.cta);await page.click('[data-zoom-way="inout"]');
    const snap=await page.evaluate(()=>window.sceneStyle.snapshot());
    fs.writeFileSync(req.out,JSON.stringify({snapshot:snap,shockFilter,errors}));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def sat(img, box):
    y0, y1 = box
    return float(cv2.cvtColor(img[y0:y1], cv2.COLOR_BGR2HSV)[..., 1].mean())


def shift(a, b, box):
    """영상 칸 안 두 프레임 사이 가로·세로 이동(화면비) — 위상상관."""
    y0, y1 = box
    ga, gb = (np.float32(cv2.cvtColor(x[y0:y1], cv2.COLOR_BGR2GRAY)) for x in (a, b))
    (dx, dy), _ = cv2.phaseCorrelate(ga, gb)
    return dx / ga.shape[1], dy / ga.shape[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--work")
    ap.add_argument("--movie")
    a = ap.parse_args()
    from shopping_shorts import scene_style, video_analysis
    from pipeline.atoms import key_vault
    work = Path(a.work or tempfile.mkdtemp(prefix="scene_motion_"))
    work.mkdir(parents=True, exist_ok=True)
    base = work / "base.mp4"
    make_base(a.src, base, sec=9.0)
    fails = []
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    hc = {"text": "옷 정리\n끝판왕"}
    ctx = scene_style.context_for(TIMELINE, hc, snap0, "qa")
    scenes = ctx["scenes"]
    firsts = {sc["moment"]: i for i, sc in enumerate(scenes) if sc.get("moment") and (i == 0 or sc["beat_idx"] != scenes[i - 1]["beat_idx"])}
    print("장면:", [(i, sc["moment"], round(sc["start"], 2), round(sc["end"], 2)) for i, sc in enumerate(scenes)], "| 중요 장면 첫 구절:", firsts)
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
    req = work / "req.json"
    req.write_text(json.dumps({"root": str(ROOT), "context": ctx, "snapshot": snap0, "files": files, "boxes": boxes,
                               "at": firsts, "out": str(work / "editor-out.json")}, ensure_ascii=False), encoding="utf-8")
    js = work / "editor.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode:
        raise SystemExit("편집기 실행 실패: " + r.stderr[-800:])
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8"))
    eff = ed["snapshot"]["effects"]
    snap = {**snap0, "effects": eff}
    print("편집기 오류:", ed["errors"], "| 흑백 충격 미리보기 filter:", ed["shockFilter"])
    print("저장값:", {k: {kk: v[kk] for kk in ("zoom", "zoomIn", "zoomMove", "shock") if kk in v} for k, v in eff.items()})
    if ed["errors"]:
        fails.append(f"편집기 오류 {ed['errors']}")
    if "grayscale(1)" not in (ed["shockFilter"] or ""):
        fails.append("미리보기에 흑백이 안 걸렸다")
    want_move = {firsts["hook"]: None, firsts["reveal"]: "pull", firsts["cta"]: "inout"}
    for i, way in want_move.items():
        if eff.get(str(i), {}).get("zoomMove") != way:
            fails.append(f"장면 {i} 확대 방식 {eff.get(str(i), {}).get('zoomMove')} (기대 {way or 'in'})")
    if not eff.get(str(firsts["problem"]), {}).get("shock"):
        fails.append("문제 장면에 흑백 충격이 안 켜졌다")
    out0, out1 = work / "plain.mp4", work / "fx.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(out0), work / "w0", hc)
    scene_style.compose(str(base), TIMELINE, snap, str(out1), work / "w1", hc)
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))

    def box(i):
        _, h, top, *_ = scene_style.media_geometry(layers[i], eff.get(str(i)))
        return top + 8, top + h - 8
    # 확대 곡선: 장면 프레임 몇 곳에서 배율을 재 zoom_move_vf 식과 대조
    for i in (firsts["hook"], firsts["reveal"], firsts["cta"]):
        e = eff[str(i)]
        Z, n = e["zoom"], round(e["zoomIn"] * 30)
        f0, f1 = round(scenes[i]["start"] * 30), round(scenes[i]["end"] * 30)
        N = f1 - f0
        way = e.get("zoomMove", "in")

        def curve(k):
            if way == "pull":
                t = min(1, k / (N - 1)); return 1 + (Z - 1) * (3 * t * t - 2 * t ** 3)
            if way == "inout" and N > 2 * n:
                b = max(0, (k - (N - n)) / n); return 1 + (Z - 1) * (1 - (1 - min(1, k / n)) ** 2) * (1 - (3 * b * b - 2 * b ** 3))
            return 1 + (Z - 1) * (1 - (1 - min(1, k / n)) ** 2)
        ks = sorted({1, n // 2, n + 1, N // 2, N - n // 2, N - 2})
        got = [scale_between(frame(out0, f0 + k), frame(out1, f0 + k), box(i)) for k in ks]
        want = [curve(k) for k in ks]
        print(f"장면 {i} [{way}] {N}프레임 · 프레임 {ks}\n   완성본 배율 {[round(g, 3) if g else None for g in got]}\n   곡선 계산값 {[round(w, 3) for w in want]}")
        pairs = [(g, w) for g, w in zip(got, want) if g is not None]   # 특징점이 모자라 못 잰 점은 뺀다(대부분 재야 한다)
        if len(pairs) < len(want) - 1 or any(abs(g - w) > .07 for g, w in pairs):
            fails.append(f"장면 {i} [{way}] 확대 곡선이 다르다")
    # 흑백 충격: 채도 ≈0, 프레임 간 흔들림(이동)이 있고, 13프레임마다 찢기듯 크게 밀림
    i = firsts["problem"]
    f0, f1 = round(scenes[i]["start"] * 30), round(scenes[i]["end"] * 30)
    s1, s0 = sat(frame(out1, f0 + 5), box(i)), sat(frame(out0, f0 + 5), box(i))
    moves = [shift(frame(out1, f0 + k), frame(out1, f0 + k + 1), box(i)) for k in range(2, 16)]
    plain_moves = [shift(frame(out0, f0 + k), frame(out0, f0 + k + 1), box(i)) for k in range(2, 16)]
    mag = [round(abs(x) * 100, 2) for x, _ in moves]
    print(f"흑백 충격 장면 {i}: 채도 {s1:.1f} (효과 없음 {s0:.1f}) · 프레임 간 가로 이동 % {mag}\n   효과 없음 이동 % {[round(abs(x) * 100, 2) for x, _ in plain_moves]}")
    if s1 > 3:
        fails.append(f"흑백 충격 장면 채도 {s1:.1f} — 흑백이 아니다")
    if max(mag) < 3 or np.mean(mag) < 1.5 * np.mean([abs(x) * 100 for x, _ in plain_moves]):
        fails.append("흑백 충격 장면에 흔들림·지지직 밀림이 안 보인다")
    if a.movie:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out0), "-i", str(out1), "-filter_complex",
                        "[0:v]scale=540:960,drawtext=text='효과 없음':fontfile='C\\:/Windows/Fonts/malgunbd.ttf':fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.6:x=20:y=910[a];"
                        "[1:v]scale=540:960,drawtext=text='효과 있음':fontfile='C\\:/Windows/Fonts/malgunbd.ttf':fontsize=36:fontcolor=yellow:box=1:boxcolor=black@0.6:x=20:y=910[b];[a][b]hstack",
                        "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", a.movie], check=True)
        print("비교 영상:", a.movie)
    print("\n결과:", "통과" if not fails else "실패")
    for f in fails:
        print("  ✗", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
