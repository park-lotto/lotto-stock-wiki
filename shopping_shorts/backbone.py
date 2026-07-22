"""백본-인터리브 코어(§8-2·8-6). 행위(F1 action_dict)를 '못'으로 화면과 대본을 잇는다.

- coverage(): A7 스파이크 — 백본 비트의 행위를 서브 풀이 얼마나 커버하나 실측(착수 게이트).
- pick_clips_for_action(): best-of-N — 그 행위의 클립을 풀에서 고른다(화면 스왑 = 차별화 1층).

행위가 화면·대본 공통 못이라, 백본이 행위 순서를 고정하고 화면은 같은 행위의 다른 클립으로
갈아끼워도 대본(행위 지목)과 안 어긋난다. 순수함수 — DB·Gemini 없음."""
import re
from collections import Counter

from shopping_shorts import action_dict
from shopping_shorts import pattern_bank

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


def target_chars(beat):
    """이 비트 화면 길이에 들어갈 최대 한글 글자수 = clip_seconds * 5.7."""
    return int(clip_seconds(beat) * _SYLLABLES_PER_SEC)


def _broll_segs(pool_sources, src_count, exclude_seg_ids, prefer_video=None):
    """행위 무관 B롤 후보. **같은 소스(prefer_video=primary 릴) 우선** — 같은 요리라 의미가
    안정된다(엉뚱한 타요리 조각 삽입 방지, 2026-07-21 바나나 커스터드 실사고). 같은 소스의
    안 쓴 조각을 다 쓴 뒤에야 다른 소스로 넘어가되, 그때는 덜 쓴 소스 우선. 이미 쓴 seg_id·
    길이 0 제외."""
    segs = [{**seg, "video_id": vid} for vid, seg in _iter_segs(pool_sources)
            if seg.get("seg_id") not in exclude_seg_ids
            and not seg.get("has_effect")                 # 원본 효과 박힌 조각은 B롤로 안 씀
            and (seg.get("end", 0) - seg.get("start", 0)) > 0.05]
    segs.sort(key=lambda c: (c.get("video_id") != prefer_video,      # 같은 소스 먼저(False<True)
                             src_count.get(c.get("video_id"), 0)))
    return segs


def fill_clips_to_cover(beat, pool_sources, src_count=None, need=None):
    """화면이 대사보다 짧으면 풀에서 클립을 더 붙여 길이를 채운다. 원본 mutate 안 함.
    need: 채울 목표 초. None이면 나레이션 추정(narration_seconds)으로 length_status가 'over'일
    때만 채운다(기존 동작). 값이 주어지면(=실 TTS 길이, TTS 후 재보정) clip_seconds가 그보다
    짧을 때 채운다 — 추정≠실제로 생긴 틈이 프리즈로 새는 걸 막는다(뿌리 fix, 2026-07-21).
    1층 — 같은 행위 클립(대본 지목과 안 어긋남). 2층 — 행위로 못 채우면 **같은 소스 우선 B롤**로
    채운다(반복은 dedup_and_balance가 비트 사이에서 잡고, 여기선 요리 일관성이 우선)."""
    if need is None:
        if length_status(beat) != "over":
            return dict(beat)
        need = narration_seconds(beat.get("narration", ""))
    elif clip_seconds(beat) >= need:
        return dict(beat)
    used = {(beat.get("primary") or {}).get("seg_id")}
    used |= {a.get("seg_id") for a in (beat.get("alternates") or [])}
    nb = dict(beat)
    nb["alternates"] = list(beat.get("alternates") or [])
    # 1층 — 같은 행위 클립(화면-대본 못 유지).
    action = segment_action(beat.get("primary") or {}) or \
        action_dict.tag_action(beat.get("narration", ""))
    if action:
        for clip in pick_clips_for_action(action, pool_sources):
            if clip.get("seg_id") in used:
                continue
            nb["alternates"].append(clip)
            used.add(clip.get("seg_id"))
            if clip_seconds(nb) >= need:
                return nb
    # 2층 — 아직 모자라면 같은 소스 우선 B롤(요리 일관성).
    if clip_seconds(nb) < need:
        sc = src_count if src_count is not None else Counter()
        prim_vid = (beat.get("primary") or {}).get("video_id")
        for clip in _broll_segs(pool_sources, sc, used, prefer_video=prim_vid):
            nb["alternates"].append(clip)
            used.add(clip.get("seg_id"))
            sc[clip.get("video_id")] = sc.get(clip.get("video_id"), 0) + 1
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
    """행위 → [seg(+video_id)] 인덱스. best-of-N·커버율의 공통 자료구조.
    원본 효과가 박힌 조각(has_effect)은 B롤 스왑/커버 후보에서 제외한다(2026-07-21)."""
    pool = {}
    for vid, seg in _iter_segs(pool_sources):
        if seg.get("has_effect"):
            continue
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


