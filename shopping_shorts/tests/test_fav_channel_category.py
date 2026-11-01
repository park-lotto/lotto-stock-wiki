"""나만의 채널 분류 (관제 261, 사장님 2026-10-24 "폰에서 채널 담을 때 분류 버튼 한 번, 지금은 나만").

잠그는 계약:
  1. 처음 열면 기본 분류 9개가 깔리고, '기타'는 목록에 없다(분류 안 한 채널 = 기타)
  2. 분류 버튼 순서 = 최근에 쓴 것 먼저
  3. 없는 이름으로 옮기면 새 분류가 생긴다(사장님이 직접 추가) — 같은 이름은 한 번만
  4. '기타'로 옮기면 분류가 풀린다. 채널을 빼면 분류 행도 같이 지워진다
  5. 분류는 관리자만 — 회원 목록·공유 응답엔 cats 가 없다(회원 화면 변화 0), 회원이 API를 부르면 거절
  6. 폰 공유로 채널을 담으면 응답에 분류 버튼 재료(cats·지금 분류)가 실린다(관리자만)
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def test_defaults_and_etc(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    names = s.fav_cat_names(customer_id=0)
    assert names == list(Store.FAV_CAT_DEFAULTS) and len(names) == 9
    assert "기타" not in names
    assert s.fav_cat_names(customer_id=0) == names          # 두 번 불러도 안 늘어난다


def test_recent_first_new_and_etc(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.fav_channel_add("youtube", "a", customer_id=0, cap=100)
    s.fav_channel_add("youtube", "b", customer_id=0, cap=100)
    assert s.fav_cat_set("youtube", "a", "샤크탱크", customer_id=0) == "샤크탱크"
    assert s.fav_cat_names(customer_id=0)[0] == "샤크탱크"
    assert s.fav_cat_set("youtube", "b", " 썰  쇼핑2 ", customer_id=0) == "썰 쇼핑2"   # 새 분류
    names = s.fav_cat_names(customer_id=0)
    assert names[:2] == ["썰 쇼핑2", "샤크탱크"] and names.count("썰 쇼핑2") == 1
    assert s.fav_cat_add("썰 쇼핑2", customer_id=0) == "썰 쇼핑2"
    assert s.fav_cat_names(customer_id=0).count("썰 쇼핑2") == 1
    assert s.fav_cat_add("기타", customer_id=0) == "기타" and "기타" not in s.fav_cat_names(customer_id=0)
    assert s.fav_cat_of(customer_id=0) == {("youtube", "a"): "샤크탱크", ("youtube", "b"): "썰 쇼핑2"}
    assert s.fav_cat_set("youtube", "a", "기타", customer_id=0) == "기타"
    assert ("youtube", "a") not in s.fav_cat_of(customer_id=0)
    s.fav_channel_remove("youtube", "b", customer_id=0)
    assert s.fav_cat_of(customer_id=0) == {}


def _client(tmp_path, monkeypatch, cid, admin):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "_verify_session", lambda tok: cid)
    monkeypatch.setattr(appmod, "_cid", lambda request: cid)
    monkeypatch.setattr(appmod, "_is_admin", lambda c: admin)
    return TestClient(appmod.app), Store(db)


def test_admin_api_flow(tmp_path, monkeypatch):
    c, s = _client(tmp_path, monkeypatch, 0, True)
    s.fav_channel_add("instagram", "show_gom", customer_id=0, cap=100)
    d = c.get("/api/fav_channel/list").json()
    assert d["cats"][0] == "연예인제품" and d["etc"] == "기타"
    assert d["items"][0]["category"] == "기타"
    d = c.post("/api/fav_channel/set_cat", json={"platform": "instagram", "channel_id": "show_gom",
                                                  "category": "해외화장품"}).json()
    assert d["ok"] and d["category"] == "해외화장품" and d["cats"][0] == "해외화장품"
    assert d["cats_fixed"] == list(Store.FAV_CAT_DEFAULTS)    # 목록 탭 순서는 안 바뀐다
    assert c.get("/api/fav_channel/list").json()["items"][0]["category"] == "해외화장품"
    d = c.post("/api/fav_channel/cats/add", json={"name": "틱톡밈"}).json()
    assert d["ok"] and "틱톡밈" in d["cats"]
    d = c.post("/api/fav_channel/set_cat", json={"platform": "instagram", "channel_id": "nope",
                                                  "category": "썰쇼핑"}).json()
    assert not d["ok"]                                       # 안 담긴 채널은 분류 못 한다


def test_share_channel_returns_cat_buttons(tmp_path, monkeypatch):
    c, s = _client(tmp_path, monkeypatch, 0, True)
    d = c.post("/api/share", json={"url": "https://www.instagram.com/home.and_joy?igsh=a",
                                   "dest": "channel"}).json()
    assert d["ok"] and d["channel_id"] == "home.and_joy"
    assert d["cats"] == list(Store.FAV_CAT_DEFAULTS) and d["category"] == "기타"


def test_member_sees_nothing_new(tmp_path, monkeypatch):
    c, s = _client(tmp_path, monkeypatch, 7, False)
    s.fav_channel_add("instagram", "x1", customer_id=7)
    d = c.get("/api/fav_channel/list").json()
    assert "cats" not in d and "category" not in d["items"][0]
    d = c.post("/api/share", json={"url": "https://www.instagram.com/home.and_joy",
                                   "dest": "channel"}).json()
    assert d["ok"] and "cats" not in d
    assert not c.post("/api/fav_channel/set_cat", json={"platform": "instagram", "channel_id": "x1",
                                                         "category": "썰쇼핑"}).json().get("ok")
    assert not c.post("/api/fav_channel/cats/add", json={"name": "a"}).json().get("ok")
