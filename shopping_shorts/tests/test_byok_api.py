"""설정 API — 키가 화면으로 새지 않는지가 핵심.

★테스트 DB 격리 (2026-08-17 실측)
과제 초안은 `SHORTS_DB` 환경변수를 쓰라고 했지만 **그런 환경변수는 없다**:
config.py:23 이 `DB_PATH = Path(__file__).parent / "data" / "reference.db"` 로
하드코딩한다(`grep -rn SHORTS_DB shopping_shorts/` → 0건). 그대로 뒀으면 테스트가
조용히 **실 개발 DB에 사용자 키를 쓰고 지웠을** 것이다.
→ 이 프로젝트가 이미 쓰는 방식을 따른다: `monkeypatch.setattr(appmod, "DB_PATH", ...)`
   (test_paywall_gate.py `_setup`, test_byok_routes.py 의 config.DB_PATH 패치와 같은 결).

★app 모듈 reload도 안 쓴다. app.py는 임포트 시점에 라우트·미들웨어·전역을 세우므로
  reload는 느리고 다른 테스트의 monkeypatch와 얽힌다. DB_PATH만 갈아끼우면 충분하다
  (라우트가 매 요청 `Store(DB_PATH)`를 새로 만든다 — 실측).

★cid는 실제 로그인 세션으로 만든다. `_cid`가 0을 주면 사장님 계정이 되어
  "사용자별 키"라는 검증 자체가 무의미해진다.
"""
import importlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import keycrypt, keyroute
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)          # 마스터키를 임포트 시점에 읽으므로 reload 필요
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    store = Store(db)
    cid = store.create_customer("byok1", "pw12")        # 가입시 체험 → 유료차단 없음
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    c = TestClient(appmod.app, cookies={"dash_auth": appmod._sign_session(cid, exp)})
    c.cid, c.store = cid, store
    yield c
    importlib.reload(keycrypt)          # 다른 테스트에 마스터키가 새지 않게 되돌린다


def test_get_keys_never_returns_plaintext(client):
    """★가장 중요 — 평문이 GET으로 나가면 등록 자체가 무의미하다."""
    client.post("/api/settings/keys", json={"service": "vmake", "key": "비밀키값"})
    r = client.get("/api/settings/keys")
    assert r.status_code == 200
    assert "비밀키값" not in r.text


def test_get_keys_returns_mask(client):
    client.post("/api/settings/keys",
                json={"service": "gemini", "key": "AQ.Ab8RNxxxxxxxxxxxxxxxxxxxxkz1MA"})
    rows = client.get("/api/settings/keys").json()["keys"]
    assert any("•" in k["label"] for k in rows)


def test_add_rejects_empty(client):
    r = client.post("/api/settings/keys", json={"service": "vmake", "key": "   "})
    assert r.status_code == 422


def test_add_rejects_unknown_service(client):
    """★모르는 서비스명을 그대로 받으면 테이블에 쓰레기가 쌓인다."""
    r = client.post("/api/settings/keys", json={"service": "해킹", "key": "k"})
    assert r.status_code == 422


def test_delete(client):
    client.post("/api/settings/keys", json={"service": "vmake", "key": "지울키"})
    kid = client.get("/api/settings/keys").json()["keys"][0]["id"]
    assert client.post("/api/settings/keys/delete", json={"id": kid}).status_code == 200
    assert client.get("/api/settings/keys").json()["keys"] == []


def test_points_shows_balance_and_prices(client):
    r = client.get("/api/settings/points")
    assert r.status_code == 200
    body = r.json()
    assert "balance" in body
    assert body["prices"]["vmake"] == 5      # 화면용 값(내부 500)


def test_gemini_accepts_multiple_at_once(client):
    """구글 키는 여러 개를 한 번에 붙여넣을 수 있어야 한다."""
    r = client.post("/api/settings/keys",
                    json={"service": "gemini", "key": "k1\nk2\nk3"})
    assert r.json()["added"] == 3


def test_vmake_key_is_not_split(client):
    """★vmake는 'ak:sk' 한 덩어리다 — 콜론이나 공백으로 쪼개면 안 된다."""
    r = client.post("/api/settings/keys",
                    json={"service": "vmake", "key": "appkey:secret"})
    assert r.json()["added"] == 1


# ─────────────────────────────────────────────────────────────────────
# 아래는 과제 초안에 없던 보강 — 실제로 새는 경로가 없는지 끝까지 본다
# ─────────────────────────────────────────────────────────────────────

def test_stored_key_is_actually_usable(client):
    """★마스크만 맞고 복호가 깨지면 '등록은 됐는데 안 쓰이는' 상태가 된다.
    화면엔 평문이 없고 keyroute 경로로만 평문이 나와야 한다."""
    client.post("/api/settings/keys", json={"service": "gemini", "key": "내키AAA"})
    keys, is_user = keyroute.keys_for(client.store, client.cid, keyroute.SVC_GEMINI)
    assert keys == ["내키AAA"] and is_user is True