_BACKBONE_SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {"beats": {"type": "array", "items": {
        "type": "object",
        "properties": {"narration": {"type": "string"}, "seg_id": {"type": "string"}},
        "required": ["narration", "seg_id"]}}},
    "required": ["beats"],
}


def _backbone_script_prompt(flow, inventory, target_seconds, style_block=""):
    flow_lines = "\n".join(
        f"  {i+1}. [{f.get('action') or '-'}] {f.get('scene_desc', '')} (~{f.get('seconds', 0)}초)"
        for i, f in enumerate(flow))
    inv_lines = "\n".join(
        f"  {it['seg_id']} [{it.get('action') or '-'}] {it.get('scene_desc', '')}"
        for it in inventory)
    return (
        f"너는 한국 쇼핑 숏폼 대본 작가다. 아래 '잘된 영상의 흐름'을 뼈대로, 약 {target_seconds}초짜리 "
        "**완전히 새로운 우리 대본**을 써라. 흐름(순서·리듬·강약)만 참고하고 문장은 절대 베끼지 마라.\n"
        "★반드시 아래 '실제 장면 목록'에 있는 seg_id만 골라 써라 — 목록에 없는 장면을 요구하는 "
        "대사는 쓰지 마라(있는 장면으로 말이 되게).\n\n"
        f"[잘된 영상 흐름 — 순서·행위·길이 참고]\n{flow_lines}\n\n"
        f"[실제 장면 목록 — 이 seg_id들만 사용]\n{inv_lines}\n\n"
        # ★짤드라마·훅·은행 부품(style_block) 주입 — 이게 없으면 흐름만 밋밋하게 따라가
        #  "여러분 ~해요/알려드려요" 설명체가 나온다(2026-07-22 실사고: 대본 초기화 현상).
        + ((style_block + "\n\n") if style_block else "")
        + "각 비트: narration(실제 읽을 우리 구어체 대사), seg_id(그 대사에 맞는 실제 장면).\n"
        # ★★내용(훅·말투·어미·CTA)은 위 [은행 부품]에서 가져와 쓴다 — 우리가 실제 우승작에서
        #  수집·큐레이션한 것이라, 여기에 예시를 하드코딩하면 은행을 묻어버린다(2026-07-22 교훈).
        "★내용 규칙(★은행 우선): 훅·말투·어미·CTA는 **위에 준 [은행 부품] 목록에서 골라 써라**. "
        "네가 새로 지어내지 말고 그 훅/어미/CTA를 실제로 활용해라(은행이 비었을 때만 직접 창작). "
        "어떤 은행 훅을 첫 비트에, 어떤 어미·CTA를 어디에 썼는지가 드러나게.\n"
        "★구조 규칙(내용 아님): ①첫 비트는 강한 훅으로 연다(설명체 오프너 금지). ②중간 비트도 "
        "행위를 '설명'하지 마라 — 화면이 이미 그 행위를 보여주므로, 대사는 반응·긴장·비법·기대로 "
        "이야기를 민다. ③스토리 아크를 비트에 분배: 앞=인물·상황 설정, 중간=그 인물을 버리지 말고 "
        "긴장·기대로 이어감, 끝=그 인물의 반응·결과+CTA. 앞에서 세운 인물이 중간·끝까지 관통한다.\n"
        "화면=행위, 대사=이야기. 좋은 대사 나열이 아니라 '한 사람의 이야기'다. 요리 순서 나열 금지.\n"
        "JSON만 출력.")


