# -*- coding: utf-8 -*-
"""일레븐랩스 개인 키 배선 검증 (2026-08-24).

사장님 지시: "일레븐랩스 api를 본인들꺼에서 차감되게 해줘."

★왜 이 파일이 필요한가 — should_charge가 False라는 것은 **과금 판정**만 본 것이다.
  그 키가 실제 합성에 쓰이는지는 별개다(vmake가 테스트 146개를 통과하고도 라이브
  사용 0건이었던 이유). 여기서는 **customer_id가 tts._api_key까지 진짜 닿는지**를 본다.
  하류(synthesize_best→synthesize_tts→_api_key→keys_for)는 원래 뚫려 있었고
  synthesize_line만 안 받아서, 회원이 키를 등록해도 항상 사장님 키로 돌았다.
"""
import inspect

import pytest
from cryptography.fernet import Fernet

from shopping_shorts import keyroute, mix_pipeline, tts
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    db = str(tmp_path / "t.db")
    monkeypatch.setattr("shopping_shorts.config.DB_PATH", db, raising=False)
    return Store(db)


def test_elevenlabs_is_wired():
    """배선이 끝났으므로 WIRED에 있어야 한다 = 등록하면 포인트 면제."""
    assert keyroute.SVC_ELEVENLABS in keyroute.WIRED


def test_elevenlabs_is_personal_not_pooled():
    """★일레븐랩스는 회원이 **자기 돈으로 결제**하는 서비스다.
    공용 풀에 넣으면 남의 크레딧으로 합성하는 꼴이 된다 — 절대 POOLED에 넣지 마라."""
    assert keyroute.SVC_ELEVENLABS not in keyroute.POOLED


def test_registered_key_is_the_one_used(store, monkeypatch):
    """★핵심 — 등록한 키가 실제로 꺼내지고, 사장님 키를 섞지 않는다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님EL"])
    store.add_customer_key(7, keyroute.SVC_ELEVENLABS, "내EL키")
    keys, is_user = keyroute.keys_for(store, 7, keyroute.SVC_ELEVENLABS)
    assert keys == ["내EL키"] and is_user is True
    assert keyroute.should_charge(store, 7, keyroute.SVC_ELEVENLABS) is False


def test_unregistered_customer_still_charged(store, monkeypatch):
    """키를 안 낸 회원은 사장님 키로 돌고 포인트를 낸다."""
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님EL"])
    keys, is_user = keyroute.keys_for(store, 9, keyroute.SVC_ELEVENLABS)
    assert keys == ["사장님EL"] and is_user is False
    assert keyroute.should_charge(store, 9, keyroute.SVC_ELEVENLABS) is True


@pytest.mark.parametrize("fn", [mix_pipeline.synthesize_line,
                                mix_pipeline._synthesize_beats,
                                tts.synthesize_tts, tts._api_key])
def test_customer_id_exists_all_the_way_down(fn):
    """★사슬 어느 한 곳만 빠져도 회원 키가 조용히 무시된다."""
    assert "customer_id" in inspect.signature(fn).parameters


def test_customer_id_actually_reaches_the_key_lookup(monkeypatch, tmp_path):
    """★시그니처만 있고 안 넘기는 경우를 잡는다 — 실제로 값이 닿는지 본다."""
    seen = {}
    monkeypatch.setattr(tts, "_api_key",
                        lambda customer_id=0: seen.setdefault("cid", customer_id) and "")
    try:
        mix_pipeline.synthesize_line(
            "테스트", str(tmp_path / "o.mp3"),
            voice={"voice_id": "v", "settings": None, "speed": 1.0,
                   "silence_trim": "off", "naturalize_profile": None,
                   "model_id": "eleven_multilingual_v2"},
            customer_id=42)
    except Exception:      # noqa: BLE001 — 키가 빈 문자열이라 합성 자체는 실패해도 된다
        pass
    assert seen.get("cid") == 42


def test_render_path_passes_the_job_owner():
    """★렌더 호출부가 job의 주인을 넘기는지 — 소스에서 확인한다.
    (여기가 빠지면 영상 만들기만 사장님 키로 돌아 조용히 비용이 샌다)"""
    import pathlib
    src = pathlib.Path(mix_pipeline.__file__).read_text(encoding="utf-8")
    calls = [ln for ln in src.splitlines() if "_synthesize_beats(plan" in ln]
    assert calls, "렌더 호출부를 못 찾았다 — 이름이 바뀌었으면 이 테스트를 고쳐라"
    # 각 호출은 다음 두 줄 안에 customer_id를 넘겨야 한다
    for ln in calls:
        i = src.splitlines().index(ln)
        block = "\n".join(src.splitlines()[i:i + 3])
        assert "customer_id" in block, f"주인을 안 넘기는 호출부: {ln.strip()}"
