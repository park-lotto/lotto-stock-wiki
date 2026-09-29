from fastapi.testclient import TestClient

from shopping_shorts import app as app_module


def _admin_client(monkeypatch):
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module, "_is_admin", lambda _cid: True)
    return TestClient(app_module.app)


def test_admin_pilot_page_and_config_do_not_expose_secret(monkeypatch):
    monkeypatch.setenv("HIGGSFIELD_API_KEY_ID", "visible-id")
    monkeypatch.setenv("HIGGSFIELD_API_KEY_SECRET", "never-return-this")
    client = _admin_client(monkeypatch)

    page = client.get("/admin/higgsfield")
    assert page.status_code == 200
    assert "Higgsfield API 시험실" in page.text

    response = client.get("/api/admin/higgsfield/config")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["charge_mode"] == "admin_pilot_no_points"
    assert "never-return-this" not in response.text
    assert "visible-id" not in response.text


def test_generate_requires_server_key_and_spend_confirmation(monkeypatch):
    monkeypatch.delenv("HIGGSFIELD_API_KEY_ID", raising=False)
    monkeypatch.delenv("HIGGSFIELD_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("HF_API_KEY_ID", raising=False)
    monkeypatch.delenv("HF_API_KEY_SECRET", raising=False)
    client = _admin_client(monkeypatch)
    body = {"image_url": "https://example.com/product.jpg", "confirm_spend": True}
    assert client.post("/api/admin/higgsfield/generate", json=body).status_code == 503

    monkeypatch.setenv("HIGGSFIELD_API_KEY_ID", "id")
    monkeypatch.setenv("HIGGSFIELD_API_KEY_SECRET", "secret")
    body["confirm_spend"] = False
    response = client.post("/api/admin/higgsfield/generate", json=body)
    assert response.status_code == 422
    assert "비용" in response.json()["error"]


def test_non_admin_cannot_open_pilot(monkeypatch):
    monkeypatch.setattr(app_module, "_AUTH_ON", False)
    monkeypatch.setattr(app_module, "_is_admin", lambda _cid: False)
    client = TestClient(app_module.app)
    assert client.get("/api/admin/higgsfield/config").status_code == 403


def test_admin_can_store_owner_key_without_echoing_secret(monkeypatch):
    saved = []

    class FakeStore:
        def __init__(self, *_a, **_k):
            pass

        def add_customer_key(self, customer_id, service, plain, label=None):
            saved.append((customer_id, service, plain, label))
            return True

        def list_customer_keys(self, customer_id, service):
            return [{"id": 9, "service": service}]

        def delete_customer_key(self, *_a, **_k):
            raise AssertionError("새 키 한 개뿐인데 삭제하면 안 됨")

    monkeypatch.setattr(app_module, "Store", FakeStore)
    monkeypatch.setattr(app_module.keycrypt, "enabled", lambda: True)
    client = _admin_client(monkeypatch)
    response = client.post("/api/admin/higgsfield/key", json={
        "key_id": "key-id-1234", "key_secret": "super-secret-value",
    })

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert saved[0][0:3] == (0, "higgsfield_owner", "key-id-1234:super-secret-value")
    assert "super-secret-value" not in response.text
