"""목소리 줄기/배경 소리 가르기 + 사람 말소리 판정(표 #28, Jev 해결 0.84·위험 0.38 · 11-06).

판정 = 0.1초 칸마다 목소리 줄기 > 같은 칸 배경 − 6dB 이고 −40dBFS 보다도 커야 함(두 조건 모두).
나누기 가상환경이 없으면 조용히 넘기지 않고 failed.
"""
import json
import wave
from pathlib import Path

import numpy as np

from tools.calcopy.engine import separate as SP


def _wav(p: Path, amp_by_sec: list[float], sr=8000):
    t = np.arange(int(sr * len(amp_by_sec))) / sr
    a = np.repeat(np.array(amp_by_sec), sr)
    x = (a * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())


def test_voice_needs_both_baseline_and_floor(tmp_path):
    v, b = tmp_path / "v.wav", tmp_path / "b.wav"
    _wav(v, [0.3, 0.3, 0.001, 0.02])        # 1·2초 큰 목소리 / 3초 아주 작음(절대 하한 밑) / 4초 작음
    _wav(b, [0.05, 0.6, 0.0005, 0.001])     # 2초는 배경이 훨씬 큼(목소리 < 배경 − 6dB) / 4초는 배경이 더 작음
    r = SP.voice_frames(str(v), str(b))
    f = np.array(r["frames"]).reshape(4, 10).mean(axis=1)
    assert f[0] == 1.0          # 목소리 > 배경, > −40
    assert f[1] == 0.0          # 기준선(배경 − 6dB) 밑
    assert f[2] == 0.0          # 절대 하한 밑
    assert f[3] == 1.0          # −34dB: 배경보다 크고 하한 위


def test_missing_venv_is_failed_not_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(SP, "VENV_PY", tmp_path / "없음" / "python.exe")
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"x")
    r = SP.separation_of(str(mp4), str(tmp_path / "sep"))
    assert r.get("failed") and "가상환경" in r["failed"]


def test_kal_add_separation_patches_old_tear(tmp_path, monkeypatch):
    from tools.calcopy.engine import kal
    tear = tmp_path / "뜯기.json"
    tear.write_text(json.dumps({"captions": {}}), encoding="utf-8")
    monkeypatch.setattr(SP, "separation_of", lambda mp4, out: {"model": "htdemucs", "voice": {"voiced_share": 0.5}})
    assert kal.add_separation(tear, tmp_path / "a.mp4") == "나누기 칸 더함"
    assert json.loads(tear.read_text(encoding="utf-8"))["separation"]["model"] == "htdemucs"
    assert kal.add_separation(tear, tmp_path / "a.mp4") is None          # 있으면 다시 안 함
