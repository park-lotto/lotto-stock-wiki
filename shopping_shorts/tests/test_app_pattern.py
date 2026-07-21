"""부품은행 큐레이션 API(app.py T3) 통합 테스트.

Gemini 실호출 금지 — pattern_bank.extract_buckets를 가짜로 monkeypatch해
ingest_script가 그 결과를 그대로 부품은행에 담게 한다.
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_mod
from shopping_shorts import pattern_bank
from shopping_shorts.store import Store


_FAKE_BUCKETS = {
    "hook": ["이거 진짜 대박이에요", "3초만 보고 가세요"],
    "ending": ["해보세요", "써보세요"],
    "cta": ["프로필 링크 확인"],
    "evidence": ["{인물}이 {행위}하더니 {반응}"],
}


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    Store(db)  # 스키마 생성
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    # AI 회피: 대본과 무관하게 고정 버킷을 반환한다.
    monkeypatch.setattr(pattern_bank, "extract_buckets", lambda *a, **k: dict(_FAKE_BUCKETS))
    return TestClient(app_mod.app), Store(db)


def test_ingest_creates_source_and_items(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/pattern/ingest",
                    json={"full_text": "잘 팔린 대본 전문", "product_category": "기미크림"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["source_id"] is not None
    # 2 hook + 2 ending + 1 cta + 1 evidence = 6
    assert body["added"] == 6
    # store에 실제로 담겼나
    assert len(store.list_pattern_items(bucket="hook")) == 2
    ev = store.list_pattern_items(bucket="evidence")
    assert len(ev) == 1 and ev[0]["slot_role"] == "template"


def test_ingest_requires_full_text(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/pattern/ingest", json={"full_text": "   "})
    assert r.status_code == 422


def test_items_list_and_order(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    client.post("/api/pattern/ingest", json={"full_text": "대본"})
    r = client.get("/api/pattern/items?bucket=hook&order=recent")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert all(it["bucket"] == "hook" for it in items)


def test_status_approve_reflected(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    client.post("/api/pattern/ingest", json={"full_text": "대본"})
    item_id = store.list_pattern_items(bucket="hook")[0]["id"]
    r = client.post("/api/pattern/item/status", json={"id": item_id, "status": "approved"})
    assert r.json()["ok"] is True
    # 재조회로 반영 확인
    got = [i for i in client.get("/api/pattern/items?bucket=hook").json()["items"] if i["id"] == item_id]
    assert got and got[0]["status"] == "approved"


def test_item_edit(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    client.post("/api/pattern/ingest", json={"full_text": "대본"})
    item_id = store.list_pattern_items(bucket="cta")[0]["id"]
    r = client.post("/api/pattern/item/edit",
                    json={"id": item_id, "text": "교정된 문구", "note": "메모"})
    assert r.json()["ok"] is True
    got = store.list_pattern_items(bucket="cta")[0]
    assert got["text"] == "교정된 문구" and got["note"] == "메모"


def test_buckets_counts(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    client.post("/api/pattern/ingest", json={"full_text": "대본"})
    counts = client.get("/api/pattern/buckets").json()["counts"]
    # 8버킷 전부 존재(빈 것도 0으로)
    assert set(counts.keys()) >= {"hook", "ending", "cta", "evidence", "adverb",
                                  "price", "conflict", "emotion"}
    assert counts["hook"]["pending"] == 2
    # approve 후 카운트 이동
    from shopping_shorts.config import DB_PATH as _  # noqa
    item_id = Store(app_mod.DB_PATH).list_pattern_items(bucket="hook")[0]["id"]
    client.post("/api/pattern/item/status", json={"id": item_id, "status": "approved"})
    counts2 = client.get("/api/pattern/buckets").json()["counts"]
    assert counts2["hook"]["approved"] == 1
    assert counts2["hook"]["pending"] == 1


def test_ingest_empty_extract_zero(monkeypatch, tmp_path):
    """extract가 {}면(무키/실패) source 없이 added=0, 200."""
    client, _ = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(pattern_bank, "extract_buckets", lambda *a, **k: {})
    r = client.post("/api/pattern/ingest", json={"full_text": "대본"})
    assert r.status_code == 200
    assert r.json()["added"] == 0 and r.json()["source_id"] is None


def test_spine_add_and_list(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/pattern/spine", json={
        "name": "무기력→반전", "situation_type": "before_after",
        "beat_chain": ["고민", "발견", "반전"], "emotion_arc": "답답→후련"})
    assert r.json()["ok"] is True and r.json()["id"]
    spines = client.get("/api/pattern/spines").json()["spines"]
    assert len(spines) == 1 and spines[0]["name"] == "무기력→반전"
    assert spines[0]["beat_chain"] == ["고민", "발견", "반전"]


def test_spine_requires_name(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/pattern/spine", json={"situation_type": "x"})
    assert r.status_code == 422