def generate_backbone_script(flow, inventory, target_seconds, call=None, style_block=""):
    """백본 흐름 + 실제 장면 인벤토리 → 완전히 새 우리 대본(비트별 narration + 고른 seg_id).
    인벤토리 밖 seg_id는 드롭(없는 장면 요구 차단). call None/실패면 [].
    style_block: 짤드라마 규칙 + 은행 훅·말투 부품(edit_plan이 조립해 주입) — 없으면 밋밋해진다."""
    if call is None:
        call = pattern_bank._default_call
    valid = {it.get("seg_id") for it in (inventory or [])}
    res = call(_backbone_script_prompt(flow or [], inventory or [], target_seconds,
                                       style_block=style_block),
               _BACKBONE_SCRIPT_SCHEMA)
    if not res or not isinstance(res, dict):
        return []
    out = []
    for b in res.get("beats", []):
        if b.get("seg_id") in valid and (b.get("narration") or "").strip():
            out.append({"narration": b["narration"].strip(), "seg_id": b["seg_id"]})
    return out


def backbone_flow(backbone_source):
    """백본 '흐름' 뼈대 = 순서대로 [{seg_id, action, scene_desc, seconds}]. 대사(narration) 없음.
    새 대본이 이 흐름(순서·행위·대략 길이)을 따르되 문장은 우리 것으로 쓴다(카피 아님)."""
    flow = []
    for seg in backbone_source.get("segments") or []:
        flow.append({
            "seg_id": seg.get("seg_id"),
            "action": segment_action(seg),
            "scene_desc": seg.get("scene_desc", ""),
            "seconds": round((seg.get("end", 0) - seg.get("start", 0)), 2),
        })
    return flow


def scene_inventory(sources):
    """대본 생성기에 줄 '실제 존재하는 장면 목록' — 없는 장면을 요구하는 대본을 원천 차단.
    → [{video_id, seg_id, action, scene_desc}]."""
    return [{"video_id": vid, "seg_id": seg.get("seg_id"),
             "action": segment_action(seg), "scene_desc": seg.get("scene_desc", "")}
            for vid, seg in _iter_segs(sources)]


def _vid_of(seg):
    return seg.get("video_id") or (seg.get("seg_id") or "").rsplit("-", 1)[0]


def dedup_and_balance(beats, pool_sources):
    """전역 중복제거 + 소스 균형. 각 비트 primary가 이미 쓴 클립이면, 같은 행위의 '안 쓴'
    클립으로 교체하되 **덜 쓴 소스 우선**. 반복장면(한 클립 여러 비트)과 한 소스 편중을 동시에 해소.
    같은 행위 대체가 없으면 원본 유지(억지 교체 안 함)."""
    used = set()
    src_count = Counter()
    out = []
    for b in beats:
        nb = dict(b)
        p = nb.get("primary") or {}
        sid = p.get("seg_id")
        if sid in used:
            action = segment_action(p)
            if action:
                fresh = [c for c in pick_clips_for_action(action, pool_sources)
                         if c.get("seg_id") not in used]
                if fresh:
                    fresh.sort(key=lambda c: src_count[_vid_of(c)])   # 덜 쓴 소스 우선
                    nb["primary"] = fresh[0]
                    p = fresh[0]
                    nb["balanced"] = True
        used.add(p.get("seg_id"))
        src_count[_vid_of(p)] += 1
        out.append(nb)
    return out


