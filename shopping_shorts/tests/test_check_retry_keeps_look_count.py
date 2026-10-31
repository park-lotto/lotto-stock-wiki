"""완성본 '다시 시도'가 눈 검수 횟수를 0으로 되돌리면 2번 한도(눈 지적만 남으면 완성)가 영원히 안 온다
— 10-31 티라미수: 회원 Claude 가 retry 를 부를 때마다 횟수가 새로 시작돼 같은 눈 검수를 8번 되풀이."""
import pytest

from tools.calcopy.hybrid import flow as F


def test_check_retry_keeps_look_count():
    st = {"version": "x", "log": [], "tries": {"look": F.LIMITS["look"]}, "auto": {"ok": True, "rows": []},
          "look": {"ok": False, "problems": ["E1 △: 자료 없음"]}}
    assert F.ph_check_retry(st, {}, {}, {}) == {"goto": "check"}
    assert st["tries"]["look"] == F.LIMITS["look"], "다시 시도가 눈 검수 횟수를 지웠다 — 한도가 영원히 안 온다"


def test_after_retry_recheck_eye_only_finishes_with_notice():
    """다시 시도 → 검사 다시 → 자동 통과·눈 지적만 → 한도 유지라 멈추지 않고 완성(남은 지적은 알림)."""
    st = {"version": "x", "log": [], "tries": {"look": F.LIMITS["look"]}, "auto": {"ok": True, "rows": []},
          "look": {"ok": False, "problems": ["E1 △: 자료 없음"]}}
    F.ph_check_retry(st, {}, {}, {})
    assert F.ph_check_judge(st, {}, {}, {}) == {"goto": "deliver"}
    assert st["look_left"] == ["E1 △: 자료 없음"]


def _finish(st):
    return F.ph_finished(st, {"final": {"video": "final.mp4"}}, {}, {})


def test_eye_only_left_actually_finishes():
    """눈 지적만 남겨 deliver 로 보낸 편이 마지막 관문에서 다시 멈추면 '멈추지 않고 완성'이 거짓이 된다."""
    st = {"version": "x", "log": [], "tries": {"look": F.LIMITS["look"]}, "auto": {"ok": True, "rows": []}, "env": {"keys": {"speechmatics": True}},
          "script": {"S": {"lines": [], "title_lines": []}}, "look": {"ok": False, "problems": ["E1 △: 자막 겹침"]}}
    assert F.ph_check_judge(st, {}, {}, {}) == {"goto": "deliver"}
    done = _finish(st)["done"]
    assert done["look_ok"] is False and done["look_left"] == ["E1 △: 자막 겹침"]


def test_no_eye_review_still_blocked():
    """눈 판정을 거치지 않고 deliver 에 온 편은 그대로 막는다."""
    st = {"version": "x", "log": [], "tries": {}, "auto": {"ok": True, "rows": []}, "look": {"ok": False, "problems": []}}
    with pytest.raises(F._Stop):
        _finish(st)


def test_failed_auto_blocked_even_with_old_left():
    st = {"version": "x", "log": [], "tries": {}, "auto": {"ok": False, "rows": []}, "look": {"ok": False, "problems": []}, "look_left": ["E1"]}
    with pytest.raises(F._Stop):
        _finish(st)


def test_new_check_clears_old_left():
    st = {"version": "x", "log": [], "tries": {}, "look_left": ["옛 지적"], "auto": {"ok": False, "rows": []}}
    F.ph_check_got(st, {"check": {"auto": {"ok": False, "rows": []}}}, {}, {})
    assert "look_left" not in st
