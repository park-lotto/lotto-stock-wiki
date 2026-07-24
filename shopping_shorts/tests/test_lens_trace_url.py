"""URL 붙여넣기 → 구글렌즈 유사영상 역추적 /api/lens/trace_url.

유튜브는 서버 yt-dlp 봇차단이라 다운로드 없이 공개 썸네일(i.ytimg.com)을 쓰고,
그 외는 download_any로 받아 중간 프레임을 뽑되 실패 시 oEmbed 썸네일로 폴백한다.
다운로드/추출/업로드/검색/메타는 mock — 배선과 가드(422/429/502)를 검증한다.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_ssrf_guard", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _capture_search(monkeypatch, calls):
    def _fake_search(image_url, source_caption=None):
        calls["img"] = image_url
        calls["cap"] = source_caption
        return [{"platform": "youtube", "url": "https://youtu.be/AAA",
                 "title": "원본", "thumbnail": "t", "match": 0.9}]
    monkeypatch.setattr(app_module, "search_similar_videos", _fake_search)


def test_youtube_uses_public_thumbnail_no_download(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = {}
    _capture_search(monkeypatch, calls)

    def _boom(*a, **k):
        raise AssertionError("유튜브는 다운로드하면 안 됨(봇차단 회피)")
    monkeypatch.setattr(app_module, "download_any", _boom)

    r = client.post("/api/lens/trace_url",
                    json={"url": "https://www.youtube.com/shorts/IPNxs-XtubM?si=PJ"})
    assert r.status_code == 200
    b = r.json()
    assert b["ok"] is True and b["count"] == 1
    # 다운로드 없이 공개 썸네일(hqdefault)을 렌즈에 넘겼나
    assert calls["img"] == "https://i.ytimg.com/vi/IPNxs-XtubM/hqdefault.jpg"


def test_nonyoutube_downloads_midframe(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = {}
    _capture_search(monkeypatch, calls)
    (tmp_path / "v.mp4").write_bytes(b"x")
    monkeypatch.setattr(app_module, "download_any", lambda url, d: (str(tmp_path / "v.mp4"), "감자 자막"))
    monkeypatch.setattr(app_module.frame_extract, "_probe_duration", lambda p: 4.0)

    def _fake_extract(video, dest, ts, filename="f.jpg"):
        calls["ts"] = ts
        out = Path(dest) / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\xff\xd8jpeg")
        return out
    monkeypatch.setattr(app_module, "extract_frame_at", _fake_extract)
    monkeypatch.setattr(app_module, "upload_frame", lambda raw: "https://img/x.jpg")

    r = client.post("/api/lens/trace_url", json={"url": "https://www.instagram.com/reel/ABC/"})
    assert r.status_code == 200
    assert calls["ts"] == 2.0                      # 중간지점 (4/2)
    assert calls["img"] == "https://img/x.jpg"
    assert calls["cap"] == "감자 자막"


def test_nonyoutube_download_fail_falls_back_to_thumbnail(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = {}
    _capture_search(monkeypatch, calls)

    def _boom(u, d):
        raise RuntimeError("yt-dlp 봇차단")
    monkeypatch.setattr(app_module, "download_any", _boom)
    monkeypatch.setattr(app_module, "probe_grab_meta",
                        lambda u: {"thumbnail": "https://cdn/thumb.jpg", "title": "제목"})

    r = client.post("/api/lens/trace_url", json={"url": "https://www.tiktok.com/@x/video/1"})
    assert r.status_code == 200                    # 다운로드 실패해도 썸네일 폴백으로 성공
    assert calls["img"] == "https://cdn/thumb.jpg"
    assert calls["cap"] == "제목"


def test_download_and_thumbnail_both_fail_502(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)

    def _boom(u, d):
        raise RuntimeError("만료")
    monkeypatch.setattr(app_module, "download_any", _boom)
    monkeypatch.setattr(app_module, "probe_grab_meta", lambda u: {})
    r = client.post("/api/lens/trace_url", json={"url": "https://insta/p/GONE"})
    assert r.status_code == 502


def test_trace_url_requires_url(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.post("/api/lens/trace_url", json={"url": ""}).status_code == 422


def test_trace_url_month_limit_429(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.set_setting("lens_month_limit", "0")     # 한도 0 → 즉시 429
    r = client.post("/api/lens/trace_url", json={"url": "https://www.youtube.com/shorts/IPNxs-XtubM"})
    assert r.status_code == 429
    assert r.json()["error_code"] == "lens_limit"
