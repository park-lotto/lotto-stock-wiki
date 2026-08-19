# -*- coding: utf-8 -*-
"""확정 대본이 있으면 3단계는 **새로 쓰지 않는다** (2026-08-17).

★사장님: "어이없게 대본을 또 쓰냐 / 당연히 대본은 확정해서 믹스 버튼을 누른 거지 /
  거기서 대본 수정까지 마무리한 거니까."

원래 설계도 그렇다 — `_plan_and_tts` docstring:
  "given_script: 있으면 확정 대본을 그대로 비트로 쪼개 영상만 매칭(영상제작 2단계)"
그런데 `if scene_first:`가 **먼저** 걸려 그 분기를 못 탔다. produce.html은
scene_first를 **항상 true**로 보내고(4950행), scene_first 경로는 given_script를
안 보고 reference_text를 '참고 대본'으로만 써서 후보 3~4개를 새로 썼다.

실측 피해 둘:
  ① 2단계가 무의미해진다 — job 832a5ffa80d9: 확정 371자
     "요즘 인스타 감성 좀 아는 엄마들이…" → 3단계 결과 162자
     "저 이거 때문에 외출할 때마다 아이랑 전쟁 치를 뻔한 거 있죠?" (완전히 다른 글)
  ② 시간이 여기서 다 간다 — job 0bd83269a8ca 8분 48초 중 대본 생성+리라이트 460초.
     restyle 실호출은 78초뿐이고 나머지가 '대본 새로 쓰기'다(후보가 c1~c5까지 늘었다).

이 파일이 지키는 것: **확정 대본이 오면 scene_first를 끈다.**
대본 없이 오는 경로(위키 직행·자동배치)는 종전대로 scene_first가 돈다(회귀 0).
"""
import inspect

from shopping_shorts import mix_pipeline as mp


def _route(scene_first, given_script):
    """_plan_and_tts의 분기와 **같은 식**. 규칙이 바뀌면 아래 소스 검사가 잡는다."""
    if scene_first and (given_script or "").strip():
        scene_first = False
    return "scene_first" if scene_first else "given_script"


def test_확정대본이_있으면_새로_쓰지_않는다():
    """사장님이 2단계에서 고르고 다듬은 대본이 그대로 영상이 돼야 한다."""
    assert _route(True, "아침마다 밀가루 빵 먹는다고 엄마한테 욕먹을 뻔했어요") == "given_script"


def test_대본이_없으면_종전대로_scene_first():
    """위키 직행·자동배치 등 대본 없이 오는 경로는 그대로 새로 쓴다(회귀 0)."""
    assert _route(True, "") == "scene_first"
    assert _route(True, None) == "scene_first"
    assert _route(True, "   ") == "scene_first"      # 공백뿐이면 대본이 아니다


def test_분기가_실제_코드에_박혀있다():
    """★소스에서 이 가드가 사라지면 사고가 그대로 재발한다 —
    produce.html이 scene_first를 항상 true로 보내므로 가드 하나가 유일한 방어선이다."""
    src = inspect.getsource(mp._plan_and_tts)
    assert "scene_first and (given_script" in src, \
        "확정 대본 가드가 사라졌다 — 3단계가 다시 대본을 새로 쓴다"


def test_docstring_계약이_유지된다():
    """원래 계약이 문서에 남아 있어야 다음 사람이 같은 실수를 안 한다."""
    doc = (mp._plan_and_tts.__doc__ or "")
    assert "given_script" in doc and "영상만 매칭" in doc
