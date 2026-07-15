"""도서관 보관영상의 포스터(첫 프레임) 서빙 라우트(/api/wiki/poster) 테스트.

우리믹스 대본선택 리스트가 <video preload=metadata>로 썸네일을 대신하던 탓에
행마다 원본 mp4(수 MB)를 통째로 받았고(=/api/wiki/video가 Range 미적용 200 응답),
10행이면 수십 MB라 메타데이터도 못 붙어 전부 검은칸이었다(2026-07-15 실측).
보관 mp4에서 첫 프레임 1장을 떠 캐시해 주면 <img>로 즉시 그려진다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module, "_WIKI_MEDIA_DIR", tmp_path / "media")
    (tmp_path / "media").mkdir()
    return TestClient(app_module.app)


def _media_path(shortcode, tmp_path):
    import hashlib
    h = hashlib.sha1(shortcode.encode()).hexdigest()[:16]
    return tmp_path / "media" / f"{h}.mp4"


def test_poster_404_when_no_archived_video(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/api/wiki/poster", params={"shortcode": "NOPE"}).status_code == 404


def test_poster_extracts_first_frame_and_caches(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    _media_path("SC1", tmp_path).write_bytes(b"fake-mp4")

    calls = []

    def _fake_extract(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
        calls.append(timestamp_sec)
        from pathlib import Path
        out = Path(dest_dir) / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\xff\xd8jpeg")  # JPEG 매직만 흉내
        return out

    monkeypatch.setattr(app_module, "extract_frame_at", _fake_extract)

    r = client.get("/api/wiki/poster", params={"shortcode": "SC1"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")
    assert r.content == b"\xff\xd8jpeg"
    assert len(calls) == 1  # 첫 요청에만 ffmpeg

    # 두번째 요청은 캐시 히트 — ffmpeg 재실행 없음
    r2 = client.get("/api/wiki/poster", params={"shortcode": "SC1"})
    assert r2.status_code == 200 and r2.content == b"\xff\xd8jpeg"
    assert len(calls) == 1


def test_poster_404_when_extract_fails(monkeypatch, tmp_path):
    """ffmpeg 실패(손상 영상 등)면 404 — 프론트가 조용히 숨기게."""
    client = _client(monkeypatch, tmp_path)
    _media_path("SC2", tmp_path).write_bytes(b"broken")
    monkeypatch.setattr(app_module, "extract_frame_at",
                        lambda *a, **k: None)
    assert client.get("/api/wiki/poster", params={"shortcode": "SC2"}).status_code == 404
