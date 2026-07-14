"""/api/wiki/generate 위키 미저장 폴백 테스트(2026-07-15, 영상제작소 대본뽑기 모달 연동).

기존 /api/wiki/generate는 store.get_wiki_item()에 전적으로 의존해 위키에 없는
shortcode면 404였다. 제작소(영상제작소)에서 위키 저장 없이 직행한 영상도 대본
생성이 되도록, body에 structure/base_script가 실려오면 그걸로 진행하는 폴백을
추가했다. 기존 위키 경로(위키에 있으면 그걸 우선)는 그대로 유지되는지도 검증."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    return TestClient(app_module.app), Store(db)


def _fake_generate_variations(structure, full_text, elem_modes, category_lookup,
                              mode="remake", my_topic="", subject="", n=3, max_key_tries=3):
    return [{"hook": "가짜 훅", "script": f"[{mode}] {full_text[:10]}", "applied": "테스트"}]


def test_generate_falls_back_to_body_when_not_in_wiki(monkeypatch, tmp_path):
    """위키에 없는 shortcode라도 body에 structure/base_script를 주면 404가 아니라
    200으로 생성이 진행돼야 한다."""
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.script_generate, "generate_variations", _fake_generate_variations)

    r = client.post("/api/wiki/generate?shortcode=notinwiki123", json={
        "mode": "remake",
        "base_script": "원본 대본 전체 텍스트입니다",
        "structure": {"hook_type": "질문형"},
        "category": "생활용품",
        "n": 1,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert len(d["drafts"]) == 1
    assert d["drafts"][0]["draft_id"]
    assert "remake" in d["drafts"][0]["script"]


def test_generate_without_wiki_or_body_fallback_is_404(monkeypatch, tmp_path):
    """위키에도 없고 body에 structure/base_script도 없으면 여전히 404(기존 동작 유지)."""
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=nothingatall", json={"mode": "remake"})
    assert r.status_code == 404


def test_generate_prefers_wiki_item_over_body_when_present(monkeypatch, tmp_path):
    """위키에 이미 있으면 body의 structure/base_script를 무시하고 위키 걸 우선한다
    (하위호환 — 기존 위키 경로가 안 깨지는지 확인)."""
    client, store = _client(monkeypatch, tmp_path)
    seen = {}

    def _capture(structure, full_text, elem_modes, category_lookup,
                 mode="remake", my_topic="", subject="", n=3, max_key_tries=3):
        seen["full_text"] = full_text
        seen["structure"] = structure
        return [{"hook": "h", "script": "s", "applied": "a"}]

    monkeypatch.setattr(app_module.script_generate, "generate_variations", _capture)
    store.save_to_wiki(
        {"shortcode": "insa1", "name": "홈에디터", "category": "생활용품", "url": "https://x.com/1"},
        {"full_text": "위키에 저장된 진짜 대본", "segments": []},
        {"hook_type": "위키구조"},
    )
    r = client.post("/api/wiki/generate?shortcode=insa1", json={
        "mode": "remake",
        "base_script": "이건 body가 보낸 가짜 대본(무시돼야 함)",
        "structure": {"hook_type": "body구조(무시돼야함)"},
        "n": 1,
    })
    assert r.status_code == 200
    assert seen["full_text"] == "위키에 저장된 진짜 대본"
    assert seen["structure"] == {"hook_type": "위키구조"}
