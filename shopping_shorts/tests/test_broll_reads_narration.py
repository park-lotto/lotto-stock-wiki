# -*- coding: utf-8 -*-
"""b-roll이 **대사를 읽고** 고르는지 + 훅 채점(2026-09-05 사장님 지적).

실측 사고(다이소 굿즈 영상, job 없음·로컬 프로브):
  problem 칸 "다이어리 꾸밀 때마다 스티커가 자꾸 들떠서 고생했거든요"에
  `사용중` 첫 컷인 **인형 팔찌 착용**이 붙었다 — 결만 맞고 내용은 딴소리.
  종전 정렬이 `is_key → 시간순`이라 대사를 한 글자도 안 봤기 때문.
"""
from shopping_shorts import edit_plan


def _seg(sid, start, end, role, desc, change="", is_key=False, has_effect=False):
    return {"seg_id": sid, "video_id": "s0", "start": start, "end": end,
            "shot_role": role, "scene_desc": desc, "change": change,
            "text": "", "is_key": is_key, "has_effect": has_effect}


def _sources(segs):
    return [{"video_id": "s0", "segments": segs}]


def test_broll이_대사와_낱말이_겹치는_컷을_고른다():
    """결(사용중)이 같은 후보가 여럿일 때, 대사에 나온 말이 있는 컷이 앞선다."""
    segs = [
        _seg("s0-0", 0, 3, "완성", "로고 화면"),
        _seg("s0-1", 3, 6, "사용중", "인형 팔찌를 손목에 감아 착용하는 모습"),   # 시간이 더 이르다
        _seg("s0-2", 6, 9, "사용중", "스티커를 다이어리에 붙이는 모습", "스티커가 들뜨지 않는다"),
        _seg("s0-3", 9, 12, "완성", "완성된 다이어리"),
    ]
    # ★출처가 하나도 없으면 build_inherit_plan은 None이다(설계). 훅에 출처를 남기고
    #   problem만 비워, 그 칸이 대사를 읽고 고르는지를 본다.
    given = "\n".join(["훅 문장입니다", "다이어리 꾸밀 때 스티커가 자꾸 들떠서 고생했거든요"])
    bs = [{"role": "hook", "seg": "s0-3", "segs": ["s0-3"]},
          {"role": "problem", "seg": "", "segs": []}]
    plan = edit_plan.build_inherit_plan(_sources(segs), given, bs)
    assert plan, "상속 계획이 만들어져야 한다"
    problem = plan["beats"][1]
    assert problem["primary"]["seg_id"] == "s0-2", \
        "대사의 '스티커·다이어리'와 겹치는 컷이어야 한다(종전엔 시간순 첫 s0-1이 붙었다)"
    assert problem["inherited"] is False and problem["fit"] == 3   # b-roll 표시는 그대로


def test_훅은_채점으로_더_센_그림을_고른다():
    """같은 '완성' 결이라도 실증+핵심·반전 표현이 있는 컷이 앞선다(사장님 채점 기준)."""
    segs = [
        _seg("s0-0", 0, 4, "완성", "제품 상자가 놓여 있음"),                    # 시간순 첫째
        _seg("s0-1", 4, 8, "실증", "물을 붓자 그대로 흡수된다", "물이 순식간에 사라진다", is_key=True),
        _seg("s0-2", 8, 12, "사용중", "손으로 제품을 만진다"),
    ]
    given = "\n".join(["여러분 이거 꼭 사세요", "쓰는 방법은 간단해요"])
    bs = [{"role": "hook", "seg": "", "segs": []},
          {"role": "demo", "seg": "s0-2", "segs": ["s0-2"]}]
    plan = edit_plan.build_inherit_plan(_sources(segs), given, bs)
    assert plan
    assert plan["beats"][0]["primary"]["seg_id"] == "s0-1", \
        "훅은 실증+핵심+반전 표현이 있는 컷(점수 최고)이어야 한다"


def test_원본효과가_박힌_컷은_훅에서_밀린다():
    """has_effect(남의 자막·효과)는 감점 — 같은 완성 결이면 깨끗한 쪽이 앞선다."""
    segs = [
        _seg("s0-0", 0, 4, "완성", "완성품 클로즈업", has_effect=True),
        _seg("s0-1", 4, 8, "완성", "완성품을 들어 보이는 모습"),
        _seg("s0-2", 8, 12, "사용중", "사용하는 모습"),
    ]
    given = "\n".join(["이거 진짜 물건이에요", "이렇게 쓰면 됩니다"])
    bs = [{"role": "hook", "seg": "", "segs": []},
          {"role": "demo", "seg": "s0-2", "segs": ["s0-2"]}]
    plan = edit_plan.build_inherit_plan(_sources(segs), given, bs)
    assert plan
    assert plan["beats"][0]["primary"]["seg_id"] == "s0-1", "효과 박힌 컷은 밀려야 한다"


def test_겹치는_낱말이_없으면_종전_순서_그대로():
    """회귀 0 — 대사와 겹치는 말이 하나도 없으면 is_key → 시간순(종전)."""
    segs = [
        _seg("s0-0", 0, 3, "완성", "로고"),
        _seg("s0-1", 3, 6, "사용중", "가위로 종이를 자른다"),
        _seg("s0-2", 6, 9, "사용중", "풀로 붙인다"),
    ]
    # 출처가 하나도 없으면 None이 설계 — 훅에만 출처를 남긴다.
    given = "\n".join(["훅입니다", "완전히 무관한 이야기입니다"])
    bs = [{"role": "hook", "seg": "s0-0", "segs": ["s0-0"]},
          {"role": "problem", "seg": "", "segs": []}]
    plan = edit_plan.build_inherit_plan(_sources(segs), given, bs)
    assert plan
    # problem 1순위(before·문제)가 없어 차선(사용중)으로 내려가고, 겹침이 없으니 시간순 첫째
    assert plan["beats"][1]["primary"]["seg_id"] in ("s0-1", "s0-2")


def test_규칙표에_없는_역할도_대사를_읽는다():
    """reveal·story처럼 _ROLE_WANT_SHOTS에 없는 칸도 대사와 겹치는 컷을 고른다.

    실측(다이소 수납템 영상): "제 지인이 다이소 매니저로 있거든요"(reveal)에
    '매장 입구 바닥'이 붙었다 — 표에 없는 역할이라 곧장 _next_cut으로 가서 대사를 안 봤다.
    """
    segs = [
        _seg("s0-0", 0, 3, "기타", "매장 입구 바닥과 집기들"),          # 시간순 첫째
        _seg("s0-1", 3, 6, "기타", "직원이 선반에 제품을 진열하는 모습"),
        _seg("s0-2", 6, 9, "사용중", "제품을 사용하는 모습"),
    ]
    given = "\n".join(["훅입니다", "지인이 매장 직원인데 선반에 진열되자마자 나간대요"])
    bs = [{"role": "hook", "seg": "s0-2", "segs": ["s0-2"]},
          {"role": "reveal", "seg": "", "segs": []}]     # 규칙표에 없는 역할
    plan = edit_plan.build_inherit_plan(_sources(segs), given, bs)
    assert plan
    assert plan["beats"][1]["primary"]["seg_id"] == "s0-1", \
        "'직원·선반·진열'이 겹치는 컷이어야 한다(종전엔 시간순 첫 s0-0='매장 입구')"
