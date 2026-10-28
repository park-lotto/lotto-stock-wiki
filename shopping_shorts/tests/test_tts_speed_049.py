# -*- coding: utf-8 -*-
"""관제 049 (2026-10-01) — TTS 속도·통째 합성 규칙을 못박는다.

사장님 청취 확정: 미나 1.35 · 그 외 전부 1.25 / 일레븐 API 1.0 통째 합성 + atempo /
0.15초 넘는 쉼만 줄임(-40dB) / "음" 추임새 없음 / 기존 고객 저장 속도도 새 값으로.
뿌리: 문장마다 따로 합성해 이어 붙이면 마디마디 끊긴다(황선희님 job 0875d89db254).
"""
import json

from shopping_shorts import mix_pipeline, tts_joined, typecast_tts, voice_presets
from shopping_shorts.store import Store

MINA = "aiUUgjHa4mpHf6UenZuf"


def test_기본속도_미나는_135_나머지는_125():
    assert voice_presets.default_speed(MINA) == 1.35
    assert voice_presets.default_speed("tc_68257f68bc6e3c161ab5078d") == 1.25   # 필재
    assert voice_presets.default_speed("아무거나") == 1.25
    assert voice_presets.default_speed(None) == 1.25


def test_기본_성우들이_주인함수를_따른다():
    assert mix_pipeline._DEFAULT_VOICE["speed"] == voice_presets.default_speed(mix_pipeline._DEFAULT_VOICE["voice_id"])
    tv = typecast_tts.TYPECAST_DEFAULT_VOICE
    assert tv["speed"] == voice_presets.default_speed(tv["voice_id"])


def test_큐레이션_파일도_같은_값이다():
    for p in voice_presets.load_presets_file():
        assert p["default_speed"] == voice_presets.default_speed(p["base_voice_id"]), p["preset_id"]


def test_시드가_라이브러리_성우_속도까지_맞춘다(tmp_path):
    """라이브러리·클론 성우는 JSON에 없고 DB에만 있다 — 시드가 안 맞추면 옛 1.6이 영영 남는다."""
    s = Store(tmp_path / "t.db")
    s.upsert_voice_preset({"preset_id": "lib-x-stable", "name": "x", "base_voice_id": "LIBX",
                           "default_speed": 1.6, "origin": "library"})
    s.upsert_voice_preset({"preset_id": "lib-mina-stable", "name": "m", "base_voice_id": MINA,
                           "default_speed": 1.6, "origin": "library"})
    voice_presets.seed_presets(s)
    assert s.get_voice_preset("lib-x-stable")["default_speed"] == 1.25
    assert s.get_voice_preset("lib-mina-stable")["default_speed"] == 1.35


def test_고객기억과_작업속도를_새값으로_바꾼다(tmp_path):
    s = Store(tmp_path / "t.db")
    cid = s.create_customer("u049", "pw")
    s.set_last_voice(cid, {"voice_id": MINA, "speed": 1.6, "preset_id": "kr-mina-stable"})
    s.set_last_voice(0, {"voice_id": "tc_68257f68bc6e3c161ab5078d", "speed": 1.2})
    s.create_mix_job("j049", ["u"], 25, "free", customer_id=cid)
    s.update_mix_job("j049", voice={"voice_id": "OTHER", "speed": 1.46})
    preview = s.rewrite_voice_speeds(voice_presets.default_speed, apply=False)
    assert {(k, new) for k, _i, _v, _o, new in preview} == {("customer", 1.35), ("owner_pref", 1.25), ("job", 1.25)}
    # 미리보기는 아무것도 안 쓴다
    assert json.loads(json.dumps(s.get_mix_job("j049")["voice"]))["speed"] == 1.46
    s.rewrite_voice_speeds(voice_presets.default_speed, apply=True)
    assert s.get_mix_job("j049")["voice"]["speed"] == 1.25
    assert s.get_pref("last_voice", 0)["speed"] == 1.25
    assert s.rewrite_voice_speeds(voice_presets.default_speed, apply=False) == []   # 다시 돌리면 0건


def test_통째합성은_기본으로_켜지고_0으로_끈다(monkeypatch):
    monkeypatch.delenv("TTS_JOINED", raising=False)
    assert tts_joined.enabled() is True
    monkeypatch.setenv("TTS_JOINED", "0")
    assert tts_joined.enabled() is False


def test_추임새는_항상_꺼진다():
    for opener in (None, True, False):
        assert mix_pipeline.line_profile(None, None, hook_opener=opener)["fillers"]["on"] is False


def test_추임새를_꺼도_호출자_프리셋을_오염시키지_않는다():
    prof = {"fillers": {"on": True, "intensity": 0.2}}
    mix_pipeline.line_profile(prof, None, hook_opener=True)
    assert prof["fillers"]["on"] is True


def test_합성글은_원문_그대로_숫자읽기와_발음교정만():
    """사장님이 고른 샘플은 원문 그대로 보낸 소리였다 — 태그·…·추임새·어미치환을 넣지 않는다."""
    from shopping_shorts.narration_naturalize import naturalize
    prof = mix_pipeline.line_profile(None, None)
    for stage in ("spoken_style", "phrasing", "endings", "fillers", "emotion_arc", "conclusion", "intonation", "whisper"):
        assert prof[stage]["on"] is False, stage
    assert prof["normalize"]["on"] is True and prof["pronunciation"]["on"] is True
    out = naturalize("이건 바로 사과 껍질 제거기", prof, beat_role="훅", beat_index=0, beat_total=5)
    assert "…" not in out and "[" not in out, out


def test_속삭임톤을_고른_스냅샷은_속삭임을_남긴다():
    prof = mix_pipeline.line_profile({"whisper": {"on": True, "roles": ["훅"]}}, None)
    assert prof["whisper"]["on"] is True


def test_오독이_같으면_짧은_후보를_고른다(tmp_path, monkeypatch):
    """필재 job 14882edcb67a: 오독 0 동점에서 4.49초(늘어진) take가 2.64초 take를 이겼다."""
    from shopping_shorts import tts, audio_post
    lens = {"_0": 4.49, "_1": 2.64}
    monkeypatch.setattr(tts, "synthesize_tts", lambda text, p, **k: open(p, "wb").write(p.encode()) and p)
    monkeypatch.setattr(tts.tts_timestamps, "copy", lambda a, b: None)
    monkeypatch.setattr(audio_post, "_audio_dur", lambda p: lens["_0" if p.endswith("_0.mp3") else "_1"])
    out = tmp_path / "b.mp3"
    tts.synthesize_best("t", str(out), n=2, base_seed=1, ranker=lambda p, t: 0)
    assert out.read_bytes().endswith(b"_1.mp3")


def test_성우저장에_속도가_안오면_성우_기본값(tmp_path):
    """2026-09-29 20:09 서버 내부 호출이 속도 없이 미나를 저장 → 사장님 기억이 1.0으로 덮였다."""
    from shopping_shorts import app
    s = Store(tmp_path / "t.db")
    snap = app._voice_snapshot(s, {"voice_id": MINA})
    assert snap["speed"] == 1.35 and snap["silence_trim"] == "mid"
    assert app._voice_snapshot(s, {"voice_id": "tc_x"})["speed"] == 1.25
    assert app._voice_snapshot(s, {"voice_id": MINA, "speed": 1.1})["speed"] == 1.1     # 보낸 값은 그대로
