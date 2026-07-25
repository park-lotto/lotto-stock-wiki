"""sub_region 지워진 자막 영역 감지 — 순수 numpy 코어 테스트(ffmpeg 불필요)."""
import numpy as np

from shopping_shorts.sub_region import _bbox_from_frames, pick_primary

H, W = 480, 270


def _blank():
    return np.full((H, W), 120, dtype=np.uint8)


def test_fixed_bottom_band_detected_at_bottom_center():
    """하단 밴드가 모든 프레임에서 원본↔클린 다르면 → 박스가 하단 중앙에 잡힌다."""
    orig, clean = [], []
    for _ in range(8):
        a = _blank()
        # 하단(약 78~90%) 가로 중앙(20~80%)에 '자막'이 있는 원본
        a[int(H * 0.78):int(H * 0.90), int(W * 0.20):int(W * 0.80)] = 255
        b = _blank()  # 클린본은 자막이 지워져 배경만
        orig.append(a)
        clean.append(b)
    box = _bbox_from_frames(orig, clean)
    assert box is not None
    assert 40 < box["x_pct"] < 60          # 가로 중앙
    assert 78 < box["y_pct"] < 92          # 하단
    assert box["w_pct"] > 40 and box["h_pct"] > 5
    assert box["score"] > 0


def test_no_difference_returns_none():
    """원본=클린(자막 없던 영상)이면 None."""
    frames = [_blank() for _ in range(8)]
    assert _bbox_from_frames(frames, [f.copy() for f in frames]) is None


def test_moving_difference_filtered_by_frequency():
    """프레임마다 다른 위치의 변화(움직이는 배경 잔차)는 저빈도로 걸러져 None."""
    orig, clean = [], []
    for i in range(8):
        a = _blank()
        b = _blank()
        # 매 프레임 다른 x위치에만 차이 → 어떤 픽셀도 절반 이상 프레임에서 바뀌지 않음
        x = int(W * (0.1 + 0.09 * i))
        b[100:120, x:x + 10] = 255
        orig.append(a)
        clean.append(b)
    assert _bbox_from_frames(orig, clean) is None


def test_tiny_speck_filtered_by_min_area():
    """지속적이어도 아주 작은 점은 min_area로 잡음 처리 → None."""
    orig, clean = [], []
    for _ in range(8):
        a = _blank()
        b = _blank()
        b[10:12, 10:12] = 255   # 2x2 = 화면의 0.003% 수준
        orig.append(a)
        clean.append(b)
    assert _bbox_from_frames(orig, clean) is None


def test_pick_primary_selects_max_score():
    """소스 여러 박스 중 score 최대가 1번."""
    a = {"x_pct": 50, "y_pct": 84, "w_pct": 60, "h_pct": 10, "score": 6.0}
    b = {"x_pct": 30, "y_pct": 20, "w_pct": 20, "h_pct": 8, "score": 1.6}
    assert pick_primary([b, a, None]) is a
    assert pick_primary([None, None]) is None
    assert pick_primary([]) is None
