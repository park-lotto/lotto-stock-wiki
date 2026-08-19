"""/api/play — 서버가 받아서 서빙하는 인라인 재생 (2026-08-17).

왜 생겼나(전부 서버 실측):
  · 틱톡 mp4 주소는 우리 서버가 **다시 받으면 403**이다(리퍼러를 틱톡으로 줘도, 인스타로
    줘도 403 = IP·세션 바인딩) → 브라우저 직접재생도 /api/video 프록시도 안 된다.
  · 그런데 yt-dlp **다운로드는 된다**(4.4초·353KB) → 받아서 파일로 주면 카드 안에서 재생된다.
네트워크는 안 탄다(download_any를 가짜로 바꾼다).
"""
import pytest

from shopping_shorts import app as appmod


@pytest.fixture
def play_dir(tmp_path, monkeypatch):
    d = tmp_path / "play_cache"
    monkeypatch.setattr(appmod, "_PLAY_CACHE_DIR", d)
    return d


def _fake_download(monkeypatch, calls, body=b"\x00\x00\x00\x18ftypmp42fakevideo"):
    def fake(url, dest_dir):
        calls.append(url)
        from pathlib import Path
        p = Path(dest_dir) / "got.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return str(p), ""
    monkeypatch.setattr(appmod, "download_any", fake)


def test_downloads_then_serves_file(play_dir, monkeypatch):
    calls = []
    _fake_download(monkeypatch, calls)
    r = appmod.api_play("tiktok", "7459783785282915606")
    assert getattr(r, "status_code", 200) == 200
    assert len(calls) == 1
    assert "tiktok.com" in calls[0] and "7459783785282915606" in calls[0]
    assert list(play_dir.glob("*.mp4")), "캐시 파일이 안 남았다"


def test_second_call_uses_cache(play_dir, monkeypatch):
    """같은 영상을 두 번 누르면 두 번 받지 않는다(느리고 비싸다)."""
    calls = []
    _fake_download(monkeypatch, calls)
    appmod.api_play("tiktok", "123456789")
    appmod.api_play("tiktok", "123456789")
    assert len(calls) == 1, "캐시가 안 먹어 매번 다시 받는다"


def test_different_ids_do_not_collide(play_dir, monkeypatch):
    """★오늘 썸네일에서 겪은 캐시키 충돌을 여기서 되풀이하지 않는다."""
    calls = []
    _fake_download(monkeypatch, calls)
    appmod.api_play("tiktok", "111111111")
    appmod.api_play("tiktok", "222222222")
    assert len(calls) == 2
    assert len(list(play_dir.glob("*.mp4"))) == 2


def test_same_id_different_platform_does_not_collide(play_dir, monkeypatch):
    calls = []
    _fake_download(monkeypatch, calls)
    appmod.api_play("tiktok", "abcdefgh")
    appmod.api_play("youtube", "abcdefgh")
    assert len(list(play_dir.glob("*.mp4"))) == 2


@pytest.mark.parametrize("platform,vid", [
    ("xiaohongshu", "abcdefgh"),      # 지원하지 않는 플랫폼
    ("tiktok", "a"),                  # 너무 짧은 id
    ("tiktok", "../../etc/passwd"),   # 경로 탈출 시도
    ("tiktok", "id with space"),
    ("", "abcdefgh"),
])
def test_bad_input_is_rejected_without_download(play_dir, monkeypatch, platform, vid):
    """id를 파일명·URL에 쓰므로 입구에서 막는다(다운로드도 하지 않는다)."""
    calls = []
    _fake_download(monkeypatch, calls)
    r = appmod.api_play(platform, vid)
    assert r.status_code == 400
    assert calls == []


def test_download_failure_returns_404_and_leaves_no_file(play_dir, monkeypatch):
    def boom(url, dest_dir):
        raise RuntimeError("yt-dlp 실패")
    monkeypatch.setattr(appmod, "download_any", boom)
    r = appmod.api_play("tiktok", "999999999")
    assert r.status_code == 404
    assert not list(play_dir.glob("*.mp4"))


def test_temp_dir_is_cleaned_up(play_dir, monkeypatch):
    calls = []
    _fake_download(monkeypatch, calls)
    appmod.api_play("tiktok", "555555555")
    assert not [p for p in play_dir.iterdir() if p.is_dir()], "임시 폴더가 남았다"


def test_cache_is_trimmed_to_limit(play_dir, monkeypatch):
    """디스크가 조용히 차지 않게 오래된 것부터 지운다."""
    monkeypatch.setattr(appmod, "_PLAY_CACHE_MAX", 3)
    calls = []
    _fake_download(monkeypatch, calls)
    for i in range(6):
        appmod.api_play("tiktok", "video%07d" % i)
    assert len(list(play_dir.glob("*.mp4"))) <= 3
