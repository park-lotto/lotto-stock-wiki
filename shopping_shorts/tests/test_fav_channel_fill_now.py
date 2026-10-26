"""나만의 채널 사진 — 담는 즉시 채우기 (관제 278, 사장님 2026-10-27 "앞으로 넣을 때도 다 들어가게").

잠그는 계약:
  1. 담기 입구 둘(_fav_channel_register = PC 버튼·폰 공유 / /api/fav_channel/add = 화면 붙여넣기)이
     담은 직후 그 채널 사진을 채운다 — 화면을 다시 여는 갱신을 기다리지 않는다
  2. 이미 사진이 있는 채널은 다시 조회하지 않는다
  3. 화면 열 때 갱신은 사진이 빈 채널부터 한다(오래된 순이면 새 채널이 맨 뒤)
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store

AV = "https://yt3.googleusercontent.com/avatar=s900"


def _setup(tmp_path, monkeypatch, calls):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)

    def probe(platform, channel_id, url=""):
        calls.append(channel_id)
        return {"avatar": AV + "/" + channel_id, "name": "이름 " + channel_id}
    monkeypatch.setattr(appmod, "_fav_channel_probe", probe)
    return db


def _drain():
    """뒤에서 도는 채우기가 끝날 때까지 기다린다(풀에 빈 작업을 넣고 그 결과를 기다림)."""
    for _ in range(3):
        appmod._FAV_FILL_POOL.submit(lambda: None).result(timeout=10)


def _avatar(db, chid, cid=0):
    return next(i for i in Store(db).fav_channel_list(customer_id=cid) if i["channel_id"] == chid)["avatar"]


def test_register_fills_avatar_right_away(tmp_path, monkeypatch):
    calls = []
    db = _setup(tmp_path, monkeypatch, calls)
    r = appmod._fav_channel_register(0, "https://www.youtube.com/@newchan")
    assert r["status"] == "added"
    _drain()
    assert _avatar(db, "newchan") == AV + "/newchan"


def test_paste_add_fills_avatar_right_away(tmp_path, monkeypatch):
    calls = []
    db = _setup(tmp_path, monkeypatch, calls)
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    r = TestClient(appmod.app).post("/api/fav_channel/add",
                                    json={"url": "https://www.youtube.com/@pasted"}).json()
    assert r["ok"] and r["added"]
    _drain()
    assert _avatar(db, "pasted") == AV + "/pasted"


def test_existing_avatar_not_probed_again(tmp_path, monkeypatch):
    calls = []
    db = _setup(tmp_path, monkeypatch, calls)
    Store(db).fav_channel_add("youtube", "hasone", avatar="https://x/old", customer_id=0, cap=0)
    appmod._fav_channel_register(0, "https://www.youtube.com/@hasone")
    _drain()
    assert calls == [] and _avatar(db, "hasone") == "https://x/old"


def test_refresh_empty_avatar_first(tmp_path, monkeypatch):
    calls = []
    db = _setup(tmp_path, monkeypatch, calls)
    s = Store(db)
    for i in range(5):                                   # 오래된 채널 5개(사진 있음, 갱신 만료)
        s.fav_channel_add("youtube", f"old{i}", avatar="https://x/a", customer_id=0, cap=0)
    s.fav_channel_add("youtube", "fresh", customer_id=0, cap=0)   # 맨 뒤에 담긴 사진 없는 채널
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    TestClient(appmod.app).post("/api/fav_channel/refresh")
    assert calls[0] == "fresh" and len(calls) == 3       # 한 번에 3개 — 빈 채널이 첫째
