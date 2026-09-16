"""강조를 **컷 단위**로 건다(2026-09-16 회원 제보).

제보: 6단계에서 "이 장면 강조할 곳"을 지정하면 **자막 덩어리 단위**로 적용된다.
자막 하나가 컷 4개로 쪼개져 있으면 네 컷 전부에 같은 자리로 원이 붙어, 정작
강조하고 싶은 컷이 아닌 곳까지 원이 떠 있었다.

뿌리: 강조 값이 beat["scene_hl"] 하나뿐이라 컷을 구분할 자리가 없었다.
→ beat["scene_hl_cuts"] = {"<컷번호>": {...}} 를 더한다.

★옛 작업 호환이 이 변경의 조건이다: scene_hl_cuts가 없으면 종전처럼 scene_hl을
  비트 전체에 적용한다(이미 만든 job들이 그대로 나와야 한다).
"""
from shopping_shorts.video_assemble import scene_hl_of


_HL = {"on": True, "mode": "zoom", "shape": "circle",
       "cx": 0.3, "cy": 0.4, "r": 0.25, "zoom": 2.0}


def test_컷지정이_없으면_종전대로_비트전체():
    """회귀 방지 — 옛 job은 scene_hl 하나로 모든 컷에 걸린다."""
    beat = {"scene_hl": _HL}
    for cut in (None, 0, 1, 5):
        got = scene_hl_of(beat, cut)
        assert got is not None
        assert abs(got["cx"] - 0.3) < 1e-9


def test_컷별로_따로_걸린다():
    beat = {"scene_hl_cuts": {"1": dict(_HL, cx=0.8)}}
    assert scene_hl_of(beat, 0) is None          # 1번 컷에만 걸었다
    assert abs(scene_hl_of(beat, 1)["cx"] - 0.8) < 1e-9
    assert scene_hl_of(beat, 2) is None


def test_컷지정이_비트전체를_이긴다():
    """한 비트에 둘 다 있으면 컷 지정이 우선 — 더 구체적인 지시가 이긴다."""
    beat = {"scene_hl": _HL, "scene_hl_cuts": {"0": dict(_HL, cx=0.9)}}
    assert abs(scene_hl_of(beat, 0)["cx"] - 0.9) < 1e-9
    # 컷 지정이 하나라도 있으면 지정 안 한 컷은 **강조 없음**이다
    # (안 그러면 "이 컷만"이라고 골랐는데 나머지에 옛 값이 남아 제보가 재발한다)
    assert scene_hl_of(beat, 1) is None


def test_컷지정_끄기는_그_컷만_끈다():
    beat = {"scene_hl_cuts": {"0": dict(_HL), "1": {"on": False}}}
    assert scene_hl_of(beat, 0) is not None
    assert scene_hl_of(beat, 1) is None


def test_cut_없이_부르면_대표값():
    """미리보기·썸네일처럼 컷을 모르는 자리는 그대로 부를 수 있어야 한다."""
    beat = {"scene_hl_cuts": {"0": dict(_HL, cx=0.7)}}
    got = scene_hl_of(beat)
    assert got is not None and abs(got["cx"] - 0.7) < 1e-9
