"""10-29 썰템쇼 회원 시험 — 컷 조각 색 표식이 원본마다 달라(smpte170m·bt709) 이어 붙인 창 영상 중간에 색 정보가 바뀌면
ffmpeg 가 필터 식을 다시 세워 trim·overlay 상태가 초기화된다 → base.mp4 3.0~5.8초 정지('화면 멈춤'·'컷≠계획' 관문 반복).
고친 길: clip_cmd 가 모든 조각을 bt709·tv 로 변환·표식(COLOR_TAGS). 검사 = 실제 조각 2개를 굽고 이어 붙여 trim 이 프레임을 잃지 않는가."""
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.calcopy.hybrid import render_bench as RB

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")


def _src(p: Path, cs: str):
    """색 표식이 다른 시험 원본(3초, 움직이는 그림)."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3", "-vf", f"setparams=colorspace={cs}:color_primaries={'bt709' if cs == 'bt709' else 'smpte170m'}:color_trc={'bt709' if cs == 'bt709' else 'smpte170m'}:range=tv",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(p)], check=True)


def test_parts_share_color_tags_and_trim_keeps_frames(tmp_path, monkeypatch):
    monkeypatch.setattr(RB, "venc", lambda q: ["-c:v", "libx264", "-preset", "ultrafast", "-crf", str(q)])
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    _src(a, "bt709")
    _src(b, "smpte170m")
    parts = []
    for i, s in enumerate((a, b, a)):
        o = tmp_path / f"c{i}.mp4"
        RB.clip(s, 0.0, 30, [0, 0, 640, 360], (320, 180), o)
        parts.append(o)
    tags = {subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=color_space,color_primaries,color_transfer,color_range",
                            "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() for p in parts}
    assert len(tags) == 1, tags                       # 조각 표식 한 벌
    lst = tmp_path / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    win = tmp_path / "window.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(win)], check=True)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(win), "-vf", "trim=start_frame=10,showinfo", "-f", "null", "-"], capture_output=True, text=True)
    import re
    n = len(re.findall(r"Parsed_showinfo\S* @ \S+\] n:\s*\d+", r.stderr))
    assert n == 80, n                                 # 90 − 10 — 표식이 바뀌면 다시 세우며 trim 이 또 10장씩 버린다
