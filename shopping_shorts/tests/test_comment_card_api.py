import io
import json

from fastapi.testclient import TestClient
from PIL import Image

import shopping_shorts.app as appmod


def _client(monkeypatch):
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    return TestClient(appmod.app)


def test_comment_card_styles_endpoint_lists_two_styles(monkeypatch):
    response = _client(monkeypatch).get("/api/produce/comment-card/styles")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["styles"]] == ["dark_social", "premium_pop"]


def test_comment_card_preview_returns_real_png(monkeypatch):
    response = _client(monkeypatch).get(
        "/api/produce/comment-card.png",
        params={"spec": json.dumps({"style": "premium_pop", "author": "로또", "text": "이거 진짜 좋네요"}, ensure_ascii=False)},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.mode == "RGBA"
        assert image.width == 920


def test_comment_avatar_upload_requires_existing_job(monkeypatch):
    image = Image.new("RGB", (20, 20), "red")
    raw = io.BytesIO()
    image.save(raw, "PNG")
    response = _client(monkeypatch).post(
        "/api/produce/mix/comment-avatar",
        data={"job_id": "missing"},
        files={"file": ("avatar.png", raw.getvalue(), "image/png")},
    )
    assert response.status_code == 404
