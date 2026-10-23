# -*- coding: utf-8 -*-
"""bench.layout — 밝은 장면 위 창 안 자막 띠 시험 (관제 097, 2026-10-23).

실사례: 울지마트롯 JlgdcIk9Gd0 — 눈 덮인 장면이라 '밝은 글자+외곽선' 존재율이 창 전체에서 0.3 을 넘어
자막 띠가 창 전체 [441,1436] 로 나왔다(실측 1168~1246).

답을 아는 합성 영상(360×640): 검정 바탕, 창 y147~479 에 흰 바탕+검정 격자가 계속 흐르는 장면(밝은 잉크+테두리가 창 전체에 있음),
창 안 y390~416 에 흰 글자+검정 테두리 자막이 3초마다 바뀌며 멈춰 있다. 정답 띠 ≈ y390~416.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from shopping_shorts.channelkit.bench import layout, probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


@pytest.fixture(scope="module")
def vid(tmp_path_factory):
    d = tmp_path_factory.mktemp("statcap")
    out = d / "cap.mp4"
    from PIL import Image, ImageDraw
    for i, txt in enumerate(["ABCDEFGH", "IJKLMNOP", "QRSTUVWX", "YZABCDEF", "GHIJKLMN", "OPQRSTUV"]):
        im = Image.new("RGBA", (360, 640), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for k, ch in enumerate(txt):
            x = 60 + k * 30
            dr.rectangle([x - 3, 387, x + 21, 419], fill=(15, 15, 15, 255))
            dr.rectangle([x, 390, x + 18, 416], fill=(255, 255, 255, 255))
        im.save(d / f"c{i}.png")
    flt = ("[1]format=gray,geq=lum='if(lt(mod(X+T*90,24),3)+lt(mod(Y+T*60,24),3),20,235)',format=yuv420p[s];"
           "[0][s]overlay=0:147[b];")
    inputs = ["-f", "lavfi", "-i", "color=black:s=360x640:r=30:d=18",
              "-f", "lavfi", "-i", "color=white:s=360x332:r=30:d=18"]
    last = "b"
    for i in range(6):
        inputs += ["-loop", "1", "-t", "18", "-i", str(d / f"c{i}.png")]
        flt += f"[{last}][{i + 2}]overlay=0:0:enable='between(t,{i * 3},{i * 3 + 2.99})'[o{i}];"
        last = f"o{i}"
    flt += f"[{last}]format=yuv420p"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", flt, "-t", "18", str(out)], check=True)
    return str(out)


def test_caption_band_on_bright_scene(vid):
    lv = layout.measure_video(vid, probe.info(vid))
    cap = lv.get("caption") or {}
    band = cap.get("band")
    assert band and abs(band[0] - 387) <= 8 and abs(band[1] - 419) <= 8, (cap, lv.get("window"))
