"""C-1(Critical) 회귀방지: /api/produce/save_to_wiki는 클라이언트가 확정한
리메이크 대본(script_text)을 저장하면 안 되고, 항상 '원본'을 저장해야 한다.

실사고(2026-07-15, 실측 확인): 제작소에서 리메이크로 확정한 대본을 위키저장했더니
script_extracts(원본 캐시)가 리메이크로 덮이고(extract_from_url은 캐시 히트 시
재추출 안 함 → 복구불가), script_wiki(학습 창고)에도 리메이크가 들어가 학습
코퍼스가 우리 출력을 재학습하는 루프가 됐다. `.superpowers/sdd/
task-7-c1-wiki-original-brief.md` 참고."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    return TestClient(app_module.app), Store(db)


def test_save_to_wiki_never_overwrites_original_extract(monkeypatch, tmp_path):
    """원본이 이미 캐시된 상태에서 리메이크 텍스트로 위키저장을 눌러도
    script_extracts(원본 캐시)는 절대 안 덮이고, 위키에도 원본이 들어간다."""
    client, store = _client(monkeypatch, tmp_path)

    # 1) 원본이 이미 캐시된 상태
    store.save_script("ABC", {"full_text": "원본대본 미쳤어요", "segments": []}, category="레시피")

    # download_any가 호출되면 안 된다(캐시 히트 시 재추출 금지) — 호출되면 즉시 fail
    def _must_not_be_called(url, dest_dir):
        raise AssertionError("캐시 히트인데 재추출을 시도함 — 원본 파괴 위험")
    monkeypatch.setattr(app_module, "download_any", _must_not_be_called)

    relearned = []
    monkeypatch.setattr(app_module, "_relearn_category",
                        lambda db_path, category: relearned.append(category))

    # 2) 리메이크 텍스트로 위키저장 호출(프론트가 여전히 보내더라도 무시돼야 함)
    r = client.post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/ABC/",
        "shortcode": "ABC",
        "script_text": "리메이크 끝내줘요",
        "structure": {"hook_type": "리메이크구조"},
        "category": "레시피",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True

    # 3) 단언: 원본 캐시가 안 덮였다
    extract = store.get_extract("ABC")
    assert extract["full_text"] == "원본대본 미쳤어요"

    # 4) 위키에도 원본이 들어갔다(리메이크 아님)
    listed = store.wiki_list()
    saved = next(i for i in listed if i["shortcode"] == "ABC")
    assert saved["full_text"] == "원본대본 미쳤어요"

    assert relearned == ["레시피"]


def test_save_to_wiki_extracts_original_when_not_cached(monkeypatch, tmp_path):
    """원본 캐시가 없을 때는 URL에서 원본을 즉석 추출해 그걸 저장한다
    (script_text로 보낸 리메이크가 아니라)."""
    client, store = _client(monkeypatch, tmp_path)

    def _fake_download(url, dest_dir):
        return "/fake/video.mp4", "캡션"
    monkeypatch.setattr(app_module, "download_any", _fake_download)

    def _fake_extract(video_path, code, caption=""):
        return {"full_text": "추출된 원본 대본", "segments": [{"text": "추출된 원본 대본", "start": 0, "end": 1}]}
    monkeypatch.setattr(app_module, "extract_script", _fake_extract)

    relearned = []
    monkeypatch.setattr(app_module, "_relearn_category",
                        lambda db_path, category: relearned.append(category))

    r = client.post("/api/produce/save_to_wiki", json={
        "url": "https://www.instagram.com/reel/NEW1/",
        "script_text": "리메이크 끝내줘요(무시돼야 함)",
        "category": "레시피",
        "name": "홈에디터",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    code = d["shortcode"]

    # script_extracts에 '추출된 원본'이 저장됐다(리메이크 아님)
    extract = store.get_extract(code)
    assert extract["full_text"] == "추출된 원본 대본"

    # 위키에도 원본이 들어갔다
    listed = store.wiki_list()
    saved = next(i for i in listed if i["shortcode"] == code)
    assert saved["full_text"] == "추출된 원본 대본"

    assert relearned == ["레시피"]


def test_save_to_wiki_requires_url_only(monkeypatch, tmp_path):
    """script_text는 더 이상 필수가 아니다(원본 저장에 불필요) — url만 필수."""
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/produce/save_to_wiki", json={"script_text": "대본만 있음"})
    assert r.status_code == 422

    def _boom(url, dest_dir):
        raise RuntimeError("다운로드 실패")
    monkeypatch.setattr(app_module, "download_any", _boom)
    r2 = client.post("/api/produce/save_to_wiki", json={"url": "https://x.com/reel/Y/"})
    assert r2.status_code == 502  # url만 있고 캐시도 없으면 추출 시도 → 다운로드 실패 시 502
