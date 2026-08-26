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


# ── 상품 확정 UI가 8단계(SEO)로 이사(2026-08-18) ────────────────────────────
# 그 화면은 무거운 /api/mix/result 대신 이 가벼운 경로로 검색어·검색URL까지 받는다.

def test_product_get_exposes_target_and_search_url(monkeypatch, tmp_path):
    """SEO 단계가 상품 확정 폼을 그리려면 검색어(affiliate_target)가 필요하다."""
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j8", target="실리콘 집게")
    got = client.get("/api/mix/product/j8").json()
    assert got["affiliate_target"] == "실리콘 집게"
    assert got["coupang_search_url"].startswith("https://www.coupang.com/np/search")
    # /api/mix/result와 같은 값이어야 한다 — 검색URL 규칙이 두 곳에서 갈라지면 안 된다(0순위-B)
    assert got["coupang_search_url"] == client.get("/api/mix/result/j8").json()["coupang_search_url"]


def test_product_get_works_before_edit_plan_exists(monkeypatch, tmp_path):
    """★매칭 전에도 200이어야 한다. /api/mix/result는 이 상태에서 404라서 못 쓴다 —
    그게 이 필드를 여기로 옮긴 이유다. 검색어는 빈 문자열이고 화면은 폼을 그린다."""
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("j9", ["u0"], 20, "free")      # edit_plan 없음
    assert client.get("/api/mix/result/j9").status_code == 404
    got = client.get("/api/mix/product/j9")
    assert got.status_code == 200
    assert got.json()["affiliate_target"] == ""


def test_product_get_keeps_inpock_keys(monkeypatch, tmp_path):
    """인포크 등록 화면(9단계)이 읽는 key를 이사 과정에서 깨뜨리지 않았는지 못 박는다."""
    client, store = _client(monkeypatch, tmp_path)
    _ready(store, "j10")
    got = client.get("/api/mix/product/j10").json()
    for key in ("ok", "product", "final_link", "description_block",
                "partners_link_page", "inpock_page"):
        assert key in got, key


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


# ── 상품 찾기(크롤) 엔드포인트(2026-07-29) ──

def test_coupang_search_endpoint_returns_items(monkeypatch, tmp_path):
    """화면 카드가 쓰는 계약 — items가 그대로 통과한다."""
    from shopping_shorts import coupang_search
    monkeypatch.setattr(coupang_search, "search", lambda q, limit=None: {
        "ok": True, "items": [{"product_id": "1", "name": "집게", "url": _PRODUCT_URL,
                               "image": "", "price": "9,900원", "rating": "(3)",
                               "rocket": True, "is_ad": False}],
        "search_url": "https://www.coupang.com/np/search?q=x", "source": "crawl", "notice": ""})
    client, _ = _client(monkeypatch, tmp_path)
    d = client.get("/api/coupang/search", params={"q": "실리콘 집게"}).json()
    assert d["ok"] is True and d["items"][0]["price"] == "9,900원"


def test_coupang_search_failure_is_200_not_500(monkeypatch, tmp_path):
    """★크롤이 막혀도 200 + ok:False다 — 화면이 수동 붙여넣기로 조용히 되돌아가야 한다."""
    from shopping_shorts import coupang_search
    monkeypatch.setattr(coupang_search, "search", lambda q, limit=None: {
        "ok": False, "items": [], "search_url": "https://www.coupang.com/np/search?q=x",
        "source": "crawl", "notice": "쿠팡이 이 IP를 막았습니다"})
    client, _ = _client(monkeypatch, tmp_path)
    r = client.get("/api/coupang/search", params={"q": "실리콘 집게"})
    assert r.status_code == 200
    assert r.json()["ok"] is False and r.json()["notice"]
