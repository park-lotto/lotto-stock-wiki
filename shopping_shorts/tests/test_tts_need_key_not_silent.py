# -*- coding: utf-8 -*-
"""키 없는 회원을 안내문으로 막은 것은 '무음 폴백'이 아니다(2026-10-02 관제 082).

★왜: 09-29부터 키 없는 회원은 무음 mp3 대신 안내문 에러로 막히는데, 막기 직전 기록이
  silent_fallback으로 남아 관리자 경보가 "고객이 무음 영상을 받았다"고 떴다.
  실측: 09-29~10-02 고객 프로세스 235건, 같은 날 완성 영상 14편 전부 -15.8~-17.5dB(무음 0편).
"""
import pytest

from shopping_shorts import api_health, keyroute, tts, typecast_tts


@pytest.fixture
def recorded(monkeypatch):
    seen = []
    monkeypatch.setattr(api_health, "record",
                        lambda service, outcome, **kw: seen.append((service, outcome)))
    monkeypatch.setattr(tts, "_api_key", lambda cid=0: "")
    monkeypatch.setattr(typecast_tts, "api_key", lambda cid=0: "")
    return seen


def _call(engine, tmp_path):
    out = str(tmp_path / "a.mp3")
    kw = dict(voice_id="v", voice_settings=None, speed=None, seed=None,
              previous_text=None, next_text=None, max_retries=1, customer_id=340)
    if engine == "typecast":
        return tts._synthesize_typecast("안녕", out, model_id="ssfm-v30", **kw), out
    kw.pop("customer_id")
    return tts.synthesize_tts("안녕", out, model_id="eleven_multilingual_v2",
                              customer_id=340, **kw), out


@pytest.mark.parametrize("engine", ["elevenlabs", "typecast"])
def test_막힌_회원은_need_own_key로_기록(recorded, monkeypatch, tmp_path, engine):
    monkeypatch.setattr(keyroute, "is_block_exempt", lambda cid: False)
    with pytest.raises(RuntimeError):
        _call(engine, tmp_path)
    assert recorded == [(engine, api_health.OUT_NEED_KEY)]
    assert api_health.OUT_NEED_KEY not in api_health.FAIL_OUTCOMES


@pytest.mark.parametrize("engine", ["elevenlabs", "typecast"])
def test_면제_회원의_진짜_무음은_그대로_silent(recorded, monkeypatch, tmp_path, engine):
    monkeypatch.setattr(keyroute, "is_block_exempt", lambda cid: True)
    monkeypatch.setattr(tts, "_write_silent_mp3", lambda p, s: open(p, "wb").close())
    _call(engine, tmp_path)
    assert recorded == [(engine, api_health.OUT_SILENT)]
