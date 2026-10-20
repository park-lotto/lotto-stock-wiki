"""나만의 채널 상한 — 관리자 100 · 회원 50 (관제 225, 사장님 2026-10-18 "100개로 늘려줘 관리자만").

잠그는 계약:
  1. 누가 몇 개인지는 app._fav_channel_cap 하나가 정한다(관리자 판정은 _is_admin)
  2. store.fav_channel_add 는 받은 cap 에서 막고, 안 받으면 회원 상한(50)에서 막는다
  3. 담기 입구(_fav_channel_register = PC 버튼·폰 공유)가 관리자 상한을 쓴다
"""
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _fill(store, n, cid, cap=None):
    return [store.fav_channel_add("instagram", f"ch{i}", customer_id=cid, cap=cap) for i in range(n)]


def test_cap_numbers(monkeypatch):
    monkeypatch.setattr(appmod, "Store", Store)
    monkeypatch.setattr(Store, "get_customer", lambda self, cid: {"email": "m@x.com", "admin": 0})
    assert appmod._fav_channel_cap(0) == 100          # 사장님
    assert appmod._fav_channel_cap(7) == 50           # 일반 회원
    monkeypatch.setattr(Store, "get_customer", lambda self, cid: {"email": "m@x.com", "admin": 1})
    assert appmod._fav_channel_cap(7) == 100          # UI로 지정한 관리자


def test_store_respects_given_cap(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    r = _fill(s, 101, cid=0, cap=100)
    assert r[:100] == [True] * 100 and r[100] is None
    r = _fill(s, 51, cid=5)                           # cap 안 주면 회원 상한
    assert r[:50] == [True] * 50 and r[50] is None


def test_register_uses_admin_cap(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    _fill(Store(db), 60, cid=0, cap=100)
    r = appmod._fav_channel_register(0, "https://www.instagram.com/new_one/")
    assert r["status"] == "added" and r["cap"] == 100
