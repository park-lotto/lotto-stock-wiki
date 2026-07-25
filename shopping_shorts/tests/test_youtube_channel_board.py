from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts import service as svc


def test_board_joins_seeds_with_metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(svc, "DB_PATH", str(tmp_path / "b.db"))

    items = [
        {"username": "UCaaaaaaaaaa", "name": "채널A", "views": 1000, "speed": 50.0,
         "density": 0.1, "accel": 3, "score": 0.9, "grade": "🔥", "thumbnail": "t"},
        {"username": "UCaaaaaaaaaa", "name": "채널A", "views": 500, "speed": 20.0,
         "density": 0.2, "accel": 1, "score": 0.3, "grade": "—", "thumbnail": "t2"},
    ]

    class FakeStore:
        def __init__(self, *a, **k): pass
        def load_last_run_platform(self, p): return items, "2026-07-25T00:00:00Z"
        def list_seeds(self, p):
            return [
                {"kind": "account", "value": "https://www.youtube.com/channel/UCaaaaaaaaaa", "added_at": "1"},
                {"kind": "account", "value": "https://www.youtube.com/channel/UCbbbbbbbbbb", "added_at": "2"},  # 최근영상 없음
            ]
    monkeypatch.setattr(svc, "Store", FakeStore)

    res = svc.youtube_channel_board(sort="views")
    assert res["total"] == 2
    a = next(r for r in res["channels"] if r["channel_id"] == "UCaaaaaaaaaa")
    assert a["collected"] is True and a["views"] == 1500 and a["video_count"] == 2
    assert a["speed"] == 50.0 and a["accel"] == 4
    b = next(r for r in res["channels"] if r["channel_id"] == "UCbbbbbbbbbb")
    assert b["collected"] is False and b["views"] == 0     # 수집대기
    assert res["channels"][0]["channel_id"] == "UCaaaaaaaaaa"   # views 정렬 상위


def test_endpoint_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "e.db"))
    c = TestClient(appmod.app)
    r = c.get("/api/youtube/channels?sort=speed").json()
    assert r["ok"] is True and "channels" in r
