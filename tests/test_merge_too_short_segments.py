# -*- coding: utf-8 -*-
"""0.8초 미만 조각 병합 — 2026-08-17 사장님 지적("조각낼 때부터 방지 못 하나")의 고정.

실측 근거: 최근 80영상 1,164구간 중 131개(11.3%)가 0.8초 미만이었다. 그 조각은
라운드로빈이 건너뛰어 화면에 안 나오고, 담으면 그 몫을 다른 컷이 늘어나 메운다.
구간이 빈틈없이 붙어 있어(인접쌍 505개 전부 간격 0) 늘리기는 불가 → 병합이 답.
"""
from shopping_shorts.script_extract import _merge_too_short


def _seg(a, b, role="사용중", text="", desc="", key=False):
    return {"start": a, "end": b, "shot_role": role, "text": text,
            "scene_desc": desc, "is_key": key}


def _lens(segs):
    return [round(s["end"] - s["start"], 2) for s in segs]


def test_짧은구간이_같은역할_인접과_합쳐진다():
    segs = [_seg(0.0, 1.2, "before", "버리려다가", "떠내는 모습"),
            _seg(1.2, 1.7, "before", "깜짝 놀랐어요", "놀라는 여성"),
            _seg(1.7, 4.0, "완성", "도자기더라고요", "컵 클로즈업")]
    out = _merge_too_short(segs)
    assert _lens(out) == [1.7, 2.3]
    # 대사는 시간순으로 이어붙는다 — 짧다고 말을 버리지 않는다.
    assert out[0]["text"] == "버리려다가 깜짝 놀랐어요"
    # 설명은 '원래 길었던 쪽'이 남는다(0.5초가 1.2초를 밀어내면 카드가 실제와 어긋난다).
    assert out[0]["scene_desc"] == "떠내는 모습"


def test_같은역할이_없으면_짧은쪽과_합친다():
    segs = [_seg(0.0, 5.0, "사용중", "긴 앞"),
            _seg(5.0, 5.6, "완성", "짧은 것"),
            _seg(5.6, 7.0, "after", "덜 긴 뒤")]
    out = _merge_too_short(segs)
    # 앞(5.0초)보다 뒤(1.4초)가 짧으므로 뒤와 합쳐진다
    assert _lens(out) == [5.0, 2.0]
    assert out[1]["text"] == "짧은 것 덜 긴 뒤"


def test_기준이상은_한_글자도_안_건드린다():
    """회귀 방지 — 멀쩡한 구간까지 합치면 장면이 뭉개진다."""
    segs = [_seg(0.0, 2.0, "사용중", "가"), _seg(2.0, 3.5, "완성", "나"),
            _seg(3.5, 4.4, "after", "다")]
    out = _merge_too_short(segs)
    assert out == segs


def test_총길이는_보존된다():
    segs = [_seg(0.0, 0.5, "완성", "가"), _seg(0.5, 0.7, "사용중", "나"),
            _seg(0.7, 3.0, "사용중", "다")]
    out = _merge_too_short(segs)
    assert out[0]["start"] == 0.0 and out[-1]["end"] == 3.0
    assert all(round(s["end"] - s["start"], 2) >= 0.8 for s in out)


def test_구간이_하나뿐이면_그대로():
    """합칠 상대가 없다 — 억지로 만들지 않는다(짧은 영상 fail-open)."""
    segs = [_seg(0.0, 0.4, "완성", "가")]
    assert _merge_too_short(segs) == segs


def test_실증표시는_한쪽만_있어도_살린다():
    segs = [_seg(0.0, 0.5, "사용중", "가", key=True), _seg(0.5, 3.0, "사용중", "나")]
    out = _merge_too_short(segs)
    assert len(out) == 1 and out[0]["is_key"] is True
