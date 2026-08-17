"""📦 인포크 자동 DM 세트 — 번호 자동부여 + 붙여넣기 문구(2026-08-18).

사장님 실제 운영 방식(채이홈 화면으로 확인):
  DM 도착 → 인포크 페이지 검색창에 번호 입력 → 상품 클릭 → 쿠팡 상품 페이지

번호는 상품 이름 앞에 직접 붙인다(`588. 스마트 미니세탁기`). 인포크 검색이 이름을
훑으므로 그 숫자로 걸린다. 영상마다 바뀌는 건 번호·상품명뿐 — DM 버튼 URL·고지문구·
답글은 고정이라 인포크 자동화를 한 번만 세팅하면 된다.

사장님 지시: "순서를 쿠팡에서 파트너스링크를 등록하면 자동으로 받아서 해",
"8단계에서 입력완료되면", "마지막번호 다음으로 하면 되는 거야".
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import coupang_partners
from shopping_shorts.store import Store

_URL = "https://www.coupang.com/vp/products/1234567890?itemId=9"
_PARTNER = "https://link.coupang.com/re/AFF?lptag=TEST"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "retype_mix_job", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _job(store, jid="j1"):
    store.create_mix_job(jid, ["u0"], 20, "free")
    return jid


# ── 순수 함수 ────────────────────────────────────────────────

def test_next_number_counts_up():
    assert coupang_partners.next_number(588) == 589
    assert coupang_partners.next_number("588") == 589


def test_next_number_starts_at_one_when_unset():
    """처음이거나 값이 깨져 있으면 1부터 — 빈 값에 +1을 시도해 죽지 않게."""
    for bad in (None, "", "abc", 0, -3, [], {}):
        assert coupang_partners.next_number(bad) == 1


def test_dm_set_shapes_all_three_lines():
    d = coupang_partners.dm_set(588, "미니 듀얼 세탁건조기")
    assert d["listing_name"] == "588. 미니 듀얼 세탁건조기"   # 인포크 등록 이름
    assert d["dm_title"] == "(588번) 미니 듀얼 세탁건조기"     # DM 카드 타이틀
    assert "588번 검색" in d["dm_button"]                     # 버튼이 번호를 안내
    assert d["dm_desc"] == coupang_partners.DISCLOSURE        # 고지문구는 고정


def test_dm_set_needs_both_number_and_name():
    """번호나 이름이 없으면 만들지 않는다 — 반쪽 문구를 붙여넣게 하지 않는다."""
    assert coupang_partners.dm_set("", "이름") is None
    assert coupang_partners.dm_set(1, "") is None
    assert coupang_partners.dm_set(None, None) is None


def test_dm_set_squashes_whitespace():
    d = coupang_partners.dm_set(7, "  미니   세탁기\n건조기 ")
    assert d["listing_name"] == "7. 미니 세탁기 건조기"


# ── API 배선 ────────────────────────────────────────────────

def test_save_assigns_next_number_automatically(monkeypatch, tmp_path):
    """8단계에서 저장이 끝나는 순간 번호가 붙는다 — 사장님이 번호를 입력하지 않는다."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    r = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "미니 듀얼 세탁건조기",
        "partner_url": _PARTNER})
    body = r.json()
    assert body["ok"] is True
    assert body["product"]["inpock_number"] == "1"          # 처음이면 1
    assert body["dm_set"]["listing_name"] == "1. 미니 듀얼 세탁건조기"


def test_number_increments_across_jobs(monkeypatch, tmp_path):
    """다음 영상은 마지막 번호 다음을 받는다."""
    client, store = _client(monkeypatch, tmp_path)
    for jid in ("j1", "j2", "j3"):
        _job(store, jid)
        client.post("/api/mix/product", json={
            "job_id": jid, "url": _URL, "name": "상품", "partner_url": _PARTNER})
    got = [client.get(f"/api/mix/product/{j}").json()["product"]["inpock_number"]
           for j in ("j1", "j2", "j3")]
    assert got == ["1", "2", "3"]


def test_number_is_stable_across_edits(monkeypatch, tmp_path):
    """★한 번 받은 번호는 링크를 고쳐도 안 바뀐다.

    바뀌면 이미 인포크에 등록해둔 이름(`588. …`)과 어긋나 시청자가 못 찾는다.
    inpock_registered를 저장 때마다 초기화하지 않는 것과 같은 이유다.
    """
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    first = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER})
    n1 = first.json()["product"]["inpock_number"]
    again = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품(이름 고침)",
        "partner_url": "https://link.coupang.com/re/AFF?lptag=NEW"})
    assert again.json()["product"]["inpock_number"] == n1
    # 이름을 고쳤으면 문구는 따라 바뀐다(번호만 고정).
    assert again.json()["dm_set"]["listing_name"] == f"{n1}. 상품(이름 고침)"


def test_get_returns_dm_set_after_reload(monkeypatch, tmp_path):
    """새로고침해도 화면이 문구를 다시 그릴 수 있어야 한다(조회 응답에도 실린다)."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "미니 세탁기", "partner_url": _PARTNER})
    d = client.get("/api/mix/product/j1").json()
    assert d["dm_set"]["dm_title"].endswith("미니 세탁기")


def test_get_without_product_has_no_dm_set(monkeypatch, tmp_path):
    """상품이 없으면 문구도 없다 — 빈 번호로 '. ' 같은 쓰레기를 만들지 않는다."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    assert client.get("/api/mix/product/j1").json()["dm_set"] is None


def test_clear_does_not_consume_a_number(monkeypatch, tmp_path):
    """해제했다가 다시 저장하면 새 번호를 받는다 — 번호는 job이 아니라 등록에 붙는다."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER})
    client.post("/api/mix/product", json={"job_id": "j1", "clear": True})
    d = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER}).json()
    assert d["product"]["inpock_number"] == "2"
