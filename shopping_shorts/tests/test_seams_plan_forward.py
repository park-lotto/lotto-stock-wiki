"""완성본 그림 대조(되감김·점프줌)가 계획이 '앞으로·안 보인 구간'이라 한 경계를 오독하면 참고로(10-27 run4 a편 헛반려).
주인 = engine/check_seams.plan_forward."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import check_seams as C  # noqa: E402


def _c(t0, t1, ss, src="a"):
    return {"t0": t0, "t1": t1, "ss": ss, "src": src}


def test_forward_and_other_src_are_not_rewind():
    cuts = [_c(0, 1, 47.1), _c(1, 2, 52.6), _c(2, 3, 0, "b")]
    assert C.plan_forward(1.0, cuts).startswith("같은 원본 앞으로")
    assert C.plan_forward(2.0, cuts) == "다른 원본으로 넘어감"


def test_hook_then_start_is_unseen_not_rewind():
    cuts = [_c(0, 1.3, 70), _c(1.3, 2.6, 78), _c(2.6, 3.8, 3.4)]
    assert "안 보인 구간" in C.plan_forward(2.6, cuts)


def test_real_rewind_still_counts():
    cuts = [_c(0, 1, 10), _c(1, 2, 10.2)]                 # 이미 보인 10~11초를 다시
    assert C.plan_forward(1.0, cuts) == ""
    assert C.plan_forward(5.0, cuts) == ""                # 경계 아님
