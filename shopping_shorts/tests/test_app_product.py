"""쿠팡 연결 상품 저장/조회 API(2026-07-28) — 승인 전 수동 흐름 배선."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts import coupang_partners
from shopping_shorts.store import Store

_PRODUCT_URL = "https://www.coupang.com/vp/products/1234567890?itemId=9&searchId=drop"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "retype_mix_job", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _plan(target="실리콘 집게"):
    return {"structure": "free", "detected_type": "product_reveal", "affiliate_target": target,
            "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                       "alternates": [], "effect": "cut"}],
            "plagiarism_flags": []}


def _ready(store, jid, target="실리콘 집게"):
    store.create_mix_job(jid, ["u0"], 20, "free")
    store.update_mix_job(jid, status="ready_for_review", edit_plan=_plan(target))


def test_result_exposes_search_url_when_no_product_yet(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j1")
    body = client.get("/api/mix/result/j1").json()
    assert body["product"] is None
    assert body["coupang_search_url"].startswith("https://www.coupang.com/np/search")
    assert body["partners_link_page"]


def test_save_product_then_result_and_get_return_it(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j2")

    r = client.post("/api/mix/product", json={
        "job_id": "j2", "url": _PRODUCT_URL, "name": "실리콘 다용도 집게", "keyword": "실리콘 집게"})
    assert r.status_code == 200
    saved = r.json()["product"]
    assert saved["product_id"] == "1234567890"
    assert "searchId" not in saved["url"]          # 추적 파라미터 제거

    # 편집안 검토 화면을 다시 열어도 그대로 보인다
    assert client.get("/api/mix/result/j2").json()["product"]["name"] == "실리콘 다용도 집게"
    # SEO 설명란·최종렌더가 꺼내 쓰는 경로
    got = client.get("/api/mix/product/j2").json()
    assert got["final_link"] == saved["url"]
    assert coupang_partners.DISCLOSURE in got["description_block"]


def test_partner_url_becomes_final_link(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j3")
    client.post("/api/mix/product", json={
        "job_id": "j3", "url": _PRODUCT_URL, "partner_url": "https://link.coupang.com/a/qQ"})
    assert client.get("/api/mix/product/j3").json()["final_link"] == "https://link.coupang.com/a/qQ"


def test_invalid_url_rejected_and_nothing_saved(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j4")
    r = client.post("/api/mix/product", json={"job_id": "j4", "url": "https://example.com/x"})
    assert r.status_code == 422
    assert client.get("/api/mix/product/j4").json()["product"] is None


def test_unknown_job_is_404(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.post("/api/mix/product", json={"job_id": "nope", "url": _PRODUCT_URL}).status_code == 404
    assert client.get("/api/mix/product/nope").status_code == 404


def test_inpock_flag_survives_link_edit(monkeypatch, tmp_path):
    """링크만 고쳤을 때 '등록 완료'가 풀리면 사장님이 인포크에 중복 등록한다."""
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j5")
    client.post("/api/mix/product", json={"job_id": "j5", "url": _PRODUCT_URL})
    client.post("/api/mix/product", json={"job_id": "j5", "url": _PRODUCT_URL,
                                          "inpock_registered": True})
    r = client.post("/api/mix/product", json={
        "job_id": "j5", "url": _PRODUCT_URL, "partner_url": "https://link.coupang.com/a/zz"})
    assert r.json()["product"]["inpock_registered"] is True


def test_clear_product(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j6")
    client.post("/api/mix/product", json={"job_id": "j6", "url": _PRODUCT_URL})
    assert client.post("/api/mix/product", json={"job_id": "j6", "clear": True}).json()["product"] is None
    assert store.get_mix_job("j6")["product"] is None


def test_product_survives_other_job_updates(monkeypatch, tmp_path):
    """렌더 진행 등으로 update_mix_job이 돌아도 상품이 날아가면 안 된다."""
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j7")
    client.post("/api/mix/product", json={"job_id": "j7", "url": _PRODUCT_URL})
    store.update_mix_job("j7", status="done", video_path="/tmp/x.mp4")
    assert store.get_mix_job("j7")["product"]["product_id"] == "1234567890"
