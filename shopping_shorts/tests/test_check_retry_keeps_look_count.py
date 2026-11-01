"""완성본 '다시 시도'가 눈 검수 횟수를 0으로 되돌리면 2번 한도(눈 지적만 남으면 완성)가 영원히 안 온다
— 10-31 티라미수: 회원 Claude 가 retry 를 부를 때마다 횟수가 새로 시작돼 같은 눈 검수를 8번 되풀이."""
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


def test_generic_retry_line_keeps_look():
    import inspect
    src = inspect.getsource(F)
    assert 'if k == "length"}' not in src, "일반 다시 시도도 눈 검수 횟수를 지우면 안 된다"


def test_no_grounds_is_told():
    assert "근거 자료가 없다" in F.eye_material_note(["bench/sheet.jpg"], "")
