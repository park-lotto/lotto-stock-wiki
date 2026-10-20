# -*- coding: utf-8 -*-
"""재미썸홈 = 숏템 템플릿 t11(이븐쇼핑 원본형)에 브랜드만 '재미썸홈'. 새로 뜯지 않는다(사장님 10-16 확정).

장면꾸미기 렌더 길(scene_style.compose_still = render_layer_one + compose 와 같은 기하)로 훅 1장·본문 1장을 그리고,
이븐쇼핑 원본 같은 시각 프레임과 나란히 붙인다(0순위-A1a: 화면이 아니라 렌더 길로 확인).
    PYTHONUTF8=1 py channel/evenshopping/preset/숏템템플릿/render_template.py
출력: C:/숏템_칼카피/evenshopping/preset_render/{hook,body}.jpg · 대조.jpg (+ 이 폴더의 대조_프레임.jpg 사본)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from shopping_shorts import scene_style  # noqa: E402

M = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
OUT = Path("C:/숏템_칼카피/evenshopping/preset_render")
SRC = Path("C:/숏템_칼카피/evenshopping/작품1_총알람")
ORIG = Path("C:/숏템_칼카피/evenshopping/mp4")


def grab(mp4, t, png):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", str(png)],
                   check=True, stdin=subprocess.DEVNULL)
    return png


def main():
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
    snap = {"mode": "story", "presetId": M["template"]["preset_id"],
            "text": {"channel": M["brand"]["channel_name"], **M["sample_title"]}}
    hook_line = M["sample_title"]["_spoken"]
    timeline = [
        {"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": hook_line, "caption_lines": [hook_line], "role": "hook",
         "primary": {"video_id": "s0", "start": 0, "end": 2}},
        {"beat_idx": 1, "t0": 2.0, "dur": 2.0, "narration": "최근 등교 전쟁 겪는 엄마들 사이에서", "caption_lines": ["최근 등교 전쟁 겪는 엄마들 사이에서"],
         "role": "body", "primary": {"video_id": "s0", "start": 2, "end": 4}},
    ]
    ctx = scene_style.context_for(timeline, None, scene_style.validate_snapshot(snap))
    body_i = next(i for i, s in enumerate(ctx["scenes"]) if s["beat_idx"] == 1)
    shots = {}
    for tag, idx, (mp4, t) in (("hook", 0, (SRC / "src_AP-6U2s1j9A.mp4", 10.0)), ("body", body_i, (SRC / "src_ProcmLGVjUs.mp4", 50.0))):
        frame = grab(mp4, t, OUT / f"src_{tag}.png")
        shots[tag] = scene_style.compose_still(frame, timeline, snap, OUT / f"work_{tag}", idx, OUT / f"{tag}.jpg")
        print(tag, idx, ctx["scenes"][idx]["kind"], ctx["scenes"][idx]["caption"])
    ref = M["compare_ref"]
    o_hook = grab(ORIG / f"{ref['id']}.mp4", ref["hook_t"], OUT / "orig_hook.png")
    o_body = grab(ORIG / f"{ref['id']}.mp4", ref["body_t"], OUT / "orig_body.png")
    tiles = [(o_hook, f"이븐쇼핑 {ref['id']} {ref['hook_t']}s"), (shots["hook"], "재미썸홈 훅(t11)"),
             (o_body, f"이븐쇼핑 {ref['id']} {ref['body_t']}s"), (shots["body"], "재미썸홈 본문(t11)")]
    W, H = 540, 960
    sheet = Image.new("RGB", (W * 4 + 30, H + 40), "white")
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    d = ImageDraw.Draw(sheet)
    for i, (p, label) in enumerate(tiles):
        im = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        sheet.paste(im, (i * (W + 10), 40)); d.text((i * (W + 10) + 6, 8), label, fill="black", font=font)
    sheet.save(OUT / "대조.jpg", quality=88)
    shutil.copy(OUT / "대조.jpg", HERE / "대조_프레임.jpg")
    print("saved", OUT / "대조.jpg")


if __name__ == "__main__":
    main()
