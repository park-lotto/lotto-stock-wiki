# -*- coding: utf-8 -*-
"""레퍼런스 장면 효과(관제 124)가 편집기 → 완성본 → 썸네일 → 캡컷까지 **같은 값**으로 나오는지 결과물로 잰다.

1) 편집기(out/scene-style-ui-showcase.html)를 실제로 띄워 [효과] 탭 버튼을 눌러 snapshot 을 받는다
   (점프 줌 컷 넣기 · 장면 1 어둡게 강조 · 시작 어두운 제목 화면) + 미리보기 영상 칸 밝기를 잰다.
2) 같은 바탕 영상을 효과 없음/있음 두 번 scene_style.compose 로 렌더해 프레임을 대조한다:
   - 점프 줌 장면: 영상 칸 확대 배율(특징점 닮음변환) ≈ 1.35
   - 어둡게 강조 장면: 영상 칸 밝기 비율 ≈ 0.32 / 틀(제목 띠)은 그대로
   - 시작 어두운 제목: 0~3프레임 ≈ 0.46, 5프레임부터 ≈ 1
3) 썸네일(compose_still) 같은 장면 밝기 비율, 4) 캡컷 초안: 어둡게 트랙 구간·투명도, 영상 조각 확대 1.35 구간.
실패하면 rc=1 과 이유. 사용: py tools/scene_fx/verify_scene_fx.py [--src 바탕영상.mp4] [--work 폴더]
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

TIMELINE = [   # 역할은 실제 고객 대본에서 많이 쓰는 이름(훅·공개·CTA)
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 주방 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "공개", "narration": "자석이라 어디든 붙고요 무게도 버티고 설치도 정말 간단해요", "t0": 2.0, "dur": 4.0},
    {"beat_idx": 2, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 6.0, "dur": 1.5},
]

PAGE_JS = r"""
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url'),puppeteer=require('puppeteer');
(async()=>{
  const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true});
  try{
    const page=await browser.newPage();await page.setViewport({width:1600,height:1100});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve(req.root,'out/scene-style-ui-showcase.html')).href+'?qa=1',{waitUntil:'networkidle0'});
    await page.evaluate(r=>window.sceneStyle.load(r.context,r.snapshot),req);
    // [효과] 탭 → 버튼을 실제로 누른다: ①중요 장면 한 번에 강조 확대 ②점프 줌(리듬) ③한 장면 어둡게 ④시작 어두운 제목
    await page.click('[data-editor-tab="effects"]');
    const before=await page.$eval('[data-ref-fx="all-zoom"]',b=>b.textContent);
    await page.click('[data-ref-fx="all-zoom"]');
    const after=await page.$eval('[data-ref-fx="all-zoom"]',b=>b.textContent);
    await page.click('[data-ref-fx="jump"]');
    await page.evaluate(i=>window.sceneStyle.show(i),req.dimScene);
    const label=await page.$eval('[data-ref-moment]',b=>b.textContent);
    await page.click('[data-ref-fx="dim"]');
    await page.click('[data-ref-fx="title"]');
    // 미리보기 밝기: 어둡게 장면 영상 칸에 걸린 filter
    const filter=await page.$eval('#a-live-preview .precision-media',m=>m.style.filter);
    const snap=await page.evaluate(()=>window.sceneStyle.snapshot());
    fs.writeFileSync(req.out,JSON.stringify({snapshot:snap,before,after,label,filter,errors}));
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def make_base(src, out, sec=6.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "3", "-i", src, "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=stereo", "-t", str(sec), "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
                   check=True)


def frame(video, n):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, n)
    ok, f = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"프레임 {n} 못 읽음: {video}")
    return f


def luma(img, box):
    y0, y1 = box
    return float(cv2.cvtColor(img[y0:y1], cv2.COLOR_BGR2GRAY).mean())


