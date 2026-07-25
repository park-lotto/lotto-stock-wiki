from fastapi.testclient import TestClient
from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(appmod.app)


def test_bench_from_videos_adds_account_seeds(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(appmod, "yt_channels_from_videos", lambda urls: [
        {"channel_id": "UCaaa", "channel_title": "로지홈",
         "channel_url": "https://www.youtube.com/channel/UCaaa"},
        {"channel_id": "UCbbb", "channel_title": "생활GIFTBOX",
         "channel_url": "https://www.youtube.com/channel/UCbbb"},
    ])

    r = c.post("/api/seeds/from_youtube_videos", json={
        "urls": ["https://youtu.be/v1", "https://youtu.be/v2"]}).json()
    assert r["ok"] and r["added"] == 2 and r["duplicate"] == 0

    seeds = c.get("/api/seeds?platform=youtube").json()["items"]
    vals = {s["value"] for s in seeds if s["kind"] == "account"}
    assert vals == {"https://www.youtube.com/channel/UCaaa",
                    "https://www.youtube.com/channel/UCbbb"}


def test_bench_from_videos_reports_duplicates(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    # 먼저 UCaaa를 이미 벤치에 등록해둠
    c.post("/api/seeds", json={"platform": "youtube", "kind": "account",
                               "value": "https://www.youtube.com/channel/UCaaa"})
    monkeypatch.setattr(appmod, "yt_channels_from_videos", lambda urls: [
        {"channel_id": "UCaaa", "channel_title": "로지홈",
         "channel_url": "https://www.youtube.com/channel/UCaaa"},
        {"channel_id": "UCbbb", "channel_title": "새채널",
         "channel_url": "https://www.youtube.com/channel/UCbbb"},
    ])
    r = c.post("/api/seeds/from_youtube_videos", json={"urls": ["https://youtu.be/v1"]}).json()
    assert r["added"] == 1 and r["duplicate"] == 1


def test_bench_from_videos_empty_urls(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/seeds/from_youtube_videos", json={"urls": []})
    assert r.status_code == 422
