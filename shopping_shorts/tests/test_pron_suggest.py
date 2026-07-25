"""AI 발음 교정 제안(2026-07-22). Gemini가 어색 구절→재표기 후보를 낸다.
무키/실패면 빈 목록(수동 입력 폴백) — 작업대가 안 죽는다."""
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from shopping_shorts import app as appmod
    return TestClient(appmod.app)


def test_suggest_returns_vault_result(client, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod.edit_plan, "_vault_call",
                        lambda prompt, schema, **k: {"suggestions": [
                            {"phrase": "좋은데요", "respelling": "조은데요", "reason": "연음"}]})
    # 관리자 우회는 기존 API 테스트 fixture 패턴을 따를 것(Task 3 주의 참고).
    r = client.post("/api/pron/suggest", json={"text": "이건 좋은데요"})
    assert r.status_code == 200
    assert r.json()["suggestions"][0]["respelling"] == "조은데요"


def test_suggest_graceful_when_no_key(client, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod.edit_plan, "_vault_call", lambda *a, **k: None)
    r = client.post("/api/pron/suggest", json={"text": "이건 좋은데요"})
    assert r.status_code == 200 and r.json()["suggestions"] == []


def test_suggest_filters_hallucination_and_noop(client, monkeypatch):
    """원문에 없는 구절(환각)과 phrase==respelling(no-op)은 걸러낸다."""
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod.edit_plan, "_vault_call",
                        lambda prompt, schema, **k: {"suggestions": [
                            {"phrase": "좋은데요", "respelling": "조은데요", "reason": "연음"},
                            {"phrase": "없는구절", "respelling": "엄는구절", "reason": "환각"},
                            {"phrase": "이건", "respelling": "이건", "reason": "no-op"},
                        ]})
    r = client.post("/api/pron/suggest", json={"text": "이건 좋은데요"})
    assert r.status_code == 200
    out = r.json()["suggestions"]
    assert len(out) == 1 and out[0]["phrase"] == "좋은데요"
