"""자막 구절 타이밍을 실제 음성(ASR 워드 타임스탬프)에 맞춘다.

순수·결정적. video_assemble._caption_segments가 만든 구절 경계는 그대로 두고,
각 구절의 '표시 시간'만 실제 말한 시각으로 다시 찍는다.
"""
import difflib

from .video_assemble import _caption_segments, _strip_punct

_MIN_MATCH_RATIO = 0.5   # 대본 단어 중 이만큼도 정렬 안 되면 신뢰불가 → None


def _norm(tok):
    return _strip_punct(tok)


def phrase_durs_from_words(narration, words, total_dur, preset=None):
    """narration의 각 자막 구절 표시시간 리스트(초) 반환. len == 구절 수, 합 ≈ total_dur.
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
    # 합을 total_dur로 정규화(보간 오차 흡수).
    tot = sum(durs)
    if tot <= 0:
        return None
    return [d * total_dur / tot for d in durs]


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
