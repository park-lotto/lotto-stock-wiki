"""재료 품질 = 지표가 아니라 '쓸 수 있는 재료인가'로 가른다(사장님 확정).

★하드 차단을 두지 않는다 — 0점도 저장하되 뒤로 민다. 하드 차단이 재사용 폴백보다
  나쁘다는 전례가 있다.
"""
from shopping_shorts.threads_parse import quality_score

_BASE = {"media_kind": "image", "coupang_url": "", "caption": "", "video_url": ""}


def test_아무것도_없으면_0점():
    assert quality_score(_BASE) == 0


def test_영상은_3점():
    assert quality_score(dict(_BASE, media_kind="video")) == 3


def test_쿠팡링크는_2점():
    assert quality_score(dict(_BASE, coupang_url="https://link.coupang.com/a/x")) == 2


def test_캡션_40자_이상은_2점():
    assert quality_score(dict(_BASE, caption="가" * 40)) == 2
    assert quality_score(dict(_BASE, caption="가" * 39)) == 0


def test_구운자막이_없으면_1점():
    assert quality_score(_BASE, text_level="none") == 1
    assert quality_score(_BASE, text_level="heavy") == 0


def test_다_갖추면_합산된다():
    p = dict(_BASE, media_kind="video", coupang_url="https://link.coupang.com/a/x",
             caption="가" * 50)
    assert quality_score(p, text_level="none") == 8


def test_캡션이_None이어도_안_터진다():
    assert quality_score(dict(_BASE, caption=None)) == 0
