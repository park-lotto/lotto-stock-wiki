"""쿠팡 검색 릴레이 — 대기열·엔드포인트 계약.

브라우저도 서버도 없이 돈다: 큐는 순수 파이썬이고, 릴레이 역할은 스레드로 흉내낸다."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import config, coupang_relay

TOKEN = "t-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "COUPANG_SEARCH_MODE", "relay")
    monkeypatch.setattr(config, "COUPANG_RELAY_TOKEN", TOKEN)
    monkeypatch.setattr(config, "COUPANG_RELAY_WAIT_SEC", 3)
    monkeypatch.setattr(coupang_relay, "QUEUE", coupang_relay.RelayQueue())
    return TestClient(app_module.app)


def test_queue_roundtrip():
    """일감을 넣고 → 릴레이가 가져가 → 답을 꽂으면, 기다리던 쪽이 그 답을 받는다."""
    q = coupang_relay.RelayQueue()

    def relay():
        job = q.take(3)
        q.complete(job.id, {"ok": True, "items": [{"product_id": "1"}]})

    threading.Thread(target=relay, daemon=True).start()
    got = q.submit("집게", 10, timeout=5)
    assert got["items"][0]["product_id"] == "1"


def test_queue_timeout_when_no_relay():
    """릴레이가 없으면(PC 꺼짐) 기다리다 None — 화면은 수동 흐름으로 돌아간다."""
    q = coupang_relay.RelayQueue()
    t = time.monotonic()
    assert q.submit("집게", 10, timeout=0.4) is None
    assert time.monotonic() - t < 3          # 무한대기 금지
    # 흔적도 남지 않는다 — 늦게 켠 릴레이가 유령 일감을 집어가면 안 된다.
    assert q.status()["waiting"] == 0


def test_take_returns_none_without_work():
    assert coupang_relay.RelayQueue().take(0.2) is None


def test_complete_unknown_id_is_false():
    """이미 타임아웃으로 접힌 요청에 답이 와도 조용히 False — 예외로 릴레이를 죽이지 않는다."""
    assert coupang_relay.RelayQueue().complete("nope", {"ok": True}) is False


def test_relay_endpoints_require_token(client):
    assert client.get("/api/coupang/relay/next", params={"token": "wrong"}).status_code == 403
    assert client.post("/api/coupang/relay/result",
                       json={"token": "wrong", "id": "x"}).status_code == 403


def test_relay_closed_when_token_unset(monkeypatch, client):
    """★토큰이 비면 아무나 검색결과를 밀어넣을 수 있다 — 그래서 아예 닫는다."""
    monkeypatch.setattr(config, "COUPANG_RELAY_TOKEN", "")
    assert client.get("/api/coupang/relay/next", params={"token": ""}).status_code == 403


def test_search_in_relay_mode_uses_relay(client):
    """/api/coupang/search가 릴레이 답을 그대로 화면에 흘려준다."""
    def relay():
        for _ in range(60):
            d = client.get("/api/coupang/relay/next",
                           params={"token": TOKEN, "wait": 1}).json()
            if d.get("job"):
                client.post("/api/coupang/relay/result", json={
                    "token": TOKEN, "id": d["job"]["id"], "ok": True,
                    "items": [{"product_id": "77", "name": "집게", "price": "9,900원"}]})
                return

    th = threading.Thread(target=relay, daemon=True)
    th.start()
    d = client.get("/api/coupang/search", params={"q": "집게"}).json()
    th.join(timeout=5)
    assert d["ok"] is True and d["source"] == "relay"
    assert d["items"][0]["product_id"] == "77"


def test_search_relay_offline_falls_back_to_manual(client):
    """릴레이가 안 떠 있으면 500이 아니라 200 + 안내 + 검색링크(수동 흐름 보존)."""
    r = client.get("/api/coupang/search", params={"q": "집게"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and d["items"] == []
    assert d["search_url"].startswith("https://www.coupang.com/np/search?q=")
    assert "PC" in d["notice"]


def test_relay_status_hides_token(client):
    d = client.get("/api/coupang/relay/status").json()
    assert d["mode"] == "relay" and d["configured"] is True
    assert TOKEN not in str(d)


def test_relay_paths_bypass_login_gate(client, monkeypatch):
    """★릴레이는 로그인 쿠키가 없다 — 로그인 게이트에 걸리면 도우미가 일감을 못 받는다.

    (토큰 검사는 엔드포인트 안에서 하므로 게이트를 열어도 안전하다: 틀린 토큰은 403.)"""
    r = client.get("/api/coupang/relay/next", params={"token": TOKEN, "wait": 1})
    assert r.status_code != 401, "로그인 게이트가 릴레이를 막고 있다"
    r2 = client.get("/api/coupang/relay/status")
    assert r2.status_code != 401
