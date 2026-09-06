# -*- coding: utf-8 -*-
"""담은 조각이 규칙보다 많으면 **조각 수를 따른다** — 손으로 담은 건 다 나온다.

★왜(2026-09-06 사장님 "한 개를 더 올리면 예전처럼 구절맞춤 3개씩 안 되나"):
  오늘 넣은 규칙(칸 길이가 컷 개수를 정함)이 자동 배분에는 맞지만, 사장님이
  **직접 조각을 더 담았을 때까지** 2컷으로 묶어버렸다. 3.6초 칸에 조각 3개를
  담아도 컷은 2개라 하나가 안 나왔다.
  오늘 ✋에서 정한 원칙과 같다 — **자동은 넉넉히, 수동은 존중**.

단, 자막 구절이 모자라면 쪼갤 자리가 없으므로 거기까지만 늘어난다.
"""
import pytest

from shopping_shorts.video_assemble import cuts_for_beat


class Test조각수가_규칙을_이긴다:
    def test_조각이_더_많으면_조각수를_따른다(self):
        # 3.6초 = 규칙상 2컷인데, 담은 조각이 3개면 3컷
        assert cuts_for_beat(3.6, n_seg=3) == 3

    def test_조각이_적으면_규칙대로(self):
        assert cuts_for_beat(3.6, n_seg=1) == 2      # 규칙 2컷을 유지
        assert cuts_for_beat(3.6, n_seg=2) == 2

    def test_짧은_칸도_조각수를_존중한다(self):
        assert cuts_for_beat(1.5, n_seg=3) == 3      # 규칙 1컷이지만 담았으면 나온다

    def test_안_넘기면_종전과_같다(self):
        """n_seg를 안 주는 옛 호출부는 하나도 안 바뀐다(하위호환)."""
        for sec, want in [(1.5, 1), (3.0, 2), (6.3, 3)]:
            assert cuts_for_beat(sec) == want

    @pytest.mark.parametrize("bad", [0, -1, None])
    def test_이상한_조각수는_무시한다(self, bad):
        assert cuts_for_beat(3.0, n_seg=bad) == 2
