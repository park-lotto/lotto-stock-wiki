"""일본어 자막을 라이브 배포 없이 이 PC에서 렌더해 본다(관제 254, 2026-10-22 사장님 "라이브 말고 렌더해서 보여줄 수 있잖아").

라이브 장면 정보(context·snapshot)와 서버의 자막 없는 바탕(final_clean_*.mp4)을 받아,
**이 폴더의 코드**(_caption_segments)로 자막을 다시 나눈 뒤 tools/render_scene_style.js 로 레이어를 만들고
바탕 프레임에 얹어 모음 한 장을 만든다.

  py tools/ja_caption/local_render_check.py <job_id> <작업폴더>
  (바탕 영상: <작업폴더>/clean.mp4 — scp 로 서버 data/mix_jobs/<job>/final_clean_*.mp4 를 받아 둔다)
"""
import itertools, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(job, work):
    from PIL import Image, ImageDraw
    from tools.live_admin import admin_page
    from shopping_shorts.video_assemble import _caption_segments
    work = Path(work); (work / "layers").mkdir(parents=True, exist_ok=True)
    with admin_page("produce") as pg:
        j = pg.evaluate(f"fetch('/api/produce/scene-style/context/{job}').then(r=>r.json())")
    ctx, snap = j["context"], j["snapshot"]
    out = []
    for _, grp in itertools.groupby(ctx["scenes"], key=lambda s: s["beat_idx"]):
        grp = list(grp); caps = [s for s in grp if s["caption"]]
        if not caps:
            out += grp; continue
        segs = _caption_segments("".join(s["caption"] for s in caps))
        t0, t1 = caps[0]["start"], caps[-1]["end"]; tot = sum(map(len, segs)); t = t0
        out += [s for s in grp if not s["caption"] and s["end"] <= t0 + 1e-3]
        for x in segs:   # 시간은 글자 수 비례(눈으로 잘림·크기 보는 용도)
            d = (t1 - t0) * len(x) / tot; sc = dict(caps[0]); sc.update(start=t, end=t + d, caption=x); sc.pop("words", None); out.append(sc); t += d
        out += [s for s in grp if not s["caption"] and s["start"] >= t1 - 1e-3]
    ctx["scenes"] = out
    req = work / "req.json"
    req.write_text(json.dumps({"snapshot": snap, "context": ctx, "output": str(work / "layers")}, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, NODE_PATH=str(ROOT.parents[1] / "node_modules") if ROOT.parent.name == ".tracks" else str(ROOT / "node_modules"))
    subprocess.run(["node", str(ROOT / "tools/render_scene_style.js"), str(req)], check=True, env=env)
    tiles = []
    for ly in json.loads((work / "layers/scene-style-layers.json").read_text(encoding="utf-8")):
        s = out[ly["sceneIndex"]]
        if not s["caption"]:
            continue
        t = (s["start"] + s["end"]) / 2
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(work / "clean.mp4"), "-frames:v", "1", "-vf", "scale=1080:1920", str(work / "bg.png")], check=True)
        im = Image.alpha_composite(Image.open(work / "bg.png").convert("RGBA"), Image.open(work / "layers" / ly["file"]).convert("RGBA"))
        im = im.convert("RGB").crop((0, 0, 1080, 1100)).resize((216, 220)); ImageDraw.Draw(im).text((3, 3), f"{t:.1f}s", fill="red"); tiles.append(im)
    cols = 9; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (216 * cols, 220 * rows), "white")
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * 216, (i // cols) * 220))
    sheet.save(work / "sheet.png"); print(work / "sheet.png", len(tiles), "자막")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
