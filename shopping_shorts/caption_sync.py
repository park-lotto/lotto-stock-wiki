"""자막 구절 타이밍을 실제 음성(ASR 워드 타임스탬프)에 맞춘다.

순수·결정적. video_assemble._caption_segments가 만든 구절 경계는 그대로 두고,
각 구절의 '표시 시간'만 실제 말한 시각으로 다시 찍는다.
"""
import difflib
from collections import namedtuple

from .video_assemble import _caption_segments, _strip_punct

_MIN_MATCH_RATIO = 0.5   # 대본 단어 중 이만큼도 정렬 안 되면 신뢰불가 → None

# durs = 구절별 표시시간, lead_in = 비트 시작~첫 발화까지의 무음(초).
# ★lead_in을 따로 돌려주는 이유(2026-08-06): 예전엔 첫 구절 시작시각을 버리고 durs 합만
# total_dur로 정규화했다. 리드인은 '이동' 오차인데 '배율'로 흡수하려 한 셈이라, 말이
# 0.5초 뒤에 시작하는 비트에서 자막이 0.5초 먼저 뜨고 그 오차가 뒤 구절까지 번졌다
# (실측: -0.50 / -0.31 / -0.20s). 이동은 이동으로 갚아야 한다.
PhraseTiming = namedtuple("PhraseTiming", "durs lead_in")


def _norm(tok):
    return _strip_punct(tok)


def phrase_durs_from_words(narration, words, total_dur, preset=None):
    """PhraseTiming(durs, lead_in) 반환. durs는 구절별 실제 발화 간격(초), len == 구절 수.
    합은 total_dur보다 작을 수 있다(리드인·끝여백은 durs에 안 들어간다).
    ASR 정렬 신뢰도 미달이면 None(호출부가 글자수 폴백).
    preset: AI가 끊어준 자막 줄 — 렌더와 같은 경계를 써야 cap_durs 개수가 어긋나지 않는다."""
    segs = _caption_segments(narration, preset=preset)
    if not segs or not words or total_dur <= 0:
        return None

    ref = narration.split()
    hyp = [w["word"] for w in words]
    # 각 hyp 단어의 시작 시각(초). 자막은 '시작 시각'만 쓴다(구절 전환 시점).
    hyp_start = [float(w["start"]) for w in words]

    # 대본 단어 ↔ ASR 단어 정렬. 각 ref 인덱스에 대응 hyp 시작시각을 채운다.
    ref_time = [None] * len(ref)
    matched = 0
    sm = difflib.SequenceMatcher(a=[_norm(t) for t in ref], b=[_norm(t) for t in hyp])
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            span = min(i2 - i1, j2 - j1)
            for k in range(span):
                ref_time[i1 + k] = hyp_start[j1 + k]
                if tag == "equal":
                    matched += 1
    if matched < _MIN_MATCH_RATIO * len(ref):
        return None

    # 못 채운 ref 시각을 앞뒤 아는 값으로 선형 보간(양끝은 0/total_dur로 클램프).
    _interp(ref_time, total_dur)

    # 각 구절의 첫 ref 단어 시작 시각. 구절→ref 단어 범위는 순서대로 소비.
    seg_starts, w_at = [], 0
    for seg in segs:
        n = len(seg.split())
        seg_starts.append(ref_time[w_at] if w_at < len(ref_time) else total_dur)
        w_at += n

    # durs[i] = 다음 구절 시작 - 이 구절 시작(마지막은 total_dur까지). 단조·비음수 보장.
    durs = []
    for i, s in enumerate(seg_starts):
        nxt = seg_starts[i + 1] if i + 1 < len(seg_starts) else total_dur
        durs.append(max(0.0, nxt - s))
    if sum(durs) <= 0:
        return None
    # ★정규화(d * total_dur / tot) 제거 — 2026-08-06.
    # 그 스케일링은 "합이 total_dur"라는 겉보기만 맞추고, 리드인만큼의 이동 오차를 전
    # 구절에 비례배분해 오히려 번지게 했다. 지금은 실제 발화 간격을 그대로 두고 리드인은
    # lead_in으로 따로 넘겨 렌더러가 '시작점'을 밀게 한다. 합 < total_dur는 정상이다
    # (리드인 + 마지막 발화 후 여백이 durs 밖에 있으므로).
    return PhraseTiming(durs, max(0.0, seg_starts[0]))


def _interp(times, total_dur):
    """None 항목을 앞뒤 아는 값으로 선형 보간. 양끝 None은 0.0/total_dur로."""
    n = len(times)
    if times[0] is None:
        times[0] = 0.0
    if times[-1] is None:
        times[-1] = total_dur
    i = 0
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        lo = times[i - 1]
        hi = times[j] if j < n else total_dur
        gap = j - (i - 1)
        for k in range(i, j):
            times[k] = lo + (hi - lo) * (k - (i - 1)) / gap
        i = j
