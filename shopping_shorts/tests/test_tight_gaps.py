# -*- coding: utf-8 -*-
"""문장 사이 공백 제거 — "끝과 시작이 거의 공간 없이" (2026-08-22 사장님).

## 실측 근거

같은 대본(메종 전사 191자)을 speed 1.6으로 합성해 무음컷 강도별로 잰 값:

    stop 0.12 -> 27.74초 (잔여 2.38초 / 20구간)  <- 거의 안 잘린다
    stop 0.05 -> 26.14초 (잔여 0.11초 /  1구간)  <- ★채택(사장님 청취)
    stop 0.02 -> 24.70초
    stop 0.00 -> 22.94초 (사람 원본 22.67초와 동급이나 숨이 없다)

★임계도 함께 움직여야 한다. -38dB는 문장 사이 '숨'을 소리로 봐서 안 자른다 —
  그래서 0.12에서 20구간이 남았고, 나는 여기서 "무음컷으로는 1.2초가 최대"라고
  잘못 결론냈다. -30dB로 올려야 그 숨까지 잡힌다.

★비교: 사람(메종 원본)은 무음이 문자 그대로 0.00초다(임계 -30/-38/-45 전부 0구간).
  같은 시간에 더 담기는 이유는 빠르게 말해서가 아니라 **쉬지 않아서**다.
"""
from shopping_shorts import audio_post


# ★2026-10-01 관제 049 — 0.05초·-30dB 는 문장별 합성의 길이를 줄이려던 값이었다. 통째 합성으로 바꾸고
#   사장님이 고른 샘플은 **0.15초·-40dB**였다(-30dB·0.05는 받침 앞 멈춤까지 잘라 단어 안이 끊겼다 —
#   황선희님 job 0875d89db254 문장당 최대 12곳). 위 08-22 실측은 옛 기록으로 남긴다.
def test_gap_is_listened_value():
    """문장 사이 공백 상한 = 0.15초 (2026-10-01 사장님 청취 확정)."""
    assert audio_post._PACE_STOP_DURATION == 0.15,         "공백 상한이 %.2f초 - 고른 값은 0.15다" % audio_post._PACE_STOP_DURATION


def test_threshold_keeps_soft_consonants():
    """임계 -40dB — -30dB는 ㅎ·ㅅ·받침 앞 멈춤을 무음으로 봐 단어 안을 잘랐다."""
    assert audio_post._PACE_THRESHOLD == "-40dB",         "임계가 %s - 고른 값은 -40dB다" % audio_post._PACE_THRESHOLD


def test_tail_pad_kept():
    """끝 여백은 남긴다 - 0이면 다음 문장이 숨 없이 붙어 기관총처럼 들린다."""
    assert audio_post._PACE_TAIL_PAD > 0, "끝 여백이 0이면 너무 붙는다"


def test_measure_uses_same_constants():
    """자를 때와 잴 때가 같은 상수를 본다(0순위-B) - 어긋나면 자막이 밀린다."""
    import inspect
    src = inspect.getsource(audio_post.measure_removed_spans)
    assert "_PACE_STOP_DURATION" in src and "_PACE_THRESHOLD" in src, \
        "측정 쪽이 상수를 안 쓰고 값을 따로 박았다 - 바꾸면 자막이 어긋난다"
