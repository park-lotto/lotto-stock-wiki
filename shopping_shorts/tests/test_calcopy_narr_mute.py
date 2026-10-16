# -*- coding: utf-8 -*-
"""컷별 원음 끄기 shots[].mute — 원음 꼴(remake_video, 틀 A) (관제 097, 10-16 썰풀다 새소재4 요청).
판단 주인 = hottem_audio.shot_muted(narr_video 원음 깔기 cut_plan_from 과 같은 함수). 진짜로 소리를 섞어(material) 잰다:
  ① mute 컷 구간 = 원음(440Hz 톤) 0 이고, 소리 전체가 'BGM-only 대조군'(그 컷 소스가 무음 영상)과 같다
  ② mute 아닌 컷은 원음 톤이 남는다"""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import hottem_audio as HA  # noqa: E402
from tools.calcopy import remake_video as RV  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 필요")
SPEC = {"canvas": [360, 640], "layers": [{"kind": "video", "x": 0, "y": 160, "w": 360, "h": 320}]}
BGM = "honwaka_puppu"


def _src(path: Path, audio: str):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=6:r=30", "-f", "lavfi", "-i", audio,
                    "-t", "6", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)


def _pcm(mp4: Path) -> np.ndarray:
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(b, np.int16).astype(float)


def _tone(x: np.ndarray) -> float:
    """440Hz 성분 세기(FFT 진폭) — 원음(톤)이 남았나."""
    f = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    fr = np.fft.rfftfreq(len(x), 1 / 48000)
    return float(f[(fr > 430) & (fr < 450)].max() / len(x))


def _mix(tmp: Path, name: str, shots: list) -> np.ndarray:
    work = tmp / name
    work.mkdir()
    out, _, _ = RV.material({"cand_dir": str(tmp), "shots": shots}, SPEC, None, 4.0, work, BGM, 0.15, -14.0)
    return _pcm(out)


@pytest.mark.skipif(not (ROOT / "shopping_shorts/assets/bgm_lib" / f"{BGM}.mp3").exists(), reason="BGM 없음")
def test_mute_shot_is_bgm_only_and_other_shot_keeps_source(tmp_path):
    _src(tmp_path / "tone.mp4", "sine=frequency=440:sample_rate=48000")
    _src(tmp_path / "quiet.mp4", "anullsrc=r=48000:cl=stereo")
    a = {"src": "tone.mp4", "ss": 0, "t0": 0.0, "t1": 2.0}
    muted = _mix(tmp_path, "m", [a, {"src": "tone.mp4", "ss": 2, "t0": 2.0, "t1": 4.0, "mute": True}])
    control = _mix(tmp_path, "c", [a, {"src": "quiet.mp4", "ss": 2, "t0": 2.0, "t1": 4.0}])   # 대조군: 그 컷 소스가 원래 무음
    plain = _mix(tmp_path, "p", [a, {"src": "tone.mp4", "ss": 2, "t0": 2.0, "t1": 4.0}])       # 사보타주 대조군: mute 없음
    sr = 48000
    s0, s1 = slice(int(0.3 * sr), int(1.7 * sr)), slice(int(2.3 * sr), int(3.4 * sr))
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)))   # noqa: E731
    assert _tone(muted[s0]) > 20 * _tone(muted[s1]), (_tone(muted[s0]), _tone(muted[s1]))     # ② 앞 컷 원음 남음 · ① 뒤 컷 원음 0
    assert _tone(plain[s1]) > 20 * _tone(muted[s1])                                          # mute 를 빼면 뒤 컷에도 원음(잣대가 잡는다)
    r_m, r_c = rms(muted[s1]), rms(control[s1])
    assert r_c > 50 and abs(r_m - r_c) / r_c < 0.05, (r_m, r_c)                              # ① mute 컷 = BGM-only 대조군(±5%)


def test_shot_muted_owner():
    assert HA.shot_muted({"mute": True}) and HA.shot_muted({"kind": "짤"}) and not HA.shot_muted({"kind": "남의영상재편집"})
    plan, _, _ = HA.cut_plan_from({"shots": [[0, 1], [1, 2]]}, {"cand_dir": ".", "shots": [{"src": "a.mp4", "ss": 0}, {"src": "a.mp4", "ss": 1, "mute": True}]})
    assert [c["video_id"] for c in plan[0]["clips"]] == ["s0", "__mute__"]
