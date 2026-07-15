import pytest
from shopping_shorts import scene_assets


def _fake_run_ok(created=None):
    """ffmpeg 성공 시뮬 — 실제로 만들었을 파일을 테스트가 대신 생성."""
    calls = []

    def run(cmd, capture_output=True, check=False):
        calls.append(cmd)
        if created:
            created.write_bytes(b"out")

        class R:
            returncode = 0
            stderr = b""
        return R()
    run.calls = calls
    return run


def _fake_run_fail(cmd, capture_output=True, check=False):
    class R:
        returncode = 1
        stderr = b"ffmpeg: error"
    return R()


def test_make_clip_cuts_segment_and_normalizes_spec(monkeypatch, tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")
    out = tmp_path / "clip.mp4"
    run = _fake_run_ok(created=out)
    monkeypatch.setattr(scene_assets.subprocess, "run", run)

    result = scene_assets.make_clip(src, 3.0, 5.5, out)

    assert result == out and out.exists()
    cmd = run.calls[0]
    joined = " ".join(str(x) for x in cmd)
    assert "-ss" in cmd and "3.000" in joined          # 시작점
    assert "-t" in cmd and "2.500" in joined           # 길이 = end - start
    # 페이즈2 concat이 -c copy라 규격이 다르면 안 붙는다 — 720x1280/30fps/libx264/aac 고정
    assert "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" in joined
    assert "-r" in cmd and "30" in cmd
    assert "libx264" in cmd and "aac" in cmd and "yuv420p" in cmd


def test_make_clip_raises_on_ffmpeg_failure(monkeypatch, tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")
    monkeypatch.setattr(scene_assets.subprocess, "run", _fake_run_fail)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        scene_assets.make_clip(src, 0, 2, tmp_path / "clip.mp4")


def test_make_clip_rejects_non_positive_span(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")

    with pytest.raises(ValueError, match="구간"):
        scene_assets.make_clip(src, 5.0, 5.0, tmp_path / "clip.mp4")
    with pytest.raises(ValueError, match="구간"):
        scene_assets.make_clip(src, 5.0, 2.0, tmp_path / "clip.mp4")


def test_extract_audio_produces_mp3(monkeypatch, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    out = tmp_path / "sfx.mp3"
    run = _fake_run_ok(created=out)
    monkeypatch.setattr(scene_assets.subprocess, "run", run)

    result = scene_assets.extract_audio(clip, out)

    assert result == out and out.exists()
    cmd = run.calls[0]
    assert "-vn" in cmd                       # 영상 버리고 오디오만
    assert "libmp3lame" in " ".join(str(x) for x in cmd)


def test_extract_audio_raises_on_failure(monkeypatch, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    monkeypatch.setattr(scene_assets.subprocess, "run", _fake_run_fail)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        scene_assets.extract_audio(clip, tmp_path / "sfx.mp3")


def test_make_poster_delegates_to_frame_extract(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    out = tmp_path / "poster.jpg"
    seen = {}

    def fake_extract(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
        seen.update(video_path=video_path, dest_dir=dest_dir,
                    timestamp_sec=timestamp_sec, filename=filename)
        out.write_bytes(b"jpg")
        return out
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at", fake_extract)

    result = scene_assets.make_poster(media, out)

    assert result == out
    assert seen["video_path"] == media
    assert seen["dest_dir"] == tmp_path
    assert seen["timestamp_sec"] == 0
    assert seen["filename"] == "poster.jpg"


def test_make_poster_returns_none_on_failure(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at",
                        lambda *a, **k: None)

    # 썸네일은 없어도 되는 것 — 예외 대신 None으로 파이프라인 유지
    assert scene_assets.make_poster(media, tmp_path / "poster.jpg") is None


def test_probe_duration_parses_ffprobe(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output=True, check=False):
        assert "ffprobe" in cmd[0]

        class R:
            returncode = 0
            stdout = b"2.53\n"
            stderr = b""
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 2.53


def test_probe_duration_returns_zero_on_failure(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output=True, check=False):
        class R:
            returncode = 1
            stdout = b""
            stderr = b"err"
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 0.0


def test_probe_duration_survives_missing_ffprobe(monkeypatch, tmp_path):
    # ffprobe가 없으면 run은 returncode가 아니라 FileNotFoundError를 던진다.
    # 길이는 표시용이므로 저장 자체가 터지면 안 된다.
    def boom(cmd, capture_output=True, check=False):
        raise FileNotFoundError("ffprobe")
    monkeypatch.setattr(scene_assets.subprocess, "run", boom)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 0.0


def test_output_dimensions_match_video_assemble():
    """scene_assets와 video_assemble의 출력 규격이 일치해야 한다.
    페이즈2에서 concat -c copy로 자산 클립을 비트 클립과 붙이기 때문에
    규격이 어긋나면 렌더가 깨진다."""
    from shopping_shorts import video_assemble

    assert scene_assets._OUT_W == video_assemble._OUT_W
    assert scene_assets._OUT_H == video_assemble._OUT_H
