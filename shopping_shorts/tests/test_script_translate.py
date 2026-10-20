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
    # 화면 "예상 초"가 영어 계수로 계산되게 같이 준다(한국어 계수로 나누면 두 배 — 2026-09-29 사장님 제보)
    from shopping_shorts import edit_plan
    assert r.json()["cps_en"] == edit_plan.speech_cps(lang="en", norm=True) > edit_plan.speech_cps(lang="ko") * 1.5


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


def test_speech_cps_is_language_aware_and_narr_secs_uses_it():
    """영어 문장은 영어 계수 — 같은 뜻의 영어(글자 2.5배)가 한국어보다 2배 길게 잡히지 않는다."""
    from shopping_shorts import edit_plan
    ko = "전력으로 달려도 귀에서 절대 안 떨어진다고 러너들 사이에서 난리가 났다는데"
    en = "Runners are going crazy because you just hook them on and they won't fall off even in a full sprint"
    assert edit_plan.speech_cps(lang="ko") == edit_plan._SYLLABLES_PER_SEC * edit_plan._speech_speed()
    assert edit_plan.speech_cps(text=en) == edit_plan.speech_cps(lang="en") == edit_plan._EN_RAW_CHARS_PER_SEC
    assert edit_plan.speech_cps(lang="en", norm=True) == edit_plan._EN_CHARS_PER_SEC < edit_plan._EN_RAW_CHARS_PER_SEC
    assert edit_plan.speech_cps(text=ko) == edit_plan.speech_cps(lang="ko")
    # 실측(2026-09-29 라이브, 같은 뜻 영어/한국어): 영어 5.0초·한국어 5.3초 — 추정은 ±25% 안에서 실제를 따라간다
    assert 4.0 <= edit_plan.narr_secs(en) <= 6.3 and 4.0 <= edit_plan.narr_secs(ko) <= 6.6


# ── 일본어모드(2026-10-21 관제 248) ─────────────────────────────────────────
JA = ["ダイソーに行ったら、これだけは絶対に買ってください。", "値段も安いのに使い道が多すぎます。", "今すぐチェックしてみてください。"]


def test_lang_of_table():
    lo = script_translate.lang_of
    assert lo(KO[0]) == "ko"
    assert lo(EN[0]) == "en"
    assert lo(JA[0]) == "ja"
    assert lo("AI") == "ko"                # 짧은 영문 토큰은 문장이 아니다
    assert lo("") == "ko" and lo(None) == "ko"
    assert lo("カタカナ") == "ja" and lo("漢字") == "ja"
    assert lo("가격 1980円") == "ko"        # 한글이 있으면 한국어가 이긴다


def test_lang_of_yen_is_ja():
    assert script_translate.lang_of("1980円") == "ja"


def test_translate_ja_keeps_line_count_and_order():
    assert script_translate.translate(KO, "ja", call=_fake(JA)) == JA


def test_translate_ja_rejects_line_without_kana_or_kanji():
    bad = list(JA); bad[1] = "Very cheap and useful"
    with pytest.raises(ValueError) as e:
        script_translate.translate(KO, "ja", call=_fake(bad), tries=1)
    assert "일본어가 아니에요" in str(e.value) and "일본어 변환에 실패" in str(e.value)


def test_translate_ja_rejects_leftover_hangul():
    bad = list(JA); bad[0] = "ダイソー 가면 買って"
    with pytest.raises(ValueError) as e:
        script_translate.translate(KO, "ja", call=_fake(bad), tries=1)
    assert "한글" in str(e.value)


def test_translate_ja_prompt_is_japanese_prompt():
    seen = []
    script_translate.translate(KO, "ja", call=lambda p, s: seen.append(p) or {"lines": list(JA)})
    assert "Japanese" in seen[0] and "です・ます" in seen[0]


def test_translate_already_japanese_not_translated_again():
    calls = []
    out = script_translate.translate(JA, "ja", call=lambda p, s: calls.append(1) or {"lines": ["x"] * 3})
    assert out == JA and calls == []


def test_translate_rejects_unknown_lang():
    with pytest.raises(ValueError):
        script_translate.translate(KO, "zh", call=_fake(JA))


