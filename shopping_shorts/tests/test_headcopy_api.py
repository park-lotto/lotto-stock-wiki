"""고정카피 API — ★캐시 적중 시 AI 호출이 **0회**인지가 이 테스트의 전부다.

자동 생성이라 캐시가 없으면 6단계를 오갈 때마다 과금된다.
"""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod

client = TestClient(app_mod.app)


@pytest.fixture
def spy(monkeypatch):
    calls = []

    def fake(script, want=4):
        calls.append(script)
        return [{"label": "짧은 훅형", "text": "이거 모르면 손해"}]

    monkeypatch.setattr(app_mod.headcopy_gen, "suggest", fake)
    return calls


def test_missing_script_is_422(spy):
    r = client.post("/api/produce/headcopy/suggest", json={"script": "  "})
    assert r.status_code == 422
    assert spy == [], "빈 대본인데 AI를 불렀다"


def test_first_call_generates(spy):
    r = client.post("/api/produce/headcopy/suggest", json={"script": "감자 대본입니다"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["cached"] is False
    assert d["copies"][0]["text"] == "이거 모르면 손해"
    assert len(spy) == 1


def test_same_script_hits_cache_zero_calls(spy):
    """★같은 대본이면 두 번째부터 호출 0회. 이게 깨지면 오갈 때마다 돈이 샌다."""
    body = {"script": "캐시 확인용 대본"}
    client.post("/api/produce/headcopy/suggest", json=body)
    assert len(spy) == 1
    r2 = client.post("/api/produce/headcopy/suggest", json=body)
    assert r2.json()["cached"] is True
    assert len(spy) == 1, f"캐시 적중인데 AI를 또 불렀다(호출 {len(spy)}회)"


def test_whitespace_variants_share_cache(spy):
    """앞뒤 공백·CRLF만 다른 건 같은 대본이다(_script_hash 규칙)."""
    client.post("/api/produce/headcopy/suggest", json={"script": "공백 테스트 대본"})
    n = len(spy)
    client.post("/api/produce/headcopy/suggest", json={"script": "  공백 테스트 대본  \r\n"})
    assert len(spy) == n, "공백만 다른 같은 대본에 다시 과금됐다"


def test_changed_script_regenerates(spy):
    client.post("/api/produce/headcopy/suggest", json={"script": "첫 번째 대본"})
    n = len(spy)
    client.post("/api/produce/headcopy/suggest", json={"script": "두 번째 대본"})
    assert len(spy) == n + 1, "대본이 바뀌었는데 옛 카피를 그대로 줬다"


def test_ai_empty_is_200_with_empty_list(monkeypatch):
    """못 뽑아도 500이 아니다 — 화면이 '못 뽑았어요'를 그릴 수 있어야 한다."""
    monkeypatch.setattr(app_mod.headcopy_gen, "suggest", lambda s, want=4: [])
    r = client.post("/api/produce/headcopy/suggest", json={"script": "실패용 대본 xyz"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "cached": False, "copies": []}
