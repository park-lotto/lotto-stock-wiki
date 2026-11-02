"""나레 줄이 실제로 놓인 시각 = 줄 목소리 파일을 완성 목소리에 맞대어(받아쓰기 낱말 시각은 원음 뒤 경계에서 밀린다 — 10-27 run4 a편 L9 0.47초 헛반려).
주인 = engine/check_line_sync.placed_at."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import check_line_sync as LS  # noqa: E402


def _tone(p, sec, f):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={f}:duration={sec}", "-af", "tremolo=f=7:d=0.9", str(p)], check=True)


def test_finds_real_position_and_rejects_wrong(tmp_path):
    line = tmp_path / "s_L1.wav"
    _tone(line, 1.2, 440)
    voice = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-i", str(line),
                    "-filter_complex", "[0]atrim=0:5[s];[1]adelay=2300|2300[d];[s][d]amix=inputs=2:normalize=0[o]", "-map", "[o]", str(voice)], check=True)
    at, cr = LS.placed_at(line, voice, 2.0)
    assert at is not None and abs(at - 2.3) < 0.02 and cr > 0.9
    assert LS.placed_at(line, voice, 4.5, win=0.3)[0] is None
