"""yt-dlp 실패 사유가 잘려서 진단을 막던 것 → 원인 줄을 골라 남긴다 (2026-09-18 실사고).

증상: "대본 분석해서 정확히 찾기"가 실패. 화면엔 `rate-limited by YouTube`.
      로그엔 이것만 남았다:

          yt-dlp 실패(https://www.youtube.com/watch?v=LlgqI7D1hS0, 3회 시도): rrent

      **`rrent` 5글자.** `stderr[-300:]`가 **끝 300자**만 남기는데 yt-dlp가 경고를
      길게 뱉어 원인이 앞에서 잘려나간 것이다.

★진짜 원인은 그 잘린 자리에 있었다:
      OSError: [Errno 28] No space left on device   (디스크 100%, 여유 0바이트)
  유튜브는 우리를 막은 적이 없다. yt-dlp가 쿠키 파일을 쓰려다 죽은 것이다.
  기록이 없으니 추측으로 메웠고 **세 번 연속 오진**했다:
    1) "android·ios 클라이언트가 죽었다"  → 반복 측정하니 기본도 됐다 안 됐다
    2) "쿠키가 범인이다"                  → 40분 뒤 쿠키로도 18/18 성공
    3) "24시간 43건 실패"                 → 실제 2건(43건은 제미니 429였다)

여기서 못 박는 것:
  1. 원인 줄을 **내용으로** 고른다 — 위치(꼬리)로 자르지 않는다.
  2. 경고가 아무리 길어도 원인이 살아남는다(위 실사고 재현).
  3. 시도별 사유를 **전부** 남긴다 — 마지막 것만 남기면 3회가 각각 다른 이유로
     죽었을 때 진단이 막힌다(클라이언트를 바꿔가며 재시도하므로 흔한 일이다).
  4. 형식이 바뀌어 표식이 없어도 빈손이 되지 않는다(마지막 줄 폴백).
"""
import pytest

from shopping_shorts import media_download as md


# 실사고를 만든 진짜 stderr 모양: 경고가 길어 원인이 앞으로 밀린다.
REAL_DISK_FULL = (
    "WARNING: [youtube] Skipping player responses\n"
    + "WARNING: " + "x" * 400 + "\n"
    + "Traceback (most recent call last):\n"
    '  File "/home/ubuntu/.local/lib/python3.12/site-packages/yt_dlp/cookies.py", line 1305\n'
    "OSError: [Errno 28] No space left on device\n"
)


def test_disk_full_cause_survives_long_warnings():
    """★본체: 경고가 길어도 `No space left on device`가 남아야 한다.

    종전(`stderr[-300:]`)은 이 케이스에서 경고 꼬리만 남겨 원인을 통째로 잃었다.
    """
    reason = md._ytdlp_reason(REAL_DISK_FULL)
    assert "No space left on device" in reason, f"원인이 사라졌다: {reason!r}"


def test_old_tail_slice_would_have_lost_it():
    """대조군: 왜 종전 방식이 실패했는지 못 박는다(이 테스트가 회귀의 근거다)."""
    assert "No space left on device" not in REAL_DISK_FULL[-300:][:80]


@pytest.mark.parametrize("stderr,needle", [
    ("ERROR: [youtube] X: Sign in to confirm you're not a bot. Use --cookies",
     "Sign in to confirm"),
    ("WARNING: " + "y" * 500 + "\nERROR: [youtube] X: current session has been "
     "rate-limited by YouTube.", "rate-limited"),
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden",
     "HTTP Error 403"),
    ("ERROR: [youtube] X: Video unavailable", "Video unavailable"),
])
def test_common_causes_are_kept(stderr, needle):
    """실제로 겪는 실패 유형들이 전부 살아남아야 한다."""
    assert needle in md._ytdlp_reason(stderr)


def test_no_marker_falls_back_not_empty():
    """yt-dlp 출력 형식이 바뀌어 표식이 없어도 빈손이 되면 안 된다."""
    reason = md._ytdlp_reason("something odd happened\nfinal line here")
    assert reason.strip()
    assert "final line here" in reason


def test_empty_stderr_is_explicit():
    """stderr가 비어도 '왜 비었는지' 알 수 있게 명시한다(빈 문자열 금지)."""
    assert md._ytdlp_reason("").strip()
    assert md._ytdlp_reason(None).strip()


def test_reason_is_length_capped():
    """스택트레이스 전문이 로그를 뒤덮지 않도록 상한을 지킨다."""
    huge = "\n".join(f"ERROR: line {i} " + "z" * 200 for i in range(50))
    assert len(md._ytdlp_reason(huge, limit=400)) <= 400


def test_all_attempts_recorded(monkeypatch, tmp_path):
    """★시도 3회가 각각 다른 이유로 죽으면 **셋 다** 메시지에 남아야 한다."""
    errs = [
        "ERROR: [youtube] X: Sign in to confirm you're not a bot",
        "OSError: [Errno 28] No space left on device",
        "ERROR: unable to download video data: HTTP Error 403: Forbidden",
    ]
    seq = {"i": 0}

    class _R:
        def __init__(self, stderr):
            self.returncode = 1
            self.stdout = ""
            self.stderr = stderr

    def fake_run(cmd, **kw):
        r = _R(errs[seq["i"]])
        seq["i"] += 1
        return r

    monkeypatch.setattr(md.subprocess, "run", fake_run)
    monkeypatch.setattr(md, "_cookies_arg", lambda u: [])
    monkeypatch.setattr(md, "_proxy_arg", lambda u: [])
    monkeypatch.setattr(md.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError) as ei:
        md._download_ytdlp("https://www.youtube.com/watch?v=X", str(tmp_path))
    msg = str(ei.value)
    for frag in ("Sign in to confirm", "No space left on device", "HTTP Error 403"):
        assert frag in msg, f"{frag}가 사라졌다 — 마지막 시도만 남는 회귀: {msg}"


def test_repeated_same_reason_is_deduped(monkeypatch, tmp_path):
    """같은 사유가 3회 반복되면 한 번만 적는다(로그 폭주 방지)."""
    class _R:
        returncode = 1
        stdout = ""
        stderr = "OSError: [Errno 28] No space left on device"

    monkeypatch.setattr(md.subprocess, "run", lambda cmd, **kw: _R())
    monkeypatch.setattr(md, "_cookies_arg", lambda u: [])
    monkeypatch.setattr(md, "_proxy_arg", lambda u: [])
    monkeypatch.setattr(md.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError) as ei:
        md._download_ytdlp("https://www.youtube.com/watch?v=X", str(tmp_path))
    assert str(ei.value).count("No space left on device") == 1
