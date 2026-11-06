"""크롭 오프셋 1px 검증(표 #71·#219, Jev 해결 0.81·위험 0.35 · 11-06).

yuv420 에 crop 을 exact 없이 홀수 오프셋으로 걸면 ffmpeg 가 오류 없이 짝수로 내려 1px 밀린다(실측 y=521 → 520).
crop 문자열은 crop.crop_vf 한 곳, 검사는 crop.check_crop 한 곳. 판 렌더(part_vf)는 판 칸 checks.exact_crop 켰을 때만 exact(기본 꺼짐).
"""
import subprocess

import numpy as np

from tools.calcopy.engine import crop as CR
from tools.calcopy.engine import preset_make as PM


def test_check_crop_reasons():
    assert CR.check_crop([0, 520, 1080, 1398], (1080, 1920)) == []
    why = CR.check_crop([0, 521, 1080, 1399], (1080, 1920))
    assert any("오프셋" in w for w in why) and any("크기" in w for w in why)
    assert any("밖" in w for w in CR.check_crop([0, 600, 1080, 1400], (1080, 1920)))


def test_crop_vf_exact():
    assert CR.crop_vf([3, 521, 100, 99]) == "crop=100:99:3:521:exact=1"
    assert CR.crop_vf([3, 521, 100, 99], exact=False) == "crop=100:99:3:521"


def test_part_vf_default_unchanged_and_flag_exact():
    c = {"box": [0, 521, 1080, 1398]}
    assert "crop=1080:1398:0:521," in PM.part_vf(c, 1080, 1398)                       # 기본 꺼짐 = 옛 문자열 그대로
    assert "crop=1080:1398:0:521:exact=1," in PM.part_vf(c, 1080, 1398, {"exact_crop": True})


def test_exact_crop_is_pixel_true(tmp_path):
    """결과물 검사: 홀수 오프셋 크롭이 정답(rgb 먼저 자름)과 같은 줄을 주나 — exact 는 0px, 그냥은 1px 밀림."""
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x480:rate=10", "-t", "1",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", str(src)], check=True)

    def grab(vf, h=200):
        b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                           capture_output=True).stdout
        return np.frombuffer(b, np.uint8).reshape(h, 320).astype(float)
    truth = grab("format=rgb24,crop=320:200:0:101")
    ex = grab(CR.crop_vf([0, 101, 320, 200]))
    plain = grab(CR.crop_vf([0, 101, 320, 200], exact=False))
    assert CR.row_shift(ex, truth) == 0
    assert abs(CR.row_shift(plain, truth)) == 1               # 고치기 전 동작: 조용히 1px
