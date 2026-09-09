# -*- coding: utf-8 -*-
"""길이 바닥 + 영상 밖 정보 사용 검사 (2026-09-09).

■ 사장님 제보 두 개가 같은 병이었다 — **말만 하고 검사를 안 했다**

  ① "10초가 안 되는 대본이야"
     25초짜리를 시켰는데 A안 71자(9.6초)가 통과했다. `density_target`이
     스타일 밀도만 보고 **목표 초를 길이의 근거로 안 썼다**(게이트 목표 112자=15초).
     천장(2026-08-18, 44초 사고)만 있고 바닥이 없어 반대쪽으로 새고 있었다.

  ② 웹에서 '폐쇄 효과'·'특정 음역대' 같은 알맹이를 3개 찾아왔는데 대본은 0개 사용.
     프롬프트에 "하나만 골라 넣어라"라고 **말만** 적어뒀다.
     ★프롬프트가 말해도 아무도 검사 안 하면 안 지켜진다(같은 이름의 메모리 교훈).

■ 못박는 계약
  · 시킨 초의 70% 미만은 반려한다
  · 범위 계산은 **한 곳**(density_range) — 판정과 조립이 같은 것을 쓴다(0순위-B)
  · 재료에 그 블록이 없으면 항목 자체를 안 만든다(회귀 0)
  · 글자 그대로 베끼길 요구하지 않는다 — 입말 각색을 반려하면 안 된다
"""
from shopping_shorts import script_gate as g, spine_fill, wow_facts


# ── ① 길이 바닥 ──────────────────────────────────────────────────────────
def test_시킨_초를_못_채우면_반려된다():
    """★사장님이 받은 그 대본이다 — A안 71자(9.6초)가 25초짜리로 통과했었다."""
    lo, _hi = g.density_range({}, 25)
    assert 71 < lo, "9.6초짜리가 25초 대본으로 통과한다"
    assert 122 < lo, "16.5초짜리도 25초 대본이라 하기엔 짧다"


def test_바닥이_목표_초를_따라_움직인다():
    """스타일 밀도가 아니라 **시킨 초**가 길이를 정한다."""
    lo20, _ = g.density_range({}, 20)
    lo30, _ = g.density_range({}, 30)
    assert lo20 < lo30, "초를 늘렸는데 요구 길이가 그대로다"


def test_천장은_그대로_지킨다():
    """★2026-08-18의 반대 사고(30초짜리에 44초 대본)를 되살리면 안 된다."""
    for sec in (20, 25, 30):
        _lo, hi = g.density_range({}, sec)
        assert hi <= int(g._speech_cps() * sec), "말속도 환산 길이를 넘겼다"


def test_판정과_조립이_같은_범위를_쓴다():
    """★두 벌이면 '판정은 반려인데 조립은 통과'가 난다 — 조용해서 더 나쁘다(0순위-B)."""
    assert spine_fill.target_range({}, 25) == g.density_range({}, 25)


def test_느린_스타일도_바닥_아래로는_안_내려간다():
    lo_slow, _ = g.density_range({"chars_per_30s": 60}, 25)
    lo_base, _ = g.density_range({}, 25)
    assert lo_slow == lo_base


# ── ② 영상 밖 정보 사용 ──────────────────────────────────────────────────
_HOOKS = [{"hook": "귀마개 꼈을 때 내 목소리가 크게 들리는 건 폐쇄 효과라고 해요", "why": "x"},
          {"hook": "공연장에서 귀 멍한 건 특정 음역대가 때리기 때문이에요", "why": "y"}]


def test_재료가_없으면_검사_자체가_없다():
    """회귀 0 — 웹 보강이 빈손인 job은 종전대로 나와야 한다."""
    assert g._wow_hooks("그냥 쿠팡 재료입니다") == []
    assert g._wow_hooks("") == []


def test_블록에서_훅을_되찾는다():
    hooks = g._wow_hooks(wow_facts.wow_prompt_block(_HOOKS))
    assert len(hooks) == 2
    assert "폐쇄 효과" in hooks[0]
    assert "근거:" not in hooks[0], "근거까지 훅으로 잘못 읽었다"


def test_안_쓴_대본은_잡고_쓴_대본은_통과():
    hooks = g._wow_hooks(wow_facts.wow_prompt_block(_HOOKS))
    안씀 = "몇천 원짜리 요놈이면 층간소음 고민 끝인겨 귀에 끼워주면 조용한 세상이 펼쳐진게"
    씀 = "귀마개 끼면 내 목소리만 크게 들리는 거 그게 폐쇄 효과라는 건데"
    assert g._uses_wow(안씀, hooks)[0] is False
    assert g._uses_wow(씀, hooks)[0] is True


def test_글자_그대로_베끼길_요구하지_않는다():
    """★입말로 각색한 대본을 반려하면 이 검사는 있으나 마나가 된다."""
    hooks = g._wow_hooks(wow_facts.wow_prompt_block(_HOOKS))
    각색 = "공연장 갔다 오면 귀 멍하잖아 그거 음역대 때문이래"
    assert g._uses_wow(각색, hooks)[0] is True


def test_마커는_한_곳에만_적혀_있다():
    """★문자열을 두 곳에 적으면 한쪽만 고쳐져 검사가 조용히 죽는다(0순위-B)."""
    assert wow_facts.WOW_MARK in wow_facts.wow_prompt_block(_HOOKS)
