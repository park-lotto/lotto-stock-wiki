"""일본어 작업을 템플릿 21종(썰 스타일 20 + 템플릿 없음)으로 이 PC에서 렌더해 한 장 모음으로 본다(관제 254).

장면은 훅 1장 + 가장 긴 본문 자막 2장만 그린다(템플릿당 1분 안). 훅 제목·자막 나누기는 **이 폴더 코드**로 다시 계산한다.
저장된 꾸미기 설정(효과·글꼴·강조 등)은 그대로 두고 presetId 만 바꾼다.

  py tools/ja_caption/all_templates_check.py <job_id> <작업폴더>   (<작업폴더>/clean.mp4 = 서버 final_clean_*.mp4)
"""
import itertools, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _scenes(ctx):
    from shopping_shorts.video_assemble import _caption_segments
    out = []
    for _, grp in itertools.groupby(ctx["scenes"], key=lambda s: s["beat_idx"]):
        grp = list(grp); caps = [s for s in grp if s["caption"]]
        if not caps:
            continue
        segs = _caption_segments("".join(s["caption"] for s in caps))
        t0, t1 = caps[0]["start"], caps[-1]["end"]; tot = sum(map(len, segs)); t = t0
        for x in segs:
            d = (t1 - t0) * len(x) / tot; sc = dict(caps[0]); sc.update(start=t, end=t + d, caption=x); sc.pop("words", None); out.append(sc); t += d
    body = sorted([s for s in out if s["kind"] != "hook"], key=lambda s: -len(s["caption"]))[:2]
    return [out[0]] + sorted(body, key=lambda s: s["start"])


def main(job, work):
    from PIL import Image, ImageDraw
    from tools.live_admin import admin_page
    from shopping_shorts.template_copy import scene_text
    work = Path(work)
    with admin_page("produce") as pg:
        j = pg.evaluate(f"fetch('/api/produce/scene-style/context/{job}').then(r=>r.json())")
    ctx, snap = j["context"], j["snapshot"]
    first = "".join(s["caption"] for s in ctx["scenes"] if s["beat_idx"] == ctx["scenes"][0]["beat_idx"])
    text = {**ctx["text"], **scene_text({"text": first})}
    scenes = _scenes(ctx)
    data = (ROOT / "out/precision20-data.js").read_text(encoding="utf-8")
    ids = [p["id"] for p in json.loads(data[len("PRECISION20="):].strip().rstrip(";"))]
    env = dict(os.environ, NODE_PATH=str(ROOT.parents[1] / "node_modules") if ROOT.parent.name == ".tracks" else str(ROOT / "node_modules"))
    rows = []
    for pid in ids:
        out = work / pid; out.mkdir(parents=True, exist_ok=True)
        sn = dict(snap, presetId=pid); sn.pop("text", None); sn.pop("sceneTexts", None)
        if pid != "plain":
            sn.pop("plainCaption", None)
        c = dict(ctx, scenes=scenes, text=text)
        req = out / "req.json"; req.write_text(json.dumps({"snapshot": sn, "context": c, "output": str(out)}, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", str(ROOT / "tools/render_scene_style.js"), str(req)], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tiles = []
        if r.returncode:
            print(pid, "실패", r.stderr[-300:]); continue
        for ly in json.loads((out / "scene-style-layers.json").read_text(encoding="utf-8")):
            s = scenes[ly["sceneIndex"]]; t = (s["start"] + s["end"]) / 2
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(work / "clean.mp4"), "-frames:v", "1", "-vf", "scale=1080:1920", str(out / "bg.png")], check=True)
            # 움직이는 장면은 마지막 프레임(등장이 끝난 모습)을 쓴다
            f = ly["file"]; an = ly.get("animation")
            if an and an.get("count"):
                f = an["pattern"] % (an["count"] - 1)
            im = Image.alpha_composite(Image.open(out / "bg.png").convert("RGBA"), Image.open(out / f).convert("RGBA")).convert("RGB")
            tiles.append(im.resize((216, 384)))
        row = Image.new("RGB", (216 * 3 + 90, 384), "white"); ImageDraw.Draw(row).text((4, 180), pid, fill="black")
        for i, im in enumerate(tiles):
            row.paste(im, (90 + i * 216, 0))
        rows.append(row); print(pid, len(tiles))
    cols = 3; h = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (rows[0].width * cols, 384 * h), "white")
    for i, row in enumerate(rows):
        sheet.paste(row, ((i % cols) * rows[0].width, (i // cols) * 384))
    sheet.save(work / "templates.png"); print(work / "templates.png", sheet.size, "hook:", text.get("hook1"), "/", text.get("hook2"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
