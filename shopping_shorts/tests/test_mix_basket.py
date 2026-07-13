"""영상 믹싱 바구니(mix basket) — store 토글/목록/삭제 + API 엔드포인트."""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    return TestClient(appmod.app)


# --- store 레벨 ---
def test_toggle_adds_then_removes(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    assert st.mix_basket_toggle("AAA", url="u1") is True      # 추가
    assert st.mix_basket_shortcodes() == {"AAA"}
    assert st.mix_basket_toggle("AAA") is False               # 다시 누르면 제거
    assert st.mix_basket_shortcodes() == set()


def test_list_keeps_add_order(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    for sc in ("A", "B", "C"):
        st.mix_basket_toggle(sc, url="u" + sc)
    order = [it["shortcode"] for it in st.mix_basket_list()]
    assert order == ["A", "B", "C"]


def test_remove(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.mix_basket_toggle("A", url="u")
    st.mix_basket_remove("A")
    assert st.mix_basket_shortcodes() == set()


# --- API 레벨 ---
def test_api_toggle_and_list(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/mix/basket/toggle",
               json={"shortcode": "X1", "url": "https://insta/x1", "name": "채널A"})
    assert r.status_code == 200
    j = r.json()
    assert j["in"] is True and j["count"] == 1

    lst = c.get("/api/mix/basket").json()
    assert lst["items"][0]["shortcode"] == "X1"
    assert lst["items"][0]["url"] == "https://insta/x1"
    assert "X1" in lst["shortcodes"]

    # 다시 토글 → 담기취소
    r2 = c.post("/api/mix/basket/toggle", json={"shortcode": "X1"})
    assert r2.json()["in"] is False and r2.json()["count"] == 0


def test_api_toggle_requires_shortcode(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/mix/basket/toggle", json={"url": "x"})
    assert r.status_code == 422


def test_api_remove(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    c.post("/api/mix/basket/toggle", json={"shortcode": "Z", "url": "u"})
    r = c.post("/api/mix/basket/remove", json={"shortcode": "Z"})
    assert r.status_code == 200 and r.json()["count"] == 0
    assert c.get("/api/mix/basket").json()["items"] == []
