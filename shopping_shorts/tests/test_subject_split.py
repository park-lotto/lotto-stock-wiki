# -*- coding: utf-8 -*-
"""재료에 **소재가 다른 영상**이 섞이면 걸러내는가 (2026-08-21 실사고).

`merge_sul` 주석에 이렇게 적혀 있었다:

    ⚠️ 같은 소재의 영상만 합쳐라. … 실무 호출부는 job에 담긴 영상들(같은 주제로
       사장님이 담은 것)을 넘기므로 **이 조건이 자연히 지켜진다**

그 가정이 깨졌다. 사장님이 구명 팔찌 6편 사이에 **미니 다리미** 한 편을 담자
재료에 `미니 다리미`·`다리미`·`170도 자동 온도 조절`이 그대로 섞여 들어왔다.
**적어두는 것만으로는 안 지켜진다** — 그래서 검사로 바꿨다.
"""
from shopping_shorts import spine_fill as sf


def _f(name, cat):
    return {"product_name": [name], "category_word": [cat]}


# 라이브 실측(사장님이 담아주신 7편에서 뽑힌 값). 문구를 바꾸지 마라 — 이게 증거다.
LIVE = [
    _f("손목 구명조끼", "안전용품"),
    _f("미니 다리미", "다리미"),          # ← 딴 소재
    _f("구명 손목 밴드", "구명도구"),
    _f("구명 팔찌", "구명장비"),
    _f("스마트워치", "스마트워치"),        # ← 구명 팔찌를 오인식한 편
    _f("손목 착용형 구명 장치", "안전장비"),
]


class TestSplitBySubject:
    def test_딴_소재를_걸러낸다(self):
        keep, drop = sf.split_by_subject(LIVE)
        names = [k["product_name"][0] for k in keep]
        assert "미니 다리미" not in names
        assert "손목 구명조끼" in names and "구명 팔찌" in names

    def test_다수결로_주_소재를_정한다(self):
        keep, drop = sf.split_by_subject(LIVE)
        assert len(keep) == 4 and len(drop) == 2

    def test_한_편뿐이면_그대로_통과(self):
        """비교 대상이 없다 — 걸러낼 근거도 없다."""
        keep, drop = sf.split_by_subject([LIVE[1]])
        assert keep == [LIVE[1]] and drop == []

    def test_전부_이질이면_판정을_포기한다(self):
        """★아무 편도 안 겹치면 무엇이 주 소재인지 알 수 없다 — 종전대로 전부 쓴다.
        여기서 임의로 첫 편을 고르면 멀쩡한 재료를 무더기로 버린다."""
        rows = [_f("다리미", "다리미"), _f("우산", "우산"), _f("신발", "신발")]
        keep, drop = sf.split_by_subject(rows)
        assert len(keep) == 3 and drop == []

    def test_표현이_달라도_같은_소재는_살린다(self):
        """'손목 구명조끼' ↔ '구명 손목 밴드' — 낱말 순서가 달라도 겹친다."""
        keep, _d = sf.split_by_subject([_f("손목 구명조끼", "안전용품"),
                                        _f("구명 손목 밴드", "구명도구")])
        assert len(keep) == 2

    def test_빈_입력에도_안_죽는다(self):
        assert sf.split_by_subject([]) == ([], [])
        assert sf.split_by_subject(None) == ([], [])


def test_조립_경로가_걸러낸_사실을_말한다():
    """★조용히 버리면 "왜 이 영상은 안 쓰였나"를 아무도 모른다(조용한 폴백 금지)."""
    import inspect
    import shopping_shorts.app as app
    src = inspect.getsource(app._assembled_drafts)
    assert "split_by_subject" in src, "조립 경로가 소재 검사를 안 쓴다"
    assert "재료에서 뺐습니다" in src, "뺀 사실을 화면에 안 알린다"


def test_커버리지_경로도_같은_검사를_쓴다():
    """화면(커버리지)과 조립이 다르게 판단하면 '된다더니 눌러보면 안 되는' 상태가 된다."""
    import inspect
    import shopping_shorts.app as app
    assert "split_by_subject" in inspect.getsource(app._slots_for_spine)
