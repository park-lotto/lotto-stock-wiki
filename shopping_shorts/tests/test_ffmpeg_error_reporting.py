"""ffmpeg 실패 시 원인이 남는가 — Task9 리포트 §5가 잠재 리스크로 기록한 것.

기전: ffmpeg/ffprobe는 stderr를 UTF-8로 낸다. subprocess에 text=True만 주면 파이썬이
로캘(윈도우=cp949)로 디코드하다 **리더 스레드에서 UnicodeDecodeError로 죽고**, 그 결과
stdout/stderr가 None이 된다. 성공 경로는 멀쩡히 지나가서 안 보이다가, **실패했을 때만**
원인이 사라진다 — 가장 필요할 때 없어지는 종류다.

실측 재현(2026-07-16, 수정 전):
  _run_ffmpeg(["ffmpeg","-i","없는영상_한글이름.mp4", ...])
    → UnicodeDecodeError(리더 스레드) → r.stderr=None
    → r.stderr[-1000:] → TypeError: 'NoneType' object is not subscriptable
  즉 "실패 시 stderr를 예외에 담아 원인을 삼키지 않는다"던 docstring과 정반대로 동작했다.
  이 저장소는 한글 파일명이 도처에 있어 흔히 밟는 경로다.
"""
import shutil
import subprocess

import pytest

from shopping_shorts import video_assemble as va


def test_ffmpeg_subprocess_decodes_utf8_not_locale():
    """계약 고정: 로캘 디코딩으로 되돌아가면 리더 스레드가 다시 죽는다."""
    assert va._FF_TEXT.get("encoding") == "utf-8", "★로캘 디코딩으로 되돌아갔다"
    assert va._FF_TEXT.get("errors") == "replace", "★못 읽는 바이트에서 다시 터진다"


def test_run_ffmpeg_still_reports_cause_when_stderr_is_none(monkeypatch):
    """★핵심: 디코드가 어떤 이유로든 실패해 stderr가 None이 돼도, 우리는 TypeError가
    아니라 '실패했다'는 사실을 알려야 한다. (수정 전엔 여기서 TypeError가 났다)"""
    class R:
        returncode = 1
        stderr = None
        stdout = None

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    with pytest.raises(RuntimeError) as ei:
        va._run_ffmpeg(["ffmpeg", "-i", "x.mp4"])
    assert "exit 1" in str(ei.value)


def test_run_ffmpeg_puts_real_stderr_in_the_exception(monkeypatch):
    class R:
        returncode = 1
        stderr = "Error opening input file 없는영상.mp4"
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="없는영상"):
        va._run_ffmpeg(["ffmpeg", "-i", "x.mp4"])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_run_ffmpeg_real_failure_with_nonascii_path_does_not_mask_cause():
    """가짜 mock이 아니라 **진짜 ffmpeg**를 한글 경로로 실패시킨다 —
    이 저장소가 겪은 실제 경로이고, mock으로는 리더 스레드 크래시를 재현할 수 없다."""
    with pytest.raises(RuntimeError) as ei:
        va._run_ffmpeg(["ffmpeg", "-v", "error", "-i", "없는영상_한글이름.mp4", "-f", "null", "-"])
    msg = str(ei.value)
    assert "ffmpeg 실패" in msg
    assert len(msg) > 40, f"★원인이 비었다 — 다시 삼켰다: {msg!r}"
