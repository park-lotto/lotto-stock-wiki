"""템플릿 목록 API — 화면이 카드를 그릴 재료를 준다."""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod

client = TestClient(app_mod.app)


def test_list_returns_twelve():
    r = client.get("/api/produce/templates")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert len(d["templates"]) == 12


def test_each_item_has_what_the_card_needs():
    items = client.get("/api/produce/templates").json()["templates"]
    for t in items:
        assert t["id"] and t["name"]
        assert t["url"].startswith("/templates/")
        assert t["url"].endswith(".png")


def test_png_actually_served():
    """목록에 있는데 파일이 없으면 카드가 깨진 이미지로 뜬다."""
    first = client.get("/api/produce/templates").json()["templates"][0]
    r = client.get(first["url"])
    assert r.status_code == 200
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n", "PNG가 아니다"


def test_every_template_url_resolves():
    """12개 전부 실제로 받아진다 — 하나라도 깨지면 그 카드만 조용히 빈다."""
    items = client.get("/api/produce/templates").json()["templates"]
    bad = []
    for t in items:
        if client.get(t["url"]).status_code != 200:
            bad.append(t["id"])
    assert not bad, f"이 템플릿들의 PNG를 못 받는다: {bad}"


def test_ids_match_metadata_source():
    """API가 메타를 그대로 흘리는가(따로 적으면 언젠가 어긋난다 — 0순위-B)."""
    from shopping_shorts import deco_templates
    api_ids = [t["id"] for t in client.get("/api/produce/templates").json()["templates"]]
    assert api_ids == [t["id"] for t in deco_templates.TEMPLATES]