def scale_between(a, b, box):
    """영상 칸(box) 안 닮음변환 배율 a→b. 특징점이 부족하면 None."""
    y0, y1 = box
    ga, gb = (cv2.cvtColor(x[y0:y1], cv2.COLOR_BGR2GRAY) for x in (a, b))
    orb = cv2.ORB_create(1500)
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None:
        return None
    ms = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(ms) < 20:
        return None
    M, inl = cv2.estimateAffinePartial2D(np.float32([ka[m.queryIdx].pt for m in ms]),
                                         np.float32([kb[m.trainIdx].pt for m in ms]), method=cv2.RANSAC)
    return float(np.hypot(M[0, 0], M[1, 0])) if M is not None else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="바탕으로 쓸 실제 영상(무늬 있는 것). 없으면 ffmpeg testsrc2")
    ap.add_argument("--work")
    a = ap.parse_args()
    from shopping_shorts import scene_style, capcut_draft
    work = Path(a.work or tempfile.mkdtemp(prefix="scene_fx_"))
    work.mkdir(parents=True, exist_ok=True)
    base = work / "base.mp4"
    if a.src:
        make_base(a.src, base, sec=7.5)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=7.5",
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "7.5", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(base)], check=True)
    fails = []
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    ctx = scene_style.context_for(TIMELINE, {"text": "주방 정리\n끝판왕"}, snap0, "qa")
    scenes = ctx["scenes"]
    body = [i for i, s in enumerate(scenes) if s["beat_idx"] == 1]
    print("장면", [(i, s["beat_idx"], round(s["start"], 2), round(s["end"], 2), s["caption"][:8]) for i, s in enumerate(scenes)])
    if len(body) < 2:
        raise SystemExit("본문 비트가 구절 2개 이상으로 안 나뉘었다 — 점프 줌을 잴 수 없다")
    dim_scene = body[1]                        # 공개 비트 둘째 구절: 점프 줌(1.35)과 어둡게가 겹치는 칸
    firsts = [i for i, sc in enumerate(scenes) if i == 0 or sc["beat_idx"] != scenes[i - 1]["beat_idx"]]
    # 1) 편집기에서 버튼을 눌러 snapshot 받기
    req = work / "editor-req.json"
    req.write_text(json.dumps({"root": str(ROOT), "context": ctx, "snapshot": snap0, "dimScene": dim_scene,
                               "out": str(work / "editor-out.json")}, ensure_ascii=False), encoding="utf-8")
    js = work / "editor.js"
    js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode:
        raise SystemExit("편집기 실행 실패: " + r.stderr[-800:])
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8"))
    snap = {**snap0, **{k: ed["snapshot"][k] for k in ("effects",)}}
    eff = snap["effects"]
    print("편집기 버튼:", ed["before"], "→", ed["after"], "| 장면 표시:", ed["label"], "| 미리보기 filter:", ed["filter"], "| 오류:", ed["errors"])
    emph = sorted(int(k) for k, v in eff.items() if v.get("fxAuto") == "emph")
    jumped = sorted(int(k) for k, v in eff.items() if v.get("fxAuto") in ("jump", "emph"))
    print("중요 장면(각 비트 첫 구절):", firsts, "moment", [scenes[i].get("moment") for i in firsts], "| 강조 확대 켜진 칸:", emph)
    if emph != firsts:
        fails.append(f"중요 장면 한 번에: 강조 확대 칸 {emph} (기대 {firsts})")
    if ed["label"] != "제품 공개":
        fails.append(f"장면 종류 표시 {ed['label']!r} (기대 '제품 공개')")
    for i in emph:
        if eff[str(i)]["zoom"] != 2:
            fails.append(f"강조 확대 장면 {i} 배율 {eff[str(i)]['zoom']} (기대 2)")
    print("점프 줌 장면:", jumped, "| 어둡게:", {k: v.get("dim") for k, v in eff.items() if v.get("dim")})
    if ed["errors"]:
        fails.append(f"편집기 오류 {ed['errors']}")
    if not jumped:
        fails.append("점프 줌 버튼을 눌렀는데 장면에 1.35배가 안 들어갔다")
    if "brightness(0.32)" not in ed["filter"]:
        fails.append(f"미리보기 어둡게가 안 보인다(filter={ed['filter']!r})")
    # 2) 완성본 두 번(효과 없음/있음)
    out0, out1 = work / "plain.mp4", work / "fx.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(out0), work / "w0", {"text": "주방 정리\n끝판왕"})
    scene_style.compose(str(base), TIMELINE, snap, str(out1), work / "w1", {"text": "주방 정리\n끝판왕"})
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))
    def box(i):
        _, h, top, *_ = scene_style.media_geometry(layers[i], eff.get(str(i)))
        return top + 8, top + h - 8
    for i in jumped:
        f = round((scenes[i]["start"] + scenes[i]["end"]) / 2 * 30)
        s = scale_between(frame(out0, f), frame(out1, f), box(i))
        want = eff[str(i)]["zoom"]          # 훅 2.0 · 본문 1.35 (편집기 REF_FX)
        print(f"점프 줌 장면 {i}({scenes[i]['kind']}) 프레임 {f}: 완성본 배율 {s} (기대 {want})")
        if not s or abs(s - want) > .05:
            fails.append(f"점프 줌 장면 {i} 완성본 배율 {s} (기대 {want})")
        if abs(want - (2.0 if i in emph else 1.35)) > 1e-6:
            fails.append(f"장면 {i} 저장 배율 {want} — 강조 2.0/점프 줌 1.35 이어야")
    fd = round((scenes[dim_scene]["start"] + scenes[dim_scene]["end"]) / 2 * 30)
    ratio = luma(frame(out1, fd), box(dim_scene)) / max(1, luma(frame(out0, fd), box(dim_scene)))
    top_ratio = luma(frame(out1, fd), (0, box(dim_scene)[0] - 20)) / max(1, luma(frame(out0, fd), (0, box(dim_scene)[0] - 20)))
    print(f"어둡게 강조 장면 {dim_scene}: 영상 칸 밝기 비율 {ratio:.3f} (기대 ≈0.32) · 틀 영역 {top_ratio:.3f} (기대 ≈1)")
    if not (.25 <= ratio <= .40):
        fails.append(f"어둡게 강조 밝기 비율 {ratio:.3f}")
    if not (.95 <= top_ratio <= 1.05):
        fails.append(f"어둡게가 틀(제목 띠)까지 어둡게 했다 {top_ratio:.3f}")
    t_ratios = [luma(frame(out1, n), box(0)) / max(1, luma(frame(out0, n), box(0))) for n in (0, 2, 3, 4, 6)]
    # 첫 장면에 확대도 걸리면 효과 없음 영상과의 비율에 확대 몫이 섞인다 → 같은 장면 4프레임 이후(어둡게 끝) 값으로 나눈다
    after = sum(t_ratios[3:]) / 2
    norm = [x / after for x in t_ratios[:3]]
    print("시작 어두운 제목 0·2·3·4·6프레임 밝기 비율:", [round(x, 3) for x in t_ratios],
          "→ 4프레임 이후 대비", [round(x, 3) for x in norm], "(기대 ≈0.46, 4프레임부터 끝)")
    if not (all(.38 <= x <= .55 for x in norm) and abs(t_ratios[3] - t_ratios[4]) < .03):
        fails.append(f"시작 어두운 제목 비율 {t_ratios}")
    # 3) 썸네일: 같은 장면을 compose_still 로 (그림은 완성본 효과 없음 프레임의 원본 = base 프레임)
    fp = work / "src_frame.jpg"
    cv2.imwrite(str(fp), frame(base, fd))
    th0, th1 = work / "thumb0.jpg", work / "thumb1.jpg"
    scene_style.compose_still(str(fp), TIMELINE, snap0, work / "t0", dim_scene, str(th0), {"text": "주방 정리\n끝판왕"})
    scene_style.compose_still(str(fp), TIMELINE, snap, work / "t1", dim_scene, str(th1), {"text": "주방 정리\n끝판왕"})
    tr = luma(cv2.imread(str(th1)), box(dim_scene)) / max(1, luma(cv2.imread(str(th0)), box(dim_scene)))
    print(f"썸네일 어둡게 밝기 비율 {tr:.3f}")
    if not (.25 <= tr <= .40):
        fails.append(f"썸네일 어둡게 비율 {tr:.3f}")
    # 4) 캡컷 초안
    dims = scene_style.dim_spans(scenes, snap, layers, work / "w1")
    zooms = scene_style.zoom_spans(scenes, snap)
    plan = {"beats": [{"beat_idx": b["beat_idx"], "role": b["role"], "narration": b["narration"],
                       "primary": {"video_id": "v0", "start": b["t0"], "end": b["t0"] + b["dur"]}} for b in TIMELINE]}
    draft, _ = capcut_draft.build_draft(plan=plan, timeline=TIMELINE, source_video_paths={"v0": str(base)},
                                        tts_paths={}, asset_paths={str(base): "C:/CapCut/QA/base.mp4"},
                                        project_name="QA", scene_overlay_layers=[], scene_dim_layers=[
                                            {**d, "_capcut_path": d["path"]} for d in dims],
                                        scene_zoom_spans=zooms)
    vt = next(t for t in draft["tracks"] if t["type"] == "video" and t["segments"] and
              all(s["material_id"] in {m["id"] for m in draft["materials"]["videos"] if m["path"].endswith("base.mp4")} for s in t["segments"]))
    segs = [(s["target_timerange"]["start"] / 1e6, s["target_timerange"]["duration"] / 1e6,
             s["clip"]["scale"]["x"], s["source_timerange"]["start"] / 1e6) for s in vt["segments"]]
    print("캡컷 영상 조각(시작·길이·확대·원본시작):", [tuple(round(x, 3) for x in s) for s in segs])
    for i in jumped:
        mid = (scenes[i]["start"] + scenes[i]["end"]) / 2
        z = next((s[2] for s in segs if s[0] <= mid < s[0] + s[1]), None)
        if z is None or abs(z - eff[str(i)]["zoom"]) > .001:
            fails.append(f"캡컷 장면 {i} 확대 {z} (기대 {eff[str(i)]['zoom']})")
    cont = all(abs(segs[k][0] + segs[k][1] - segs[k + 1][0]) < 1e-3 and abs(segs[k][3] + segs[k][1] - segs[k + 1][3]) < 2e-3
               for k in range(len(segs) - 1) if segs[k][3] + segs[k][1] < segs[k + 1][3] + 1)
    if not cont:
        fails.append("캡컷 조각을 나눈 곳에서 원본이 끊기거나 겹친다")
    dt = next((t for t in draft["tracks"] if t.get("name") == "scene-style-dim"), None)
    dseg = [(s["target_timerange"]["start"] / 1e6, s["target_timerange"]["duration"] / 1e6) for s in (dt or {}).get("segments", [])]
    print("캡컷 어둡게 트랙:", [tuple(round(x, 3) for x in s) for s in dseg])
    want = sorted([(0.0, round(.13 * 30) / 30), (scenes[dim_scene]["start"], scenes[dim_scene]["end"] - scenes[dim_scene]["start"])])
    if len(dseg) != 2 or any(abs(x[0] - y[0]) > .02 or abs(x[1] - y[1]) > .02 for x, y in zip(sorted(dseg), want)):
        fails.append(f"캡컷 어둡게 구간 {dseg} (기대 {want})")
    for d in dims:
        from PIL import Image
        im = Image.open(d["path"])
        alpha = im.getpixel((540, (box(0)[0] + box(0)[1]) // 2))[3]
        print("어둡게 막", Path(d["path"]).name, "가운데 투명도", alpha, "/ 위쪽(틀) 투명도", im.getpixel((540, 10))[3])
    print("\n결과:", "통과" if not fails else "실패")
    for f in fails:
        print("  ✗", f)
    print("작업 폴더:", work)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
