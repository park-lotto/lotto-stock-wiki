"""가림막 흐림 — 그림이 아니라 **렌더가 영상에** 먹인다(2026-08-28).

★왜 계약이 필요한가: 흐림은 경로가 둘로 갈린다(PNG=색 막 / ffmpeg=흐림).
  한쪽만 고치면 "화면엔 흐린데 완성본은 선명" 또는 그 반대가 된다.
  두 경로가 **같은 모양 함수**를 쓴다는 것을 여기서 못 박는다.
"""
import pathlib

import pytest

from shopping_shorts import deco_frame


def _spec(masks, **kw):
    d = {"preset": "plain_black", "bar_h": 0, "bottom_h": 0, "masks": masks}
    d.update(kw)
    return d


BLUR = {"l": 20, "t": 40, "w": 60, "h": 12, "shape": "rect",
        "fx": "blur", "color": "#000000", "op": 100, "soft": 50, "rot": 0}


def test_blur_is_not_painted_into_the_png():
    """★그림에 그리면 흐림이 아니라 '검은 막'이 하나 더 생긴다."""
    im = deco_frame.render(_spec([BLUR]))
    assert im.getpixel((540, 900))[3] == 0, "흐림 자리는 PNG에서 투명이어야 한다"


def test_blurdark_paints_only_the_darkening():
    """흐림+어둡게는 '어둡게'만 그림이 맡는다(흐림은 렌더)."""
    im = deco_frame.render(_spec([dict(BLUR, fx="blurdark")]))
    px = im.getpixel((540, 900))
    assert 0 < px[3] < 255, "반투명 검정이어야 한다"
    assert px[:3] == (0, 0, 0)


def test_solid_still_painted():
    """회귀 차단 — 단색은 지금까지처럼 그림이 그린다."""
    im = deco_frame.render(_spec([dict(BLUR, fx="solid")]))
    assert im.getpixel((540, 900))[3] == 255


def test_blur_mask_holds_only_blur_masks():
    m = deco_frame.render_blur_mask(_spec([
        BLUR,                                   # 흐림 → 들어감
        dict(BLUR, t=70, fx="solid"),           # 단색 → 안 들어감
    ]))
    assert m is not None
    assert m.getpixel((540, 900))[3] == 255, "흐림 자리는 칠해져야 한다"
    assert m.getpixel((540, 1450))[3] == 0, "단색 자리는 비어 있어야 한다"


def test_no_mask_when_no_blur():
    assert deco_frame.render_blur_mask(_spec([dict(BLUR, fx="solid")])) is None
    assert deco_frame.render_blur_mask_to(_spec([dict(BLUR, fx="fade")])) is None


def test_mask_follows_the_same_shape_rule():
    """★마스크와 색 막이 **같은 함수**로 그려진다 — 보이는 자리 = 흐려지는 자리."""
    pill = dict(BLUR, shape="pill")
    m = deco_frame.render_blur_mask(_spec([pill]))
    # 알약이면 좌우 끝 모서리는 둥글게 잘려 비어 있다(사각이면 칠해져 있다)
    x0 = int(1080 * pill["l"] / 100.0) + 2
    y0 = int(1920 * pill["t"] / 100.0) + 2
    assert m.getpixel((x0, y0))[3] < 128, "알약 모서리는 비어야 한다"
    assert m.getpixel((540, 900))[3] == 255


def test_sigma_scales_with_soft_and_is_strong_enough():
    """실측: 1080폭·70px 글자에서 40이면 형태가 남고 80이면 사라진다."""
    weak = deco_frame.blur_sigma([dict(BLUR, soft=0)])
    strong = deco_frame.blur_sigma([dict(BLUR, soft=100)])
    assert weak >= 25 and strong >= 78 and strong > weak


def test_sigma_zero_without_blur():
    assert deco_frame.blur_sigma([dict(BLUR, fx="solid")]) == 0


def test_sigma_takes_the_strongest():
    """막마다 다른 세기를 줄 수 없다 — 가장 센 것으로 맞춘다(약한 쪽에 맞추면 안 가려진다)."""
    v = deco_frame.blur_sigma([dict(BLUR, soft=10), dict(BLUR, t=70, soft=90)])
    assert v == deco_frame.blur_sigma([dict(BLUR, soft=90)])


def test_mask_cache_path_differs_from_frame():
    """★같은 이름에 저장하면 마스크가 틀 그림을 덮어쓴다."""
    sp = _spec([BLUR])
    assert deco_frame.blur_mask_path(sp) != deco_frame.cache_path(sp)


def test_template_layer_carries_the_mask():
    """mix_pipeline이 렌더에 넘겨주지 않으면 흐림은 조용히 사라진다."""
    from shopping_shorts import mix_pipeline
    out = mix_pipeline._template_layer({"frame": _spec([BLUR])})
    assert out and out.get("blur_mask") and pathlib.Path(out["blur_mask"]).exists()
    assert out.get("blur_sigma", 0) > 0


def test_template_layer_has_no_mask_without_blur():
    from shopping_shorts import mix_pipeline
    out = mix_pipeline._template_layer({"frame": _spec([dict(BLUR, fx="solid")])})
    assert out and "blur_mask" not in out
