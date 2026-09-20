# -*- coding: utf-8 -*-
"""짧은 칸에서 자막 실측 타이밍이 통째로 버려지던 것 (2026-09-01 사장님 3단계↔6단계 대조).

사장님 캡처: 3단계 hook 칸은 컷 4개(1.2/0.9/0.9/0.6)에 자막 4구절인데, 6단계 미리보기는
자막 2번째("반전 기능으로")일 때 뒤쪽 컷(기차 케이크)을 띄웠다 → "4장면으로 싱크 맞춰".

★실측(job 84b5f66a8e1f 칸0): ASR로 잰 구절 길이는 0.58/0.78/1.13/0.78인데
  _caption_durations가 **균등 0.89×4**를 돌려줬다. 하한 폴백
      if _CAP_MIN_DUR * n >= dur: return [dur/n]*n     # 1.0 × 4 = 4.0 >= 3.55
  이 실측 분기보다 **위**에 있었기 때문이다. 구절 맞춤(_plan_phrase_clips)은 컷 경계를
  이 값으로 잡으므로 컷까지 균등이 되어 자막↔화면이 밀렸다.
  바로 아래 주석은 "실측이 있으면 하한을 건너뛴다"라고 이미 못박아 뒀는데, 위의 폴백이
  먼저 걸려 통째로 무력이었다(CLAUDE.md 0순위-B).

계약: 실측(real_durs)이 있으면 하한 폴백보다 먼저 쓴다. 하한은 글자수 '추정'이 만든
      찰나 구절을 막는 장치라, 실제로 그렇게 말한 구절을 늘리면 싱크가 깨진다.
"""
from shopping_shorts import video_assemble as V

_SEGS = ["예측 못 한", "반전 기능으로", "개떡상한 움직이는", "기차 케이크임"]
_REAL = [0.5756, 0.7755, 1.1346, 0.7789]
_DUR = 3.552          # 하한 1.0 × 4구절 = 4.0 > 3.552 → 옛 코드는 여기서 균등분할로 샜다


def test_짧은_칸에서도_실측_타이밍을_쓴다():
    got = V._caption_durations(_SEGS, _DUR, real_durs=_REAL)
    assert [round(x, 2) for x in got] == [0.58, 0.78, 1.13, 0.78], \
        f"실측을 버리고 균등분할했다: {[round(x, 2) for x in got]}"


def test_구절맞춤_컷경계가_자막경계와_1대1():
    """컷 경계 = 리드인 + 구절 누적. 렌더(_plan_phrase_clips)가 이 값을 그대로 쓴다."""
    lead = 0.2874
    durs = V._caption_durations(_SEGS, _DUR, real_durs=_REAL)
    t, bounds = lead, [0.0]
    for d in durs[:-1]:
        t += d
        bounds.append(round(t, 2))
    assert bounds == [0.0, 0.86, 1.64, 2.77], f"컷 경계가 자막 경계와 다르다: {bounds}"


def test_실측이_없으면_예전대로_균등분할():
    """하한조차 못 채우는 칸의 폴백은 그대로 살아 있어야 한다(추정 경로는 안 건드렸다)."""
    got = V._caption_durations(_SEGS, _DUR)
    assert [round(x, 2) for x in got] == [0.89, 0.89, 0.89, 0.89], got


def test_실측_길이가_구절수와_다르면_폴백():
    got = V._caption_durations(_SEGS, _DUR, real_durs=[1.0, 1.0])
    assert [round(x, 2) for x in got] == [0.89, 0.89, 0.89, 0.89], got
