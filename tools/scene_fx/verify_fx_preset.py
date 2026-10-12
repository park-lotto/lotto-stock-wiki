# -*- coding: utf-8 -*-
"""강조효과 프리셋 + 내 프리셋에서 강조효과 빼기(관제 158) — 편집기에서 실제로 버튼을 눌러 보고, 완성본·캡컷까지 따라간다.

  py tools/scene_fx/verify_fx_preset.py --src <바탕영상> [--work <폴더>] [--movie 비교영상.mp4]

① 새 영상을 열면 AI 추천이 깔린다 — 짤 칸(연결어)은 'meme' 장면으로 잡힌다(서버 scene_style.moment_of).
② 한 장면을 손으로 고친다(제품 공개에 흑백 추가).
③ [＋ 새로 만들기] → 표를 눌러 정한다(훅=어둡게+0.5초 확대 · 연결어=확대→복귀 · CTA=쭉 당기기 · 나머지 없음) → [이 표로 저장하고 적용].
   → 표대로 다시 깔리고, 손으로 고친 장면은 그대로여야 한다.
④ 같은 브라우저로 새 영상을 열면 그 프리셋이 바로 깔린다(마지막 선택 기억).
⑤ [AI 추천]을 누르면 AI가 깐 상태로 돌아간다.
⑥ 내 프리셋 저장에 강조효과(effects)·효과팩 번호·강조효과 프리셋이 안 담기고, 내 프리셋 적용이 효과팩 번호·장면 효과를 안 바꾼다.
⑦ 서버 검사(validate_snapshot)가 프리셋을 받고, 틀린 프리셋은 거절한다.
⑧ 완성본(compose): 훅 장면이 어둡고 확대, 연결어 장면 확대 / 캡컷(capcut_fx_spans): 훅·연결어·CTA 장면에 확대 구간.
"""
import argparse, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
import cv2  # noqa: E402
from verify_scene_fx import make_base, frame, scale_between, luma  # noqa: E402

TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 2.0},
    {"beat_idx": 2, "role": "공개", "narration": "이게 바로 그 태그건입니다", "t0": 4.0, "dur": 2.0},
    {"beat_idx": 3, "role": "twist", "meme": True, "narration": "이게 미친 포인트인 게 한 번에 꽂혀요", "t0": 6.0, "dur": 2.0},
    {"beat_idx": 4, "role": "고조1", "narration": "옷감도 안 상해요", "t0": 8.0, "dur": 1.5},
    {"beat_idx": 5, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 9.5, "dur": 2.5},
]
WANT = {"hook": ["dim", "in"], "problem": [], "reveal": [], "meme": ["inout"], "peak": [], "cta": ["pull"]}

