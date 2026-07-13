import base64
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store

# 유효한 최소 JPEG(1x1)
_JPG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA"
    "AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK"
    "FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWG"
    "h4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl"
    "5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
    "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk"
    "NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE"
    "hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk"
    "5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)


def _client(tmp_path, monkeypatch, items=None, limit_reached=False):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://example.test")
    monkeypatch.setattr(appmod, "search_similar_videos",
                        lambda url: items if items is not None else [])
    if limit_reached:
        Store(db).set_setting("lens_month_limit", "0")
    return TestClient(appmod.app), db


def _post_img(c):
    return c.post("/api/lens/search",
                  files={"frame": ("f.jpg", _JPG_1PX, "image/jpeg")})


def test_lens_search_returns_filtered_videos(tmp_path, monkeypatch):
    items = [{"platform": "youtube", "url": "https://youtu.be/a", "title": "t", "thumbnail": "x"}]
    c, db = _client(tmp_path, monkeypatch, items=items)
    r = _post_img(c)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["items"] == items and d["count"] == 1
    from datetime import datetime, timezone
    m = datetime.now(timezone.utc).strftime("%Y-%m")
    assert Store(db).lens_month_count(m) == 1


def test_lens_search_blocked_when_month_limit_reached(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch, items=[], limit_reached=True)
    r = _post_img(c)
    assert r.status_code == 429
    assert r.json()["error_code"] == "lens_limit"


def test_media_url_returns_direct_mp4(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "resolve_media_url",
                        lambda platform, vid: "https://cdn.example/v.mp4?sig=1")
    c = TestClient(appmod.app)
    r = c.get("/api/media?platform=youtube&id=abc123")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "url": "https://cdn.example/v.mp4?sig=1"}


def test_media_url_not_found_returns_ok_false(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "resolve_media_url", lambda platform, vid: "")
    c = TestClient(appmod.app)
    r = c.get("/api/media?platform=tiktok&id=x")
    assert r.status_code == 200
    assert r.json()["ok"] is False
