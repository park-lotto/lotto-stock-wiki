# -*- coding: utf-8 -*-
"""타입캐스트 키를 못 쓰는 회원의 기본 성우가 타입캐스트면 일레븐 기본 성우로(2026-09-29 사장님).

관리자 키 차단(09-29) 뒤 배승훈(580)·최소연(134) 등 기본 성우가 타입캐스트로 기억된 회원이 3단계 TTS에서
막혀 5단계(성우 바꾸기)에 못 갔다. 판단은 typecast_tts.use_fallback 한 곳, 갈아끼우는 자리는 store.get_last_voice(성우 시드의 유일한 출구).
"""
import importlib

import pytest

from shopping_shorts import keycrypt, keyroute, typecast_tts
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="
TC = {"preset_id": "tc-changsu-stable", "voice_id": "tc_6059dad0b83", "model_id": "ssfm-v30", "settings": {}}
EL = {"preset_id": "el-x", "voice_id": "abc123", "model_id": "eleven_v3", "settings": {}}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님TC"])
    monkeypatch.setattr(typecast_tts, "enabled", lambda: True)
    from shopping_shorts import config
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "DB_PATH", db)
    return Store(db)


def test_member_without_typecast_key_but_with_eleven_key_gets_eleven_default(store):
    cid = store.create_customer("u1", "pw12")
    store.add_customer_key(cid, keyroute.SVC_ELEVENLABS, "EL")
    store.set_last_voice(cid, TC)
    assert store.get_last_voice(cid) == typecast_tts.FALLBACK_VOICE


def test_member_without_any_voice_key_is_not_switched(store):
    """일레븐 유료 키가 없으면 대체하지 않는다 — 관문이 '키 등록' 안내로 막고, 사장님 키로 가지 않는다."""
    cid = store.create_customer("u0", "pw12")
    store.set_last_voice(cid, TC)
    assert store.get_last_voice(cid)["preset_id"] == "tc-changsu-stable"
    assert keyroute.keys_for(store, cid, keyroute.SVC_ELEVENLABS) == ([], False)
    assert keyroute.keys_for(store, cid, keyroute.SVC_TYPECAST) == ([], False)


def test_member_with_typecast_key_keeps_typecast(store):
    cid = store.create_customer("u2", "pw12")
    store.add_customer_key(cid, keyroute.SVC_TYPECAST, "TC")
    store.set_last_voice(cid, TC)
    assert store.get_last_voice(cid)["preset_id"] == "tc-changsu-stable"


def test_eleven_memory_untouched(store):
    cid = store.create_customer("u3", "pw12")
    store.set_last_voice(cid, EL)
    assert store.get_last_voice(cid)["preset_id"] == "el-x"


def test_exempt_member_keeps_typecast(store):
    """면제 명단(회사 키 사용)은 그대로 타입캐스트."""
    ex = sorted(keyroute.BLOCK_EXEMPT_CIDS)[0]
    store._conn().execute("INSERT OR IGNORE INTO customers(id,username,password_hash,salt,created_at) VALUES(?,?,?,?,?)", (ex, "ex", "h", "s", "t")).connection.commit()
    store.set_last_voice(ex, TC)
    assert (store.get_last_voice(ex) or {}).get("preset_id") == "tc-changsu-stable"


def test_use_fallback_without_customer_unchanged():
    assert typecast_tts.use_fallback("ssfm-v30") is False or not typecast_tts.enabled()
    assert typecast_tts.use_fallback("eleven_v3", 7) is False
