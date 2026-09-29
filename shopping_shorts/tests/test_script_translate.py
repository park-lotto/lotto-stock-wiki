# -*- coding: utf-8 -*-
"""대본 영어모드 변환(2026-09-29 사장님 "한국어 대본 뽑고 영어모드로 변환만 되게", 관제 029).

지키는 것: 줄 수 계약(장면 배정이 문장 순서에 묶여 있다) · 원문 보관과 되돌리기 · 한글 잔존 거부 ·
영어 문장은 한국어 다듬기(naturalize)를 건너뛴다 · 영어모드(given_script 영어)에선 타입캐스트 성우 금지 · /api/script/translate 줄 수 계약.
"""
import importlib

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import narration_naturalize, script_translate
from shopping_shorts import app as appmod
from shopping_shorts import keycrypt
from shopping_shorts.store import Store

KO = ["여러분 다이소 가시면 이건 무조건 담으세요", "가격도 착한데 활용도가 미쳤어요", "지금 바로 확인해 보세요"]
EN = ["If you go to Daiso, you have to grab this.", "It's cheap and insanely useful.", "Go check it out right now."]


def _fake(lines_out):
    return lambda prompt, schema: {"lines": list(lines_out)}


def test_to_english_keeps_line_count_and_order():
    assert script_translate.to_english(KO, call=_fake(EN)) == EN


def test_line_count_mismatch_is_rejected_not_trimmed():
    with pytest.raises(ValueError) as e:
        script_translate.to_english(KO, call=_fake(EN[:2]), tries=1)
    assert "줄 수" in str(e.value)


def test_leftover_hangul_is_rejected():
    bad = list(EN); bad[1] = "가격도 cheap"
    with pytest.raises(ValueError) as e:
        script_translate.to_english(KO, call=_fake(bad), tries=1)
    assert "한글" in str(e.value)


def test_empty_response_message():
    with pytest.raises(ValueError):
        script_translate.to_english(KO, call=lambda p, s: {}, tries=1)


def test_already_english_is_not_translated_again():
    calls = []
    out = script_translate.to_english(EN, call=lambda p, s: calls.append(1) or {"lines": ["x"] * 3})
    assert out == EN and calls == []


def test_job_lang_detects_from_given_script():
    assert script_translate.job_lang({"given_script": "\n".join(EN)}) == "en"
    assert script_translate.job_lang({"given_script": "\n".join(KO)}) == "ko"
    assert script_translate.job_lang({"edit_plan": {"lang": "en"}, "given_script": "\n".join(KO)}) == "en"
    assert script_translate.job_lang({}) == "ko"


def test_naturalize_skips_korean_stages_for_english():
    """spoken_style 등 한국어 단계가 영어 문장을 건드리면 안 된다."""
    out = narration_naturalize.naturalize_detail(EN[0], {"spoken_style": {"on": True, "intensity": 1.0}})
    assert out["text"] == EN[0] and out["applied"] == {}


def test_is_english():
    assert script_translate.is_english(EN[0]) and not script_translate.is_english(KO[0])
    assert not script_translate.is_english("가격도 cheap")
    assert script_translate.english_ratio(EN) == 1.0


# ── API ────────────────────────────────────────────────────────────────
_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    st = Store(db)
    cid = st.create_customer("en1", "pw12")        # 가입시 체험 → 유료차단 없음(test_byok_api와 같다)
    st.create_mix_job("J1", ["https://x/1"], 20, "template", customer_id=cid)
    st.update_mix_job("J1", edit_plan={"beats": [
        {"beat_idx": i, "narration": t, "caption_lines": ["a", "b"], "cap_durs": [1, 1], "cap_lead": 0.3}
        for i, t in enumerate(KO)]}, status="ready_for_review")
    monkeypatch.setattr(script_translate.script_generate, "_call_json", lambda p, s: {"lines": list(EN)})
    import time
    exp = int(time.time()) + 3600
    c = TestClient(appmod.app, cookies={"dash_auth": appmod._sign_session(cid, exp)})
    c.cid = cid
    return c, st


def test_api_script_translate_returns_same_count(client):
    c, st = client
    st.add_customer_key(c.cid, "elevenlabs", "EL")          # 음성 키 없는 계정은 402로 먼저 안내
    r = c.post("/api/script/translate", json={"lines": KO, "product": "젓가락"})
    assert r.status_code == 200, r.text
    assert r.json()["lines"] == EN


def test_api_script_translate_rejects_empty(client):
    c, st = client
    st.add_customer_key(c.cid, "elevenlabs", "EL")
    assert c.post("/api/script/translate", json={"lines": []}).status_code == 422


def test_lang_voice_block_only_in_english_mode():
    job_en = {"given_script": "\n".join(EN), "edit_plan": {}}
    assert appmod._lang_voice_block(job_en, {"model_id": "ssfm-v30"}) is not None
    assert appmod._lang_voice_block(job_en, {"model_id": "eleven_v3"}) is None
    assert appmod._lang_voice_block({"given_script": "\n".join(KO), "edit_plan": {}}, {"model_id": "ssfm-v30"}) is None


def test_short_latin_tokens_still_get_korean_naturalize():
    """'AI'·'3.5kg' 같은 짧은 영문 토큰은 문장이 아니다 — 발음 사전·숫자 읽기가 계속 돌아야 한다(게이트가 잡은 회귀)."""
    assert not script_translate.is_english_sentence("AI")
    assert not script_translate.is_english_sentence("3.5kg")
    assert script_translate.is_english_sentence(EN[0])
    p = {"pronunciation": {"on": True, "dict": {"AI": "에이아이"}}, "fillers": {"on": False}, "emotion_arc": {"on": False}}
    assert narration_naturalize.naturalize("AI", p) == "에이아이"
