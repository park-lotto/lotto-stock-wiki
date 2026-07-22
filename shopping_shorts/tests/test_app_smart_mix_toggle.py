"""스마트 믹스 토글 — bank_enabled + ping_pong_enabled를 한 스위치로 켠다.
제작소에서 사장님이 딸깍으로 부품은행·반복회피·핑퐁을 켜고 끄게."""
from fastapi.testclient import TestClient

import shopping_shorts.app as app_mod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    Store(app_mod.DB_PATH)   # 스키마 생성
    return TestClient(app_mod.app)


def test_smart_mix_default_off(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/settings/smart_mix")
    assert r.json() == {"ok": True, "on": False}


def test_smart_mix_toggle_on_sets_both(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/settings/smart_mix", json={"on": True})
    assert r.json()["ok"] is True
    s = Store(app_mod.DB_PATH)
    assert s.get_setting("bank_enabled") == "1"
    assert s.get_setting("ping_pong_enabled") == "1"
    assert s.get_setting("backbone_base_enabled") == "1"   # 백본-베이스도 함께 켜진다
    assert c.get("/api/settings/smart_mix").json()["on"] is True


def test_smart_mix_toggle_off_clears_both(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    c.post("/api/settings/smart_mix", json={"on": True})
    c.post("/api/settings/smart_mix", json={"on": False})
    s = Store(app_mod.DB_PATH)
    assert s.get_setting("bank_enabled") == "0"
    assert s.get_setting("ping_pong_enabled") == "0"
    assert s.get_setting("backbone_base_enabled") == "0"
    assert c.get("/api/settings/smart_mix").json()["on"] is False
