"""백본-인터리브 코어(§8-2·8-6). 행위(F1 action_dict)를 '못'으로 화면과 대본을 잇는다.

- coverage(): A7 스파이크 — 백본 비트의 행위를 서브 풀이 얼마나 커버하나 실측(착수 게이트).
- pick_clips_for_action(): best-of-N — 그 행위의 클립을 풀에서 고른다(화면 스왑 = 차별화 1층).

행위가 화면·대본 공통 못이라, 백본이 행위 순서를 고정하고 화면은 같은 행위의 다른 클립으로
갈아끼워도 대본(행위 지목)과 안 어긋난다. 순수함수 — DB·Gemini 없음."""
from shopping_shorts import action_dict


def segment_action(seg):
    """세그먼트의 행위 — 저장된 action 태그 우선, 없으면 text+scene_desc로 사전 태깅."""
    a = seg.get("action")
    if a in action_dict.ACTION_VOCAB:
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


def pick_clips_for_action(action, pool_sources, exclude_video=None):
    """그 행위의 클립들(화면 스왑 best-of-N 후보). exclude_video=백본이면 서브만 반환
    (차별화 1층: 순서·싱크는 백본, 픽셀은 다른 소스)."""
    clips = action_pool(pool_sources).get(action, [])
    if exclude_video:
        clips = [c for c in clips if c.get("video_id") != exclude_video]
    return clips
