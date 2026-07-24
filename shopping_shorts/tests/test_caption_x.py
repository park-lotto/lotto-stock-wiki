"""자막 가로위치(x_pct) 배선 — style.x_pct가 최종 drawtext x= 좌표에 반영되는지.

예전엔 _caption_drawtexts가 _segmented_drawtext에 x=50을 하드코딩해, UI로 자막을 옮겨도
최종 렌더는 항상 중앙이었다(2026-07-25 수정). 이 테스트가 그 회귀를 막는다.
"""
import re

from shopping_shorts.video_assemble import _caption_drawtexts


def _first_x(parts):
    """drawtext 필터 리스트에서 첫 x= 정수값을 뽑는다."""
    for p in parts:
        m = re.search(r"(?:^|:)x=(-?\d+)", p)
        if m:
            return int(m.group(1))
    return None


def test_x_pct_shifts_caption_left_and_right(tmp_path):
    narration = "안녕하세요"
    common = dict(narration=narration, dur=2.0, work=tmp_path, idx=0)
    left = _caption_drawtexts(**common, style={"x_pct": 20, "y_pct": 84})
    center = _caption_drawtexts(**common, style={"x_pct": 50, "y_pct": 84})
    right = _caption_drawtexts(**common, style={"x_pct": 80, "y_pct": 84})
    xl, xc, xr = _first_x(left), _first_x(center), _first_x(right)
    assert xl is not None and xc is not None and xr is not None
    assert xl < xc < xr, f"x_pct가 x좌표에 반영 안됨: {xl} < {xc} < {xr}"


def test_x_pct_default_is_center(tmp_path):
    """x_pct 미지정이면 종전대로 중앙(50%) 기준."""
    narration = "테스트"
    no_x = _caption_drawtexts(narration=narration, dur=2.0, work=tmp_path, idx=0,
                              style={"y_pct": 84})
    fifty = _caption_drawtexts(narration=narration, dur=2.0, work=tmp_path, idx=0,
                               style={"x_pct": 50, "y_pct": 84})
    assert _first_x(no_x) == _first_x(fifty)
