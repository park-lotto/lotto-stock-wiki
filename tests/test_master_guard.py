"""완성본 진짜 최고점 지킴이(engine/master_guard) — 순간음(클릭)이 있는 소리는 AAC 뒤 최고점이 넘치고, encode_final 이 고친다."""
import subprocess
from pathlib import Path

from tools.calcopy.engine import master_guard as MG


FIX = Path(__file__).parent / "fixtures" / "master_guard_ssok_1018.wav"   # 10-18 원샷1_전동칫솔 mix.wav 15~17초('쏙') — 합성 클릭은 AAC 가 눌러 재현 안 됨


def _media(tmp: Path):
    import shutil
    wav = tmp / "mix.wav"
    shutil.copyfile(FIX, wav)
    vid = tmp / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid)], check=True)
    return vid, wav


def test_plain_aac_overshoots(tmp_path):
    vid, wav = _media(tmp_path)
    MG._mux(vid, wav, tmp_path / "plain.mp4")
    assert MG.loudness(tmp_path / "plain.mp4")[1] > -0.5           # 빨강: 그냥 인코딩하면 넘친다


def test_encode_final_keeps_peak(tmp_path):
    vid, wav = _media(tmp_path)
    r = MG.encode_final(vid, wav, tmp_path / "final.mp4", -0.5, log=lambda *a: None)
    assert r["ok"] and r["tp"] <= -0.5 and len(r["tries"]) >= 2 and Path(r["mix_used"]).exists()
    assert wav.exists()                                              # 원래 mix 는 그대로


def test_final_keeps_all_video_frames(tmp_path):
    """10-18 실측: -shortest + 영상 복사로 끝 4프레임이 잘려 B9 끝 밝기 검사가 멈췄다."""
    vid, wav = _media(tmp_path)
    MG.encode_final(vid, wav, tmp_path / "final.mp4", -0.5, log=lambda *a: None)
    n = lambda p: subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames",
                                  "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    assert n(tmp_path / "final.mp4") == n(vid)
