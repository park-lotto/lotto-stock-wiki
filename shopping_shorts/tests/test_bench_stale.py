"""10-30 설치본 시험: 소재 창고 다음 순위로 넘어가도 bench/ 에 첫 영상이 남아 yt-dlp 가 '이미 받음' → 같은 영상 5번. 다른 소재면 비우고 받는다(runner_ops.c_bench)."""
import json

import pytest

from tools.calcopy.hybrid import runner_ops as R


def test_other_video_left_is_cleared(tmp_path, monkeypatch):
    bd = tmp_path / "bench"
    bd.mkdir()
    (bd / "bench.mp4").write_bytes(b"old")
    (bd / "bench.info.json").write_text(json.dumps({"id": "AAAAAAAAAAA"}), encoding="utf-8")
    seen = {}
    monkeypatch.setattr(R, "CACHE", False)
    def yt(args):
        seen["left"] = sorted(p.name for p in bd.iterdir())
        raise StopIteration                       # 받기 자리까지만 본다
    monkeypatch.setattr(R, "yt", yt)
    with pytest.raises(StopIteration):
        R.c_bench(tmp_path, {"url": "https://www.youtube.com/shorts/BBBBBBBBBBB"})
    assert seen["left"] == []                     # 받기 전에 옛 소재 파일이 없다


def test_same_video_kept(tmp_path, monkeypatch):
    bd = tmp_path / "bench"
    bd.mkdir()
    (bd / "bench.mp4").write_bytes(b"old")
    (bd / "bench.info.json").write_text(json.dumps({"id": "BBBBBBBBBBB"}), encoding="utf-8")
    seen = {}
    monkeypatch.setattr(R, "CACHE", False)
    def yt(args):
        seen["left"] = sorted(p.name for p in bd.iterdir())
        raise StopIteration                       # 받기 자리까지만 본다
    monkeypatch.setattr(R, "yt", yt)
    with pytest.raises(StopIteration):
        R.c_bench(tmp_path, {"url": "https://www.youtube.com/shorts/BBBBBBBBBBB"})
    assert "bench.mp4" in seen["left"]
