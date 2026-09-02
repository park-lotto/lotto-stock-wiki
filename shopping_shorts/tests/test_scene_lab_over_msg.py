"""3단계 칸 표시가 '재료 남음'을 두 곳에서 다르게 말하지 않는지.

2026-09-02 라이브 실측(job 353493f20d31):
  같은 칸을 두고 위 타임라인은 "7.9/4.5초 · **3.4초는 안 나와요**",
  아래 칸 줄은 "재료 7.9/멘트 4.5초 · **다 채웠어요**" 라고 서로 다른 말을 했다.
  5칸 합쳐 5.8초가 실제로 버려지는데 칸 줄은 전부 "다 채웠어요"였다.

뿌리: 남는 재료(f.over) 표시가 2026-08-21에 타임라인에만 들어가고
      칸 줄(render)은 안 고쳐졌다 — lack이 없으면 무조건 else('다 채웠어요')로 떨어진다.
      (0순위-B: 같은 판단을 두 곳에서 따로 적으면 반드시 어긋난다)

문자열 검색만으로는 약하므로(리팩터링에 우연히 통과) **두 자리 모두 f.over를 보는지**를
확인한다 — 한쪽에서 빼면 빨개진다.
"""
import pathlib
import re

SCENE_LAB = pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"


def _src() -> str:
    return SCENE_LAB.read_text(encoding="utf-8")


def test_beat_row_reports_surplus_too():
    """칸 줄도 f.over를 보고 '안 나와요'를 말해야 한다."""
    src = _src()
    # '다 채웠어요'가 나오는 줄 앞에 f.over 분기가 있어야 한다.
    idx = src.index("' · 다 채웠어요'")
    window = src[max(0, idx - 700):idx]
    assert "f.over" in window, (
        "칸 줄이 남는 재료를 안 본다 — lack이 없으면 무조건 '다 채웠어요'가 되어, "
        "타임라인의 'N초는 안 나와요'와 같은 칸을 두고 서로 다른 말을 한다")


def test_both_places_use_same_over_signal():
    """타임라인과 칸 줄이 **같은 값**(f.over)으로 판단하는지 — 각자 계산하면 또 어긋난다."""
    src = _src()
    hits = re.findall(r"f\.over\s*>\s*0\.1", src)
    # 타임라인(색 dwarn, 툴팁, 문구) + 칸 줄(색, 문구) — 최소 두 자리 이상에서 쓰여야 한다
    assert len(hits) >= 4, f"f.over 분기가 너무 적다({len(hits)}곳) — 한쪽만 고쳐진 상태일 수 있다"


def test_surplus_chip_is_not_green():
    """재료가 남으면 초록(good)이 아니어야 한다 — 버려지는 상태를 '정상'으로 칠하면 안 된다."""
    src = _src()
    idx = src.index("재료 ${have.toFixed(1)}/멘트")
    head = src[max(0, idx - 400):idx]
    assert "f.over" in head, (
        "칸 줄 chip 색이 남는 재료를 반영하지 않는다 — 5.8초가 버려져도 초록불로 보인다")
