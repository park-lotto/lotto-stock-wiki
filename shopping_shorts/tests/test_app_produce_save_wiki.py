"""제작소에서 지정한 원본 영상을 URL 기반으로 위키에 저장하는 라우트
(/api/produce/save_to_wiki) 테스트. 기존 /api/wiki/save는 last_run에
있는 항목만 저장 가능해, 즐겨찾기 경유로 제작소에 직행한 영상은
저장 불가했다(last_run 미의존, 2026-07-15).

[2026-07-15 C-1 수정] 이 라우트는 클라이언트가 확정한 script_text(리메이크)를
저장하는 게 아니라 항상 '원본'을 저장한다 — /api/wiki/save와 같은 의미.
원본 파괴 회귀방지 테스트는 test_produce_save_to_wiki_original.py 참고."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    return TestClient(app_module.app), Store(db)


def test_save_to_wiki_by_url_extracts_original_and_relearns(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)

    # 원본 캐시가 없으므로 URL에서 즉석 추출 경로를 탄다.
    def _fake_download(url, dest_dir):
        return "/fake/video.mp4", "캡션"
    monkeypatch.setattr(app_module, "download_any", _fake_download)

    def _fake_extract(video_path, code, caption=""):
        return {"full_text": "생선 굽기 꿀팁 대본(원본)", "segments": []}
    monkeypatch.setattr(app_module, "extract_script", _fake_extract)

    relearned = []
    monkeypatch.setattr(app_module, "_relearn_category",
                        lambda db_path, category: relearned.append(category))

    r = client.post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/ABC123/",
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

    code = d["shortcode"]
    listed = client.get("/api/wiki/list").json()["items"]
    assert any(i["shortcode"] == code for i in listed)
    saved_item = next(i for i in listed if i["shortcode"] == code)
    assert saved_item["full_text"] == "생선 굽기 꿀팁 대본(원본)"
    assert saved_item["category"] == "레시피"

    # script_extracts(원본 캐시)에도 원본이 저장됐다.
    extract = store.get_extract(code)
    assert extract["full_text"] == "생선 굽기 꿀팁 대본(원본)"

    assert relearned == ["레시피"]


def test_save_to_wiki_download_failure_returns_502_when_not_cached(monkeypatch, tmp_path):
    """원본 캐시가 없는 상태에서 다운로드가 실패하면(URL 만료 등) 원본을
    확보할 방법이 없으므로 502 — script_text로 대신 채우지 않는다."""
    client, store = _client(monkeypatch, tmp_path)

    def _boom(url, dest_dir):
        raise RuntimeError("다운로드 실패")
    monkeypatch.setattr(app_module, "download_any", _boom)

    r = client.post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/ABC123/",
        "category": "레시피",
    })
    assert r.status_code == 502
    assert client.get("/api/wiki/list").json()["items"] == []


def test_save_to_wiki_requires_url(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/save_to_wiki", json={"script_text": "대본만 있음"})
    assert r.status_code == 422
