# -*- coding: utf-8 -*-
"""bench.cuts — 가변 그림 칸(게시글형) 바탕 빼기 시험 (관제 097, 2026-10-16).

답을 아는 합성 영상: 흰 바탕 360×640, 창 [0,200,360,300] 안에 280×150 그림 칸.
  syn   : 0~1초 testsrc2 → 1초에 mandelbrot 으로 바뀜(소스가 다른 경계 = 컷 1개, 1.0초)
  nocut : 2초 내내 testsrc2(컷 0)
  fade  : testsrc2 가 흰색으로 서서히 사라짐(컷 0)
수리 전 코드: syn 의 scene 점수 0.193(<0.3, 흰 바탕이 창의 절반이라 희석) · 앞뒤 상관 0.789(≥0.6, 흰 여백이 상관을 부풀림)
→ 컷 0개로 놓쳤다(리센느 빵 final 4.63·7.53·23.4·25.37 과 같은 꼴).
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from shopping_shorts.channelkit.bench import cuts, probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")

WIN = [0, 200, 360, 300]
VL = {"window": WIN, "bg_rgb": [255, 255, 255]}


def _ff(args, out):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-t", "2", str(out)], check=True)
    return str(out)


@pytest.fixture(scope="module")
def vids(tmp_path_factory):
    d = tmp_path_factory.mktemp("cuts_bg")
    page = ["-f", "lavfi", "-i", "color=white:s=360x640:r=30:d=2"]
    syn = _ff(page + ["-f", "lavfi", "-i", "testsrc2=s=280x150:r=30:d=1", "-f", "lavfi", "-i", "mandelbrot=s=280x150:r=30",
                      "-filter_complex", "[2]trim=duration=1,setpts=PTS-STARTPTS+1/TB[b];[0][1]overlay=40:200:eof_action=pass[t];"
                                         "[t][b]overlay=40:200:enable='gte(t,1)':eof_action=pass,format=yuv420p"], d / "syn.mp4")
    nocut = _ff(page + ["-f", "lavfi", "-i", "testsrc2=s=280x150:r=30:d=2",
                        "-filter_complex", "[0][1]overlay=40:200,format=yuv420p"], d / "nocut.mp4")
    fade = _ff(page + ["-f", "lavfi", "-i", "testsrc2=s=280x150:r=30:d=2",
                       "-filter_complex", "[1]fade=t=out:st=0.5:d=1.2:color=white[f];[0][f]overlay=40:200,format=yuv420p"],
               d / "fade.mp4")
    # pre : syn 과 같은데 컷 직전 0.92~0.99초에 칸 위쪽 1/3 이 검게 덮인다(부분 변화). 보정 점수로 0.933 도 문턱을
    #       넘는데, merge_close 가 앞의 약한 0.933 을 남기면 그 앞뒤(둘 다 testsrc2)는 상관이 높아 진짜 컷 1.0 을 잃는다
    #       (방구석 ILIi 원본 5.933(0.19)·6.0(0.40) 실측과 같은 꼴)
    pre = _ff(page + ["-f", "lavfi", "-i", "testsrc2=s=280x150:r=30:d=1", "-f", "lavfi", "-i", "mandelbrot=s=280x150:r=30",
                      "-filter_complex", "[2]trim=duration=1,setpts=PTS-STARTPTS+1/TB[b];[0][1]overlay=40:200:eof_action=pass[t];"
                                         "[t]drawbox=x=40:y=200:w=280:h=50:color=black:t=fill:enable='between(t,0.92,0.99)'[t2];"
                                         "[t2][b]overlay=40:200:enable='gte(t,1)':eof_action=pass,format=yuv420p"], d / "pre.mp4")
    # move: 같은 testsrc2 가 1초에 (40,200) 280×150 → (30,225) 300×160 으로 자리·크기만 바뀜(게시글형 자막 줄이 늘 때 칸이
    #       밀리는 꼴, rGFX 원본 7.83·15.7·22.93 실측). 컷이 아니다 — 바탕 빼기 상관만 보면 0.28 로 컷이 된다
    move = _ff(page + ["-f", "lavfi", "-i", "testsrc2=s=280x150:r=30:d=2",
                       "-filter_complex", "[1]split[a][b];[b]scale=300:160[b2];[0][a]overlay=40:200:enable='lt(t,1)'[t];"
                                          "[t][b2]overlay=30:225:enable='gte(t,1)',format=yuv420p"], d / "move.mp4")
    return {"syn": syn, "nocut": nocut, "fade": fade, "pre": pre, "move": move}


def _measure(path, vl):
    return cuts.measure_video(path, vl, probe.info(path), [], zoom=False)


def test_variable_box_cut_is_found(vids):
    """소스가 다른 경계(1.0초)를 잡는다 — 수리 전 코드는 [] (빨강)."""
    r = _measure(vids["syn"], VL)
    assert len(r["cuts"]) == 1 and abs(r["cuts"][0] - 1.0) <= 1 / 30 + 1e-6, r["cuts"]
    assert r["corr"][0] is not None and r["corr"][0] < 0.6, r["corr"]


def test_old_ruler_raw_is_kept(vids):
    """raw(scene>T 그대로, 기준선 재현용)는 바탕 빼기와 무관 — 희석된 점수 0.19 라 raw 에는 없다."""
    r = _measure(vids["syn"], VL)
    assert r["raw"] == cuts.scene_detect(vids["syn"], WIN) == []
    assert r["bg_gray"] == 255.0 and r["detected"] == r["cuts"]


def test_no_bg_means_old_behaviour(vids):
    """배경을 모르면(bg_rgb 없음) 옛 방식 그대로 — 그래서 이 영상의 컷을 놓친다(옛 결함의 증거)."""
    r = _measure(vids["syn"], {"window": WIN})
    assert r["bg_gray"] is None and r["detected"] == r["raw"] and r["cuts"] == []


@pytest.mark.parametrize("name", ["nocut", "fade"])
def test_no_false_cut(vids, name):
    """같은 장면이 이어지거나 흰색으로 사라지는 것은 컷이 아니다(바탕 빼기가 거짓 컷을 만들지 않는다)."""
    assert _measure(vids[name], VL)["cuts"] == []


def test_strongest_frame_wins_merge(vids):
    """보정으로 문턱을 넘은 약한 앞 프레임이 진짜 컷을 밀어내지 않는다 — 묶음마다 보정 점수 최대 프레임."""
    r = _measure(vids["pre"], VL)
    assert len(r["cuts"]) == 1 and abs(r["cuts"][0] - 1.0) <= 1 / 30 + 1e-6, (r["detected"], r["corr"], r["cuts"])


def test_same_picture_moved_is_not_a_cut(vids):
    """그림 칸이 자리·크기만 바뀐 것은 컷이 아니다 — 후보로는 잡히지만 moved 로 빠진다."""
    r = _measure(vids["move"], VL)
    assert r["cuts"] == [], (r["detected"], r["corr"], r.get("moved"))
    assert len(r["moved"]) == 1 and abs(r["moved"][0][0] - 1.0) <= 1 / 30 + 1e-6, r["moved"]
