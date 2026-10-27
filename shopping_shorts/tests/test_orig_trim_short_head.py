"""원음 줄 앞 무음을 빼면 첫 컷만 짧아진다 — MIN_PIECE_SEC 밑이면 그 조각을 빼고 다음 컷을 줄 처음부터(입 맞춤 그대로).
10-27 펜티 편: Claude 가 0.4·0.5초로 적은 첫 컷이 앞 무음 0.068·0.388초에 깎여 0.33·0.13초 → '번쩍' 반려."""
import copy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def test_short_head_after_trim_is_dropped(monkeypatch, tmp_path):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:d=70:r=30", "-c:v", "libx264", "-preset", "ultrafast",
                    str(tmp_path / "o.mp4")], check=True)
    monkeypatch.setattr(RB, "orig_edges", lambda p, sp: (0.388, 0.0))
    monkeypatch.setattr("tools.calcopy.hybrid.material_fit.action_order", lambda S, M, log=None: None)
    S = {"lines": [{"id": "O2", "kind": "orig", "src": "o.mp4", "span": [61.9, 66.0], "caps": [{"text": "와", "s0": 0.0, "s1": 1.0}]}]}
    M = {"cand_dir": str(tmp_path), "cuts": {"O2": [{"src": "o.mp4", "ss": 61.9, "at": 0.0, "max": 0.5}, {"src": "o.mp4", "ss": 62.8, "at": 0.5, "max": 3.0}]}}
    T = RB.timeline(copy.deepcopy(S), M, {}, None, None)
    o2 = [c for c in T["cuts"] if c["line"] == "O2"]
    assert all(c["t1"] - c["t0"] >= RB.MIN_PIECE_SEC - 1e-6 for c in o2), [(c["ss"], c["t1"] - c["t0"]) for c in o2]
    assert abs(float(o2[0]["ss"]) - (62.8 - (0.5 - 0.388))) < 0.02     # 다음 컷이 줄 처음부터 — 원본 초도 같은 만큼 당김(입 맞춤)
