# -*- coding: utf-8 -*-
"""remake.py --plan-only 계획 시트 — 컷 길이에 비례해 찍는다(관제 097, 10-16 썰풀다 담당: 0.2·1.0·1.8 세 장 고정이라 6초 넘는 컷 뒤가 안 보였다).
판단 주인 = remake.sheet_samples. 진짜 시트를 그려 폭으로 장 수를 잰다."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import remake as R  # noqa: E402


def test_samples_scale_with_shot_length():
    long = R.sheet_samples({"src": "a.mp4", "ss": 10.0, "est_dur": 6.5})
    assert len(long) >= 4 and long[-1][1] >= 10.0 + 6.0, long          # 6.5초 컷 → 4장↑, 마지막 장이 컷 끝(6초 넘음)
    assert len(R.sheet_samples({"src": "a.mp4", "t0": 0, "t1": 20})) == R.SHEET_MAX
    assert [round(x[1], 2) for x in R.sheet_samples({"src": "a.mp4", "ss": 1})] == [1.2, 2.0, 2.8]   # 길이 모르면 종전 세 장
    assert len(R.sheet_samples({"src": "a.mp4", "dur": 1.5})) == 3


def test_samples_follow_page_cuts():
    s = {"src": "r.mp4", "ss": 0, "src_crop": [1, 1, 5, 5], "cuts": [{"src": "r.mp4", "ss": 3, "dur": 2.0}, {"src": "b.mp4", "ss": 7, "dur": 4.5, "src_crop": [2, 2, 8, 8]}]}
    sm = R.sheet_samples(s)
    assert len(sm) >= 4
    assert sm[0][0] == "r.mp4" and sm[0][2] is None and sm[-1][0] == "b.mp4" and sm[-1][2] == [2, 2, 8, 8]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 필요")
def test_plan_sheet_draws_more_frames_for_long_shot(tmp_path):
    from PIL import Image
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:d=8:r=30", "-pix_fmt", "yuv420p", str(tmp_path / "v.mp4")], check=True)
    def width(shot):
        M = {"cand_dir": str(tmp_path), "shots": [dict(shot, i=0, src="v.mp4", ss=0, full=True)]}
        R.plan_sheet(M, {}, tmp_path / "s.jpg")
        return Image.open(tmp_path / "s.jpg").width
    tw = int(200 * 1080 / 1008)
    assert width({"est_dur": 6.5}) == 560 + 4 * (tw + 6)
    assert width({}) == 560 + 3 * (tw + 6)        # 대조군: 길이 모르는 컷은 종전 세 장
