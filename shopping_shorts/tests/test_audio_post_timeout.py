# -*- coding: utf-8 -*-
"""ffmpeg 무한대기 차단 (2026-08-06).

★실사고(라이브 job 4ca11b8270ae): 4.1초짜리 비트 mp3 하나를 후처리하다 ffmpeg가
**영원히 끝나지 않아** 워커가 통째로 멈췄다 — 18분째 hrtimer_nanosleep, CPU 0.4%,
출력 0바이트. 대본은 57초 만에 정상으로 나왔는데 그 뒤 16분을 여기서 썼고, 뒤에 온
사장님 작업은 큐에서 대기만 했다("대본이 왜 안 뽑히나 너무 오래 걸림").

서버 3회 재현: atempo + apad + loudnorm이 **전부** 있고 그 파일일 때만 멈춘다.
하나만 빼면 매번 정상 → ffmpeg 내부 문제라 우리가 못 고친다. 그래서 **끊고 원본으로
진행**한다(비트 하나가 덜 다듬어지는 건 괜찮다, 멈추면 제작이 안 끝난다).
"""
import subprocess

import pytest

from shopping_shorts import audio_post


def test_모든_ffmpeg_호출에_timeout이_있다():
    """★하나라도 빠지면 그 경로로 워커가 다시 멈춘다."""
    import inspect
    src = inspect.getsource(audio_post)
    calls = src.count("subprocess.run(")
    timeouts = src.count("timeout=FFMPEG_TIMEOUT_SEC")
    assert timeouts >= calls, \
        f"subprocess.run {calls}개 중 timeout이 {timeouts}개뿐 — 빠진 호출이 있다"


def test_타임아웃이면_원본을_돌려준다(monkeypatch, tmp_path):
    """예외를 올리면 비트 하나 때문에 제작 전체가 실패한다. 후처리는 다듬기지 필수가 아니다."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x" * 100)

    def _hang(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)

    monkeypatch.setattr(audio_post.subprocess, "run", _hang)
    out = audio_post.post_process(str(src), str(tmp_path / "out.mp3"),
                                  tempo=1.333, pace_mode=True, loudnorm=True)
    assert out == str(src), "타임아웃이면 원본 경로를 그대로 돌려줘야 한다"


def test_타임아웃을_조용히_넘기지_않는다(monkeypatch, tmp_path, capsys):
    """조용히 넘기면 '왜 소리가 덜 다듬어졌나'를 아무도 모른다(캐시키 사고와 같은 계보)."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x" * 100)
    monkeypatch.setattr(audio_post.subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)))
    audio_post.post_process(str(src), str(tmp_path / "out.mp3"),
                            tempo=1.333, pace_mode=True, loudnorm=True)
    assert "ffmpeg" in capsys.readouterr().out


def test_타임아웃_기본값이_정상처리보다_넉넉하다():
    """정상 처리는 실측 0.2초 — 30초면 정상 작업을 자를 위험이 없다."""
    assert audio_post.FFMPEG_TIMEOUT_SEC >= 15


def test_타임아웃_외_예외는_그대로_올린다(monkeypatch, tmp_path):
    """진짜 오류(깨진 파일 등)까지 삼키면 무음 산출물이 조용히 나간다."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x" * 100)

    def _boom(*a, **kw):
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(audio_post.subprocess, "run", _boom)
    with pytest.raises(subprocess.CalledProcessError):
        audio_post.post_process(str(src), str(tmp_path / "out.mp3"),
                                tempo=1.333, pace_mode=True, loudnorm=True)


def test_측정함수는_타임아웃시_빈리스트(monkeypatch, tmp_path):
    """measure_removed_spans가 멈추면 자막 싱크 계산이 통째로 막힌다 → 선형 폴백."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x" * 100)
    monkeypatch.setattr(audio_post.subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)))
    assert audio_post.measure_removed_spans(str(src)) == []
