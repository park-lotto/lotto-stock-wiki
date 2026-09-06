# -*- coding: utf-8 -*-
"""칸 길이로 컷 개수를 정한다 — 잘게 썰려 "정신없다"던 것을 막는다.

★왜(2026-09-06 사장님 "컷이 너무 잘게 썰려나오는게 다들 불만이야 정신없다고"):
  구절 맞춤은 컷 개수를 **자막 구절 수**로 정했다. 서버가 자막을 8자로 자르니
  3.0초 칸이 구절 4개로 갈라져 컷이 0.75초씩 됐다.
  실측(대본 1,013구간): 컷의 **71%가 1초 미만**, 중앙값 0.88초.

★규칙(사장님): 2초 미만 1컷 / 2초 이상은 자연스러운 중간에서 2컷.
  실측상 칸의 95%가 4.5초 이하라 그 위만 3컷으로 둔다.
  적용 시: 중앙값 1.50초, 1초 미만 **0%**, 1.2~1.8초 안에 66%.

★쪼개는 자리는 **자막 구절 경계**를 쓴다 — 새 판정을 만들지 않는다(0순위-B).
  구절 경계는 문장부호·어절을 이미 본 결과라 그 자체가 "자연스러운 자리"다.
"""
import pytest

from shopping_shorts.video_assemble import cuts_for_beat, pick_split_bounds


class Test컷개수:
    @pytest.mark.parametrize("sec, want", [
        (0.9, 1), (1.5, 1), (1.99, 1),      # 2초 미만 = 1컷
        (2.0, 2), (3.0, 2), (4.0, 2),        # 2~4.0초 = 2컷
        (4.1, 3), (4.3, 3), (6.3, 3), (7.4, 3),   # 4.0초 초과 = 3컷
    ])
    def test_칸길이로_정한다(self, sec, want):
        assert cuts_for_beat(sec) == want

    def test_길이가_이상하면_1컷(self):
        for bad in (0, -1, None):
            assert cuts_for_beat(bad) == 1


class Test쪼개는자리:
    def test_구절경계중_가운데에_가까운곳을_고른다(self):
        # 6.0초 칸, 구절 경계 4개 → 2컷이면 3.0초에 가장 가까운 2.9를 고른다
        out = pick_split_bounds([0, 1.2, 2.9, 4.4, 6.0], 6.0, 2)
        assert out == [0, 2.9, 6.0]

    def test_3컷이면_3등분_지점에_가까운_둘을_고른다(self):
        out = pick_split_bounds([0, 1.0, 2.1, 3.0, 4.2, 5.1, 6.0], 6.0, 3)
        assert len(out) == 4 and out[0] == 0 and out[-1] == 6.0
        assert out[1] == 2.1 and out[2] == 4.2      # 2.0·4.0에 가장 가까운 경계

    def test_1컷이면_양끝만(self):
        assert pick_split_bounds([0, 1.0, 2.0, 3.0], 3.0, 1) == [0, 3.0]

    def test_경계가_모자라면_있는것만_쓴다(self):
        # 구절이 하나뿐이면 쪼갤 자리가 없다 → 1컷
        assert pick_split_bounds([0, 5.0], 5.0, 2) == [0, 5.0]

    def test_같은_경계를_두번_고르지_않는다(self):
        out = pick_split_bounds([0, 2.9, 6.0], 6.0, 3)   # 쓸 수 있는 내부 경계 1개
        assert len(out) == len(set(out)) and out == [0, 2.9, 6.0]

    def test_결과는_오름차순이고_양끝을_지킨다(self):
        out = pick_split_bounds([0, 0.8, 1.9, 3.1, 4.0, 5.5, 7.0], 7.0, 3)
        assert out[0] == 0 and out[-1] == 7.0
        assert all(b > a for a, b in zip(out, out[1:]))
