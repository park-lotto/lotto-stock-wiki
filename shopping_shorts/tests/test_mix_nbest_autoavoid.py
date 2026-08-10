"""N-best 오독 자동회피 켜기(2026-07-22, 사장님 ② 결정).

증상: 특정 비트에 발음/오독·어색함이 섞인다. 뿌리: 비트마다 take 1개만 뽑아
그 take가 오독이면 그대로 나간다(n_best 기본 1).

fix: Whisper 랭커(GROQ 키)가 실동작할 때만 n을 최소 2로 끌어올려(best-of-2)
오독 적은 take를 자동 선택한다. 랭커가 못 도는 상황(키 없음)에선 n을 profile값
그대로 둔다 — 키 없이 N배 합성하면 랭킹이 안 되니 TTS 비용만 낭비다.

불변식:
- GROQ 키 有 + 프로파일 n_best<2  → n=2 (자동회피 ON)
- GROQ 키 有 + 프로파일 n_best=3  → n=3 (명시 프리셋 보존, floor라 안 깎음)
- GROQ 키 無                      → n=프로파일값 그대로 (낭비 0, 기존 동작)
"""
from shopping_shorts import mix_pipeline


def _run_capture_n(monkeypatch, tmp_path, profile, groq_key):
    seen = {}

    def fake_synth_best(text, out_path, **kw):
        seen.update(kw)
        open(out_path, "wb").write(b"x")
        return out_path

    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", fake_synth_best)
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])
    monkeypatch.setattr(mix_pipeline.config, "GROQ_API_KEY", groq_key)

    beats = [{"beat_idx": 0, "narration": "안녕하세요", "role": "hook"}]
    voice = {"voice_id": "v", "settings": None, "speed": 1.0, "silence_trim": "off",
             "naturalize_profile": profile}
    mix_pipeline._synthesize_beats(beats, tmp_path, voice=voice)
    return seen


def test_groq_present_floor_raises_to_2(monkeypatch, tmp_path):
    seen = _run_capture_n(monkeypatch, tmp_path, {"n_best": 1, "seed": 5}, "gk_live")
    assert seen["n"] == 2, "GROQ 키가 있으면 자동회피로 최소 best-of-2여야 한다"


def test_groq_present_preserves_higher_preset(monkeypatch, tmp_path):
    seen = _run_capture_n(monkeypatch, tmp_path, {"n_best": 3, "seed": 5}, "gk_live")
    assert seen["n"] == 3, "명시 프리셋(3)은 floor보다 크므로 그대로 보존"


def test_no_groq_keeps_profile_value(monkeypatch, tmp_path):
    seen = _run_capture_n(monkeypatch, tmp_path, {"n_best": 1, "seed": 5}, "")
    assert seen["n"] == 1, "GROQ 키가 없으면 랭킹 불가 → n을 안 올려 N배 낭비를 막는다"
