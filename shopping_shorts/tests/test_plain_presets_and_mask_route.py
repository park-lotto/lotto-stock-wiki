"""빈 틀 프리셋 + 가림막 쿼리 배선 계약(2026-08-28).

★왜 테스트가 필요한가: 가림막 값은 **배열**인데 틀 그림은 쿼리스트링으로 온다.
  라우트가 JSON을 안 풀면 `_norm_masks`가 조용히 빈 목록으로 떨어져
  "화면에선 만들었는데 완성본엔 없다"가 된다 — 조용한 폴백은 제일 나쁜 실패다.
"""
import json

import pytest

from shopping_shorts import deco_frame


PLAIN = ("plain_black", "plain_white", "plain_coral", "plain_navy")


@pytest.mark.parametrize("pid", PLAIN)
def test_plain_preset_has_no_ui_parts(pid):
    """빈 틀 = 색띠만. 아이콘·가운데 글자가 하나라도 있으면 '빈 틀'이 아니다."""
    p = deco_frame.PRESETS[pid]
    assert p["left_icon"] == "none"
    assert p["right_icon"] == "none"
    assert p["center_kind"] == "없음"
    assert p["name"].startswith("빈 틀")


@pytest.mark.parametrize("pid", PLAIN)
def test_plain_preset_renders_transparent_middle(pid):
    """가운데는 **투명**이어야 영상이 보인다(불투명하면 영상을 통째로 가린다)."""
    im = deco_frame.render({"preset": pid, "bar_h": 190, "bottom_h": 160})
    assert im.mode == "RGBA"
    assert im.getpixel((540, 960))[3] == 0        # 한가운데 = 투명
    assert im.getpixel((540, 50))[3] == 255       # 위 띠 = 불투명
    assert im.getpixel((540, 1870))[3] == 255     # 아래 띠 = 불투명


def _route_spec(q):
    """/api/produce/frame.png 가 쿼리를 spec으로 푸는 규칙 그대로."""
    spec = {k: q.get(k) for k in deco_frame.DEFAULTS if k in q}
    for b in ("ad_badge", "icons"):
        if b in spec:
            spec[b] = str(spec[b]).lower() in ("1", "true", "on", "yes")
    if "masks" in spec:
        try:
            spec["masks"] = json.loads(spec["masks"] or "[]")
        except Exception:
            spec["masks"] = []
    return spec


def test_masks_query_is_parsed_not_dropped():
    m = [{"l": 6, "t": 44, "w": 88, "h": 12, "shape": "round",
          "fx": "fade", "color": "#000000", "op": 100, "soft": 35, "rot": 0}]
    spec = _route_spec({"preset": "news_coral", "masks": json.dumps(m)})
    assert isinstance(spec["masks"], list) and len(spec["masks"]) == 1
    assert deco_frame.normalize(spec)["masks"], "정규화에서 사라지면 그림에도 안 나온다"


def test_broken_masks_query_does_not_500():
    spec = _route_spec({"preset": "news_coral", "masks": "{망가진 값"})
    assert spec["masks"] == []


def test_masks_change_the_cached_image():
    """같은 자리에 저장되면 가림막을 켜도 **옛 그림**이 나온다(캐시 사고)."""
    base = {"preset": "news_coral", "bar_h": 190}
    m = [{"l": 10, "t": 40, "w": 80, "h": 10}]
    assert (deco_frame.cache_key(base)
            != deco_frame.cache_key(dict(base, masks=m)))


def test_mask_actually_covers_pixels():
    """계약이 아니라 **그림**으로 확인한다 — 덮였나."""
    spec = {"preset": "news_coral", "bar_h": 0,
            "masks": [{"l": 20, "t": 40, "w": 60, "h": 20,
                       "shape": "rect", "fx": "solid", "color": "#000000",
                       "op": 100, "soft": 0, "rot": 0}]}
    im = deco_frame.render(spec)
    assert im.getpixel((540, 960)) == (0, 0, 0, 255)   # 막 안쪽 = 검게 덮임
    assert im.getpixel((30, 960))[3] == 0              # 막 바깥 = 그대로 투명


# ── 띠 끝부분 효과(2026-08-28 사장님 시안 ②) ─────────────────────────────────
BAR_FX = ("solid", "grad", "blur", "blurdark")


def _alpha_col(spec, xs=540):
    im = deco_frame.render(spec)
    return [im.getpixel((xs, y))[3] for y in (0, 150, 190, 260, 400)]


def test_bar_fx_default_does_not_change_old_frames():
    """★기본이 solid라 지금까지의 그림은 **하나도** 안 바뀌어야 한다(회귀 차단)."""
    base = {"preset": "news_coral", "bar_h": 190, "bottom_h": 160}
    assert (deco_frame.cache_key(base)
            == deco_frame.cache_key(dict(base, bar_fx="solid", bar_soft=0)))


@pytest.mark.parametrize("fx", BAR_FX)
def test_bar_fx_is_accepted(fx):
    s = deco_frame.normalize({"preset": "news_coral", "bar_fx": fx, "bar_soft": 40})
    assert s["bar_fx"] == fx and s["bar_soft"] == 40


def test_unknown_bar_fx_falls_back_to_solid():
    """이름이 틀렸는데 조용히 딴 효과가 나가면 더 나쁘다."""
    assert deco_frame.normalize({"preset": "news_coral", "bar_fx": "없는효과"})["bar_fx"] == "solid"


def test_grad_fades_the_inner_edge():
    base = {"preset": "plain_black", "bar_h": 190, "bar_soft": 40, "bar_color": "#2b2b2b"}
    a = _alpha_col(dict(base, bar_fx="solid"))
    g = _alpha_col(dict(base, bar_fx="grad"))
    assert a[1] == 255 and 0 < g[1] < 255, "안쪽이 흘러야 한다"
    assert a[0] == g[0] == 255, "바깥쪽 끝(화면 맨 위)은 그대로 진해야 한다"


def test_blur_softens_past_the_edge_but_keeps_outer_edge():
    """★블러는 바깥으로도 번진다 — 화면 맨 위까지 옅어지면 띠가 통째로 흐려진다."""
    base = {"preset": "plain_black", "bar_h": 190, "bar_soft": 40, "bar_color": "#2b2b2b"}
    b = _alpha_col(dict(base, bar_fx="blur"))
    assert b[0] == 255, "맨 위는 불투명이어야 한다"
    assert 0 < b[3] < 255, "경계 바깥(y=260)까지 부드럽게 이어져야 한다"


def test_blurdark_is_darker_than_blur():
    base = {"preset": "plain_black", "bar_h": 190, "bar_soft": 40, "bar_color": "#808080"}
    b = deco_frame.render(dict(base, bar_fx="blur")).getpixel((540, 50))
    d = deco_frame.render(dict(base, bar_fx="blurdark")).getpixel((540, 50))
    assert d[0] < b[0], "어둡게가 더 어두워야 한다"


def test_bottom_bar_uses_the_same_rule():
    """위·아래가 다른 규칙으로 잘리면 언젠가 어긋난다(0순위-B)."""
    base = {"preset": "plain_black", "bar_h": 200, "bottom_h": 200,
            "bar_soft": 40, "bar_fx": "grad", "bar_color": "#2b2b2b"}
    im = deco_frame.render(base)
    top = [im.getpixel((540, y))[3] for y in (0, 150, 199)]
    bot = [im.getpixel((540, 1919 - y))[3] for y in (0, 150, 199)]
    assert top == bot
