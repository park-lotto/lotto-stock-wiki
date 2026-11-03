"""피쉬오디오: 낱자를 소리 내어 읽지 않고, 쉼이 짧아도 받아쓰기로 줄을 자른다(11-02 회원 실측)."""
import math
import struct
import subprocess
import wave

from tools.calcopy.engine import narr_verify as NV, voice_synth as VS
from tools.calcopy.hybrid import render_itssum as RI


def test_speakable_drops_jamo():
    assert VS.speakable("이거 대박 ㄷㄷ") == "이거 대박"
    assert VS.speakable("진짜 ㅋㅋ 좋아요") == "진짜 좋아요"
    assert VS.speakable("ㅋㅋ") == "ㅋㅋ"          # 줄 전체가 낱자면 빈 합성을 보내지 않는다


def test_spans_by_speech_finds_line_ends(tmp_path, monkeypatch):
    p = tmp_path / "n.wav"
    sr = 8000
    samples = []
    for sec, f in ((1.0, 300), (0.1, 0), (1.0, 500)):        # 줄 사이 0.1초뿐 — 쉼 문턱 0.16초 아래
        samples += [int(12000 * math.sin(2 * math.pi * f * i / sr)) if f else 0 for i in range(int(sec * sr))]
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    monkeypatch.setattr(NV, "heard_words", lambda path: [{"s": 0.0, "e": 1.0, "w": "가나다라", "conf": 1.0}, {"s": 1.1, "e": 2.1, "w": "마바사아", "conf": 1.0}])
    sp = RI.spans_by_speech(p, [{"tts": "가나다라"}, {"tts": "마바사아"}], log=lambda s: None)
    assert len(sp) == 2
    assert 0.95 <= sp[0][1] <= 1.15
