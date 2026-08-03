"""틱톡 등 yt-dlp 간헐 실패(rehydration) 자가치유 재시도 검증 (2026-07-23)."""
from pathlib import Path

import pytest

from shopping_shorts import media_download


class _FakeR:
    def __init__(self, rc):
        self.returncode = rc
        self.stderr = "ERROR: Unable to extract universal data for rehydration"


def test_download_ytdlp_retries_then_raises(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        return _FakeR(1)   # 매번 실패

    monkeypatch.setattr(media_download.subprocess, "run", fake_run)
    monkeypatch.setattr(media_download.time, "sleep", lambda *_: None)   # 실제 대기 없음

    with pytest.raises(RuntimeError) as e:
        media_download._download_ytdlp("https://www.tiktok.com/@x/video/1",
                                       str(tmp_path), max_attempts=3)
    assert calls["n"] == 3               # 3회 재시도
    assert "3회 시도" in str(e.value)


def test_download_ytdlp_succeeds_after_transient_failure(monkeypatch, tmp_path):
    seq = [1, 0]   # 첫 시도 실패 → 둘째 성공

    def fake_run(cmd, **k):
        rc = seq.pop(0)
        if rc == 0:
            out = cmd[cmd.index("-o") + 1]          # -o 다음 인자 = 출력 템플릿
            stem = Path(out).stem.split(".")[0]
            (tmp_path / (stem + ".mp4")).write_text("v")   # 산출물 더미 생성
        return _FakeR(rc)

    monkeypatch.setattr(media_download.subprocess, "run", fake_run)
    monkeypatch.setattr(media_download.time, "sleep", lambda *_: None)

    path, cap = media_download._download_ytdlp("https://www.tiktok.com/@x/video/1",
                                               str(tmp_path), max_attempts=3)
    assert path.endswith(".mp4")
    assert cap == ""
    assert seq == []                     # 정확히 2회 호출(실패→성공)
