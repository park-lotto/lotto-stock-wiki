# -*- coding: utf-8 -*-
"""관제 266 ④ — render_bench 목소리도 회원 팩 provider·감정을 따른다(합성 분기 주인 preset_make.make_synth · 캐시 열쇠 narr_align.voice_key).
옛 길(타입캐스트 tc_·미나 kr-, 감정 없음)은 열쇠·합성 모두 옛 그대로여야 한다(받아 둔 캐시 재과금 금지). 진짜 합성은 부르지 않는다(가짜로 바꿔 끼움)."""
from __future__ import annotations

import json

import pytest

from tools.calcopy.engine import narr_align as NA
from tools.calcopy.engine import preset_make as PM
from tools.calcopy.hybrid import render_itssum as RI
from tools.calcopy.hybrid.common import StageError

TC = "tc_6059dad0b83880769a50502f"


@pytest.fixture
def fake(monkeypatch):
    calls = []
    from shopping_shorts import typecast_tts
    from shopping_shorts.channelkit import providers

    def tc(text, out, **kw):
        calls.append(("typecast", kw.get("voice_id"), kw.get("emotion")))
        open(out, "wb").write(b"\0" * 2000)
        return {"characters": list(text), "character_start_times_seconds": [0.0] * len(text), "character_end_times_seconds": [0.1] * len(text)}

    def ms(prov, voice, tempo, emo):
        def go(text, out):
            calls.append((prov, voice, emo))
            open(out, "wb").write(b"\0" * 2000)
        return go
    monkeypatch.setattr(typecast_tts, "synthesize", tc)
    monkeypatch.setattr(providers, "typecast_key", lambda *a: "k")
    monkeypatch.setattr(PM, "make_synth", ms)
    monkeypatch.setattr(NA, "_proc_slots", lambda: [])
    return calls


def test_old_path_keeps_old_key_and_typecast_call(tmp_path, fake):
    out = tmp_path / "a.mp3"
    NA.synth_cached("안녕하세요", TC, 1.1, out, log=lambda *_: None)
    assert fake == [("typecast", TC, None)]
    assert json.loads(NA.sidecar_of(out).read_text(encoding="utf-8"))["key"] == NA.cache_key("안녕하세요", TC, 1.1)   # 옛 열쇠 그대로
    NA.synth_cached("안녕하세요", TC, 1.1, out, log=lambda *_: None, provider="typecast", emotion="normal")              # 명시 typecast·normal = 옛 캐시 적중
    assert len(fake) == 1


def test_emotion_new_key_and_timestamps_endpoint(tmp_path, fake):
    out = tmp_path / "b.mp3"
    a = NA.synth_cached("안녕하세요", TC, 1.1, out, log=lambda *_: None, emotion="happy")
    assert fake == [("typecast", TC, "happy")] and a and len(a["characters"]) == 5            # 감정도 글자 시각 유지(타임스탬프 엔드포인트)
    assert json.loads(NA.sidecar_of(out).read_text(encoding="utf-8"))["key"] != NA.cache_key("안녕하세요", TC, 1.1)


def test_fish_and_searched_eleven_go_make_synth(tmp_path, fake):
    NA.synth_cached("가나", "fs-abc", None, tmp_path / "c.mp3", log=lambda *_: None, provider="fish")
    NA.synth_cached("가나", "AbCdEfGhIjKlMnOpQrSt", None, tmp_path / "d.mp3", log=lambda *_: None, provider="elevenlabs")
    assert fake == [("fish", "fs-abc", None), ("elevenlabs", "AbCdEfGhIjKlMnOpQrSt", None)]


def test_voice_args_from_script_and_check():
    assert RI.voice_args({"voice": {"voice_id": TC}}) == {}
    assert RI.voice_args({"voice": {"voice_id": TC, "provider": "typecast", "emotion": "happy"}}, check=True) == {"provider": "typecast", "emotion": "happy"}
    with pytest.raises(StageError):
        RI.voice_args({"voice": {"voice_id": "kr-mina-expressive", "provider": "elevenlabs", "emotion": "happy"}}, check=True)   # 감정은 타입캐스트만
