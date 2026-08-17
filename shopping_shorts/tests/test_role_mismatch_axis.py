# -*- coding: utf-8 -*-
"""두 번째 판정축(역할↔결) — 동사사전이 죽어도 어긋남을 잡는다.

배경(2026-08-18 사장님 "장면매칭이 왜 이렇게 힘드냐 / 1단계 태깅이 문제냐"):
  1단계 태깅은 멀쩡했다(라이브 실측 채움률 scene_desc·shot_role 100%).
  문제는 **교정 장치가 통째로 꺼져 있던 것**이다:

    동사사전 30개(요리 전용) → 스토리형 대사엔 동사 없음
      → 대사행위 None 148/168건(88%)
      → beat_action_mismatch가 "판정 보류"로 False
      → _verify_fits가 fit을 못 깎음 → fit 5로 남음
      → _repick_weak_beats(fit<=3)에 안 걸림 → 아무도 안 고침

  라이브 실측: 훅·CTA 58건 중 27건이 어긋났는데 fit>=4라 교정 대상에서 빠졌다.
  fit=5 자기신고 37건 중 26건(70%)이 실제로는 결이 어긋나 있었다.

이 파일이 지키는 것:
  1) 동사가 하나도 없어도(=기존 축 무력) 역할↔결 어긋남을 잡는다
  2) 정당한 차선 선택은 어긋남으로 치지 않는다(오탐 = 멀쩡한 화면 교체)
  3) 판정표는 _ROLE_WANT_SHOTS 한 곳만 쓴다(0순위-B) — 여기에 표를 복사하지 않는다
"""
import pytest

from shopping_shorts import backbone, edit_plan


def _beat(role, shot_role, narration="저 이거 때문에 전쟁 치를 뻔한 거 있죠?", fit=5):
    """대사엔 사전 동사가 없다 — 기존 축(action)이 무력한 상황을 그대로 재현한다."""
    return {"beat_idx": 0, "role": role, "narration": narration, "fit": fit,
            "primary": {"seg_id": "s0-1", "shot_role": shot_role,
                        "scene_desc": "화면 설명", "text": ""}}


def test_동사없는_훅이_조리화면이면_어긋남으로_잡힌다():
    """실측에서 가장 많았던 경우 — 훅에 '사용중'(조리)이 붙고 fit 5로 통과하던 것."""
    b = _beat("훅", "사용중")
    assert backbone.beat_action_mismatch(b) is False, "전제: 기존 축은 이 대사를 판정 못 한다"
    assert backbone.beat_role_mismatch(b) is True


def test_훅에_완성이_붙으면_정상():
    for sr in ("완성", "after"):
        b = _beat("훅", sr)
        assert backbone.beat_role_mismatch(b) is False, sr


def test_cta도_같은_기준():
    assert backbone.beat_role_mismatch(_beat("cta", "사용중")) is True
    assert backbone.beat_role_mismatch(_beat("cta", "완성")) is False


def test_해결결과는_조리가_맞다():
    """훅과 반대 — 여기는 '사용중'이 정답이고 '완성'은 차선이다."""
    assert backbone.beat_role_mismatch(_beat("해결", "사용중")) is False
    assert backbone.beat_role_mismatch(_beat("결과", "조리")) is False
    assert backbone.beat_role_mismatch(_beat("해결", "before")) is True


def test_정당한_차선은_어긋남이_아니다():
    """레시피엔 before·문제 결이 0건이라 차선(조리)으로 내려가는 게 정상이다.

    이걸 어긋남으로 치면 고칠 수 없는 걸 계속 재픽하게 된다(무한 헛돌기).
    """
    assert backbone.beat_role_mismatch(_beat("문제", "사용중")) is False
    assert backbone.beat_role_mismatch(_beat("문제", "before")) is False
    assert backbone.beat_role_mismatch(_beat("문제", "완성")) is True


@pytest.mark.parametrize("role", ["", "심화", "추가", "unknown"])
def test_표에_없는_역할은_판정보류(role):
    """모르는 역할까지 깎으면 오탐이 난다 — 보수적으로 보류."""
    assert backbone.beat_role_mismatch(_beat(role, "사용중")) is False


def test_결이_없으면_판정보류():
    """shot_role이 안 붙은 옛 추출본은 판정하지 않는다(fail-open)."""
    assert backbone.beat_role_mismatch(_beat("훅", "")) is False
    b = _beat("훅", "사용중")
    b["primary"].pop("shot_role")
    assert backbone.beat_role_mismatch(b) is False


def test_verify_fits가_역할축으로도_깎는다():
    """핵심 배선 — 이게 되어야 재픽(fit<=3)이 돌기 시작한다."""
    beats = [_beat("훅", "사용중", fit=5)]
    out = edit_plan._verify_fits(beats)
    assert out[0]["fit"] == 2, "fit이 안 깎이면 재픽 문턱(<=3)을 못 넘는다"
    assert out[0]["fit_evidence"] == "role_mismatch"


def test_verify_fits가_맞는_비트는_안_건드린다():
    beats = [_beat("훅", "완성", fit=5)]
    out = edit_plan._verify_fits(beats)
    assert out[0]["fit"] == 5
    assert "fit_evidence" not in out[0]


def test_두_축이_동시에_걸리면_증거에_둘_다():
    """어느 축이 잡았는지 사후에 갈라볼 수 있어야 한다."""
    b = _beat("훅", "사용중", narration="양파를 자르고 기름을 붓습니다")
    b["primary"]["action"] = "뒤집다"
    assert backbone.beat_action_mismatch(b) is True
    out = edit_plan._verify_fits([b])
    assert out[0]["fit_evidence"] == "action+role_mismatch"


def test_판정표를_복사하지_않았다():
    """0순위-B — 표는 _ROLE_WANT_SHOTS 한 곳만. 여기서 shot_role 문자열을 하드코딩해
    판정하면 표를 고쳐도 이 축은 옛 규칙으로 돈다."""
    import inspect
    src = inspect.getsource(backbone.beat_role_mismatch)
    assert "_ROLE_WANT_SHOTS" in src, "표를 참조하지 않고 자체 판단을 만들었다"
