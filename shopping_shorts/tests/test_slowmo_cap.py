"""P1(장면스파인): 무제한 슬로우모션 제거 — 상한 1.15배 + 초과분은 마지막 프레임 정지(freeze).

_speed_and_freeze(src_dur, out_dur, max_slowmo)는 순수함수:
비트 나레이션 길이(out_dur)를 소스 구간 길이(src_dur)로 채울 때,
움직이는 재생은 최대 max_slowmo배까지만 늘리고 나머지는 정지프레임으로 떠안는다.
반환: (play_out, freeze). play_out + freeze == out_dur (길이·오디오 싱크 보존).
"""
import pytest

from shopping_shorts.video_assemble import _speed_and_freeze, _MAX_SLOWMO


def test_no_stretch_when_out_le_src():
    # 소스가 충분히 길면 늘릴 필요 없음 — 그대로.
    play, freeze = _speed_and_freeze(3.0, 2.0)
    assert (play, freeze) == (2.0, 0.0)


def test_gentle_slowmo_within_cap_untouched():
    # 1.15배 이내면 그대로 완만한 슬로우 허용(정지 없음).
    play, freeze = _speed_and_freeze(2.0, 2.2)   # factor 1.1 ≤ 1.15
    assert freeze == 0.0
    assert play == pytest.approx(2.2)


def test_over_cap_splits_into_capped_play_plus_freeze():
    # 2.0초 소스로 3.0초를 채워야 함(factor 1.5, 상한 초과):
    # 재생은 2.0*1.15=2.3초까지만, 나머지 0.7초는 정지프레임.
    play, freeze = _speed_and_freeze(2.0, 3.0, max_slowmo=1.15)
    assert play == pytest.approx(2.3)
    assert freeze == pytest.approx(0.7)
    # 총 길이 보존(오디오·자막 싱크 불변).
    assert play + freeze == pytest.approx(3.0)


def test_default_cap_is_1_15():
    assert _MAX_SLOWMO == 1.15


def test_playback_factor_never_exceeds_cap():
    # 극단: 0.5초 소스로 5초 채우기 → 재생 0.5*1.15=0.575, freeze 나머지.
    play, freeze = _speed_and_freeze(0.5, 5.0)
    assert play / 0.5 <= _MAX_SLOWMO + 1e-9
    assert play + freeze == pytest.approx(5.0)
