# -*- coding: utf-8 -*-
"""자막 파편 방지(2026-08-17) — 쉼표 나열에서 1~2자 구절이 번쩍이던 것을 막는다.

사장님 제보: "썸네일 자막이 넘어가는 글자들이 너무 짧게 빠르게 넘어간다."
실측(칸 4.4초): 요거트 0.40s / 계란 0.27s / 식빵 0.27s — 눈으로 못 읽는다.

두 겹으로 막는다:
  ① _CAP_MIN_DUR 0.25 → 0.7초 (표시시간 하한)
  ② 쉼표는 앞 구절이 _CAP_COMMA_MINCHARS 이상일 때만 끊는다 (분할 단계)
"""
from shopping_shorts.video_assemble import (
    _caption_segments, _caption_durations, _CAP_MIN_DUR, _CAP_COMMA_MINCHARS,
)

# 사장님 화면(job 수플레 식빵)의 실제 대사
NARR_LIST = "요거트, 계란, 전분으로 만드는 일본식 요거트 식빵, 지금 확인해보세요!"
NARR_BANG = "오븐 없이 섞어 구우면 끝! 꾸덕하고 찰진 수플레 식감이라 속도 정말 편해요."


def test_짧은_나열은_쉼표를_넘겨_붙인다():
    """'요거트,' '계란,' 이 각각 한 구절이 되면 안 된다."""
    segs = _caption_segments(NARR_LIST)
    assert "요거트" not in segs, f"1어절 파편이 남았다: {segs}"
    assert "계란" not in segs, f"1어절 파편이 남았다: {segs}"
    # 짧은 조각이 앞뒤로 묶여 구절 수가 준다(실측 5 → 3)
    assert len(segs) <= 3, f"여전히 잘게 쪼개진다: {segs}"


def test_긴_쉼표는_그대로_끊는다_회귀방지():
    """앞 구절이 충분히 길면 종전대로 쉼표에서 끊어야 한다(기존 동작 보존).

    ※ 표시용 구절에서 꼬리 문장부호는 떨어져 나가므로 쉼표 없이 비교한다.
    """
    segs = _caption_segments("빵 달라는 아이, 아무 식빵이나 사줬는데 이제는 달라졌어요")
    heads = [s.rstrip(",、") for s in segs]
    assert "빵 달라는 아이" in heads, f"긴 쉼표까지 뭉쳐버렸다: {segs}"
    assert len(segs) >= 3, f"쉼표 경계가 사라졌다: {segs}"


def test_문장부호는_짧아도_끊는다():
    """마침표·느낌표는 문장 경계라 짧아도 끊는다(쉼표와 다르다)."""
    segs = _caption_segments(NARR_BANG)
    assert any(s.endswith("끝!") for s in segs), f"문장 경계가 사라졌다: {segs}"


def test_표시시간_하한을_지킨다():
    """어떤 구절도 _CAP_MIN_DUR 미만으로 번쩍이지 않는다."""
    for narr, dur in ((NARR_LIST, 4.4), (NARR_BANG, 4.7)):
        segs = _caption_segments(narr)
        durs = _caption_durations(segs, dur)
        assert min(durs) >= _CAP_MIN_DUR - 1e-6, \
            f"{narr!r}: {min(durs):.2f}s 짜리가 있다 → {list(zip(segs, durs))}"


def test_하한을_줘도_총길이는_안_변한다():
    """하한을 채운 시간은 다른 구절에서 비례로 빼 온다 — 칸 길이는 그대로."""
    for narr, dur in ((NARR_LIST, 4.4), (NARR_BANG, 4.7),
                      ("장모님과 아이도 다 좋아했어요. 궁금한 점은 댓글 남겨주세요!", 9.7)):
        durs = _caption_durations(_caption_segments(narr), dur)
        assert abs(sum(durs) - dur) < 0.01, f"{narr!r}: 합 {sum(durs):.3f} != {dur}"


def test_상수가_읽을_수_있는_값이다():
    """0.25초처럼 사실상 없는 하한으로 되돌아가지 않게 못을 박는다."""
    assert _CAP_MIN_DUR >= 0.9, "표시시간 하한이 다시 낮아졌다"
    assert _CAP_COMMA_MINCHARS >= 4, "쉼표 최소 글자수가 다시 낮아졌다"


# ── 2차(2026-08-17): 항목 4개 이상인 나열이 중간에서 잘리던 것 ──────────────
# 사장님: "CTA쪽 바바 / 아침/빵/퐁신 다 따로따로 너무 휙휙 지나가"
NARR_CTA = ("장모님과 아이도 5kg 감량한 고소한 아침 레시피! "
            "아침, 풍신, 빵, 나도 중 댓글 남겨주시면 단백질 케이크 비법 링크 보내드려요.")


def test_긴_나열은_중간에서_안_잘린다():
    """'아침, 풍신,' 에서 끊겨 나열이 두 동강 나던 것(누적 6자 도달 순간 끊김)."""
    segs = _caption_segments(NARR_CTA)
    assert "아침, 풍신," not in segs, f"나열이 중간에서 잘렸다: {segs}"
    joined = [s for s in segs if "아침," in s]
    assert joined, f"나열 구절을 못 찾겠다: {segs}"
    # 네 항목이 한 구절에 다 들어와야 한다
    assert all(k in joined[0] for k in ("아침", "풍신", "빵", "나도")), \
        f"나열이 흩어졌다: {joined}"


def test_나열을_묶어도_한줄_폭을_안_넘는다():
    """묶기가 폭주해 화면 밖으로 나가면 안 된다."""
    from shopping_shorts.video_assemble import _CAP_LIST_MAXCHARS
    for s in _caption_segments(NARR_CTA):
        assert len(s.replace(" ", "")) <= max(_CAP_LIST_MAXCHARS, 19), \
            f"한 줄이 너무 길다: {s!r}"


def test_CTA도_하한을_지킨다():
    segs = _caption_segments(NARR_CTA)
    durs = _caption_durations(segs, 9.7)
    assert min(durs) >= _CAP_MIN_DUR - 1e-6, \
        f"{min(durs):.2f}s 짜리가 있다 → {list(zip(segs, durs))}"
    assert abs(sum(durs) - 9.7) < 0.01


def test_아주_짧은_칸은_하한보다_균등분배가_우선():
    """구절수 × 하한 > 칸 길이면 하한을 못 지킨다 — 그때도 총길이는 지켜야 한다(폭주 금지)."""
    narr = "요거트, 계란, 전분으로 만드는 일본식 요거트 식빵, 지금 확인해보세요!"
    durs = _caption_durations(_caption_segments(narr), 1.0)   # 말도 안 되게 짧은 칸
    assert abs(sum(durs) - 1.0) < 0.01, f"총길이가 어긋났다: {sum(durs)}"
    assert all(d > 0 for d in durs), f"0초 구절이 생겼다: {durs}"
