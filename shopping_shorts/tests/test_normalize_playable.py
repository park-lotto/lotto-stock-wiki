# -*- coding: utf-8 -*-
"""받아 온 영상은 **브라우저가 재생하는 모양**으로 맞춘다 (2026-09-02).

강규봉님 제보: "3단계 미리보기에서 틱톡 영상들은 검게 안 보인다."
실측(job 26181de7df55): 틱톡 소스 3개가 전부 hevc(H.265), 유튜브만 h264.
크롬·엣지는 hevc를 재생하지 못해 화면이 통째로 검게 뜬다.

같은 처방이 도우인에는 이미 있었는데(douyin_fetch._normalize) 그 함수에만 있어서
틱톡에서 그대로 재발했다 — 그래서 **받는 문(download_any) 한 곳**으로 옮겼다.
"""
import subprocess

import pytest

from shopping_shorts import media_download as md


def _mk(path, codec):
    """테스트용 짧은 영상. ffmpeg가 없으면 이 테스트는 건너뛴다."""
    enc = "libx265" if codec == "hevc" else "libx264"
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=320x568:duration=1:rate=15",
         "-c:v", enc, "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0 or not path.exists():
        pytest.skip("ffmpeg에 %s 인코더가 없다" % enc)
    return path


def _codec(path):
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()


def test_hevc는_h264로_바뀐다(tmp_path):
    src = _mk(tmp_path / "t.mp4", "hevc")
    out = md.normalize_playable(src)
    assert _codec(out) == "h264"


def test_h264는_손대지_않는다(tmp_path):
    """이미 안전하면 변환 0초 — 대부분의 소스가 여기로 빠진다."""
    src = _mk(tmp_path / "ok.mp4", "h264")
    out = md.normalize_playable(src)
    assert str(out) == str(src)


def test_없는_파일도_죽지_않는다(tmp_path):
    p = tmp_path / "nope.mp4"
    assert md.normalize_playable(p) == str(p)


def test_다운로드_출구에서_한번_걸린다(monkeypatch, tmp_path):
    """플랫폼별 함수에 흩어 적으면 새 플랫폼마다 같은 사고가 난다(0순위-B)."""
    seen = {}
    monkeypatch.setattr(md, "_download_any_raw",
                        lambda url, d: (str(tmp_path / "x.mp4"), "cap"))
    def _fake_norm(p):
        seen["p"] = str(p)      # ★`setdefault(...) or ...`는 단락돼 경로가 그대로 나간다
        return "정규화됨.mp4"
    monkeypatch.setattr(md, "normalize_playable", _fake_norm)
    path, cap = md.download_any("https://www.tiktok.com/@u/video/1", str(tmp_path))
    assert seen["p"].endswith("x.mp4")
    assert path == "정규화됨.mp4" and cap == "cap"


def test_도우인도_같은_함수를_쓴다():
    """두 벌로 두면 한쪽만 고쳐져 또 어긋난다 — 실제로 이번이 그 사고였다."""
    import inspect

    from shopping_shorts import douyin_fetch
    assert "normalize_playable" in inspect.getsource(douyin_fetch._normalize)
