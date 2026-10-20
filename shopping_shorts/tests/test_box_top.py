# -*- coding: utf-8 -*-
"""그림 칸 윗변(narr_video.box_top) — 자막이 그림 안에서 시작하는 틀은 원본 자리 그대로(10-20 회원 실시험: 얜샷템 창 1080 중 870px 흰 바탕).
게시글형(자막이 그림 위 빈칸)은 10-16 조율대로 자막 바로 밑에 붙인다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.narr_video import box_top  # noqa: E402


def test_caption_over_picture_keeps_box():
    assert box_top(420, 1292, True, cap_top=1206) == 420        # 얜샷템: 창 y420 · 자막 y1206(영상 위에 겹침)
    assert box_top(559, 1488, True, cap_top=1384) == 559        # 숏템리폿


def test_caption_above_picture_anchors_under_caption():
    assert box_top(690, 753, True, cap_top=555) == 753          # 연예인꿀맛(게시글형) — 자막 밑으로
    assert box_top(750, 658, True, cap_top=488) == 658          # 제품비하인드썰형 — 빈칸 위로 끌어올림(10-16)


def test_no_caption_info_is_old_behavior_and_no_anchor_pushes_down():
    assert box_top(420, 1292, True) == 1292
    assert box_top(420, 1292, False) == 1292 and box_top(1400, 1292, False) == 1400
