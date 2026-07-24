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
_LONG_RATIO = 1.4          # 목표의 이 배를 넘으면 너무 김(오버슛 방어, 2026-07-24)
_MIN_BEATS = 5          # 이보다 적으면 이야기가 안 선다(스키마 minItems와 같은 바닥)


_ADJ_TOL = 0.35   # 앞 클립 끝과 다음 클립 시작이 이만큼 이내면 '이어붙임'(컷이 아니다)


def _clips(beat):
    out = []
    p = beat.get("primary") or {}
    if p.get("seg_id"):
        out.append(p)
    out += [a for a in (beat.get("alternates") or []) if a.get("seg_id")]
    return out


def _continuous_runs(beats):
    """영상 전체를 한 줄로 펴서 '같은 소스의 인접 구간이 연달아' 이어지는 구간을 찾는다.

    ★2026-07-24 실사고: seg_id는 전부 고유(반복 0)라 반복 게이트를 통과했는데, 실제 화면은
    s2-0→s2-1→s2-2… 원본을 시간순으로 그냥 튼 것이라 **컷이 없었다**(사장님: "10·14·16·22초
    연속재생"). 고유성만 재면 이 증상을 못 잡는다 — 이어붙임 길이를 따로 잰다.
    반환: [(시작클립인덱스, 이어진 클립 수, 초)] 중 2개 이상 이어진 것만."""
    flat = []
    for b in beats:
        for cl in _clips(b):
            flat.append(cl)
    runs, cur = [], []
    for i, cl in enumerate(flat):
        if not cur:
            cur = [cl]
            continue
        prev = cur[-1]
        # 필드 없으면 '모른다'=컷(오탐 방지) — video_id 둘 다 None이면 같다고 오판된다.
        pv, cv = prev.get("video_id"), cl.get("video_id")
        same = bool(pv) and bool(cv) and pv == cv
        adj = (prev.get("end") is not None and cl.get("start") is not None
               and abs(float(prev["end"]) - float(cl["start"])) <= _ADJ_TOL)
        if same and adj:
            cur.append(cl)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = [cl]
    if len(cur) >= 2:
        runs.append(cur)
    out = []
    for run in runs:
        secs = sum(max(0.0, float(c.get("end") or 0) - float(c.get("start") or 0)) for c in run)
        out.append({"clips": len(run), "seconds": round(secs, 1),
                    "from": run[0].get("seg_id"), "to": run[-1].get("seg_id")})
    return out


def _seg_ids(beat):
    out = []
    p = beat.get("primary") or {}
    if p.get("seg_id"):
        out.append(p["seg_id"])
    for a in (beat.get("alternates") or []):
        if a.get("seg_id"):
            out.append(a["seg_id"])
    return out


def check_plan(beats, target_seconds=None, pool_video_count=None):
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

    # ★연속재생(컷 없음) — 고유 seg여도 인접 구간을 순서대로 붙이면 원본을 그냥 트는 것과 같다.
    runs = _continuous_runs(beats)
    long_runs = [r for r in runs if r["clips"] >= 3 or r["seconds"] >= 4.0]
    if long_runs:
        top = ", ".join(f"{r['from']}~{r['to']}({r['seconds']}초)" for r in long_runs[:3])
        v.append(f"컷 없이 이어지는 구간 {len(long_runs)}곳 — 원본을 그대로 트는 느낌 ({top})")

    # ★소스 편중(2026-07-24): 여러 영상을 담았는데 한 소스만 통째로 쓰면 '믹스'가 아니다.
    # 실측 사고: 후보마다 s0만/s1만/s2만 써서 원본 하나를 그대로 트는 화면이 됐다.
    vids = [c.get("video_id") for b in beats for c in _clips(b) if c.get("video_id")]
    vset = set(vids)
    if vids and len(vset) == 1 and pool_video_count and pool_video_count > 1:
        v.append(f"소스 {pool_video_count}개 중 1개({next(iter(vset))})만 사용 — 믹스가 안 됐습니다")

    secs = round(sum(float(b.get("target_seconds") or 0) for b in beats), 1)
    if target_seconds and secs and secs < target_seconds * _SHORT_RATIO:
        v.append(f"길이가 {secs}초로 목표 {target_seconds}초보다 많이 짧습니다")
    # ★너무 김(2026-07-24 실사고: 목표30초인데 77초·441자로 오버슛). 대본이 목표의 1.4배 넘으면 반려.
    if target_seconds and secs and secs > target_seconds * _LONG_RATIO:
        v.append(f"길이가 {secs}초로 목표 {target_seconds}초보다 너무 깁니다 — 대본을 줄이세요")

    return {
        "ok": not v,
        "violations": v,
        "beat_count": len(beats),
        "seconds": secs,
        "repeat_segs": sorted(repeats),
        "unique_segs": len(dup),
        "total_clips": len(all_segs),
        "sources_used": sorted(vset),
        "continuous_runs": runs,          # 컷 없이 이어진 구간(진단용 — 화면엔 위반만 뜬다)
    }
