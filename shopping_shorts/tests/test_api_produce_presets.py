# 제작소 프리셋 3종(내 프리셋·내 템플릿·자막 프리셋) 계정 저장(2026-09-17)
# ★종전 localStorage 저장이라 회사 PC→집 PC에서 사라졌다(이윤정님 제보). 서버 customer_prefs로 이관.
from shopping_shorts.store import Store


def _setup(tmp_path, monkeypatch):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    appmod._ACCESS_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return appmod, s


def _client(appmod, cid):
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return TestClient(appmod.app, cookies={"dash_auth": appmod._sign_session(cid, exp)})


def test_presets_saved_per_account_and_isolated(tmp_path, monkeypatch):
    appmod, s = _setup(tmp_path, monkeypatch)
    a = _client(appmod, s.create_customer("a", "pw12"))
    b = _client(appmod, s.create_customer("b", "pw12"))
    assert a.get("/api/produce/presets/fr_my_templates").json() == {"ok": True, "items": [], "is_default": True}
    r = a.post("/api/produce/presets/fr_my_templates",
               json={"items": [{"name": " 내 기본틀 ", "frame": {"id": "bar", "color": "#fff"}}]})
    assert r.status_code == 200 and r.json()["items"][0]["name"] == "내 기본틀"
    # 같은 계정은 다른 브라우저(=새 클라이언트)에서도 보인다 — 이게 이 작업의 목적
    assert a.get("/api/produce/presets/fr_my_templates").json()["items"][0]["frame"]["id"] == "bar"
    # 다른 계정엔 안 보인다
    assert b.get("/api/produce/presets/fr_my_templates").json()["items"] == []


def test_presets_merge_migrates_local_without_duplicates(tmp_path, monkeypatch):
    appmod, s = _setup(tmp_path, monkeypatch)
    c = _client(appmod, s.create_customer("u", "pw12"))
    c.post("/api/produce/presets/cap_presets", json={"items": [{"name": "A", "cap": {"size": 1}}]})
    r = c.post("/api/produce/presets/cap_presets",
               json={"merge": [{"name": "A", "cap": {"size": 1}},      # 이미 있음 → 안 겹침
                               {"name": "B", "cap": {"size": 2}},      # 새것 → 붙음
                               {"cap": {"size": 3}}]})                 # 이름 없음 → 버림
    assert [x["name"] for x in r.json()["items"]] == ["A", "B"]


def test_presets_rejects_bad_kind_and_shape(tmp_path, monkeypatch):
    appmod, s = _setup(tmp_path, monkeypatch)
    c = _client(appmod, s.create_customer("u", "pw12"))
    assert c.get("/api/produce/presets/whatever").status_code == 404
    assert c.post("/api/produce/presets/hc_my_presets", json={"items": "x"}).status_code == 422