# 백본 가능 플랫폼 = 한글 대본이 있는 것만(인스타·유튜브). 나머지(샤오홍슈·도우인 등)=서브 전용.
_BACKBONE_PLATFORMS = {"instagram", "youtube"}

_PLATFORM_DOMAINS = [
    ("instagram", ("instagram.com",)),
    ("youtube", ("youtube.com", "youtu.be")),
    ("xiaohongshu", ("xiaohongshu.com", "xhslink.com", "rednote")),
    ("douyin", ("douyin.com",)),
    ("tiktok", ("tiktok.com",)),
]


def platform_of(url):
    """URL 도메인 → 플랫폼 이름. 모르면 ''."""
    u = (url or "").lower()
    for name, domains in _PLATFORM_DOMAINS:
        if any(d in u for d in domains):
            return name
    return ""


def score_backbones(sources, meta=None):
    """각 소스를 백본 후보로 채점 → [{video_id, coverage, engagement, score}] 점수 내림차순.
    ★60대는 어느 걸 메인으로 둘지 판단 못 하니 시스템이 점수로 자동 선정하기 위한 근거(2026-07-22).
      · coverage = 그 소스의 행위들을 '나머지 풀'이 얼마나 커버하나(재조합 가능성) — 높을수록
        장면 갈아끼우기가 잘 돼 좋은 뼈대.
      · engagement = 댓글수(meta) 정규화.
      score = 0.6·coverage + 0.4·engagement. 순수 계산(추가 Gemini 없음)."""
    if not sources:
        return []
    meta = meta or {}
    max_c = max((meta.get(s.get("video_id"), {}).get("comments") or 0) for s in sources) or 1
    out = []
    for s in sources:
        vid = s.get("video_id")
        others = [o for o in sources if o.get("video_id") != vid]
        cov = coverage(s, others)["coverage_pct"] if others else 0.0
        eng = (meta.get(vid, {}).get("comments") or 0) / max_c
        out.append({"video_id": vid, "coverage": round(cov, 3),
                    "engagement": round(eng, 3), "score": round(0.6 * cov + 0.4 * eng, 3)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def pick_backbone(sources, meta=None, forced=None):
    """백본 선정(사장님 규칙):
      0) forced(사장님이 UI에서 지정한 메인)가 있으면 그게 무조건 우선(override).
      1) 백본 = 인스타·유튜브(한글 대본)만 후보. 플랫폼 아는 소스 중 그 둘만.
      2) 후보 중 **score_backbones 최고점**(재조합 가능성 coverage + 참여도) — 60대가 메인을
         안 골라도 시스템이 '잘 섞일' 백본을 자동 선정한다(2026-07-22, 예전 댓글수·세그먼트수 대체).
    meta 없어도 coverage(순수계산)로 채점된다. 소스 없거나 후보 0이면 None."""
    if not sources:
        return None
    if forced and any(s.get("video_id") == forced for s in sources):
        return forced
    meta = meta or {}
    known = [s for s in sources if meta.get(s.get("video_id"), {}).get("platform")]
    if known:
        cands = [s for s in known
                 if meta[s["video_id"]]["platform"].lower() in _BACKBONE_PLATFORMS]
        cands = cands or [s for s in sources]   # 인스타/유튜브 하나도 없으면 전체(폴백)
    else:
        cands = list(sources)                   # 플랫폼 정보 없음 → coverage로 채점
    scores = {r["video_id"]: r["score"] for r in score_backbones(sources, meta)}
    # coverage 동점(예: 세그먼트 없음)이면 세그먼트 최다로 tiebreak → 기존 동작 보존.
    return max(cands, key=lambda s: (scores.get(s.get("video_id"), 0.0),
                                     len(s.get("segments") or []))).get("video_id")


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


def ping_pong_reconcile(beats, pool_sources, rewrite_call=None, max_rounds=2, trim_call=None):
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
    # 길이 맞춤 1) 화면 늘리기: 대사보다 화면 짧으면(over) 클립 더 붙임. src_count를 전 비트에
    # 걸쳐 유지해 fill이 안 쓴 릴부터 끌어오게 한다(한 릴 편중=반복장면 해소, 2026-07-21).
    src_count = Counter()
    for b in out:
        v = (b.get("primary") or {}).get("video_id")
        if v:
            src_count[v] += 1
    for i, b in enumerate(out):
        if length_status(b) == "over":
            out[i] = fill_clips_to_cover(b, pool_sources, src_count=src_count)
    # 길이 맞춤 2) 대사 줄이기: 화면을 못 늘려 여전히 넘치면(over) 대사를 화면 길이에
    # 맞게 줄인다(trim_call). '부어보세요'가 완성 장면까지 넘어가는 것 방지(캡컷 수작업 제거).
    over = [dict(out[i], beat_idx=out[i].get("beat_idx", i), target_chars=target_chars(out[i]))
            for i in range(len(out)) if length_status(out[i]) == "over" and target_chars(out[i]) > 0]
    if over and trim_call is not None:
        try:
            trims = trim_call(over) or {}
        except Exception:
            trims = {}
        for b in out:
            bi = b.get("beat_idx")
            if bi in trims and trims[bi]:
                b["narration"] = trims[bi]
                b["length_trimmed"] = True
    return out


def ensure_sources_used(beats, pool_sources):
    """서브 의무삽입(P1): 모든 소스가 최소 1회 화면에 뜨게 강제. Gemini 선택편중(s2=0)은
    dedup_and_balance('반복'만 고침)로 못 잡아, 안 쓰인 소스의 클립을 **같은 행위**(narration↔clip)로
    비트 primary에 밀어넣는다 — 행위 못을 유지하므로 sync 안 깨진다. 행위가 안 맞으면 억지삽입
    안 함(mismatch 금지). 교체 대상은 현재 primary가 가장 많이 쓰인 소스인 비트 우선(유일사용
    소스는 안 뺏는다). 소스 1개 이하면 무변경."""
    all_vids = {s.get("video_id") for s in (pool_sources or []) if s.get("segments")}
    all_vids.discard(None)
    if len(all_vids) <= 1:
        return beats
    out = [dict(b) for b in beats]
    for vid in sorted(all_vids):
        counts = Counter((b.get("primary") or {}).get("video_id") for b in out)
        if counts.get(vid, 0) > 0:
            continue  # 이미 쓰임
        by_action = action_pool([s for s in pool_sources if s.get("video_id") == vid])
        if not by_action:
            continue
        # 현재 primary 소스가 많이 쓰인 비트부터(유일사용 소스를 뺏지 않게)
        order = sorted(range(len(out)),
                       key=lambda i: -counts.get((out[i].get("primary") or {}).get("video_id"), 0))
        for i in order:
            b = out[i]
            cur_vid = (b.get("primary") or {}).get("video_id")
            if counts.get(cur_vid, 0) <= 1:
                continue  # 그 비트의 소스가 유일사용이면 건드리지 않음
            n_act = action_dict.tag_action(b.get("narration", ""))
            clips = by_action.get(n_act) if n_act else None
            if not clips:
                continue
            nb = dict(b)
            nb["primary"] = clips[0]
            nb["forced_source"] = True
            out[i] = nb
            break
    return out


def pick_clips_for_action(action, pool_sources, exclude_video=None):
    """그 행위의 클립들(화면 스왑 best-of-N 후보). exclude_video=백본이면 서브만 반환
    (차별화 1층: 순서·싱크는 백본, 픽셀은 다른 소스)."""
    clips = action_pool(pool_sources).get(action, [])
    if exclude_video:
        clips = [c for c in clips if c.get("video_id") != exclude_video]
    return clips
