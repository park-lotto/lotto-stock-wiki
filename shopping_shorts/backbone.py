"""백본-인터리브 코어(§8-2·8-6). 행위(F1 action_dict)를 '못'으로 화면과 대본을 잇는다.

- coverage(): A7 스파이크 — 백본 비트의 행위를 서브 풀이 얼마나 커버하나 실측(착수 게이트).
- pick_clips_for_action(): best-of-N — 그 행위의 클립을 풀에서 고른다(화면 스왑 = 차별화 1층).

행위가 화면·대본 공통 못이라, 백본이 행위 순서를 고정하고 화면은 같은 행위의 다른 클립으로
갈아끼워도 대본(행위 지목)과 안 어긋난다. 순수함수 — DB·Gemini 없음."""
import re

from shopping_shorts import action_dict

_SYLLABLES_PER_SEC = 5.7      # edit_plan과 동일(한국어 초당 음절)
_LEN_TOL = 0.35               # ±35%면 ok(넘침/모자람 판정 여유)


def narration_seconds(narration):
    """나레이션 읽는 시간(초) = 한글 음절수 / 5.7."""
    syl = len(re.sub(r"[^가-힣]", "", narration or ""))
    return syl / _SYLLABLES_PER_SEC


def clip_seconds(beat):
    """비트에 담긴 화면 총 길이(primary + alternates)."""
    segs = [beat.get("primary")] + list(beat.get("alternates") or [])
    return round(sum((s.get("end", 0) - s.get("start", 0)) for s in segs if s), 3)


def length_status(beat):
    """대사 읽는시간 vs 화면 길이. 'over'(대사가 화면보다 김=넘침)/'under'(화면이 남음)/'ok'."""
    need = narration_seconds(beat.get("narration", ""))
    have = clip_seconds(beat)
    if need <= 0 or have <= 0:
        return "ok"
    if have < need * (1 - _LEN_TOL):
        return "over"     # 화면이 모자라 대사가 넘어감
    if have > need * (1 + _LEN_TOL):
        return "under"    # 화면이 대사보다 많이 남음
    return "ok"


def fill_clips_to_cover(beat, pool_sources):
    """화면이 대사보다 짧으면(over) 같은 행위 클립을 풀에서 더 붙여 길이를 채운다.
    이미 담긴 seg_id는 제외. 대사 읽는시간 근처까지만 채운다(과충전 방지)."""
    need = narration_seconds(beat.get("narration", ""))
    if length_status(beat) != "over":
        return dict(beat)
    action = segment_action(beat.get("primary") or {}) or \
        action_dict.tag_action(beat.get("narration", ""))
    if not action:
        return dict(beat)
    used = {(beat.get("primary") or {}).get("seg_id")}
    used |= {a.get("seg_id") for a in (beat.get("alternates") or [])}
    nb = dict(beat)
    nb["alternates"] = list(beat.get("alternates") or [])
    for clip in pick_clips_for_action(action, pool_sources):
        if clip.get("seg_id") in used:
            continue
        nb["alternates"].append(clip)
        used.add(clip.get("seg_id"))
        if clip_seconds(nb) >= need:
            break
    return nb


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


def pick_backbone(sources):
    """제일 완결된 영상 = 백본. 휴리스틱: 세그먼트(과정 조각) 최다 영상.
    동수면 먼저 온 것. 소스 없으면 None."""
    best, best_n = None, -1
    for s in sources or []:
        n = len(s.get("segments") or [])
        if n > best_n:
            best, best_n = s.get("video_id"), n
    return best


def order_by_backbone(beats, backbone_video):
    """백본 순서 고정(§8-2·D13): movable body 비트의 화면을 백본 시간순으로 재배치.
    나레이션(대사)은 제자리 — 화면만 (재료→조리→완성) 흐르게. 제외(앵커):
      ①꼬리(마지막) 비트 ②action_fixed(핑퐁이 맞춘) 비트 ③백본 영상이 아닌 화면.
    이렇게 '결과 말하는데 조리중간 화면'류 순서 어긋남을 잡는다."""
    if not beats:
        return beats
    body, tail = beats[:-1], beats[-1]
    movable = [i for i, b in enumerate(body)
               if not b.get("action_fixed")
               and (b.get("primary") or {}).get("video_id") == backbone_video]
    clips = sorted((body[i].get("primary") for i in movable),
                   key=lambda p: (p or {}).get("start", 0.0))
    out = [dict(b) for b in body]
    for i, clip in zip(movable, clips):
        out[i] = dict(body[i])
        out[i]["primary"] = clip
        out[i]["respined_backbone"] = True
    out.append(dict(tail))
    return out


def ping_pong_reconcile(beats, pool_sources, rewrite_call=None, max_rounds=2):
    """핑퐁(대본↔장면 왕복). 매 라운드:
      1) action 불일치 비트 찾기(fit 안 믿음 — beat_action_mismatch).
      2) 각 비트: 같은 행위 클립이 풀에 있으면 **화면 스왑**(장면 쪽), 없으면 재작성 대기(대본 쪽).
      3) 재작성 대기 비트 나레이션을 화면에 맞게 rewrite_call로 1회 수정.
    불일치 0 또는 max_rounds 소진까지 반복. rewrite_call(beats)->{beat_idx: 새나레이션}.
    rewrite_call 없거나 실패면 그 비트는 스왑만(대본 쪽 스킵). 원본 mutate 안 함."""
    out = [dict(b) for b in beats]
    for _ in range(max_rounds):
        bad = [i for i, b in enumerate(out) if beat_action_mismatch(b)]
        if not bad:
            break
        need_rewrite = []
        for i in bad:
            nb, still = reconcile_beat_by_action(out[i], pool_sources)
            out[i] = nb
            if still:
                need_rewrite.append(out[i])
        if need_rewrite and rewrite_call is not None:
            try:
                fixes = rewrite_call(need_rewrite) or {}
            except Exception:
                fixes = {}
            for b in out:
                if b.get("beat_idx") in fixes and fixes[b["beat_idx"]]:
                    b["narration"] = fixes[b["beat_idx"]]
                    b.pop("need_rewrite", None)
    # 길이 맞춤: 스왑/원본 클립이 대사보다 짧으면(over) 같은 행위 클립 더 붙여 채운다
    # (화면이 대사 도중 끊겨 '넘어가'는 것 방지 — 캡컷 수작업 제거).
    for i, b in enumerate(out):
        if length_status(b) == "over":
            out[i] = fill_clips_to_cover(b, pool_sources)
    return out


def pick_clips_for_action(action, pool_sources, exclude_video=None):
    """그 행위의 클립들(화면 스왑 best-of-N 후보). exclude_video=백본이면 서브만 반환
    (차별화 1층: 순서·싱크는 백본, 픽셀은 다른 소스)."""
    clips = action_pool(pool_sources).get(action, [])
    if exclude_video:
        clips = [c for c in clips if c.get("video_id") != exclude_video]
    return clips
