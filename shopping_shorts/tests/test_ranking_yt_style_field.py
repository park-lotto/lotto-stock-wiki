"""랭킹 항목에 yt_style을 실어 보낸다 (2026-08-19).

사장님 지시: 유튜브 탭은 **채널 스타일**로 거른다(썰쇼핑·연예인결합·레시피쇼핑).
그러려면 /api/reference가 내는 항목에 스타일 값이 실려야 한다 — 화면이 읽을 게 없으면
필터를 붙여도 전부 빈칸이 된다.

★`category`와 **나란히** 실린다(덮어쓰지 않는다). 두 축은 서로 다른 질문이라
교차 조회가 목적이다 — "썰쇼핑 중 홈템".

★채널 폴백은 `_category_of`와 같은 규칙을 따른다: 캡션으로 못 잡으면 채널에 못 박힌
스타일을 쓴다. 유튜브 제목은 밋밋할 때가 많아(이븐쇼핑 실측 12/12 '기타') 채널이
더 안정적인 신호다.
"""
from datetime import datetime, timedelta, timezone

from shopping_shorts.ranking import build_items


def _reel(code, caption, **kw):
    """★고정 날짜를 쓰지 마라 — build_items는 48h 창이고 age<0(미래)도 버린다.

    이 테스트를 처음 쓸 때 '2026-08-19T00:00:00Z'를 박았더니 그 시각이 UTC 기준
    **미래**라 age=-5.5h가 나와 전부 0건이 됐다(실측). 며칠 뒤엔 반대로 창을 벗어나
    또 깨진다 — 어느 쪽이든 시한폭탄이다(memory: 테스트_시한폭탄_침묵except).
    그래서 '지금으로부터 1시간 전'으로 만든다."""
    ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    d = {"shortCode": code, "caption": caption, "commentsCount": 5,
         "videoViewCount": 100, "timestamp": ts}
    d.update(kw)
    return d


def _none(_sc):
    """★prev_comments/prev_delta는 **콜백**이다(dict 아님).

    처음에 {}를 넘겼다가 "'dict' object is not callable"로 전부 죽었다 — 시그니처를
    안 읽고 짐작해 쓴 내 실수였다. 이력이 없다는 뜻으로 None을 준다."""
    return None


def _items(caption, meta=None):
    meta = meta or {"name": "테스트채널", "username": "t"}
    return build_items([_reel("abc", caption)], meta, _none, _none)


def test_항목에_yt_style_키가_있다():
    """없으면 화면이 읽을 게 없어 필터가 통째로 빈다."""
    items = _items("개발자도 예상 못한 미친 활용법")
    assert items and "yt_style" in items[0]


def test_썰쇼핑이_실린다():
    items = _items("제조사도 예상 못한 뜻밖의 사용법 #주방템")
    assert items[0]["yt_style"] == "썰쇼핑"


def test_연예인결합이_실린다():
    items = _items("아이유가 쓰는 화장품 추천")
    assert items[0]["yt_style"] == "연예인결합"


def test_레시피쇼핑이_실린다():
    items = _items("자취생 요리 필수템 추천")
    assert items[0]["yt_style"] == "레시피쇼핑"


def test_category를_덮어쓰지_않는다():
    """★두 축은 나란히 산다 — 교차 조회가 목적이다."""
    items = _items("제조사도 예상 못한 뜻밖의 사용법 #주방템")
    assert items[0]["yt_style"] == "썰쇼핑"
    assert items[0]["category"] == "오용형"      # 제품축은 그대로


def test_못_잡으면_빈값():
    """'기타'라는 가짜 스타일을 만들지 않는다."""
    items = _items("오늘 날씨가 좋네요")
    assert items[0]["yt_style"] == ""


def test_채널에_못박힌_스타일을_폴백으로_쓴다():
    """★유튜브 제목은 밋밋할 때가 많다(이븐쇼핑 실측: 제목만으론 12/12 '기타').

    meta에 실린 채널 스타일이 있으면 그걸 쓴다 — _category_of와 같은 규칙."""
    meta = {"name": "이븐쇼핑", "username": "even", "yt_style": "썰쇼핑"}
    items = build_items([_reel("x", "이건 진짜 신기하네요")], meta, _none, _none)
    assert items[0]["yt_style"] == "썰쇼핑"


def test_캡션_판정이_채널폴백보다_우선():
    """개별 영상이 더 정확할 때가 있다(_category_of와 같은 우선순위)."""
    meta = {"name": "어떤채널", "username": "x", "yt_style": "레시피쇼핑"}
    items = build_items([_reel("y", "아이유가 쓰는 화장품 추천")], meta, _none, _none)
    assert items[0]["yt_style"] == "연예인결합"


def test_기존_호출부를_안_깬다():
    """meta에 yt_style이 없어도 그냥 돈다(인스타 경로 = 회귀 0)."""
    items = build_items([_reel("z", "주방 정리수납 꿀템 추천")],
                        {"name": "살림템", "username": "s"}, _none, _none)
    assert items[0]["category"] == "홈템"
    assert items[0]["yt_style"] == ""