def test_job_lang_ja():
    assert script_translate.job_lang({"given_script": "\n".join(JA)}) == "ja"
    assert script_translate.job_lang({"edit_plan": {"lang": "ja"}, "given_script": "\n".join(KO)}) == "ja"
    assert script_translate.job_lang({"given_script": "\n".join(KO)}) == "ko"


def test_naturalize_skips_korean_stages_for_japanese():
    out = narration_naturalize.naturalize_detail(JA[0], {"spoken_style": {"on": True, "intensity": 1.0}})
    assert out["text"] == JA[0] and out["applied"] == {}


def test_lang_voice_block_japanese_mode():
    job_ja = {"given_script": "\n".join(JA), "edit_plan": {}}
    r = appmod._lang_voice_block(job_ja, {"model_id": "ssfm-v30"})
    assert r is not None and r.status_code == 422 and "일본어모드" in r.body.decode("utf-8")
    from shopping_shorts import fish_tts
    fish_id = fish_tts._MODEL_PREFIX + "s1"
    assert fish_tts.is_fish(fish_id)
    r2 = appmod._lang_voice_block(job_ja, {"model_id": fish_id})
    assert r2 is not None and r2.status_code == 422 and "일본어모드" in r2.body.decode("utf-8")
    assert appmod._lang_voice_block(job_ja, {"model_id": "eleven_v3"}) is None


def test_speech_cps_japanese():
    from shopping_shorts import edit_plan
    assert edit_plan.speech_cps(lang="ja", norm=True) == edit_plan._JA_CHARS_PER_SEC == 6.8
    assert edit_plan.speech_cps(lang="ja") == edit_plan._JA_RAW_CHARS_PER_SEC == 7.4
    assert edit_plan.speech_cps(text=JA[0]) == edit_plan._JA_RAW_CHARS_PER_SEC
    assert edit_plan.speech_cps(text=JA[0], norm=True) == edit_plan._JA_CHARS_PER_SEC


def test_asr_language():
    al = script_translate.asr_language
    assert al(JA[0]) == "ja" and al(EN[0]) == "en" and al(KO[0]) == "ko" and al("") == "ko"


def test_caption_tokens():
    ct = script_translate.caption_tokens
    assert ct("値段、安い。") == ["値", "段", "安", "い"]
    assert ct(KO[0]) == KO[0].split()
    assert ct(EN[0]) == EN[0].split()
    assert ct("") == [] and ct(None) == []


def test_foreign_helpers():
    assert script_translate.is_japanese(JA[0]) and not script_translate.is_japanese(KO[0])
    assert script_translate.is_foreign_sentence(JA[0]) and script_translate.is_foreign_sentence(EN[0])
    assert not script_translate.is_foreign_sentence(KO[0])
    assert script_translate.foreign_ratio(JA + KO[:1], "ja") == 0.75
    assert script_translate.LANG_LABEL == {"en": "영어", "ja": "일본어", "ko": "한국어"}


def test_api_script_translate_ja(client, monkeypatch):
    c, st = client
    st.add_customer_key(c.cid, "elevenlabs", "EL")
    monkeypatch.setattr(script_translate.script_generate, "_call_json", lambda p, s: {"lines": list(JA)})
    r = c.post("/api/script/translate", json={"lines": KO, "lang": "ja"})
    assert r.status_code == 200, r.text
    d = r.json()
    from shopping_shorts import edit_plan
    assert d["lines"] == JA and d["lang"] == "ja" and d["cps"] == edit_plan.speech_cps(lang="ja", norm=True)
    assert "cps_en" not in d


def test_api_script_translate_en_keeps_cps_en(client):
    c, st = client
    st.add_customer_key(c.cid, "elevenlabs", "EL")
    d = c.post("/api/script/translate", json={"lines": KO}).json()
    assert d["lang"] == "en" and d["cps"] == d["cps_en"]


def test_api_script_translate_rejects_unknown_lang(client):
    c, st = client
    st.add_customer_key(c.cid, "elevenlabs", "EL")
    r = c.post("/api/script/translate", json={"lines": KO, "lang": "xx"})
    assert r.status_code == 422 and r.json()["error"] == "지원하지 않는 언어예요"
