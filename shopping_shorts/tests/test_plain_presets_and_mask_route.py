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
