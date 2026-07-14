"""제작소에서 확정한 대본을 URL 기반으로 위키에 저장하는 라우트
(/api/produce/save_to_wiki) 테스트. 기존 /api/wiki/save는 last_run에
있는 항목만 저장 가능해, 즐겨찾기 경유로 제작소에 직행한 영상은
저장 불가했다(last_run 미의존, 2026-07-15)."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    return TestClient(app_module.app), Store(db)


def test_save_to_wiki_by_url_persists_and_relearns(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)

    # 영상 다운로드는 실패해도(예: URL 만료) 대본·구조는 저장돼야 한다.
    def _boom(url, dest_dir):
        raise RuntimeError("다운로드 실패")
    monkeypatch.setattr(app_module, "download_any", _boom)

    relearned = []
    monkeypatch.setattr(app_module, "_relearn_category",
                        lambda db_path, category: relearned.append(category))

    r = client.post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/ABC123/",
        "script_text": "생선 굽기 꿀팁 대본",
        "category": "레시피",
        "name": "홈에디터",
        "video_url": "https://cdn.example/v.mp4",
        "caption": "캡션",
        "followers": 100,
        "comments": 50,
        "density": 0.1,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["shortcode"]
    assert d["has_video"] is False  # 다운로드 실패했으니 영상은 없음

    code = d["shortcode"]
    listed = client.get("/api/wiki/list").json()["items"]
    assert any(i["shortcode"] == code for i in listed)
    saved_item = next(i for i in listed if i["shortcode"] == code)
    assert saved_item["full_text"] == "생선 굽기 꿀팁 대본"
    assert saved_item["category"] == "레시피"

    assert relearned == ["레시피"]


def test_save_to_wiki_requires_url_and_script(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/save_to_wiki", json={"script_text": "대본만 있음"})
    assert r.status_code == 422
    r2 = client.post("/api/produce/save_to_wiki", json={"url": "https://x.com/reel/Y/"})
    assert r2.status_code == 422
