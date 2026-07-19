"""URL 붙여넣기 → 구글렌즈 유사영상 역추적 엔드포인트 /api/lens/trace_url.

/api/lens/search(프레임 업로드)와 같은 경로지만 입력이 URL이라, download_any로 받아
중간 프레임을 뽑아 search_similar_videos에 태운다. 다운로드/추출/업로드/검색은 전부
mock — 배선(입력 URL→검색 이미지·캡션 전달)과 가드(422/429/502)를 검증한다.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _wire_happy(monkeypatch, tmp_path, calls):
    monkeypatch.setattr(app_module, "_ssrf_guard", lambda *a, **k: None)
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

    def _fake_search(image_url, source_caption=None):
        calls["img"] = image_url
        calls["cap"] = source_caption
        return [{"platform": "youtube", "url": "https://youtu.be/AAA",
                 "title": "원본", "thumbnail": "t", "match": 0.91}]

    monkeypatch.setattr(app_module, "search_similar_videos", _fake_search)


def test_trace_url_returns_similar_videos(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    calls = {}
    _wire_happy(monkeypatch, tmp_path, calls)
    r = client.post("/api/lens/trace_url", json={"url": "https://youtube.com/shorts/X"})
    assert r.status_code == 200
    b = r.json()
    assert b["ok"] is True and b["count"] == 1
    assert b["items"][0]["platform"] == "youtube"
    # 중간지점 프레임(4.0/2)이 렌즈 이미지·다운로드 캡션이 검색에 그대로 전달됐나
    assert calls["ts"] == 2.0
    assert calls["img"] == "https://img/x.jpg"
    assert calls["cap"] == "감자 자막"


def test_trace_url_requires_url(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.post("/api/lens/trace_url", json={"url": ""}).status_code == 422


def test_trace_url_download_failure_502(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "_ssrf_guard", lambda *a, **k: None)

    def boom(u, d):
        raise RuntimeError("URL 만료")

    monkeypatch.setattr(app_module, "download_any", boom)
    r = client.post("/api/lens/trace_url", json={"url": "https://insta/p/GONE"})
    assert r.status_code == 502


def test_trace_url_month_limit_429(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "_ssrf_guard", lambda *a, **k: None)
    store.set_setting("lens_month_limit", "0")   # 한도 0 → 다운로드 전에 즉시 429
    r = client.post("/api/lens/trace_url", json={"url": "https://youtube.com/shorts/X"})
    assert r.status_code == 429
    assert r.json()["error_code"] == "lens_limit"
