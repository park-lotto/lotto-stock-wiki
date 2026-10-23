# -*- coding: utf-8 -*-
"""bench.captions.caption_anim — 움직이는 밝은 영상 위 자막 등장효과 (관제 097, 2026-10-23).

실사례: 울지마트롯 JlgdcIk9Gd0 — 자막은 한 프레임에 바뀌는데(프레임 모음 확인) 눈 덮인 영상 줌이 잉크로 잡혀 '확대/축소'.
합성: 흐르는 흰 격자 영상 위 흰 글자+검정 테두리 상자. (가) 바로 뜸 → '없음'  (나) 0.3초 동안 0.5→1.0 확대 → '없음'이 아니어야.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from shopping_shorts.channelkit.bench import captions

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")

# 밝은 그림 한 장이 천천히 커지는 장면(울지마트롯 눈 장면 꼴). 매 프레임 무작위 점무늬·주기 격자는 '밝은 채 그대로'인 화소가 많아
# 실제 영상과 달랐다
SCENE = "hue=s=0,eq=brightness=0.35:contrast=1.6,scale=w='360*(1+0.15*t/3)':h='640*(1+0.15*t/3)':eval=frame,crop=360:640"


def _make(path, zoom: bool):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (300, 40), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for k in range(8):
        x = 6 + k * 36
        dr.rectangle([x, 4, x + 28, 36], fill=(15, 15, 15, 255))
        dr.rectangle([x + 3, 7, x + 25, 33], fill=(255, 255, 255, 255))
    png = str(path) + ".png"
    im.save(png)
    sc = "scale=w='300*min(1,0.5+0.5*(t-1)/0.3)':h='40*min(1,0.5+0.5*(t-1)/0.3)':eval=frame," if zoom else ""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=s=360x640:r=30:d=0.04",
                    "-loop", "1", "-t", "3", "-framerate", "30", "-i", png,
                    "-filter_complex", f"[0]loop=loop=-1:size=1,trim=duration=3,setpts=PTS-STARTPTS,{SCENE},format=yuv420p[s];[1]{sc}format=rgba[c];"
                                       "[s][c]overlay=x='(W-w)/2':y='420-h/2':enable='gte(t,1)':eval=frame,format=yuv420p",
                    "-t", "3", str(path)], check=True)


@pytest.fixture(scope="module")
def vids(tmp_path_factory):
    d = tmp_path_factory.mktemp("anim")
    out = {}
    for name, z in (("instant", False), ("zoom", True)):
        _make(d / f"{name}.mp4", z)
        out[name] = str(d / f"{name}.mp4")
    return out


VL = {"canvas": [360, 640], "window": [0, 0, 360, 640], "caption": {"pos": "inside", "band": [395, 445], "ink": "bright"},
      "bg_rgb": [0, 0, 0]}


def test_instant_caption_on_moving_bright_scene(vids):
    assert captions.caption_anim(vids["instant"], VL, 0.93, 30.0) == "없음"


def test_zoom_caption_not_instant(vids):
    assert captions.caption_anim(vids["zoom"], VL, 0.93, 30.0) != "없음"
