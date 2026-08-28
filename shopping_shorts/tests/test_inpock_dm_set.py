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


def test_dm_set_needs_a_name():
    """이름이 없으면 만들지 않는다 — 만들 게 없다."""
    assert coupang_partners.dm_set(1, "") is None
    assert coupang_partners.dm_set(None, None) is None


def test_dm_set_without_number_is_blank(number=""):
    """★번호는 비워둘 수 있다(2026-08-28 사장님 "번호는 공란으로 표시해줘").

    전엔 전역 카운터로 자동 부여했는데 그 카운터를 **전 고객이 공유**해서 내 두 번째
    영상이 29번을 받았다(실측: cid174=30·cid110=29·cid201=28). 자동 부여를 걷어낸
    지금, 번호를 넣기 전까지는 번호 없는 문구를 보여준다.
    """
    d = coupang_partners.dm_set("", "미니 듀얼 세탁건조기")
    assert d is not None
    assert d["number"] == ""
    assert d["listing_name"] == "미니 듀얼 세탁건조기"     # 앞에 "N. "이 안 붙는다
    assert d["dm_title"] == "미니 듀얼 세탁건조기"
    assert d["dm_button"] == "✅ 제품 확인하기"            # "N번 검색"이 없다
    assert d["dm_desc"] == coupang_partners.DISCLOSURE


def test_dm_set_squashes_whitespace():
    d = coupang_partners.dm_set(7, "  미니   세탁기\n건조기 ")
    assert d["listing_name"] == "7. 미니 세탁기 건조기"


# ── API 배선 ────────────────────────────────────────────────

def test_save_leaves_number_blank(monkeypatch, tmp_path):
    """★저장해도 번호를 **자동으로 붙이지 않는다**(2026-08-28 정책 변경).

    전엔 next_number(settings 전역 카운터)로 붙였는데, settings는 key가 PK라 계정
    축이 없어(store.py:1072) 전 고객이 카운터 하나를 나눠 썼다. 고객 눈에는
    "무작위로 29번"으로 보였다. 이제 사람이 넣는다.
    """
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    r = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "미니 듀얼 세탁건조기",
        "partner_url": _PARTNER})
    body = r.json()
    assert body["ok"] is True
    assert body["product"]["inpock_number"] == ""            # 공란
    assert body["dm_set"]["listing_name"] == "미니 듀얼 세탁건조기"


def test_number_is_set_by_hand(monkeypatch, tmp_path):
    """번호를 보내면 그대로 쓴다 — 화면의 '번호 저장' 버튼이 이 경로다."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    r = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER,
        "inpock_number": "29"})
    assert r.json()["product"]["inpock_number"] == "29"
    assert r.json()["dm_set"]["listing_name"] == "29. 상품"
    assert "29번 검색" in r.json()["dm_set"]["dm_button"]


def test_number_can_be_changed_and_cleared(monkeypatch, tmp_path):
    """★한 번 넣은 번호도 고치고 지울 수 있다.

    전엔 prev가 body보다 먼저라 한 번 붙은 번호를 영영 못 고쳤다 — 자동 부여가
    엉뚱한 번호를 줬을 때 손쓸 방법이 없었던 이유다.
    """
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    base = {"job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER}
    client.post("/api/mix/product", json=dict(base, inpock_number="29"))
    got = client.post("/api/mix/product", json=dict(base, inpock_number="7"))
    assert got.json()["product"]["inpock_number"] == "7"      # 고쳐진다
    cleared = client.post("/api/mix/product", json=dict(base, inpock_number=""))
    assert cleared.json()["product"]["inpock_number"] == ""   # 비울 수도 있다
    assert cleared.json()["dm_set"]["listing_name"] == "상품"


def test_number_survives_edits_that_do_not_touch_it(monkeypatch, tmp_path):
    """번호를 안 보내는 저장(링크만 고치기)은 기존 번호를 건드리지 않는다."""
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    base = {"job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER}
    client.post("/api/mix/product", json=dict(base, inpock_number="29"))
    again = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품(이름 고침)",
        "partner_url": "https://link.coupang.com/re/AFF?lptag=NEW"})
    assert again.json()["product"]["inpock_number"] == "29"   # 그대로
    assert again.json()["dm_set"]["listing_name"] == "29. 상품(이름 고침)"


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


def test_clear_drops_the_number(monkeypatch, tmp_path):
    """해제하면 번호도 같이 없어진다 — 자동 부여를 걷어낸 뒤의 동작(2026-08-28).

    전엔 여기서 '다음 번호(2)'를 새로 받았다. 이제 번호를 주는 곳은 사람뿐이라,
    해제 후 다시 저장하면 공란에서 시작한다.
    """
    client, store = _client(monkeypatch, tmp_path)
    _job(store)
    client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER,
        "inpock_number": "29"})
    client.post("/api/mix/product", json={"job_id": "j1", "clear": True})
    d = client.post("/api/mix/product", json={
        "job_id": "j1", "url": _URL, "name": "상품", "partner_url": _PARTNER}).json()
    assert d["product"]["inpock_number"] == ""
