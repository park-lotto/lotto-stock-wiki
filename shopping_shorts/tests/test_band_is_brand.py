# -*- coding: utf-8 -*-
"""고정 띠 역할 판단 한 곳(to_frame.band_is_brand) — 맨 위 좁은 왼쪽 띠 = 로고(채널 표식). 실측(스냅봤니 Z956 11-06): 로고 띠 194~318 잉크 x≈100~420(1080폭),
제목 줄 띠 332~411·424~501 은 가운데 정렬·폭 80%+."""
from tools.calcopy.engine import to_frame as T


def test_top_left_narrow_band_is_brand():
    assert T.band_is_brand((194, 318), (100, 420), 1080, 1920, first=True)          # 로고+채널명
    assert not T.band_is_brand((332, 411), (110, 970), 1080, 1920, first=False)     # 제목 줄
    assert not T.band_is_brand((194, 318), (380, 700), 1080, 1920, first=True)      # 맨 위라도 가운데 정렬 짧은 제목은 제목
    assert T.band_is_brand((40, 90), (400, 680), 1080, 1920)                        # 옛 규칙: 화면 맨 위 6% 좁은 띠([광고])
