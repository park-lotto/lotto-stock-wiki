"""채널 보드(/api/youtube/channels) 응답에 쇼핑 적합도가 실리는지 검증(2026-07-29).

실제 엔드포인트는 브리프의 추정치(/api/channel_board)가 아니라 /api/youtube/channels다.
index.html의 openChannelBoard()가 부르는 URL을 확인해 맞췄다. 응답 구조도
{"ok", "channels": [...], "collected_at", "total"} 이며 각 행 키는 channel_id/name 등이다
("channel" 키가 아니라 "name").
"""
from fastapi.testclient import TestClient
import shopping_shorts.app as app_mod

client = TestClient(app_mod.app)


def test_channel_board_includes_fitness(monkeypatch):
    UC_A = "UCAAAAAAAAAAAAAAAAAAAAAA"
    UC_B = "UCBBBBBBBBBBBBBBBBBBBBBB"
    fake_items = [
        {"name": "살림수집가", "username": UC_A, "category": "홈템", "views": 100},
        {"name": "살림수집가", "username": UC_A, "category": "기타", "views": 50},
        {"name": "연예노트", "username": UC_B, "category": "기타", "views": 999},
    ]
    monkeypatch.setattr(app_mod.Store, "load_last_run_platform",
                        lambda self, p: (fake_items, "2026-07-29T00:00:00+00:00"))
    monkeypatch.setattr(app_mod.Store, "list_seeds", lambda self, p: [
        {"kind": "account", "value": f"https://www.youtube.com/channel/{UC_A}", "added_at": ""},
        {"kind": "account", "value": f"https://www.youtube.com/channel/{UC_B}", "added_at": ""},
    ])

    r = client.get("/api/youtube/channels?sort=views")
    assert r.status_code == 200
    body = r.json()
    rows = {row["name"]: row for row in body["channels"]}

    assert abs(rows["살림수집가"]["fitness"] - 0.5) < 1e-9
    assert rows["살림수집가"]["good"] == 1
    assert rows["살림수집가"]["other"] == 1

    assert rows["연예노트"]["fitness"] == 0.0
    assert rows["연예노트"]["other"] == 1

    # seed_url·total(영상수)도 다음 태스크(DELETE /api/seeds)가 쓰므로 함께 검증
    assert rows["살림수집가"]["seed_url"] == f"https://www.youtube.com/channel/{UC_A}"
    assert rows["살림수집가"]["video_count"] == 2

    # 적합도 오름차순 정렬 확인
    r2 = client.get("/api/youtube/channels?sort=fitness")
    names = [row["name"] for row in r2.json()["channels"]]
    assert names.index("연예노트") < names.index("살림수집가")
