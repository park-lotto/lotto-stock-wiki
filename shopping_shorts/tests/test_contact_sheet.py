"""G-10 렌더 없는 눈 검사 — render_bench.contact_sheet: 컷마다 처음·가운데·끝 3장이 관문 ④와 같은 그림(cut_frame·cut_crop·재료 blur)인가."""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def test_sheet_tiles_are_gate_frames(tmp_path):
    src = tmp_path / "a.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=640x360:r=30:d=4", "-pix_fmt", "yuv420p", str(src)],
                   check=True, stdin=subprocess.DEVNULL)
    st = {"frame": {"kind": "window", "window": [0, 434, 1080, 1052]}}
    crop = [100, 20, 300, 292]
    M = {"cand_dir": str(tmp_path), "blur": {"a.mp4": [[0, 0, 640, 60]]}}
    T = {"cuts": [{"line": "N1", "src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 2.0, "dur": 2.0, "crop": crop},
                  {"line": "N2", "src": "없음.mp4", "ss": 0.0, "t0": 2.0, "t1": 3.0, "dur": 1.0, "crop": crop}]}
    S = {"lines": [{"id": "N1", "kind": "tts", "tts": "첫 줄 글."}]}
    out = RB.contact_sheet(T, M, st, tmp_path / "plan" / "sheet.jpg", S)
    from PIL import Image
    sh = np.asarray(Image.open(out).convert("RGB")).astype(int)
    th = round(RB.SHEET_W * 1052 / 1080)
    assert sh.shape[1] == RB.SHEET_W * 3 and sh.shape[0] == 2 * (44 + th)      # 컷 2줄(원본 없는 컷도 줄은 남는다 — 빠지면 눈이 못 본다)
    for j, dt in enumerate(RB.look_times(60)):
        a = RB.cut_frame(src, 1.0 + dt, crop, (1080, 1052), M["blur"]["a.mp4"])
        want = np.asarray(Image.fromarray(np.ascontiguousarray(a[:, :, ::-1])).resize((RB.SHEET_W, th))).astype(int)
        got = sh[44:44 + th, j * RB.SHEET_W:(j + 1) * RB.SHEET_W]
        assert np.abs(got - want).mean() < 4, j          # jpg 손실만
    assert sh[44 + th + 44:, :].max() < 30               # 원본 없는 컷 = 빈 칸
