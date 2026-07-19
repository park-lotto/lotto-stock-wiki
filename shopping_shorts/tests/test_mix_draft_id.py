"""조합 생성 초안이 서버에 저장돼 draft_id를 받는지 — 요소 업그레이드의 전제."""
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
    Store(str(tmp))  # 스키마 생성
    monkeypatch.setattr(
        script_generate, "generate_mix",
        lambda sources, target_seconds=20, n=3: [
            {"hook": "훅1", "script": "대본1", "applied": "조합"},
            {"hook": "훅2", "script": "대본2", "applied": "조합"},
        ])
    return TestClient(appmod.app), str(tmp)


def test_mix_attaches_draft_id_and_saves(client):
    c, dbp = client
    body = {"sources": [
        {"shortcode": "a", "full_text": "가나다 대본 A"},
        {"shortcode": "b", "full_text": "라마바 대본 B"}], "target_seconds": 20, "n": 3}
    r = c.post("/api/produce/script/mix", json=body)
    assert r.status_code == 200, r.text
    drafts = r.json()["drafts"]
    assert drafts and all(d.get("draft_id") for d in drafts)
    # 서버에 실제로 저장됐는지
    saved = Store(dbp).get_draft(drafts[0]["draft_id"])
    assert saved and saved["script_text"] == "대본1" and saved["edit_mode"] == "mix"
