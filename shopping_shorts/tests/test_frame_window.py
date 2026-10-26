"""창 영역 주인 한 곳(styles.frame_window) — 10-27 실사고: 전체화면 판(두유노판)에서 flow._ar 가 frame['window'] 를 직접 읽어 KeyError,
대본을 받은 직후 흐름이 죽었다. 모든 판에서 흐름·실행기·렌더러가 같은 창을 쓰는지, frame['window'] 직접 읽기가 다시 생기지 않는지."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import styles as STY  # noqa: E402


def test_every_style_has_a_window_and_paths_agree():
    n = 0
    for v in STY.names():
        if v.startswith("_"):
            continue
        fr = STY.load(v).get("frame") or {}
        if not fr:
            continue
        w = STY.window_of(v)
        assert len(w) == 4 and w[2] > 0 and w[3] > 0, v
        assert RB.frame_window(fr) == w, v                     # 렌더러 = 같은 주인
        assert abs(F._ar(v) - w[2] / w[3]) < 1e-9, v           # 흐름 = 같은 주인
        n += 1
    assert n > 5


def test_full_frame_style_is_whole_screen():
    full = [v for v in STY.names() if not v.startswith("_") and (STY.load(v).get("frame") or {}).get("kind") == "full"]
    assert full, "전체화면 판이 하나는 있어야 이 시험이 뜻이 있다"
    for v in full:
        assert STY.window_of(v) == [0, 0, 1080, 1920]


def test_no_direct_frame_window_reads():
    """주인 밖에서 frame['window'] 를 직접 읽으면 전체화면 판에서 다시 죽는다."""
    bad = []
    for f in (ROOT / "tools" / "calcopy").rglob("*.py"):
        if f.name == "styles.py":
            continue
        for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r'\["frame"\]\["window"\]', ln):
                bad.append(f"{f.relative_to(ROOT)}:{i}")
    assert not bad, bad
