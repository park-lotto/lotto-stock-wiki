# -*- coding: utf-8 -*-
"""타입캐스트 백엔드 배선 테스트 (2026-08-19).

지키려는 계약:
  ① 엔진 분기가 model_id 하나로 갈린다 — 일레븐랩스 프리셋은 종전 경로 그대로.
  ② 타임스탬프 변환이 우리 사이드카 형식과 맞는다(end 누락 시 자막이 조용히 강등됨).
  ③ 속도를 후처리로 **또** 당기지 않는다(이중 가속 방지).
  ④ 키가 없으면 무음 mock — 일레븐랩스 경로와 같은 계약.
"""
import json

import pytest
import requests

from shopping_shorts import tts, typecast_tts, tts_timestamps, mix_pipeline


# ── ① 엔진 분기 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("model_id,expected", [
    ("ssfm-v30", True), ("ssfm-v21", True), ("SSFM-V30", True),
    ("eleven_v3", False), ("eleven_multilingual_v2", False),
    (None, False), ("", False),
])
def test_is_typecast(model_id, expected):
    assert typecast_tts.is_typecast(model_id) is expected


def test_synthesize_tts_routes_to_typecast(monkeypatch, tmp_path):
    """model_id가 ssfm-*면 일레븐랩스를 아예 안 부른다."""
    called = {}

    def fake_synth(text, out_path, **kw):
        called.update(kw)
        called["text"] = text
        with open(out_path, "wb") as f:
            f.write(b"ID3fake")
        return {"characters": ["안"], "character_start_times_seconds": [0.0],
                "character_end_times_seconds": [0.1]}

    monkeypatch.setattr(typecast_tts, "synthesize", fake_synth)
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "k")
    # 일레븐랩스로 새면 즉시 터지게 한다
    monkeypatch.setattr(tts.requests, "post",
                        lambda *a, **k: pytest.fail("일레븐랩스로 샜다"))
    out = str(tmp_path / "a.mp3")
    assert tts.synthesize_tts("안녕", out, voice_id="tc_x", model_id="ssfm-v30") == out
    assert called["voice_id"] == "tc_x"
    assert called["text"] == "안녕"


def test_synthesize_tts_eleven_path_unchanged(monkeypatch, tmp_path):
    """일레븐랩스 프리셋은 타입캐스트를 안 탄다(회귀 방지)."""
    monkeypatch.setattr(typecast_tts, "synthesize",
                        lambda *a, **k: pytest.fail("타입캐스트로 샜다"))
    monkeypatch.setattr(tts, "_api_key", lambda cid=0: "")   # 키 없음 → 무음 mock
    out = str(tmp_path / "b.mp3")
    assert tts.synthesize_tts("안녕", out, model_id="eleven_v3") == out


# ── ② 타임스탬프 변환 ──────────────────────────────────────────────────────
def test_to_alignment_matches_our_sidecar_shape():
    """words_from_alignment가 실제로 읽을 수 있어야 한다."""
    chars = [{"text": "이", "start": 0.1, "end": 0.2},
             {"text": "거", "start": 0.2, "end": 0.3},
             {"text": " ", "start": 0.3, "end": 0.4},
             {"text": "좋", "start": 0.4, "end": 0.5}]
    al = typecast_tts.to_alignment(chars)
    words = tts_timestamps.words_from_alignment(al)
    assert [w["word"] for w in words] == ["이거", "좋"]
    assert words[0]["start"] == 0.1


def test_to_alignment_includes_end_times():
    """★end가 빠지면 words_from_alignment가 None을 반환해 자막이 조용히 ASR로 강등된다."""
    al = typecast_tts.to_alignment([{"text": "가", "start": 0.0, "end": 0.1}])
    assert "character_end_times_seconds" in al
    assert tts_timestamps.words_from_alignment(al) is not None


def test_to_alignment_bad_shape_returns_none():
    assert typecast_tts.to_alignment(None) is None
    assert typecast_tts.to_alignment([{"text": "가"}]) is None      # start/end 없음


def test_synthesize_saves_alignment_sidecar(monkeypatch, tmp_path):
    out = tmp_path / "c.mp3"
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "k")
    monkeypatch.setattr(typecast_tts, "synthesize",
                        lambda text, o, **kw: typecast_tts.to_alignment(
                            [{"text": "가", "start": 0.0, "end": 0.5}]))
    tts.synthesize_tts("가", str(out), voice_id="v", model_id="ssfm-v30")
    saved = json.loads(open(tts_timestamps.sidecar_path(str(out)), encoding="utf-8").read())
    assert saved["characters"] == ["가"]


# ── ③ 이중 가속 방지 ───────────────────────────────────────────────────────
def test_typecast_speed_not_double_applied():
    """타입캐스트는 API가 tempo를 직접 받으므로 후처리 atempo는 1.0이어야 한다."""
    _, _, speed, extra, *_ = mix_pipeline._voice_params(
        {"voice_id": "v", "speed": 1.6, "model_id": "ssfm-v30"})
    assert speed == 1.6
    assert extra == 1.0


