"""레퍼런스 채널 URL 등록(2026-07-18) — 엔드포인트 + union cap 우선순위."""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.channels import merge_tracked
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    # 엔드포인트가 엑셀을 못 읽어도(로컬/서버 무엑셀) 발굴목록만으로 동작해야 한다
    monkeypatch.setattr(app_module, "load_channels", lambda: [])
    return TestClient(app_module.app), Store(db)


def test_register_extracts_username_and_saves(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/reference/register",
                    params={"url": "https://www.instagram.com/salim__mami/"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "username": "salim__mami", "already": False}
    assert store.discovered_channels()[0]["username"] == "salim__mami"


def test_register_rejects_reel_url(monkeypatch, tmp_path):
    # 릴스 URL(reel/코드)은 채널 아이디가 아니라 예약경로 → username 못 뽑음 → 422
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/reference/register",
                    params={"url": "https://www.instagram.com/reel/ABC123/"})
    assert r.status_code == 422
    assert not r.json()["ok"]
    assert "채널" in r.json()["error"]  # 프로필 주소를 넣으라는 안내


def test_register_accepts_full_profile_url_with_query(monkeypatch, tmp_path):
    # 전체 URL(www·트레일링 슬래시·쿼리스트링) 그대로 붙여넣어도 아이디만 뽑는다
    client, store = _client(monkeypatch, tmp_path)
    r = client.post("/api/reference/register",
                    params={"url": "https://www.instagram.com/home.director_/?hl=ko&igsh=abc"})
    assert r.status_code == 200
    assert r.json()["username"] == "home.director_"


def test_register_rejects_non_instagram(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/reference/register",
                    params={"url": "https://youtube.com/@someone"})
    assert r.status_code == 422
    assert "인스타" in r.json()["error"]


def test_register_duplicate_reports_already(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    store.add_discovered("dup")
    r = client.post("/api/reference/register",
                    params={"url": "https://instagram.com/dup"})
    assert r.json() == {"ok": True, "username": "dup", "already": True}
    # 중복 추가 안 됨(여전히 1개)
    assert len(store.discovered_channels()) == 1


def test_register_duplicate_against_excel(monkeypatch, tmp_path):
    # 이미 엑셀에 있는 채널이면 already=True, 발굴목록엔 안 들어간다
    client, store = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "load_channels",
                        lambda: [{"username": "excelch", "name": "", "followers": 0, "inpock": ""}])
    r = client.post("/api/reference/register",
                    params={"url": "https://instagram.com/ExcelCh"})  # 대소문자 무관
    assert r.json()["already"] is True
    assert store.discovered_channels() == []


# ── union cap 우선순위: 등록 채널은 MAX_CHANNELS를 넘겨도 살아남는다 ──
def _ch(u, followers=0):
    return {"username": u, "name": u, "followers": followers, "inpock": ""}


def test_merge_tracked_registered_survives_cap():
    # 엑셀이 cap을 꽉 채운 상황(3개, cap=3)에서 등록채널 1개가 앞에 살아남고
    # 엑셀 꼬리(마지막) 1개가 밀려난다 → 총량은 cap 유지.
    excel = [_ch("e1"), _ch("e2"), _ch("e3")]
    discovered = [_ch("mypick")]
    merged = merge_tracked(excel, discovered, removed=set(), max_channels=3)
    users = [c["username"] for c in merged]
    assert len(users) == 3
    assert "mypick" in users            # 등록채널 살아남음
    assert users[0] == "mypick"         # 앞쪽 우선
    assert "e3" not in users            # 엑셀 꼬리가 밀려남


def test_merge_tracked_dedupes_and_drops_removed():
    excel = [_ch("a"), _ch("b")]
    # a는 엑셀 중복 → fresh 아님, c는 removed → 제외
    merged = merge_tracked(excel, [_ch("A"), _ch("c")], removed={"c"}, max_channels=10)
    users = [c["username"] for c in merged]
    assert users.count("a") == 1 and "A" not in users   # 중복 dedupe
    assert "c" not in users
