"""샷 구간 표에서 디졸브·끊김 자리를 뺀다(10-27 hdn3: shot_starts 는 딱 끊는 전환만 잡아 J6Nft 112초를 샷 1개로, lBleNklHu2A 36.2~41.37 을 한 샷으로 줬고
그 안 디졸브를 source_rule_scan 이 '장면 전환'으로 반려). 표와 검사가 같은 문턱(JUMP_*)을 쓴다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_dissolve_is_cut_out_of_span(monkeypatch, tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"x")
    dd = [5.0] * 100                       # 10fps 10초
    for i in range(40, 49):                # 4.1~4.9초 디졸브(차 30)
        dd[i] = 30.0
    monkeypatch.setattr(R, "_cut_jumps", lambda src, ss, dur, fps=10, n=64: dd)
    out = R.jump_free_spans(p, [[0.0, 10.0]])
    assert out[0] == [0.0, 3.9] and out[-1] == [5.1, 10.0]
    assert not any(a < 4.5 < b for a, b in out)


def test_scan_and_table_share_threshold():
    assert R._jumpy([R.JUMP_MAX + 1])
    assert R._jumpy([R.JUMP_MANY + 1] * R.JUMP_MANY_N)
    assert not R._jumpy([R.JUMP_MANY + 1] * (R.JUMP_MANY_N - 1))
