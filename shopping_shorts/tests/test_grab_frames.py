"""검수 단축 ②(10-26): 1초 시트·0.1초 띠를 한 번 디코드(remake.grab_frames)로 — 시각마다 ffmpeg -ss 로 따로 뽑던 것과 픽셀이 같아야 한다."""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def test_grab_frames_same_pixels_as_seek(tmp_path):
    from tools.calcopy.engine.remake import grab_frames
    from tools.calcopy.hybrid.compare_sheet import grab
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=3", "-pix_fmt", "yuv420p", str(v)],
                   check=True, stdin=subprocess.DEVNULL)
    ts = [0.0, 0.5, 1.33, 2.1, 2.9]
    got = grab_frames(v, ts, size=(162, 288))
    for t in ts:
        assert np.array_equal(np.asarray(got[t]), np.asarray(grab(v, t, (162, 288)))), t
    assert 9.0 not in grab_frames(v, [9.0], size=(162, 288))          # 영상 끝 밖 = 빠짐(부르는 쪽이 붉은 칸)
