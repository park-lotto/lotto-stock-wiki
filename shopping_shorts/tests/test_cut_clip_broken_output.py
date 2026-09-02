"""컷 조각이 **재생 가능한지**까지 보고 성공이라 말한다.

## 왜 (2026-09-03 고객 제보 — 캡컷에 "파일 손상됨" 22개)

`_cut_clip`은 `size > 0`만 봤다. 그런데 ffmpeg는 **소스 끝 너머를 -ss로 잡으면
rc=0으로 빠져나오면서 스트림이 하나도 없는 262바이트 mp4**를 남긴다.
크기가 0이 아니니 True가 되고, 서버는 그걸 200 OK로 내보내고, 프론트의
2048바이트 가드는 파일이 그보다 크면 통과시킨다. 캡컷에서야 "파일 손상됨"으로 드러난다.

실측(로컬 ffmpeg 8.1.2): 5초 소스에 `-ss 20` → rc=0, 262바이트, nb_frames 없음, duration=N/A.
mp3(shutil.copy)는 멀쩡한데 cut_*.mp4만 전멸하던 고객 증상과 정확히 맞는다.
"""
import shutil
import subprocess

import pytest

from shopping_shorts.export_bundle import _cut_clip


def _have_ffmpeg():
    return bool(shutil.which("ffmpeg"))


def _make_src(path, seconds):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc=size=320x240:rate=30:duration={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True, stdin=subprocess.DEVNULL)


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg 없음")
def test_seek_past_end_is_not_success(tmp_path):
    """소스 끝 너머를 자르면 False여야 한다 — 종전엔 262바이트를 True라 했다."""
    src = tmp_path / "src.mp4"
    _make_src(src, 3)
    out = tmp_path / "past.mp4"
    assert _cut_clip(src, 20.0, 22.0, out) is False, (
        "소스(3초) 끝 너머 20초를 잘랐는데 성공이라고 했다 — "
        "캡컷에 '파일 손상됨'으로 가는 그 파일이다")
    assert not out.exists(), "재생 불가 조각을 남겨두면 안 된다(캡컷이 집어간다)"


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg 없음")
def test_normal_cut_still_succeeds(tmp_path):
    """정상 구간은 그대로 성공해야 한다(가드가 멀쩡한 컷을 죽이면 안 된다)."""
    src = tmp_path / "src.mp4"
    _make_src(src, 5)
    out = tmp_path / "ok.mp4"
    assert _cut_clip(src, 1.0, 3.0, out) is True
    assert out.exists() and out.stat().st_size > 2048


@pytest.mark.skipif(not _have_ffmpeg(), reason="ffmpeg 없음")
def test_partial_overlap_kept(tmp_path):
    """소스 끝에 걸친 컷은 **짧아도 살린다** — 프레임이 실제로 들어 있다."""
    src = tmp_path / "src.mp4"
    _make_src(src, 3)
    out = tmp_path / "partial.mp4"
    assert _cut_clip(src, 2.5, 4.5, out) is True, "0.5초라도 화면이 있으면 쓸 수 있다"
    assert out.exists()
