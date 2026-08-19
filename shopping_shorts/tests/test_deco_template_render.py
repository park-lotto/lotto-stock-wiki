"""템플릿 합성 — 전체/첫장면, 그리고 ★사장님 로고와 공존하는가.

템플릿이 overlay 슬롯을 덮어쓰면 사장님이 올린 로고가 조용히 사라진다.
"""
from shopping_shorts import video_assemble as va


def test_template_layer_full_has_no_enable():
    """전체 구간이면 enable=이 붙으면 안 된다(붙으면 그 구간에만 뜬다)."""
    layers = [{"_abspath": "/tmp/tpl_01.png", "x": 50, "y": 50, "alpha": 1}]
    _inp, fc, _v, _i = va._motion_layer_filters(layers, 1, "v0")
    joined = ";".join(fc)
    assert "overlay=" in joined
    assert "enable=" not in joined


def test_template_layer_first_scene_has_enable_window():
    layers = [{"_abspath": "/tmp/tpl_01.png", "x": 50, "y": 50, "alpha": 1,
               "start": 0, "dur": 3.5}]
    _inp, fc, _v, _i = va._motion_layer_filters(layers, 1, "v0")
    joined = ";".join(fc)
    assert "enable='between(t,0.000,3.500)'" in joined


def test_template_and_logo_both_composited():
    """★둘 다 얹혀야 한다. 하나가 다른 하나를 대체하면 회귀다."""
    layers = [
        {"_abspath": "/tmp/tpl_01.png", "x": 50, "y": 50, "alpha": 1},
        {"_abspath": "/tmp/logo.png", "x": 80, "y": 10, "alpha": 0.9},
    ]
    inp, fc, vcur, idx = va._motion_layer_filters(layers, 1, "v0")
    assert inp.count("-i") == 2, "레이어 2개인데 입력이 2개가 아니다"
    assert ";".join(fc).count("overlay=") == 2
    assert vcur == "mlv1" and idx == 3


def test_layer_without_abspath_is_skipped():
    """경로 해석에 실패한 레이어를 그대로 태우면 ffmpeg가 통째로 죽는다."""
    inp, fc, vcur, _i = va._motion_layer_filters(
        [{"x": 50, "y": 50}], 1, "v0")
    assert inp == [] and fc == [] and vcur == "v0"
