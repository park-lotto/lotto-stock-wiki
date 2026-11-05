"""11-05 한정수 #7670: '원음 줄 컷 ss 가 원음 구간 밖'을 한 줄씩만 알려 L2→L4→L6 고칠 때마다 다음 줄이 걸려 '같은 원인 3번 연속'. 줄 전체를 모아 한 번에."""
import copy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def test_all_out_of_span_lines_reported_together(monkeypatch, tmp_path):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:d=40:r=30", "-c:v", "libx264", "-preset", "ultrafast",
                    str(tmp_path / "o.mp4")], check=True)
    monkeypatch.setattr(RB, "orig_edges", lambda p, sp: (0.0, 0.0))
    monkeypatch.setattr("tools.calcopy.hybrid.material_fit.action_order", lambda S, M, log=None: None)
    S = {"lines": [{"id": "L2", "kind": "orig", "src": "o.mp4", "span": [1.7, 3.263], "caps": [{"text": "가", "s0": 0.0, "s1": 1.0}]},
                   {"id": "L4", "kind": "orig", "src": "o.mp4", "span": [23.571, 26.184], "caps": [{"text": "나", "s0": 0.0, "s1": 1.0}]}]}
    M = {"cand_dir": str(tmp_path), "cuts": {"L2": [{"src": "o.mp4", "ss": 0.0}], "L4": [{"src": "o.mp4", "ss": 11.6}]}}
    with pytest.raises(RB.StageError) as e:
        RB.timeline(copy.deepcopy(S), M, {}, None, None)
    assert "L2 원음 줄 컷" in str(e.value) and "L4 원음 줄 컷" in str(e.value), str(e.value)
