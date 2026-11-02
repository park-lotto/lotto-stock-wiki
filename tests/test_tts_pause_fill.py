# -*- coding: utf-8 -*-
"""tts_pause.shape — 짧은 쉼에 말 꼬리가 섞였을 때 늘린 쉼이 말소리 반복이 되지 않는다(10-18 샥탬 4편 L7|L9 실측 결함)."""
import array
import math
import subprocess
import wave

from tools.calcopy.engine import tts_pause

SR = 24000


def _tone(sec, amp):
    return [int(amp * math.sin(2 * math.pi * 220 * i / SR)) for i in range(int(sec * SR))]


def _write_mp3(tmp_path, samples):
    wav = tmp_path / "in.wav"
    w = wave.open(str(wav), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(array.array("h", samples).tobytes()); w.close()
    mp3 = tmp_path / "in.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "192k", str(mp3)], check=True)
    return mp3


def _rms_db(mp3, t0, dur):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t0}", "-t", f"{dur}", "-i", str(mp3), "-af", "astats=metadata=0", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace").stderr
    return float(r.split("RMS level dB:")[1].split()[0])


def test_short_loud_gap_is_filled_with_room_tone(tmp_path):
    # 말 1초 · 쉼 자리 0.1초(말 꼬리 남음, 소리 큼) · 말 1초 · 끝에 조용한 0.3초(방 잡음)
    samples = _tone(1.0, 8000) + _tone(0.1, 4000) + _tone(1.0, 8000) + [3] * int(0.3 * SR)
    mp3 = _write_mp3(tmp_path, samples)
    align = {"characters": list("가나다.라마바"),
             "character_start_times_seconds": [0.0, 0.3, 0.6, 1.0, 1.1, 1.5, 1.8],
             "character_end_times_seconds": [0.3, 0.6, 1.0, 1.0, 1.5, 1.8, 2.1]}
    out = tmp_path / "out.mp3"
    log = tts_pause.shape(str(mp3), align, str(out))
    assert log and log[0]["now"] >= tts_pause.PAUSE["."] - 0.02
    # 늘린 부분(원래 쉼 0.1초 뒤 ~0.18초)은 방 잡음 수준이어야 한다 — 옛 코드는 말 꼬리를 반복해 −30dB 안팎
    assert _rms_db(out, 1.12, 0.12) < -45
