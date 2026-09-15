# -*- coding: utf-8 -*-
"""목표 초에 맞는 칸 수의 스파인을 먼저 고른다 (2026-09-09).

■ 사장님: "토막토막 끊겨 이야기가 안 된다" / "왜 놓치는 구조를 만드나"

  실측(tools/현황.py):
      우리 대본     중앙값 24.2초 · **8칸** · 칸당 3.0초
      히트작 4,915편        25.0초 · **4칸** · 칸당 6.3초
  길이는 이미 맞았다. **같은 시간을 두 배로 쪼개는 것**이 문제였다.

  뿌리: 자동 스타일 선택이 `target_seconds`를 **안 봤다**(실적순으로만 골랐다).
  게이트는 칸 수를 만들지 않는다 — 스파인의 `beat_roles`가 먼저 정한다(아스트라 지적).
  그래서 게이트가 아니라 **고르는 층**에서 푼다.

■ 못박는 계약
  · 후보를 **버리지 않는다** — 4칸짜리가 없는 카테고리면 그 소재가 통째로 막힌다
  · 칸 수가 같으면 원래 순서(실적순)를 지킨다
  · 칸 정보를 못 읽어도 죽지 않는다
"""
from shopping_shorts.app import _sort_spines_by_seconds as sort_by_sec


def _sp(i, n):
    return {"id": i, "beat_roles": '["r"]' if n == 1 else "[" + ",".join(['"r"'] * n) + "]"}


def test_25초면_4칸짜리가_먼저():
    """★사장님이 받은 그 대본이 8칸이었다."""
    out = sort_by_sec([_sp(1, 8), _sp(2, 4), _sp(3, 5)], 25)
    assert out[0]["id"] == 2


def test_긴_영상이면_칸이_많은_것이_먼저():
    """초를 실제로 본다는 증거 — 상수를 박아둔 게 아니다."""
    out = sort_by_sec([_sp(1, 8), _sp(2, 4), _sp(3, 5)], 50)
    assert out[0]["id"] == 1


def test_후보를_하나도_안_버린다():
    """★버리면 4칸짜리 없는 카테고리는 대본이 아예 안 나온다."""
    src = [_sp(1, 8), _sp(2, 9), _sp(3, 12)]
    assert len(sort_by_sec(src, 25)) == 3


def test_칸수가_같으면_원래_순서를_지킨다():
    """실적순이 2차 기준 — 잘 나가는 것이 먼저다."""
    out = sort_by_sec([_sp(7, 4), _sp(8, 4), _sp(9, 4)], 25)
    assert [x["id"] for x in out] == [7, 8, 9]


def test_칸정보가_없거나_깨져도_죽지_않는다():
    out = sort_by_sec([{"id": 1}, {"id": 2, "beat_roles": "깨진값"}, _sp(3, 4)], 25)
    assert out[0]["id"] == 3 and len(out) == 3


def test_빈_목록도_안전():
    assert sort_by_sec([], 25) == []
    assert sort_by_sec(None, 25) == []


def test_이상한_초가_와도_죽지_않는다():
    for sec in (None, 0, "abc", -5, 9999):
        assert len(sort_by_sec([_sp(1, 4), _sp(2, 8)], sec)) == 2
