"""재료 문턱 — "재료다 = 영상이 있고 5점 이상"을 못박는다.

2026-08-18 실측 128건으로 문턱 5를 산출했다. 근거는 분위수가 아니라 점수 구성이었다:
문턱 4면 영상 없는 17건이 섞이고(믹스 재료가 안 된다), 5면 남은 58건이 전부 영상,
7이면 영상 63건 중 35건만 남아 너무 좁다.

★단 "5점 = 영상 있음"은 점수만으로는 보장되지 않는다 — 영상 없이도
  쿠팡(2)+캡션(2)+자막없음(1)로 5점이 된다. 그래서 판정은 is_material()이 하고,
  이 파일이 그 성질을 지킨다. (이 함정은 테스트가 먼저 잡았다)
"""
from shopping_shorts import threads_parse as tp


def _post(video=False, coupang=False, caption_len=0):
    return {
        "media_kind": "video" if video else "image",
        "coupang_url": "https://link.coupang.com/a/x" if coupang else "",
        "caption": "가" * caption_len,
    }


def test_영상이_없으면_점수가_문턱을_넘어도_재료가_아니다():
    """★핵심 회귀 검사. 쿠팡+긴캡션+자막없음이면 영상 없이 5점이 나온다."""
    p = _post(video=False, coupang=True, caption_len=tp.CAPTION_MIN)
    assert tp.quality_score(p, text_level="none") >= tp.MATERIAL_MIN_QUALITY  # 점수는 넘지만
    assert tp.is_material(p, text_level="none") is False                      # 재료는 아니다


def test_영상이_있고_문턱을_넘으면_재료다():
    assert tp.is_material(_post(video=True, caption_len=tp.CAPTION_MIN)) is True


def test_영상만_있고_점수가_모자라면_재료가_아니다():
    """영상(3)뿐이면 3점 — 캡션도 쿠팡도 없는 건 말맛 재료가 안 된다(실측 5건)."""
    p = _post(video=True, caption_len=0)
    assert tp.quality_score(p) < tp.MATERIAL_MIN_QUALITY
    assert tp.is_material(p) is False


def test_영상없는_쿠팡글은_4점이고_걸러진다():
    """실측 17건이 이 구간(쿠팡2+캡션2, 영상 없음)이었다."""
    p = _post(video=False, coupang=True, caption_len=tp.CAPTION_MIN)
    assert tp.quality_score(p) == 4
    assert tp.is_material(p) is False


def test_문턱값이_5다():
    """산출 결과를 고정한다 — 바꾸려면 표본을 다시 재고 근거를 주석에 남겨라."""
    assert tp.MATERIAL_MIN_QUALITY == 5


def test_이상한_입력에도_안죽는다():
    assert tp.is_material(None) is False
    assert tp.is_material({}) is False
