"""렌더 직전 불변식 게이트(2026-07-24, P2) — "고쳤는데 또 그대로"의 구조적 차단막.

이 파이프라인은 단계가 많고(생성→grounding→핑퐁→dedup→TTS→refill→conform), **뒷단계가
앞단계를 조용히 되돌리는** 사고가 반복됐다(dedup 후 refill이 반복 부활, fill이 파편 재삽입 등).
개별 단계를 아무리 고쳐도 새 단계가 또 되돌리면 밖으로 샌다.

그래서 **최종 plan 하나만 보고** 지켜야 할 것들을 코드로 재는 그물을 마지막에 둔다.
여기서 잡히면 어느 단계가 범인이든 사용자 화면에 '왜 이상한지'가 뜬다(조용한 실패 금지).

순수 계산(Gemini·IO 없음) — 실패해도 job을 죽이지 않게 호출부가 try로 감싼다.
"""
from shopping_shorts import config

# 목표 길이의 이 비율보다 짧으면 '빈약'으로 본다(30초 목표에 20초면 0.67 → 위반).
_SHORT_RATIO = 0.75
_MIN_BEATS = 5          # 이보다 적으면 이야기가 안 선다(스키마 minItems와 같은 바닥)


def _seg_ids(beat):
    out = []
    p = beat.get("primary") or {}
    if p.get("seg_id"):
        out.append(p["seg_id"])
    for a in (beat.get("alternates") or []):
        if a.get("seg_id"):
            out.append(a["seg_id"])
    return out


def check_plan(beats, target_seconds=None):
    """최종 beats를 불변식으로 검사 → {"ok", "violations"[], 지표들}.

    violations는 **사람이 읽는 한 줄**로 만든다(그대로 UI에 뜬다).
    - repeat: 같은 seg가 영상 전체에서 2번 이상 쓰임(비트 사이 반복 = 사장님이 제일 싫어하는 것)
    - beats: 비트 수가 바닥 미만
    - short: 실제 나레이션 길이(target_seconds 합)가 목표의 _SHORT_RATIO 미만
    - clips: 비트당 클립이 상한(MAX_CLIPS_PER_BEAT) 초과 = 파편
    """
    beats = [b for b in (beats or []) if b]
    v = []
    all_segs = []
    over_clip_beats = []
    for i, b in enumerate(beats):
        segs = _seg_ids(b)
        all_segs += segs
        cap = getattr(config, "MAX_CLIPS_PER_BEAT", 3) or 3
        if len(segs) > cap:
            over_clip_beats.append(i + 1)

    dup = {}
    for s in all_segs:
        dup[s] = dup.get(s, 0) + 1
    repeats = {s: n for s, n in dup.items() if n > 1}

    if repeats:
        top = ", ".join(f"{s}×{n}" for s, n in
                        sorted(repeats.items(), key=lambda kv: -kv[1])[:3])
        v.append(f"같은 장면이 반복됩니다 ({len(repeats)}개: {top})")
    if len(beats) < _MIN_BEATS:
        v.append(f"비트가 {len(beats)}개뿐입니다(최소 {_MIN_BEATS})")
    if over_clip_beats:
        v.append(f"컷이 너무 잘게 쪼개진 비트: {over_clip_beats}번")

    secs = round(sum(float(b.get("target_seconds") or 0) for b in beats), 1)
    if target_seconds and secs and secs < target_seconds * _SHORT_RATIO:
        v.append(f"길이가 {secs}초로 목표 {target_seconds}초보다 많이 짧습니다")

    return {
        "ok": not v,
        "violations": v,
        "beat_count": len(beats),
        "seconds": secs,
        "repeat_segs": sorted(repeats),
        "unique_segs": len(dup),
        "total_clips": len(all_segs),
    }
