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


# ── ①-b 2026-09-18: "2개 골랐는데 1개만 나온다"의 뿌리 ─────────────────────
#   박복래(cid 205) work 4124ceb3a88a — 스타일 2개를 골랐는데 1안만 나왔다.
#   죽은 스타일의 4번 시도가 209·191·222·187자였고 **전부** 말 밀도로 반려됐는데
#   실제 음성은 19.3~22.9초로 **요청한 25초보다 짧았다.** 게이트가 말속도를
#   7.41자/초(실측 9.69의 76%)로 믿어 "25초"를 19.1초로 요구한 탓이다.
#   라이브 대본 1,912개 실측: `말 밀도`가 재작성 3,010회·사망 386건으로 압도적 1위 사인.

def test_창은_절대_뒤집히지_않는다():
    """★lo > hi 면 그 스타일은 **무엇을 써도 반려**다(통과 불가능한 창).

    2026-09-18 실측: 느린 스타일은 hi(=tgt*1.4)가 길이바닥보다 작아
    `169~86` 같은 창이 나왔다. lo만 cap으로 조이고 hi와 대조하지 않은 탓이다.
    """
    for raw in (60, 73, 102, 136, 157, 181, 215, 240, 264, 300, 327, 377):
        for sec in (15, 20, 25, 30, 45):
            lo, hi = g.density_range({"chars_per_30s": raw}, sec)
            assert lo <= hi, f"창이 뒤집혔다(raw={raw}, {sec}초): {lo}~{hi}"


def test_말속도는_라이브_실측과_맞는다():
    """★게이트가 믿는 말속도가 실제 TTS와 어긋나면 초 계산이 통째로 틀린다.

    라이브 실측 9.69자/초(2026-09-16, 최근 60 job·비트 389개의 TTS 실길이,
    `edit_plan.narr_secs` 주석). 게이트는 이 값을 그대로 빌려 써야 한다(0순위-B).
    ±5% 안이면 통과 — 배속을 조정하면 이 테스트가 먼저 알려준다.
    """
    assert abs(g._speech_cps() - 9.69) / 9.69 < 0.05, (
        f"게이트 말속도 {g._speech_cps():.2f}자/초가 라이브 실측 9.69와 어긋난다 — "
        "상한이 실제보다 좁아져 요청한 초를 채운 대본이 '너무 길다'고 반려된다")


def test_요청한_초를_채운_대본이_반려되지_않는다():
    """★박복례 건의 회귀 가드 — 25초를 요청했으면 25초짜리가 통과해야 한다."""
    cps = g._speech_cps()
    for sec in (20, 25, 30):
        _lo, hi = g.density_range({"chars_per_30s": 327}, sec)
        # 요청한 초의 딱 90%를 채운 대본 = 명백히 통과해야 하는 길이
        n = int(cps * sec * 0.9)
        assert n <= hi, (
            f"{sec}초를 요청했는데 {n}자({n / cps:.1f}초)가 상한 {hi}를 넘어 반려된다")


def test_목표는_스타일의_색을_지운다면_안된다():
    """★바닥을 목표에까지 걸면 느린 스타일이 전부 바닥에 붙어 밀도가 죽는다.

    2026-09-18 실측(25초): `_FILL_FLOOR`가 `density_target` 안에 있으면
    밀도 240·264·300이 **전부 232**로 같아졌다 — 08-24가 되살린 병의 재발이다.
    시간 강제는 `density_range`의 `_LEN_FLOOR` 한 곳에서만 한다(0순위-B).
    """
    a = g.density_target({"chars_per_30s": 240}, 25)
    b = g.density_target({"chars_per_30s": 300}, 25)
    assert a != b, "서로 다른 밀도가 같은 목표를 받는다 — 스타일의 색이 죽었다"


# ── ② 영상 밖 정보 사용 ──────────────────────────────────────────────────
_SOURCE = {"title": "검증 문서", "url": "https://example.com/evidence"}


def _verified(hook):
    size = len(hook.encode("utf-8"))
    return {"hook": hook, "why": "", "sources": [_SOURCE], "grounding": {
        "grounded_text": hook,
        "supports": [{"start": 0, "end": size, "text": hook,
                      "segment_text": hook, "sources": [_SOURCE]}],
        "sources": [_SOURCE],
    }}


_HOOKS = [_verified("귀마개 꼈을 때 내 목소리가 크게 들리는 건 폐쇄 효과라고 해요"),
          _verified("공연장에서 귀 멍한 건 특정 음역대가 때리기 때문이에요")]


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
