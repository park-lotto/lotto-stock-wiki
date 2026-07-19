"""요소 업그레이드 — 고른 요소만 free로 generate_variations 호출하고 새 버전 저장."""
import pathlib
import tempfile

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import script_generate
from shopping_shorts.store import Store


@pytest.fixture
def client(monkeypatch):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "t.db"
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp))
    st = Store(str(tmp))
    st.save_draft("d1", "cust", None, None, "옛훅", "옛 대본 전체", None, "mix")
    monkeypatch.setattr(appmod, "analyze_structure", lambda text: {"product_category": "레시피", "hook_type": "경고형"})
    captured = {}

    def fake_var(structure, full_text, elem_modes, category_lookup, **kw):
        captured["elem_modes"] = elem_modes
        captured["n"] = kw.get("n")
        return [{"hook": "새훅", "script": "새 대본", "applied": "훅 변형"}]

    monkeypatch.setattr(script_generate, "generate_variations", fake_var)
    return TestClient(appmod.app), str(tmp), captured


def test_upgrade_only_selected_element_is_free(client):
    c, dbp, captured = client
    r = c.post("/api/wiki/draft/upgrade", json={"draft_id": "d1", "elements": ["hook"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["script_text"] == "새 대본"
    # 고른 hook만 free, n=1
    assert captured["elem_modes"] == {"hook": "free"} and captured["n"] == 1
    # 새 버전이 parent를 가리키며 저장됨
    saved = Store(dbp).get_draft(j["draft_id"])
    assert saved["parent_draft_id"] == "d1" and saved["edit_mode"] == "upgrade"


def test_upgrade_rejects_empty_elements(client):
    c, _, _ = client
    r = c.post("/api/wiki/draft/upgrade", json={"draft_id": "d1", "elements": []})
    assert r.status_code == 422


def test_upgrade_unknown_draft_404(client):
    c, _, _ = client
    r = c.post("/api/wiki/draft/upgrade", json={"draft_id": "nope", "elements": ["hook"]})
    assert r.status_code == 404
