"""영상 즐겨찾기(collection.html) — 플랫폼 배지 + 메타 없는 카드 재수집 버튼
(2026-07-21 사장님 요청: "어떤 플랫폼인지 표시하고, 팔로워·조회수 안 뜨는 건 재수집").

- 배지: URL로 플랫폼 판별(youtube/tiktok/instagram/xiaohongshu/douyin) — _grab_platform과 동일 도메인.
- 재수집: 보강메타(m)가 없는 카드에 버튼 → POST /api/mix/basket/reprobe → _enrich_grab 재실행.
"""
import pathlib

from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store

COLLECTION_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "collection.html"
_U = "https://www.tiktok.com/@x/video/123"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


# ── 프론트: 플랫폼 배지 ─────────────────────────────────────────────
def test_collection_has_platform_badge_for_all_five():
    html = COLLECTION_HTML.read_text(encoding="utf-8")
    assert "function platformBadge" in html, "플랫폼 배지 함수가 없다"
    for dom in ("tiktok.com", "instagram.com", "youtu", "xiaohongshu", "douyin"):
        assert dom in html, f"플랫폼 판별에 {dom}가 없다"


def test_collection_renders_badge_in_card():
    html = COLLECTION_HTML.read_text(encoding="utf-8")
    # 카드 렌더에서 배지 함수를 실제로 호출해야 한다(정의만 하고 안 쓰면 안 뜬다).
    body = html[html.find("el.innerHTML = ITEMS.map"):]
    assert "platformBadge(" in body, "카드 렌더에서 배지를 안 그린다"


# ── 프론트: 메타 없는 카드에 재수집 버튼 ─────────────────────────────
def test_collection_has_reprobe_button_when_meta_missing():
    html = COLLECTION_HTML.read_text(encoding="utf-8")
    assert "/api/mix/basket/reprobe" in html, "재수집 호출이 없다"
    assert "reprobeMeta" in html, "재수집 함수(reprobeMeta)가 없다"
    # 메타가 있으면(metaLine 비어있지 않으면) 버튼을 안 띄운다 — 조건부여야 한다.
    body = html[html.find("el.innerHTML = ITEMS.map"):]
    assert "i.meta" in body and "reprobeMeta(" in body, "카드에서 조건부 재수집 버튼을 안 그린다"


# ── 백엔드: 재수집 엔드포인트 ───────────────────────────────────────
def test_reprobe_enriches_missing_meta(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    holder = {"v": {}}
    monkeypatch.setattr(app_module, "probe_grab_meta", lambda url: holder["v"])
    # 담기(메타 없음 — probe가 {} 반환이라 보강 안 됨)
    client.post("/api/mix/basket/toggle", json={"shortcode": "SC1", "url": _U})
    # 이제 probe가 실제 메타를 준다 → 재수집
    holder["v"] = {"views": 999, "likes": 5, "comments": 3, "ts": 1700000000}
    r = client.post("/api/mix/basket/reprobe", json={"shortcode": "SC1"})
    assert r.status_code == 200 and r.json()["ok"] is True
    items = client.get("/api/mix/basket").json()["items"]
    it = next(x for x in items if x["shortcode"] == "SC1")
    assert (it.get("meta") or {}).get("views") == 999, f"재수집으로 메타가 안 채워졌다: {it!r}"


def test_reprobe_unknown_shortcode_is_404(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/mix/basket/reprobe", json={"shortcode": "NOPE"})
    assert r.status_code == 404
