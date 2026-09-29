# -*- coding: utf-8 -*-
"""대본 영어모드 변환(2026-09-29 사장님 "한국어 대본 뽑고 영어모드로 변환만 되게", 관제 029).

지키는 것: 줄 수 계약(장면 배정이 문장 순서에 묶여 있다) · 원문 보관과 되돌리기 · 한글 잔존 거부 ·
영어 문장은 한국어 다듬기(naturalize)를 건너뛴다 · 영어모드에선 타입캐스트 성우 금지 · API가 자막 메타를 지운다.
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


def test_apply_lang_en_keeps_original_and_ko_restores():
    plan = {"beats": [{"beat_idx": i, "narration": t, "caption_lines": ["a"], "cap_durs": [1]} for i, t in enumerate(KO)]}
    n = script_translate.apply_lang(plan, "en", call=_fake(EN))
    assert n == 3 and plan["lang"] == "en"
    assert [b["narration"] for b in plan["beats"]] == EN
    assert [b["narration_ko"] for b in plan["beats"]] == KO
    # 영어 상태에서 다시 en → 원문(narration_ko)을 재료로 쓰고 결과가 같으면 바뀐 수 0
    assert script_translate.apply_lang(plan, "en", call=_fake(EN)) == 0
    n = script_translate.apply_lang(plan, "ko")
    assert n == 3 and plan["lang"] == "ko"
    assert [b["narration"] for b in plan["beats"]] == KO


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


def test_api_lang_en_translates_and_clears_caption_meta(client):
    c, st = client
    r = c.post("/api/mix/lang", json={"job_id": "J1", "lang": "en"})
    assert r.status_code == 200, r.text
    d = r.json(); assert d["lang"] == "en" and d["changed"] == 3 and d["narrations"] == EN
    plan = st.get_mix_job("J1")["edit_plan"]
    assert plan["lang"] == "en"
    for b in plan["beats"]:
        assert "caption_lines" not in b or not b.get("caption_lines")
        assert not b.get("cap_durs")
    r = c.post("/api/mix/lang", json={"job_id": "J1", "lang": "ko"})
    assert r.status_code == 200 and r.json()["narrations"] == KO


def test_api_lang_rejects_other_customers_job(client, monkeypatch):
    c, st = client
    import time
    cid2 = st.create_customer("en2", "pw12")
    other = TestClient(appmod.app, cookies={"dash_auth": appmod._sign_session(cid2, int(time.time()) + 3600)})
    r = other.post("/api/mix/lang", json={"job_id": "J1", "lang": "en"})
    assert r.status_code == 403


def test_lang_voice_block_only_in_english_mode():
    job_en = {"edit_plan": {"lang": "en"}}
    assert appmod._lang_voice_block(job_en, {"model_id": "ssfm-v30"}) is not None
    assert appmod._lang_voice_block(job_en, {"model_id": "eleven_v3"}) is None
    assert appmod._lang_voice_block({"edit_plan": {"lang": "ko"}}, {"model_id": "ssfm-v30"}) is None


def test_short_latin_tokens_still_get_korean_naturalize():
    """'AI'·'3.5kg' 같은 짧은 영문 토큰은 문장이 아니다 — 발음 사전·숫자 읽기가 계속 돌아야 한다(게이트가 잡은 회귀)."""
    assert not script_translate.is_english_sentence("AI")
    assert not script_translate.is_english_sentence("3.5kg")
    assert script_translate.is_english_sentence(EN[0])
    p = {"pronunciation": {"on": True, "dict": {"AI": "에이아이"}}, "fillers": {"on": False}, "emotion_arc": {"on": False}}
    assert narration_naturalize.naturalize("AI", p) == "에이아이"
