# -*- coding: utf-8 -*-
"""유튜브 썸네일을 카드 크기에 맞는 규격으로 낮춰 받는다 (2026-08-30).

사장님 제보: "유튜브 카테고리 탭 들어가면 썸네일 로딩이 엄청 오래 걸린다."

★실측(2026-08-30, 같은 영상 -abOFBl05S4):
    oardefault 168,835B / sddefault 52,222B / hqdefault 12,643B / mqdefault 6,517B
  수집된 유튜브 8,000건이 **전량 oardefault** 였다. 카드는 CSS(.card img)가
  `aspect-ratio:9/16`으로 그리므로 원본이 1280×720이든 480×360이든 **화면 크기는 같다**.
  즉 165KB는 그대로 낭비다 — 200장이면 32.2MB.

★덤: `_yt_thumb_alternates` 주석에 이미 적혀 있듯 oardefault는 **7.5%가 404**다
  (영상마다 있을 수도 없을 수도 한 변형). hqdefault는 사실상 항상 있다.
  즉 이 교체는 속도만이 아니라 **검은 카드도 같이 줄인다**.

★서버에서 바꾼다(0순위-B): 프론트 thumbURL만 고치면 다른 호출부(도서관·트렌드·
  히트작 등 index.html에만 9곳)가 제각각 남는다. 프록시 한 곳에서 정하면 전부 적용된다.
"""
from shopping_shorts.app import _yt_thumb_downscale


YT = "https://i.ytimg.com/vi/-abOFBl05S4/oardefault.jpg"


def test_oardefault_downgraded_to_hq():
    """무거운 oardefault → hqdefault(13배 작다)."""
    assert _yt_thumb_downscale(YT) == "https://i.ytimg.com/vi/-abOFBl05S4/hqdefault.jpg"


def test_maxres_and_sd_also_downgraded():
    """maxres·sd도 카드에는 과하다 — 같이 낮춘다."""
    for name in ("maxresdefault.jpg", "sddefault.jpg"):
        u = "https://i.ytimg.com/vi/ABC123/%s" % name
        assert _yt_thumb_downscale(u).endswith("/hqdefault.jpg")


def test_video_id_is_preserved():
    """★영상ID가 바뀌면 카드↔영상이 어긋난다(렌즈썸네일_구글짝지음과 같은 종류의 사고)."""
    assert "/vi/-abOFBl05S4/" in _yt_thumb_downscale(YT)


def test_already_small_is_untouched():
    """이미 작은 규격은 그대로 — 더 낮추면 화질만 잃는다."""
    for name in ("hqdefault.jpg", "mqdefault.jpg"):
        u = "https://i.ytimg.com/vi/ABC123/%s" % name
        assert _yt_thumb_downscale(u) == u


def test_non_youtube_untouched():
    """인스타·틱톡·핀터레스트 경로는 건드리지 않는다(회귀 0)."""
    for u in ("https://scontent.cdninstagram.com/v/t51/abc.jpg?oe=123",
              "https://p16.tiktokcdn.com/obj/xyz",
              "https://i.pinimg.com/236x/aa/bb.jpg"):
        assert _yt_thumb_downscale(u) == u


def test_unknown_shape_untouched():
    """`/vi/<id>/<name>.jpg` 모양이 아니면 손대지 않는다(모르는 건 그대로)."""
    u = "https://i.ytimg.com/an_webp/ABC/mqdefault_6s.webp"
    assert _yt_thumb_downscale(u) == u


def test_query_string_is_kept():
    """?sqp=... 같은 쿼리가 붙어 있어도 잃지 않는다."""
    got = _yt_thumb_downscale("https://i.ytimg.com/vi/ABC/oardefault.jpg?sqp=xy&rs=z")
    assert got == "https://i.ytimg.com/vi/ABC/hqdefault.jpg?sqp=xy&rs=z"


def test_empty_is_safe():
    assert _yt_thumb_downscale("") == ""
    assert _yt_thumb_downscale(None) is None
