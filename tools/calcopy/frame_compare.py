"""틀 설명서(frame.json) → 라이브 렌더 경로(썸네일 = compose_still → render_layer_one)로 한 장 → 원본 프레임과 나란히 + 잉크 좌표표.

설계 2026-10-15-칼카피엔진 §6-3·§6-5(대조). 쓰는 법:
  py tools/calcopy/frame_compare.py <frame.json> <원본프레임.png> <출력폴더> --title "1줄\n2줄" --caption "자막"
나오는 것: <출력>/ours.png(우리 완성 구도 한 장) · <출력>/layer.png(투명 장면 레이어) · <출력>/compare.png(원본|우리) ·
          표준출력에 층별 잉크 상자(원본 vs 우리, 차이 px).
원본의 영상 창은 설명서의 video 층 자리에서 오려 우리 영상 창에 넣는다(같은 그림을 깔아야 틀만 비교된다).
"""
import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from shopping_shorts import scene_style  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402


def timeline_for(caption):
    # 20초 — 설명서의 template_off(끝 N초 틀 끄기)에 걸리지 않는 첫 장면 하나(짧게 잡으면 첫 장면이 '끝 N초' 안이 돼 틀이 꺼진다)
    return [{"beat_idx": 0, "t0": 0, "dur": 20, "narration": caption, "caption_lines": [caption], "role": "hook",
             "primary": {"video_id": "s0", "start": 0, "end": 20}}]


def ink_box(im, y0, y1, x0=0, x1=None, dark=200):
    """[y0,y1)×[x0,x1) 안에서 어두운 점(r+g+b<dark)의 상자 (x0,y0,x1,y1) — 없으면 None."""
    im = im.convert("RGB"); x1 = x1 or im.width; px = im.load()
    xs, ys = [], []
    for y in range(max(0, y0), min(im.height, y1)):
        for x in range(max(0, x0), min(im.width, x1)):
            if sum(px[x, y]) < dark:
                xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def line_runs(im, y0, y1, x0, x1, dark, want):
    """구역 안 어두운 점이 있는 줄들을 빈 줄 기준으로 덩어리로 나눠 위에서부터 want 개 상자 — 제목처럼 줄 칸이 붙은 층용.
    (칸 경계로 자르면 글자가 칸을 몇 px 넘을 때 옆 줄 잉크가 섞인다 — 2026-10-16 실측 title1 이 둘째 줄 윗부분을 먹었다)"""
    im = im.convert("RGB"); px = im.load()
    rows = [y for y in range(max(0, y0), min(im.height, y1))
            if sum(1 for x in range(max(0, x0), min(im.width, x1)) if sum(px[x, y]) < dark) > 3]
    runs, s, p = [], None, None
    for y in rows:
        if s is None:
            s = y
        elif y != p + 1:
            runs.append((s, p)); s = y
        p = y
    if s is not None:
        runs.append((s, p))
    runs = sorted(sorted(runs, key=lambda r: r[0] - r[1])[:want])   # 키 큰 덩어리 want 개(점 같은 잡티 제외)를 위→아래로
    return [ink_box(im, a, b + 1, x0, x1, dark) for a, b in runs] + [None] * (want - len(runs))


def measure(im, spec):
    """설명서의 글자 층마다 실제 잉크 상자 — 원본과 우리를 같은 구역·같은 방법으로 잰다."""
    out = []
    for l in spec["layers"]:
        if l["kind"] != "text":
            continue
        x0 = l["x"] - l["w"] / 2 if l["align"] == "center" else (l["x"] if l["align"] == "left" else l["x"] - l["w"])
        dark = 400 if l["role"] == "brand" else 200
        n = l["lines"] if l["role"] == "title" else 1
        boxes = line_runs(im, int(l["y"] - 12), int(l["y"] + n * l["line_h"] + 12), int(max(0, x0 - 40)), int(x0 + l["w"] + 40), dark, n)
        for i, b in enumerate(boxes):
            out.append((f"{l['role']}{i + 1 if n > 1 else ''}", b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("original"); ap.add_argument("out")
    ap.add_argument("--title", default=""); ap.add_argument("--caption", default="")
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    frame = json.loads(pathlib.Path(a.frame).read_text(encoding="utf-8"))
    spec = schema.validate(frame)
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    original = Image.open(a.original).convert("RGB")
    video = next((l for l in spec["layers"] if l["kind"] == "video"), None)
    src = out / "video_src.png"
    (original.crop((video["x"], video["y"], video["x"] + video["w"], video["y"] + video["h"])) if video else original).save(src)
    tl = timeline_for(a.caption)
    head = {"text": a.title.replace("\\n", "\n")}
    ours = out / "ours.png"
    scene_style.compose_still(str(src), tl, snap, out / "work", 0, ours, head)
    shutil.copy(out / "work" / json.loads((out / "work" / "scene-style-layers.json").read_text(encoding="utf-8"))[0]["file"], out / "layer.png")
    mine = Image.open(ours).convert("RGB")
    print(f"{'층':10s} {'원본 (x0,y0,x1,y1)':28s} {'우리 (x0,y0,x1,y1)':28s} 차이(x0,y0,x1,y1)")
    rows = []
    for (name, b0), (_, b1) in zip(measure(original, spec), measure(mine, spec)):
        diff = tuple(q - p for p, q in zip(b0, b1)) if b0 and b1 else None
        rows.append({"layer": name, "original": b0, "ours": b1, "diff": diff})
        print(f"{name:10s} {str(b0):28s} {str(b1):28s} {diff}")
    (out / "ink.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    W, H = original.size
    sheet = Image.new("RGB", (W * 2 + 30, H + 80), (40, 40, 40))
    sheet.paste(original, (0, 80)); sheet.paste(mine.resize((W, H)), (W + 30, 80))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(str(ROOT / "shopping_shorts/static/fonts/NotoSansKR-Bold.otf"), 44)
    except OSError:
        f = None
    d.text((20, 15), f"원본 {spec['source'] or ''}", fill="white", font=f)
    d.text((W + 50, 15), "우리 (frame.json → 라이브 렌더러)", fill="white", font=f)
    sheet.save(out / "compare.png")
    print("compare:", out / "compare.png")


if __name__ == "__main__":
    main()
