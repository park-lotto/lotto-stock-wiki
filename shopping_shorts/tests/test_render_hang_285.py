# -*- coding: utf-8 -*-
"""관제 285 — 영상보다 긴 장면 시간표가 ffmpeg 를 끝없이 돌리던 사고(10-29 잇템로그 2편, 4시간 멈춤)."""
import subprocess
import time

import pytest

from shopping_shorts import scene_style
from tools.caption_pack.check_bench_packs import rows_to_timeline


def test_compose_stops_when_timeline_longer_than_video(tmp_path):
    video = tmp_path / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=360x640:r=30:d=1", "-pix_fmt", "yuv420p", str(video)],
                   check=True, stdin=subprocess.DEVNULL)
    tts = tmp_path / "s.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", str(tts)], check=True, stdin=subprocess.DEVNULL)
    rows = [{"line": "L1", "text": "앞", "t0": 0.0, "t1": 0.9, "speaker": "narr", "variant": "", "sticker": "", "emph": ""},
            {"line": "L2", "text": "뒤", "t0": 1.5, "t1": 2.0, "speaker": "narr", "variant": "", "sticker": "", "emph": ""}]
    tl = rows_to_timeline(rows, tts, 2.0)
    snap = scene_style.validate_snapshot({"version": 1, "mode": "story", "presetId": "plain", "sceneIndex": 0, "frameKind": "body",
                                          "frameRule": "body_all", "text": {"channel": "", "hook1": "", "hook2": "", "bodyTitle": ""}})
    t = time.time()
    with pytest.raises(RuntimeError, match="장면 시간표가 영상보다 길다"):
        scene_style.compose(str(video), tl, snap, str(tmp_path / "out.mp4"), tmp_path / "cw", {"text": ""})
    assert time.time() - t < 30