def test_eleven_speed_still_compensated():
    """일레븐랩스는 1.2 상한이라 초과분을 후처리로 갚는 기존 동작 유지."""
    _, _, speed, extra, *_ = mix_pipeline._voice_params(
        {"voice_id": "v", "speed": 1.6, "model_id": "eleven_v3"})
    assert speed == 1.6
    assert abs(extra - 1.6 / 1.2) < 1e-9


def test_build_payload_does_not_clamp_to_eleven_range():
    body = typecast_tts.build_payload("t", "v", speed=1.6)
    assert body["output"]["audio_tempo"] == 1.6
    # API 상한 밖은 잘린다
    assert typecast_tts.build_payload("t", "v", speed=9)["output"]["audio_tempo"] == 2.0


# ── ④ 키 없으면 무음 mock ──────────────────────────────────────────────────
def test_no_key_falls_back_to_silent_mock(monkeypatch, tmp_path):
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "")
    monkeypatch.setattr(typecast_tts, "synthesize",
                        lambda *a, **k: pytest.fail("키 없는데 호출했다"))
    out = str(tmp_path / "d.mp3")
    assert tts.synthesize_tts("안녕", out, voice_id="v", model_id="ssfm-v30") == out
    assert tmp_path.joinpath("d.mp3").stat().st_size > 0


# ── 감정 매핑 ──────────────────────────────────────────────────────────────
def test_emotion_from_voice_settings(monkeypatch, tmp_path):
    """프리셋 settings의 emotion/intensity가 그대로 전달된다."""
    got = {}
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "k")

    def fake(text, o, **kw):
        got.update(kw)
        return None
    monkeypatch.setattr(typecast_tts, "synthesize", fake)
    tts.synthesize_tts("안녕", str(tmp_path / "e.mp3"), voice_id="v",
                       model_id="ssfm-v30",
                       voice_settings={"emotion": "toneup", "emotion_intensity": 1.3})
    assert got["emotion"] == "toneup"
    assert got["intensity"] == 1.3


def test_eleven_settings_are_not_sent_as_emotion(monkeypatch, tmp_path):
    """일레븐랩스 축(stability/style)은 타입캐스트에 없다 — normal로 떨어진다."""
    got = {}
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "k")

    def fake(text, o, **kw):
        got.update(kw)
        return None
    monkeypatch.setattr(typecast_tts, "synthesize", fake)
    tts.synthesize_tts("안녕", str(tmp_path / "f.mp3"), voice_id="v",
                       model_id="ssfm-v30",
                       voice_settings={"stability": 0.5, "style": 0.4})
    assert got["emotion"] == typecast_tts.DEFAULT_EMOTION
    assert got["intensity"] is None


def test_build_payload_smart_context_only_without_emotion():
    """감정 미지정 시에만 문맥 자동감정(smart) — v3에서 막히던 값이 여기선 살아난다."""
    b = typecast_tts.build_payload("t", "v", previous_text="앞", next_text="뒤")
    assert b["prompt"]["emotion_type"] == "smart"
    assert b["prompt"]["previous_text"] == "앞"
    b2 = typecast_tts.build_payload("t", "v", emotion="toneup",
                                    previous_text="앞", next_text="뒤")
    assert b2["prompt"]["emotion_type"] == "preset"
    assert "previous_text" not in b2["prompt"]


# ── v3 태그 제거 (2026-08-19 e2e에서 실제로 읽힌 사고) ────────────────────
def test_strip_v3_tags_removes_eleven_tags():
    """`[curious]`를 안 지우면 타입캐스트가 소리 내어 읽는다(실측)."""
    assert typecast_tts.strip_v3_tags("[curious] 와, 좋아요") == "와, 좋아요"
    assert typecast_tts.strip_v3_tags("[curious][whispers] 안녕") == "안녕"
    assert typecast_tts.strip_v3_tags("태그 없음") == "태그 없음"


def test_strip_v3_tags_keeps_text_when_only_tags():
    """태그만 있으면 빈 문자열이 되므로 원문을 살린다(무음 합성 방지)."""
    assert typecast_tts.strip_v3_tags("[curious]") == "[curious]"
    assert typecast_tts.strip_v3_tags("") == ""
    assert typecast_tts.strip_v3_tags(None) is None


def test_payload_text_has_no_tags():
    b = typecast_tts.build_payload("[curious] 와, 이거 좋아요", "v")
    assert "[" not in b["text"]
    assert b["text"] == "와, 이거 좋아요"


def test_smart_context_also_stripped():
    b = typecast_tts.build_payload("t", "v", previous_text="[curious] 앞",
                                   next_text="[whispers] 뒤")
    assert b["prompt"]["previous_text"] == "앞"
    assert b["prompt"]["next_text"] == "뒤"


def test_retry_on_network_error(monkeypatch, tmp_path):
    """네트워크 실패는 재시도한다(일레븐랩스 경로와 같은 계약)."""
    calls = {"n": 0}
    monkeypatch.setattr(typecast_tts, "api_key", lambda *a, **kw: "k")
    monkeypatch.setattr(tts.time, "sleep", lambda s: None)

    def flaky(text, o, **kw):
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.ConnectionError("boom")
        return None
    monkeypatch.setattr(typecast_tts, "synthesize", flaky)
    tts.synthesize_tts("안녕", str(tmp_path / "g.mp3"), voice_id="v",
                       model_id="ssfm-v30", max_retries=3)
    assert calls["n"] == 2