PAGE_JS = r"""
const fs=require('fs'),puppeteer=require('puppeteer');
(async()=>{
  const req=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const browser=await puppeteer.launch({headless:true});
  const out={errors:[],steps:{}};
  try{
    const page=await browser.newPage();await page.setViewport({width:1600,height:1100});
    page.on('pageerror',e=>out.errors.push(e.message));
    let promptAnswer='';page.on('dialog',d=>d.accept(promptAnswer));
    await page.setRequestInterception(true);
    page.on('request',r=>{const u=r.url();
      if(req.files[u])return r.respond({status:200,contentType:'image/jpeg',headers:{'access-control-allow-origin':'*'},body:fs.readFileSync(req.files[u])});
      if(u.includes('/scene_focus/'))return r.respond({status:200,contentType:'application/json',body:JSON.stringify({ok:true,box:null})});
      r.continue();});
    const wait=ms=>new Promise(r=>setTimeout(r,ms));
    // 누를 단추를 화면 가운데로 굴린 뒤 누른다 — 아래 고정된 [현재 설정 저장] 띠가 화면 끝 단추를 덮는다(사람도 굴려서 누른다)
    const tap=async sel=>{await page.$eval(sel,el=>el.scrollIntoView({block:'center'}));await wait(60);await page.click(sel);};
    const fxAll=()=>page.evaluate(()=>window.sceneStyle.moments().map((m,i)=>({i,m,fx:window.sceneStyle.sceneFx(i)})));
    const openJob=async()=>{
      await page.goto(req.page,{waitUntil:'networkidle0'});
      // 제작소가 새 영상에 보내는 것과 같이 — snapshot 없음(새 작업: 편집기가 api.snapshot()+freshEffects 로 시작)
      await page.evaluate(r=>window.postMessage({type:'scene-style-context',context:r.context},location.origin),req);
      await wait(2500);
      await page.evaluate(()=>[...document.querySelectorAll('.edit-pane .tool-tabs button')].find(b=>b.textContent.includes('효과'))?.click());
      await wait(300);
    };
    await page.goto(req.page,{waitUntil:'networkidle0'});await page.evaluate(()=>localStorage.clear());
    // ① 새 영상 — AI 추천
    await openJob();
    out.steps.ai=await fxAll();
    out.steps.aiLabel=await page.$$eval('[data-fxp]',bs=>bs.map(b=>[b.textContent,b.classList.contains('active')]));
    // ② 손으로 고치기: 제품 공개 장면에 흑백 추가
    const reveal=out.steps.ai.find(s=>s.m==='reveal').i;
    await page.evaluate(i=>window.sceneStyle.show(i),reveal);await wait(200);
    await tap('[data-scene-fx="shock"]');await wait(300);
    out.steps.revealHand=await page.evaluate(i=>window.sceneStyle.sceneFx(i),reveal);
    // ③ 새로 만들기 → 표 누르기 → 저장
    await tap('[data-fxp="new"]');await wait(200);
    for(const [m,want] of Object.entries(req.want)){
      for(;;){const on=await page.$$eval(`[data-fxp-row="${m}"] [data-fxp-kind].active`,bs=>bs.map(b=>b.dataset.fxpKind));const extra=on.find(k=>!want.includes(k));if(!extra)break;await tap(`[data-fxp-row="${m}"] [data-fxp-kind="${extra}"]`);}
      for(const k of want){const on=await page.$$eval(`[data-fxp-row="${m}"] [data-fxp-kind].active`,bs=>bs.map(b=>b.dataset.fxpKind));if(!on.includes(k))await tap(`[data-fxp-row="${m}"] [data-fxp-kind="${k}"]`);}
    }
    out.steps.editTable=await page.$$eval('[data-fxp-row]',rows=>Object.fromEntries(rows.map(r=>[r.dataset.fxpRow,[...r.querySelectorAll('[data-fxp-kind].active')].map(b=>b.dataset.fxpKind)])));
    promptAnswer='훅 어둡게';await tap('[data-fxp-act="save"]');await wait(1500);
    out.steps.preset=await fxAll();
    out.steps.presetLabel=await page.$$eval('[data-fxp]',bs=>bs.map(b=>[b.textContent,b.classList.contains('active')]));
    out.steps.snapPreset=await page.evaluate(()=>window.sceneStyle.snapshot().fxPreset||null);
    out.steps.snapshot=await page.evaluate(()=>window.sceneStyle.snapshot());
    // ⑥ 내 프리셋 저장 — 강조효과가 안 담기나
    const mpBefore=out.steps.snapshot.motionPack||'';
    await page.evaluate(()=>document.querySelector('[data-left-tab="mine"]')?.click());await wait(200);
    promptAnswer='내 자막';await tap('[data-my-save]');await wait(300);
    out.steps.mine=await page.evaluate(()=>JSON.parse(localStorage.getItem('scene_style_my_presets')||'[]')[0]?.snap||null);
    // 저장본에 다른 효과팩 번호를 박아 둔 옛 프리셋이라도 적용이 번호·장면 효과를 안 바꾸나
    await page.evaluate(()=>{const l=JSON.parse(localStorage.getItem('scene_style_my_presets'));l[0].snap.motionPack='7';l[0].snap.effects={'0':{shock:true}};localStorage.setItem('scene_style_my_presets',JSON.stringify(l));});
    await page.evaluate(()=>document.querySelector('[data-left-tab="scene"]')?.click());await page.evaluate(()=>document.querySelector('[data-left-tab="mine"]')?.click());await wait(200);
    await tap('[data-my-apply]');await wait(800);
    out.steps.afterMine={motionPack:await page.evaluate(()=>window.sceneStyle.snapshot().motionPack||''),fx:await fxAll(),mpBefore};
    // ④ 새 영상 다시 열기 — 마지막 강조효과 프리셋이 이어지나
    await openJob();
    out.steps.next=await fxAll();
    out.steps.nextPreset=await page.evaluate(()=>window.sceneStyle.snapshot().fxPreset||null);
    // ⑤ AI 추천으로 되돌리기
    await tap('[data-fxp="ai"]');await wait(1200);
    out.steps.back=await fxAll();
    out.steps.backPreset=await page.evaluate(()=>window.sceneStyle.snapshot().fxPreset||null);
    await page.screenshot({path:req.shot});
  }finally{fs.writeFileSync(req.out,JSON.stringify(out));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--work")
    ap.add_argument("--movie")
    a = ap.parse_args()
    from shopping_shorts import scene_style
    work = Path(a.work or tempfile.mkdtemp(prefix="fx_preset_"))
    work.mkdir(parents=True, exist_ok=True)
    total = sum(b["dur"] for b in TIMELINE)
    base = work / "base.mp4"
    make_base(a.src, base, sec=total)
    fails = []

    def need(ok, msg):
        print(("  통과  " if ok else "★ 실패  ") + msg)
        if not ok:
            fails.append(msg)
    snap0 = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop"}
    hc = {"text": "옷 정리\n끝판왕"}
    ctx = scene_style.context_for(TIMELINE, hc, snap0, "qa")
    ctx.update(jobId="qa", fxEnabled=True, autoNew=True)
    scenes = ctx["scenes"]
    moments = [sc.get("moment") for sc in scenes]
    need("meme" in moments and moments[[sc["beat_idx"] for sc in scenes].index(3)] == "meme",
         f"짤 칸(twist+짤) = 연결어 'meme' 으로 잡힘 {moments}")
    need(scene_style.moment_of("twist") == "peak" and scene_style.moment_of("훅", True) == "hook" and scene_style.moment_of("benefit", True) == "meme",
         "moment_of: 짤 없는 twist=고조 · 훅+짤=훅 · benefit+짤=연결어")
    files = {}
    for si, sc in enumerate(scenes):
        pts = []
        for k, t in enumerate((sc["start"] + .05, (sc["start"] + sc["end"]) / 2, sc["end"] - .05)):
            url = f"http://qa.local/api/produce/mix/beatframe/qa/{sc['beat_idx']}?at={t:.2f}"
            p = work / f"pt_{si}_{k}.jpg"
            cv2.imwrite(str(p), frame(base, round(t * 30)))
            files[url] = str(p); pts.append(url)
        sc["media_points"] = pts
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(ROOT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    req = work / "req.json"
    req.write_text(json.dumps({"context": ctx, "files": files, "want": WANT,
                               "page": f"http://127.0.0.1:{port}/out/scene-style-ui-showcase.html",
                               "out": str(work / "editor-out.json"), "shot": str(work / "editor.png")}, ensure_ascii=False), encoding="utf-8")
    js = work / "editor.js"; js.write_text(PAGE_JS, encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(ROOT.parent.parent / "node_modules") + os.pathsep + str(ROOT / "node_modules")}
    try:
        r = subprocess.run(["node", str(js), str(req)], capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        server.terminate()
    if not (work / "editor-out.json").exists():
        raise SystemExit("편집기 실행 실패: " + r.stderr[-1500:])
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8"))
    st = ed["steps"]
    if r.returncode:
        print("편집기 오류 끝:", r.stderr[-800:])
    first = {}
    for s in st.get("ai", []):
        if s["m"] and s["m"] not in first and (s["i"] == 0 or scenes[s["i"]]["beat_idx"] != scenes[s["i"] - 1]["beat_idx"]):
            first[s["m"]] = s["i"]
    fx_of = lambda step, m: sorted(next(x["fx"] for x in st[step] if x["i"] == first[m]))
    print("장면 첫 구절:", first)
    need(set(first) == set(WANT), f"장면 종류 6개가 편집기에 다 들어옴 {sorted(first)}")
    need(any(x["fx"] != ["none"] for x in st["ai"]) and fx_of("ai", "meme") != ["none"], f"① AI 추천 자동 배치 · 연결어 장면 {fx_of('ai', 'meme')}")
    need(st["aiLabel"][0] == ["AI 추천", True], f"① 처음엔 [AI 추천]이 선택 {st['aiLabel']}")
    need("shock" in st["revealHand"], f"② 손으로 고친 제품 공개 {st['revealHand']}")
    need({k: sorted(v) for k, v in st["editTable"].items()} == {k: sorted(v) for k, v in WANT.items()}, f"③ 표를 눌러 정함 {st['editTable']}")
    for m, want in WANT.items():
        got = fx_of("preset", m)
        if m == "reveal":
            need(got == sorted(st["revealHand"]), f"③ 손으로 고친 제품 공개는 그대로 {got}")
        else:
            need(got == (sorted(want) or ["none"]), f"③ 프리셋 적용 {m}: {got} (기대 {sorted(want) or ['none']})")
    others = [x for x in st["preset"] if x["fx"] != ["none"] and x["i"] not in first.values()]
    need(not others, f"③ 장면 첫 구절 말고는 안 깔림 {others}")
    need(any(lbl == "훅 어둡게" and on for lbl, on in st["presetLabel"]), f"③ 저장한 프리셋 버튼이 선택됨 {st['presetLabel']}")
    need({k: sorted(v) for k, v in ((st["snapPreset"] or {}).get("table") or {}).items()} == {k: sorted(v) for k, v in WANT.items()}, f"③ 영상 저장값에 fxPreset {st['snapPreset']}")
    mine = st["mine"] or {}
    need(mine and not ({"effects", "motionPack", "fxPreset"} & set(mine)), f"⑥ 내 프리셋 저장에 강조효과 없음 (키: {sorted(mine)[:40]})")
    am = st["afterMine"]
    need(am["motionPack"] == am["mpBefore"], f"⑥ 내 프리셋 적용 뒤 효과팩 번호 그대로 {am['mpBefore']!r} → {am['motionPack']!r}")
    need([x["fx"] for x in am["fx"]] == [x["fx"] for x in st["preset"]], "⑥ 내 프리셋 적용 뒤 장면 효과 그대로")
    for m, want in WANT.items():
        need(fx_of("next", m) == (sorted(want) or ["none"]), f"④ 새 영상에도 프리셋: {m} {fx_of('next', m)}")
    need((st["nextPreset"] or {}).get("name") == "훅 어둡게", "④ 새 영상 저장값에 프리셋 이름")
    need([x["fx"] for x in st["back"]] == [x["fx"] for x in st["ai"]] and st["backPreset"] is None, "⑤ [AI 추천]으로 되돌리면 AI가 깐 그대로")
    need(not ed["errors"], f"페이지 오류 {ed['errors'][:3]}")
    # ⑦ 서버 검사
    snap = st["snapshot"]
    try:
        v = scene_style.validate_snapshot(snap); need(snap.get("fxPreset") and v.get("fxPreset") == snap["fxPreset"], "⑦ 서버 검사가 fxPreset 을 받아 남김")
    except ValueError as e:
        need(False, f"⑦ 서버 검사 거절 {e}")
    for bad in ({"name": "x", "table": {"hook": ["in", "pull"]}}, {"name": "x", "table": {"nope": []}}, {"name": "x", "table": {"hook": ["fly"]}}):
        try:
            scene_style.validate_snapshot({**snap, "fxPreset": bad}); need(False, f"⑦ 틀린 프리셋을 받아 버림 {bad}")
        except ValueError:
            pass
    # ⑧ 완성본·캡컷 — 편집기가 저장한 그대로
    eff = snap.get("effects") or {}
    plain, out = work / "plain.mp4", work / "preset.mp4"
    scene_style.compose(str(base), TIMELINE, snap0, str(plain), work / "w0", hc)
    scene_style.compose(str(base), TIMELINE, {**snap0, "effects": eff}, str(out), work / "w1", hc)
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))

    def box(i):
        _, h, top, *_ = scene_style.media_geometry(layers[i], eff.get(str(i)))
        return top + 8, top + h - 8
    i = first["hook"]; f = round((scenes[i]["start"] + scenes[i]["end"]) / 2 * 30)
    b0, b1 = box(i)
    edge = [(b0, b0 + int((b1 - b0) * .25)), (b0 + int((b1 - b0) * .75), b1)]
    dark = sum(luma(frame(out, f), rr) for rr in edge) / max(1, sum(luma(frame(plain, f), rr) for rr in edge))
    print(f"   완성본 훅 장면 {i}: 밝기 비 {dark:.2f}")
    need(dark < .6, f"⑧ 완성본 훅 장면이 어두워짐 ({dark:.2f})")
    for m in ("meme", "cta"):
        i = first[m]; f0 = round(scenes[i]["start"] * 30); n = round(scenes[i]["end"] * 30) - f0
        z = scale_between(frame(plain, f0 + n // 2), frame(out, f0 + n // 2), box(i))
        print(f"   완성본 {m} 장면 {i}: 가운데 배율 {z}")
        need(z is not None and z > 1.05, f"⑧ 완성본 {m} 장면 확대 ({z})")
    i = first["problem"]; f = round((scenes[i]["start"] + scenes[i]["end"]) / 2 * 30)
    diff = float(cv2.absdiff(frame(plain, f), frame(out, f)).mean())
    need(diff < 3, f"⑧ 완성본 문제 장면은 효과 없음(프리셋이 비움) 차이 {diff:.2f}")
    spans = scene_style.capcut_fx_spans(scenes, {**snap0, "effects": eff}, layers)
    zs = {m: max((sp.get("zoom", 1) for sp in spans if abs(sp["start"] - scenes[first[m]]["start"]) < 1e-6), default=1) for m in ("hook", "meme", "cta", "problem")}
    print("   캡컷 장면별 확대:", zs)
    need(zs["hook"] > 1 and zs["meme"] > 1 and zs["cta"] > 1 and zs["problem"] <= 1, "⑧ 캡컷: 훅·연결어·CTA 확대, 문제 장면 없음")
    (work / "dim").mkdir(exist_ok=True)
    dims = scene_style.dim_spans(scenes, {**snap0, "effects": eff}, layers, work / "dim")
    dim_at = lambda m: any(abs(d["start"] - scenes[first[m]]["start"]) < 1e-6 for d in dims)
    print("   캡컷 어둡게 막:", [(round(d["start"], 2), round(d["end"], 2)) for d in dims])
    need(dim_at("hook") and not dim_at("meme") and not dim_at("peak"), "⑧ 캡컷: 훅 장면에만 어둡게 막(프리셋이 고조의 어둡게를 뺌)")
    if a.movie:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(plain), "-i", str(out), "-filter_complex",
                        "[0:v]scale=540:960[a];[1:v]scale=540:960[b];[a][b]hstack", "-an", "-c:v", "libx264", "-crf", "20",
                        "-pix_fmt", "yuv420p", a.movie], check=True)
        print("비교 영상:", a.movie)
    print("편집기 화면:", work / "editor.png")
    print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
