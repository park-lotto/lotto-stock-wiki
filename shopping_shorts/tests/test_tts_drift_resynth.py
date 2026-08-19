"""대본이 갈린 비트는 렌더 직전에 **자동으로 다시 합성**된다(2026-08-19).

탐지(tts_matches_narration)만으로는 아무것도 안 고쳐진다. 실제 방어선은
렌더 경로의 `_synthesize_beats(skip_existing=True)`가 **현재 대본의 해시 경로**를
기준으로 스킵을 판정한다는 점이다 — 대본이 갈리면 그 경로의 파일이 없으므로
스킵되지 않고 새로 합성된다.

이 테스트는 그 자기치유가 **실제로 도는지**를 못박는다. 여기가 깨지면
"대본은 새 것, 소리는 옛 것"이 렌더까지 그대로 나간다(사장님 제보의 그 증상).
"""
from pathlib import Path

import shopping_shorts.mix_pipeline as mp


def _stub_synth(monkeypatch, calls):
    def fake(narration, out_path, **kw):
        calls.append((str(out_path), narration))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"MP3")
        return narration
    monkeypatch.setattr(mp, "synthesize_line", fake)
    monkeypatch.setattr(mp.audio_post, "trim_tail_silence", lambda a, b: None)
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 2.0)
    monkeypatch.setattr(mp, "_beat_words", lambda *a, **k: None)


def test_대본이_갈리면_렌더전에_재합성된다(tmp_path, monkeypatch):
    calls = []
    _stub_synth(monkeypatch, calls)
    tts = tmp_path / "tts"

    beats = [{"beat_idx": 0, "narration": "원래 대본입니다", "role": "훅"}]
    mp._synthesize_beats(beats, tts, voice=None)
    first = beats[0]["tts_path"]
    assert mp.tts_matches_narration(beats[0]) is True
    assert len(calls) == 1

    # 어떤 리라이터가 대본만 갈아치웠다(재합성 없이) — 라이브에서 난 그 상태
    beats[0]["narration"] = "완전히 다른 새 대본입니다"
    assert mp.tts_matches_narration(beats[0]) is False, "어긋남을 탐지 못 했다"

    # 렌더 직전 보장 패스: skip_existing=True인데도 **다시 합성해야** 한다
    mp._synthesize_beats(beats, tts, voice=None, skip_existing=True)
    assert len(calls) == 2, "대본이 갈렸는데 재합성을 건너뛰었다(옛 소리가 그대로 나간다)"
    assert beats[0]["tts_path"] != first, "tts_path가 새 대본 파일로 안 바뀌었다"
    assert calls[-1][1] == "완전히 다른 새 대본입니다"
    assert mp.tts_matches_narration(beats[0]) is True


def test_대본이_같으면_재합성_안_한다(tmp_path, monkeypatch):
    """자기치유가 과잉이면 매 렌더마다 돈이 나간다 — 같은 대본은 0원이어야 한다."""
    calls = []
    _stub_synth(monkeypatch, calls)
    tts = tmp_path / "tts"
    beats = [{"beat_idx": 0, "narration": "그대로인 대본", "role": "훅"}]
    mp._synthesize_beats(beats, tts, voice=None)
    mp._synthesize_beats(beats, tts, voice=None, skip_existing=True)
    assert len(calls) == 1, "같은 대본인데 다시 합성했다(불필요한 과금)"


def test_mismatched_beats_목록(tmp_path, monkeypatch):
    calls = []
    _stub_synth(monkeypatch, calls)
    beats = [{"beat_idx": 0, "narration": "가", "role": "훅"},
             {"beat_idx": 1, "narration": "나", "role": "본문"},
             {"beat_idx": 2, "narration": "다", "role": "CTA"}]
    mp._synthesize_beats(beats, tmp_path / "tts", voice=None)
    assert mp.mismatched_beats(beats) == []
    beats[1]["narration"] = "바뀐 문장"
    assert mp.mismatched_beats(beats) == [1]
