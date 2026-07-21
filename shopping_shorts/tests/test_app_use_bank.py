"""생성 라우트가 use_bank 플래그로 부품은행 컨텍스트를 실제 생성에 넘기는지.
기본(플래그 없음)이면 bank_context=''(회귀0)."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts import script_generate, bank_assemble
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    cap = {}

    def fake_gen(structure, full_text, elem_modes, category_lookup, **kw):
        cap["bank_context"] = kw.get("bank_context")
        cap["has_bank_kw"] = "bank_context" in kw
        return [{"hook": "h", "script": "s", "applied": "a"}]
    monkeypatch.setattr(script_generate, "generate_variations", fake_gen)
    monkeypatch.setattr(bank_assemble, "assemble_bank_context",
                        lambda store, category, **k: "[승인된 부품] 훅:대박")
    return TestClient(app_mod.app), cap


def test_use_bank_passes_context(monkeypatch, tmp_path):
    client, cap = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본 대본", "category": "레시피", "use_bank": True})
    assert r.status_code == 200
    assert cap["bank_context"] == "[승인된 부품] 훅:대박"


def test_default_no_bank(monkeypatch, tmp_path):
    client, cap = _client(monkeypatch, tmp_path)
    r = client.post("/api/wiki/generate?shortcode=X",
                    json={"base_script": "원본 대본", "category": "레시피"})
    assert r.status_code == 200
    # 기본(off): bank_context 인자를 아예 안 넘긴다 = 호출이 기존과 완전 동일(회귀0)
    assert cap["has_bank_kw"] is False
