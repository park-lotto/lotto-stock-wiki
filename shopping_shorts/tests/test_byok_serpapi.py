"""렌즈 검색(SerpApi) BYOK — 등록한 키가 **실제로 쓰이는가**.

★왜 이 파일이 있나: 다른 서비스(TTS·유튜브)는 keyroute까지만 배선돼 있고
  호출부가 cid를 안 넘겨서 "저장은 되는데 안 쓰이는" 상태로 남았다
  (handoff/키등록포인트.md ⏭6번). 같은 일이 SerpApi에도 나면
  "키 등록했는데 사장님 키로 나가고 포인트도 깎이는" 최악이 된다.
  그래서 화면·저장이 아니라 **키가 어디서 나오는지**를 못 박는다.
"""
import pytest

from shopping_shorts import keyroute
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    # 키 저장은 Fernet 암호화라 마스터키가 없으면 RuntimeError로 막힌다
    # (평문 폴백 없음 = 의도된 설계). 테스트용 키를 심어준다.
    # ★_fernet은 import 시점에 한 번 만들어진다 — 환경변수를 나중에 심어도 안 먹는다.
    from cryptography.fernet import Fernet
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


def test_serpapi_is_a_known_service():
    """화이트리스트에 없으면 /api/settings/keys가 422로 등록 자체를 거부한다."""
    assert keyroute.SVC_SERPAPI == "serpapi"
    assert keyroute.SVC_SERPAPI in keyroute.SERVICES


def test_user_key_wins_and_owner_key_is_not_mixed(store, monkeypatch):
    """사용자 키가 있으면 그 키만. 사장님 키를 섞으면 폴백 없음 원칙이 깨진다."""
    monkeypatch.setattr("shopping_shorts.config.SERPAPI_KEYS", ["owner1", "owner2"],
                        raising=False)
    store.add_customer_key(7, keyroute.SVC_SERPAPI, "mine-1")

    keys, is_user = keyroute.keys_for(store, 7, keyroute.SVC_SERPAPI)
    assert is_user is True
    assert keys == ["mine-1"]
    assert "owner1" not in keys


def test_owner_keys_used_when_customer_has_none(store, monkeypatch):
    monkeypatch.setattr("shopping_shorts.config.SERPAPI_KEYS", ["owner1"], raising=False)
    keys, is_user = keyroute.keys_for(store, 7, keyroute.SVC_SERPAPI)
    assert (keys, is_user) == (["owner1"], False)


def test_charging_follows_the_serpapi_key(store, monkeypatch):
    """포인트 차감은 SerpApi 키 유무를 따라야 한다 — 화면 문구('내 키 등록하면 0P')와
    실제가 어긋나면 "등록했는데 왜 깎이냐"가 된다."""
    monkeypatch.setattr("shopping_shorts.config.SERPAPI_KEYS", ["owner1"], raising=False)
    assert keyroute.should_charge(store, 7, keyroute.SVC_SERPAPI) is True
    store.add_customer_key(7, keyroute.SVC_SERPAPI, "mine-1")
    assert keyroute.should_charge(store, 7, keyroute.SVC_SERPAPI) is False


def test_search_uses_given_keys_only(monkeypatch):
    """search_similar_videos(api_key=[...])가 정말 그 키로 나가는가.
    목록도 받아야 한다 — 사용자가 키를 여러 개 등록할 수 있다."""
    from shopping_shorts import lens_discover

    used = []

    class _Resp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"visual_matches": []}

    def _fake_get(url, params=None, timeout=None, **kw):
        used.append((params or {}).get("api_key"))
        return _Resp()

    monkeypatch.setattr(lens_discover.requests, "get", _fake_get)
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", ["owner1"], raising=False)
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", "owner1", raising=False)

    lens_discover.search_similar_videos("https://ex.com/f.jpg", api_key=["mine-1"])

    assert used, "SerpApi를 아예 안 불렀다"
    assert set(used) == {"mine-1"}, f"사장님 키가 샜다: {used}"


def test_lens_call_count_matches_the_ui_copy():
    """화면에 '검색 1번에 3회'라고 적어뒀다. 코드가 그 숫자여야 한다 —
    로케일이나 캡을 바꾸면 이 테스트가 먼저 깨져서 문구도 같이 고치게 된다."""
    from shopping_shorts import lens_discover
    assert lens_discover._MAX_CALLS_PER_SEARCH == 3
    assert len(lens_discover._LENS_LOCALES) == 3
