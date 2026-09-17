from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod


def test_frame_presets_expose_first_hook_copy_family():
    data = TestClient(app_mod.app).get("/api/produce/frame/presets").json()
    assert data["presets"]
    assert {p["copy_family"] for p in data["presets"]} == {"youtube_reveal"}
