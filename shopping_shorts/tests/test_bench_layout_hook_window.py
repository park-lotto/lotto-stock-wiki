# -*- coding: utf-8 -*-
"""bench.layout — 앞 훅(틀이 다른 구간)이 창을 늘리는 결함 시험 (관제 097, 2026-10-23).

실사례: 울지마트롯 JlgdcIk9Gd0 — 0~4.5초 훅(검정 바탕 누끼가 화면 아래 끝까지 줌)이 편 전체 움직임 통계에 섞여
창이 [0,440,1080,1379](아래 끝 1819)로 늘었다. 실제 창은 y440~1436(왼쪽 열 밝기 6시점 실측).
편 전체 창이 화면의 95% 미만이라 조각 다수결(window_vote)을 건너뛴 것이 뿌리 — 다수결은 3/4 조각이 996 으로 맞혔다.

답을 아는 합성 영상(360×640 = 1080×1920 의 1/3): 검정 바탕 18초.
  0~4.5초 훅: y50~640 에 정지 그림 한 장을 1.00→1.07 천천히 확대(실제 훅 꼴 — 누끼 줌)
  4.5~18초 본문: 창 y147~479(=440~1436/3) 에 움직이는 testsrc2
정답 창 = y147, 높이 332 (±4px).
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from shopping_shorts.channelkit.bench import layout, probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


@pytest.fixture(scope="module")
def vid(tmp_path_factory):
    out = tmp_path_factory.mktemp("hookwin") / "hook.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=black:s=360x640:r=30:d=18",
                    "-f", "lavfi", "-i", "testsrc2=s=360x590:r=30:d=0.04",
                    "-f", "lavfi", "-i", "testsrc2=s=360x332:r=30:d=13.5",
                    "-filter_complex", "[1]loop=loop=-1:size=1,trim=duration=4.5,scale=w='360*(1+0.07*t/4.5)':h='590*(1+0.07*t/4.5)':eval=frame,crop=360:590,setpts=PTS-STARTPTS[h];"
                                       "[2]setpts=PTS-STARTPTS+4.5/TB[b];[0][h]overlay=0:50:eof_action=pass[t];"
                                       "[t][b]overlay=0:147:enable='gte(t,4.5)':eof_action=pass,format=yuv420p",
                    "-t", "18", str(out)], check=True)
    return str(out)


def test_hook_does_not_stretch_window(vid):
    lv = layout.measure_video(vid, probe.info(vid))
    x, y, w, h = lv["window"]
    assert abs(y - 147) <= 4 and abs(h - 332) <= 4, (lv["window"], lv.get("window_method"))
