"""#5442(11-04 서지환 68e387d3d7a1 썰템쇼판): 재료에 숫자로 적은 crop [x,0,608,1080] 을 창 1080x870 으로 늘려 영상이 가로 약 2.2배 찌그러짐.
cut_crop(자를 칸 주인)이 숫자 crop 을 그대로 썼고 clip_cmd 는 비율 없이 창 크기로 scale 한다. 숫자 crop 비율이 창과 다르면 cut_crop 이 창 비율로 바로잡는다."""
import subprocess
from pathlib import Path

from tools.calcopy.hybrid import render_bench as RB


def _src(tmp_path, w=1920, h=1080):
    p = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s={w}x{h}:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   check=True, stdin=subprocess.DEVNULL)
    return p


def test_숫자_crop_비율이_창과_다르면_바로잡는다(tmp_path):
    src = _src(tmp_path)
    c = {"crop": [600, 0, 608, 1080], "ss": 0.0, "dur": 1.0}
    x, y, w, h = RB.cut_crop(c, src, (1080, 870))
    assert abs(w / h - 1080 / 870) < 0.02, (w, h)
    assert h == 1080 and 0 <= x and x + w <= 1920
    assert abs((x + w / 2) - (600 + 304)) <= 2          # 가운데는 그대로


def test_비율이_맞으면_그대로(tmp_path):
    src = _src(tmp_path)
    c = {"crop": [100, 0, 1340, 1080], "ss": 0.0, "dur": 1.0}
    assert RB.cut_crop(c, src, (1080, 870)) == [100, 0, 1340, 1080]


def test_원본보다_넓으면_폭은_원본_높이를_줄인다(tmp_path):
    src = _src(tmp_path, 1080, 1920)                    # 세로 원본
    c = {"crop": [0, 0, 1080, 1920], "ss": 0.0, "dur": 1.0}
    x, y, w, h = RB.cut_crop(c, src, (1080, 870))
    assert w == 1080 and abs(w / h - 1080 / 870) < 0.02 and y + h <= 1920
