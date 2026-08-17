"""TTS·유튜브가 사용자 키를 집어가는지.

★"keyroute가 맞게 고른다"만 보면 배선을 못 잡는다 — tts.py·youtube_client.py가
  **실제로 keyroute를 거치는지**를 같이 본다. 예전에 캐시키·계정프록시에서
  "함수는 맞는데 호출부가 안 부른다"로 조용히 죽은 사고가 여러 번 있었다.
"""
import importlib
import pytest
from shopping_shorts import keycrypt, keyroute
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


def test_tts_uses_user_key(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님TTS"])
    store.add_customer_key(3, keyroute.SVC_ELEVENLABS, "내TTS")
    keys, is_user = keyroute.keys_for(store, 3, keyroute.SVC_ELEVENLABS)
    assert keys == ["내TTS"] and is_user is True


def test_youtube_uses_user_key(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님YT"])
    store.add_customer_key(3, keyroute.SVC_YOUTUBE, "내YT")
    keys, is_user = keyroute.keys_for(store, 3, keyroute.SVC_YOUTUBE)
    assert keys == ["내YT"] and is_user is True


def test_batch_uses_owner_keys(store, monkeypatch):
    """★크론·태거는 회사 부담이므로 cid 0으로 돌아 사장님 키를 쓴다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    keys, is_user = keyroute.keys_for(store, 0, keyroute.SVC_GEMINI)
    assert keys == ["사장님키"] and is_user is False


# ─────────────────────────────────────────────────────────────────────
# 배선 — 두 모듈이 진짜 keyroute를 거치는가
# tts._api_key / youtube_client._tokens_for 는 함수 안에서 Store(config.DB_PATH)를
# 만든다. 그래서 config.DB_PATH를 테스트 DB로 갈아끼우면 실 DB를 안 건드린다.
# ─────────────────────────────────────────────────────────────────────

def test_tts_helper_returns_user_key(store, monkeypatch):
    """★tts.py가 실제로 keyroute를 거치는지 — 배선 확인."""
    from shopping_shorts import tts
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님TTS"])
    store.add_customer_key(9, keyroute.SVC_ELEVENLABS, "내TTS키")
    monkeypatch.setattr(tts.config, "DB_PATH", store.db_path)
    assert tts._api_key(9) == "내TTS키"


def test_tts_helper_falls_back_to_owner_key(store, monkeypatch):
    """키 미등록 사용자(그리고 cid 0)는 사장님 키를 그대로 쓴다 — 기존 동작 유지."""
    from shopping_shorts import tts
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님TTS"])
    monkeypatch.setattr(tts.config, "DB_PATH", store.db_path)
    assert tts._api_key(0) == "사장님TTS"
    assert tts._api_key(9) == "사장님TTS"


def test_tts_helper_empty_when_no_key(store, monkeypatch):
    """키가 아무데도 없으면 빈 문자열 → 호출부가 무음 mock으로 내려앉는다."""
    from shopping_shorts import tts
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: [])
    monkeypatch.setattr(tts.config, "DB_PATH", store.db_path)
    assert tts._api_key(0) == ""


def test_synthesize_tts_sends_user_key_header(store, monkeypatch, tmp_path):
    """★합성 요청 헤더에 사용자 키가 실려 나가는지 — 여기까지 봐야 배선이다."""
    from shopping_shorts import tts
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님TTS"])
    store.add_customer_key(9, keyroute.SVC_ELEVENLABS, "내TTS키")
    monkeypatch.setattr(tts.config, "DB_PATH", store.db_path)
    monkeypatch.setattr(tts.config, "ELEVENLABS_TIMESTAMPS", False)

    seen = {}

    class R:
        content = b"mp3"

        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["key"] = (headers or {}).get("xi-api-key")
        return R()

    monkeypatch.setattr(tts.requests, "post", fake_post)
    tts.synthesize_tts("안녕", str(tmp_path / "a.mp3"), customer_id=9)
    assert seen["key"] == "내TTS키"


def test_synthesize_tts_mocks_when_no_key_anywhere(store, monkeypatch, tmp_path):
    """★기존 동작 유지: 키가 없으면 무음 mock. 사용자 키 경유로 바꿔도 안 깨진다."""
    from shopping_shorts import tts
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: [])
    monkeypatch.setattr(tts.config, "DB_PATH", store.db_path)
    called = {}
    monkeypatch.setattr(tts, "_write_silent_mp3",
                        lambda p, s: called.setdefault("mock", True))
    monkeypatch.setattr(tts.requests, "post",
                        lambda *a, **k: pytest.fail("키 없는데 API를 불렀다"))
    out = str(tmp_path / "m.mp3")
    assert tts.synthesize_tts("안녕", out) == out
    assert called.get("mock") is True


def test_youtube_helper_returns_user_key(store, monkeypatch):
    """★youtube_client._tokens_for가 사용자 키를 집는지."""
    from shopping_shorts import youtube_client
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님YT"])
    store.add_customer_key(9, keyroute.SVC_YOUTUBE, "내YT키")
    monkeypatch.setattr(youtube_client.config, "DB_PATH", store.db_path)
    assert youtube_client._tokens_for(9) == ["내YT키"]


def test_youtube_helper_falls_back_to_owner_keys(store, monkeypatch):
    """cid 0(크론·발굴)은 사장님 풀 그대로 — 기존 로테이션이 안 바뀐다."""
    from shopping_shorts import youtube_client
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["K1", "K2"])
    monkeypatch.setattr(youtube_client.config, "DB_PATH", store.db_path)
    assert youtube_client._tokens_for(0) == ["K1", "K2"]


def test_search_shorts_uses_user_key(store, monkeypatch):
    """★search_shorts가 사용자 키로 검색하는지 — 실제 요청 토큰을 본다."""
    from shopping_shorts import youtube_client as yc
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님YT"])
    store.add_customer_key(9, keyroute.SVC_YOUTUBE, "내YT키")
    monkeypatch.setattr(yc.config, "DB_PATH", store.db_path)

    used = []
    monkeypatch.setattr(yc, "_search_page",
                        lambda kw, after, n, tok, region="KR", lang="ko":
                        (used.append(tok), (200, []))[1])
    monkeypatch.setattr(yc, "_stats", lambda ids, tok: {})
    yc.search_shorts(["살림꿀팁"], "2026-08-01T00:00:00Z", customer_id=9)
    assert used == ["내YT키"]


def test_search_shorts_explicit_token_wins(store, monkeypatch):
    """token= 을 명시하면 그 토큰만 — 기존 계약 유지(호출부 여러 곳이 이걸 쓴다)."""
    from shopping_shorts import youtube_client as yc
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님YT"])
    store.add_customer_key(9, keyroute.SVC_YOUTUBE, "내YT키")
    monkeypatch.setattr(yc.config, "DB_PATH", store.db_path)

    used = []
    monkeypatch.setattr(yc, "_search_page",
                        lambda kw, after, n, tok, region="KR", lang="ko":
                        (used.append(tok), (200, []))[1])
    monkeypatch.setattr(yc, "_stats", lambda ids, tok: {})
    yc.search_shorts(["살림꿀팁"], "2026-08-01T00:00:00Z", token="ONLY", customer_id=9)
    assert used == ["ONLY"]
