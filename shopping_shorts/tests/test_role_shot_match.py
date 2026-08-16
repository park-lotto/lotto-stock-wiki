# -*- coding: utf-8 -*-
"""비트 역할(훅·CTA·결과…) → 그 칸에 어울리는 장면 결(shot_role) (2026-08-17).

★왜 생겼나 — 사장님 "장면 매칭이 훅부터 기준이 뭘로 한 건지 확인해봐":
  매칭은 "대사의 행위 = 화면의 행위"로 맞추는데, 그 판정이 동사 사전 30개
  (자르다·붓다·섞다·굽다…)라 **요리·살림 영상 전용**이다. 스토리형 대본은
  동작 동사가 없어 대사 행위가 통째로 None이 된다.

  실측(job 832a5ffa80d9) — 5개 비트 **전부** 대사행위 None:
    훅  "저 이거 때문에 외출할 때마다 아이랑 전쟁 치를 뻔한 거 있죠?" → 행위 없음
    붙은 화면: "스마트폰에 OTG 케이블로 기기를 직접 연결해 …"(fit=2, action_mismatch)
  대사 행위가 없으니 ①beat_action_mismatch가 "판정 보류"로 어긋남을 못 잡고
  ②ping_pong도 "대사 행위 없으면 손 안 댐"이라 고칠 기회가 없다 → 사실상 무작위.

★답은 이미 있었다: shot_role 태그가 5,634개(전체 6,824 중 83%) 채워져 있고,
  장면 실험실(scene_lab.html `useTags`)은 **이미 이 규칙으로** 칸을 채운다.
  서버 자동매칭만 안 쓰고 있었다 — 같은 판단이 두 곳에 다르게(0순위-B).

⚠️ 이 표는 scene_lab.html `useTags`와 **짝**이다. 한쪽만 고치면 화면과 서버가
   서로 다른 장면을 고르게 된다 — 반드시 같이 고칠 것.
"""
import pytest

from shopping_shorts.edit_plan import _want_shots_for_role


# 라이브에 실재하는 shot_role 값(2026-08-17 실측 분포):
#   사용중 2956 · 완성 1032 · 기타 601 · after 522 · 조리 220 · 문제 158 · before 145
# ★권장 결은 반드시 이 안에 있어야 한다. 없는 값을 적으면 조용히 0건이 된다.
_LIVE_SHOT_ROLES = {"사용중", "완성", "기타", "after", "조리", "문제", "before"}

# 라이브에 실재하는 비트 role 값(같은 job에서 실측): 훅·해결·결과·CTA
_LIVE_BEAT_ROLES = ["훅", "해결", "결과", "CTA"]


@pytest.mark.parametrize("role", _LIVE_BEAT_ROLES)
def test_라이브_역할은_전부_매핑된다(role):
    """실제로 쓰이는 역할이 하나라도 빠지면 그 칸은 종전대로 무작위가 된다."""
    shots, why = _want_shots_for_role(role)
    assert shots, "역할 %r이 매핑에서 빠졌다" % role
    assert why, "설명이 없으면 프롬프트가 이유를 못 말한다"


def test_권장결은_라이브에_실재하는_값만_쓴다():
    """없는 결을 적으면 후보가 0건이 되고 아무 효과 없이 조용히 지나간다."""
    for role in _LIVE_BEAT_ROLES + ["문제", "전개"]:
        shots, _ = _want_shots_for_role(role)
        for s in (shots or ()):
            assert s in _LIVE_SHOT_ROLES, "%r: 라이브에 없는 결 %r" % (role, s)


def test_훅은_시선끄는_완성품을_고른다():
    """훅 = 첫 3초. 실험실 useTags의 '완성·after → 후킹용'과 같아야 한다."""
    shots, _ = _want_shots_for_role("훅")
    assert shots == ("완성", "after")


def test_cta는_완성품():
    """실험실: 완성 → CTA용."""
    assert _want_shots_for_role("CTA")[0] == ("완성",)
    assert _want_shots_for_role("마무리")[0] == ("완성",)


def test_문제는_before():
    """쓰기 전 상황 — 완성품을 붙이면 문제가 안 보인다."""
    assert "before" in _want_shots_for_role("문제")[0]


def test_영문_역할도_잡는다():
    """모델이 한글·영문 아무거나 쓴다(_KNOWN_ROLE_WORDS와 같은 전제)."""
    assert _want_shots_for_role("hook")[0] == ("완성", "after")
    assert _want_shots_for_role("cta")[0] == ("완성",)
    assert "before" in _want_shots_for_role("problem")[0]


def test_모르는_역할은_보류():
    """억지로 배정하지 않는다 — 빈 값이면 종전 동작 그대로(회귀 0)."""
    for r in ("", None, "듣도보도못한역할"):
        shots, why = _want_shots_for_role(r)
        assert shots is None and why == ""


def test_대소문자_섞여도_잡는다():
    assert _want_shots_for_role("CTA")[0] == _want_shots_for_role("cta")[0]
    assert _want_shots_for_role("Hook")[0] == _want_shots_for_role("hook")[0]
