"""비트 끝 무음 트림 — 비트 사이 dead-air 제거(2026-07-22, 레퍼런스 릴스는 무음 0).
ffmpeg 없이 로직(성공 교체·mock 보호·실패 폴백)만 검증(subprocess/probe 주입)."""
import os
from shopping_shorts import audio_post


def _touch(p, data=b"x"):
    with open(p, "wb") as f:
        f.write(data)


def test_trims_and_replaces(tmp_path, monkeypatch):
    src = tmp_path / "beat.mp3"; _touch(src, b"original")
    # ffmpeg가 성공해 tmp에 결과를 쓴다고 가정(파일 생성), 길이는 정상(말 있는 비트).
    def _run(cmd, **kw):
        out = cmd[-1]   # target = 마지막 인자
        _touch(out, b"trimmed")
        class R: pass
        return R()
    monkeypatch.setattr(audio_post.subprocess, "run", _run)
    monkeypatch.setattr(audio_post, "_audio_dur", lambda p: 3.0)   # in·out 모두 정상
    r = audio_post.trim_tail_silence(src, src)
    assert r == str(src)
    assert src.read_bytes() == b"trimmed"      # 트림 결과로 교체됨


def test_mock_guard_keeps_original(tmp_path, monkeypatch):
    # 말 있는 비트(2s)가 0.1s로 잘리면 = 전부 무음(mock) → 원본 유지.
    src = tmp_path / "beat.mp3"; _touch(src, b"original")
    def _run(cmd, **kw):
        out = cmd[-1]   # target = 마지막 인자
        class R: pass
        return R()
    monkeypatch.setattr(audio_post.subprocess, "run", _run)
    durs = iter([2.0, 0.1])                     # in=2.0, out=0.1
    monkeypatch.setattr(audio_post, "_audio_dur", lambda p: next(durs))
    r = audio_post.trim_tail_silence(src, src)
    assert r == str(src)
    assert src.read_bytes() == b"original"      # 원본 보존


def test_ffmpeg_failure_returns_original(tmp_path, monkeypatch):
    src = tmp_path / "beat.mp3"; _touch(src, b"original")
    def _boom(cmd, **kw):
        raise RuntimeError("ffmpeg 죽음")
    monkeypatch.setattr(audio_post.subprocess, "run", _boom)
    monkeypatch.setattr(audio_post, "_audio_dur", lambda p: 3.0)
    assert audio_post.trim_tail_silence(src, src) == str(src)
    assert src.read_bytes() == b"original"