def test_keys_are_per_customer(client):
    """★남의 키가 내 목록에 뜨면 안 된다."""
    client.store.add_customer_key(client.cid + 999, keyroute.SVC_VMAKE, "남의키:xx")
    assert client.get("/api/settings/keys").json()["keys"] == []


def test_delete_cannot_touch_other_customers_key(client):
    """★id만 알면 남의 키가 지워지는지 — store가 cid를 조건에 넣는지 라우트에서 확인."""
    other = client.cid + 999
    client.store.add_customer_key(other, keyroute.SVC_VMAKE, "남의키:xx")
    kid = client.store.list_customer_keys(other)[0]["id"]
    client.post("/api/settings/keys/delete", json={"id": kid})
    assert len(client.store.list_customer_keys(other)) == 1      # 그대로 살아있어야 한다


def test_duplicate_key_is_not_counted_twice(client):
    """같은 키를 두 번 넣으면 added=0. store가 중복을 False로 돌려준다."""
    client.post("/api/settings/keys", json={"service": "vmake", "key": "dup:key"})
    r = client.post("/api/settings/keys", json={"service": "vmake", "key": "dup:key"})
    assert r.json()["added"] == 0
    assert len(client.get("/api/settings/keys").json()["keys"]) == 1


def test_points_history_uses_display_units(client):
    """★내부값(×100)을 그대로 보이면 5P가 500으로 뜬다."""
    client.store.points_add(client.cid, 1000, "charge")
    client.store.points_try_deduct(client.cid, 500, "vmake")
    body = client.get("/api/settings/points").json()
    assert body["balance"] == 5                       # (1000-500)/100
    assert body["history"][0]["delta"] == -5


def test_verify_marks_status_and_never_leaks_key(client, monkeypatch):
    """검증 결과가 저장되고, 응답에 평문이 안 실리는지."""
    client.post("/api/settings/keys", json={"service": "gemini", "key": "검증대상키"})
    monkeypatch.setattr(appmod, "_probe_user_key", lambda svc, key: True)
    r = client.post("/api/settings/keys/verify", json={"service": "gemini"})
    assert r.status_code == 200
    assert "검증대상키" not in r.text
    assert client.get("/api/settings/keys").json()["keys"][0]["status"] == "ok"


def test_verify_marks_bad(client, monkeypatch):
    client.post("/api/settings/keys", json={"service": "gemini", "key": "죽은키"})
    monkeypatch.setattr(appmod, "_probe_user_key", lambda svc, key: False)
    client.post("/api/settings/keys/verify", json={"service": "gemini"})
    assert client.get("/api/settings/keys").json()["keys"][0]["status"] == "bad"


def test_verify_rejects_unknown_service(client):
    r = client.post("/api/settings/keys/verify", json={"service": "해킹"})
    assert r.status_code == 422


def test_probe_vmake_checks_format_only(monkeypatch):
    """★vmake 실호출은 크레딧을 먹는다 — 형식만 본다."""
    monkeypatch.setattr(appmod.requests, "get",
                        lambda *a, **k: pytest.fail("vmake는 실호출하면 안 된다"))
    assert appmod._probe_user_key(keyroute.SVC_VMAKE, "ak:sk") is True
    assert appmod._probe_user_key(keyroute.SVC_VMAKE, "콜론없음") is False


def test_probe_gemini_uses_rest_probe(monkeypatch):
    """★SDK models.list를 쓰면 살아있는 키도 전부 죽음으로 보인다(2026-08-07).
    comment_gen._probe_key_alive(REST)를 거치는지 확인한다."""
    from shopping_shorts import comment_gen
    seen = []
    monkeypatch.setattr(comment_gen, "_probe_key_alive",
                        lambda k, **kw: (seen.append(k), True)[1])
    assert appmod._probe_user_key(keyroute.SVC_GEMINI, "k1") is True
    assert seen == ["k1"]


def test_probe_returns_false_on_network_error(monkeypatch):
    """네트워크 예외는 '검증 실패'로 판정한다 — 500으로 터지지 않는다."""
    def boom(*a, **k):
        raise appmod.requests.RequestException("no net")
    monkeypatch.setattr(appmod.requests, "get", boom)
    assert appmod._probe_user_key(keyroute.SVC_ELEVENLABS, "k") is False


def test_add_blocked_when_master_key_missing(client, monkeypatch):
    """★마스터키가 없으면 503. 평문 저장으로 조용히 폴백하면 안 된다."""
    monkeypatch.setattr(keycrypt, "enabled", lambda: False)
    r = client.post("/api/settings/keys", json={"service": "vmake", "key": "k:v"})
    assert r.status_code == 503
