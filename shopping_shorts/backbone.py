"""백본-인터리브 코어(§8-2·8-6). 행위(F1 action_dict)를 '못'으로 화면과 대본을 잇는다.

- coverage(): A7 스파이크 — 백본 비트의 행위를 서브 풀이 얼마나 커버하나 실측(착수 게이트).
- pick_clips_for_action(): best-of-N — 그 행위의 클립을 풀에서 고른다(화면 스왑 = 차별화 1층).

행위가 화면·대본 공통 못이라, 백본이 행위 순서를 고정하고 화면은 같은 행위의 다른 클립으로
갈아끼워도 대본(행위 지목)과 안 어긋난다. 순수함수 — DB·Gemini 없음."""
from shopping_shorts import action_dict


def segment_action(seg):
    """세그먼트의 행위 — 저장된 action 태그를 그대로 신뢰(추출기가 붙인 권위값,
    현재 사전에 없어도 존중). 없거나 '없음'이면 text+scene_desc로 사전 태깅 폴백."""
    a = seg.get("action")
    if a and a != "없음":
        return a
    return action_dict.tag_action(f"{seg.get('text', '')} {seg.get('scene_desc', '')}")


def _iter_segs(sources):
    for s in sources or []:
        vid = s.get("video_id", "")
        for seg in s.get("segments", []):
            yield vid, seg


def action_pool(pool_sources):
    """행위 → [seg(+video_id)] 인덱스. best-of-N·커버율의 공통 자료구조."""
    pool = {}
    for vid, seg in _iter_segs(pool_sources):
        a = segment_action(seg)
        if a:
            pool.setdefault(a, []).append({**seg, "video_id": vid})
    return pool


def coverage(backbone_source, pool_sources):
    """A7 스파이크: 백본 비트 행위를 풀(메인+서브)이 얼마나 커버하나.
    → {coverage_pct, covered:[행위], uncovered:[행위], anchor_actions:[순서대로]}.
    uncovered가 많으면 best-of-N 스왑 전제가 흔들림(스펙 착수 게이트)."""
    pool = action_pool(pool_sources)
    anchors = [a for _, seg in _iter_segs([backbone_source]) if (a := segment_action(seg))]
    if not anchors:
        return {"coverage_pct": 0.0, "covered": [], "uncovered": [], "anchor_actions": []}
    covered = [a for a in anchors if a in pool]
    uncovered = [a for a in anchors if a not in pool]
    return {"coverage_pct": len(covered) / len(anchors),
            "covered": sorted(set(covered)), "uncovered": sorted(set(uncovered)),
            "anchor_actions": anchors}


def beat_action_mismatch(beat):
    """비트의 나레이션 행위 vs 배정 화면 행위가 다르면 True.
    ★fit 점수를 안 믿는다 — fit5여도 '썰다↔뒤집다'면 어긋남으로 잡는다(banana 실사고).
    한쪽 행위가 없으면(모호) False = 판정 보류(오탐 방지)."""
    n_act = action_dict.tag_action(beat.get("narration", ""))
    s_act = segment_action(beat.get("primary") or {})
    return bool(n_act and s_act and n_act != s_act)


def reconcile_beat_by_action(beat, pool_sources):
    """핑퐁 장면-쪽: 나레이션 행위에 맞는 클립을 풀에서 찾아 화면 스왑.
    → (new_beat, need_rewrite). 찾으면 primary 교체+action_fixed, 못 찾으면 need_rewrite=True
    (→ 나레이션 재작성으로 넘김 = 핑퐁 대본-쪽). 나레이션 행위가 없으면 손 안 댐."""
    n_act = action_dict.tag_action(beat.get("narration", ""))
    if not n_act:
        return dict(beat), False
    clips = pick_clips_for_action(n_act, pool_sources)
    if clips:
        nb = dict(beat)
        nb["primary"] = clips[0]
        nb["fit"] = 5
        nb["action_fixed"] = True
        return nb, False
    nb = dict(beat)
    nb["need_rewrite"] = True
    return nb, True


def pick_clips_for_action(action, pool_sources, exclude_video=None):
    """그 행위의 클립들(화면 스왑 best-of-N 후보). exclude_video=백본이면 서브만 반환
    (차별화 1층: 순서·싱크는 백본, 픽셀은 다른 소스)."""
    clips = action_pool(pool_sources).get(action, [])
    if exclude_video:
        clips = [c for c in clips if c.get("video_id") != exclude_video]
    return clips
