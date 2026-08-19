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


# 완성·시즐 등 '맛있어 보이는' 비주얼 키워드(2026-07-22 사장님 원칙: 앰비언트 비트는 매칭
# 욕심 대신 음식이 맛있어 보이는 장면 위주). scene_desc에 이게 있으면 B롤로 우선.
_VISUAL_KEYWORDS = ("완성", "클로즈", "클로즈업", "치즈", "육즙", "시즐", "흐르", "윤기", "노릇",
                    "플레이팅", "먹음직", "김이", "부드럽", "촉촉", "바삭", "당기", "늘어", "골든")


def _visual_score(seg):
    """세그먼트가 '맛있어 보이는 비주얼'인가 — scene_desc 키워드 기반(0~N). 앰비언트 채움에서
    조리 중간 파편보다 완성·클로즈업·시즐을 우선하게 한다."""
    desc = seg.get("scene_desc", "") or ""
    return sum(1 for kw in _VISUAL_KEYWORDS if kw in desc)


def _seg_dur(seg):
    return (seg.get("end", 0) - seg.get("start", 0)) if seg else 0.0


# 비트 성격 ↔ 어울리는 shot_role(2026-08-01 실사고). 마무리 자리에 조리 과정이 다시
# 나오면 "조리 재방송"이 된다 — 사장님 실측 제보: 완성품→조리→완성품→조리→완성품.
_BEAT_ROLE_SHOTS = {
    "cta": ("완성", "after"),
    "결과": ("완성", "after"),
    "result": ("완성", "after"),
    "마무리": ("완성", "after"),
    "resolution": ("완성", "after"),
    "과정": ("사용중",),
    "process": ("사용중",),
    "해결": ("사용중",),
    "solution": ("사용중",),
}


def _wanted_shots(beat_role):
    r = (beat_role or "").strip().lower()
    for k, v in _BEAT_ROLE_SHOTS.items():
        if k in r:
            return v
    return ()


def _broll_segs(pool_sources, src_count, exclude_seg_ids, prefer_video=None, min_shot=0.0,
                want_shots=()):
    """행위 무관 B롤 후보. **같은 소스(prefer_video=primary 릴) 우선** — 같은 요리라 의미가
    안정된다(엉뚱한 타요리 조각 삽입 방지, 2026-07-21 바나나 커스터드 실사고). 같은 소스의
    안 쓴 조각을 다 쓴 뒤에야 다른 소스로 넘어가되, 그때는 덜 쓴 소스 우선. 이미 쓴 seg_id·
    길이 0 제외.
    min_shot(2026-07-22): 이보다 짧은 파편은 뒤로 미룬다(뚝뚝 끊김 방지). 같은 소스 안에서는
    ★맛있어 보이는 비주얼(_visual_score) → 긴 컷 순으로 골라 앰비언트를 매력적으로 채운다."""
    segs = [{**seg, "video_id": vid} for vid, seg in _iter_segs(pool_sources)
            if seg.get("seg_id") not in exclude_seg_ids
            and not seg.get("has_effect")                 # 원본 효과 박힌 조각은 B롤로 안 씀
            and _seg_dur(seg) > 0.05]
    # ★비트 성격에 맞는 컷 먼저(2026-08-01). CTA·결과 자리엔 완성컷, 과정 자리엔 조리컷을
    #   앞세운다 — 실측(job a75c22f644ad)에서 CTA 비트가 s0의 조리 전과정(설탕붓기→잼섞기
    #   →짜넣기→뚜껑덮기) 4컷을 통째로 끌어와 영상 끝이 "조리 재방송"이 됐다. 세 후보 모두
    #   같은 모양이라 취향이 아니라 구조 문제였다.
    #   ★버리지 않고 **순서만** 미룬다 — 이 함수가 채울 재료를 줄이면 렌더가 정지/슬로우로
    #   때우는 프리즈가 돌아온다(이 구역의 두더지잡기 이력). 맞는 계열이 없으면 종전대로
    #   전부 후보로 남는다.
    segs.sort(key=lambda c: (bool(want_shots) and c.get("shot_role") not in want_shots,
                             c.get("video_id") != prefer_video,      # 같은 소스 먼저(False<True)
                             src_count.get(c.get("video_id"), 0),
                             _seg_dur(c) < min_shot,                  # 너무 짧은 파편은 뒤로
                             -_visual_score(c),                       # 맛있어 보이는 것 우선
                             -_seg_dur(c)))                           # 긴 컷 우선(파편 억제)
    return segs


def fill_clips_to_cover(beat, pool_sources, src_count=None, need=None,
                        max_clips=None, min_shot=None, avoid_segs=None):
    """화면이 대사보다 짧으면 풀에서 클립을 더 붙여 길이를 채운다. 원본 mutate 안 함.
    need: 채울 목표 초. None이면 나레이션 추정(narration_seconds)으로 length_status가 'over'일
    때만 채운다(기존 동작). 값이 주어지면(=실 TTS 길이, TTS 후 재보정) clip_seconds가 그보다
    짧을 때 채운다 — 추정≠실제로 생긴 틈이 프리즈로 새는 걸 막는다(뿌리 fix, 2026-07-21).
    1층 — 같은 행위 클립(대본 지목과 안 어긋남). 2층 — 행위로 못 채우면 **같은 소스 우선 B롤**로
    채운다(반복은 dedup_and_balance가 비트 사이에서 잡고, 여기선 요리 일관성이 우선).
    ★max_clips(2026-07-22): 비트당 총 클립 상한 — 이만큼 차면 부족해도 파편을 그만 붙인다
    (모자란 길이는 conform/홀드가 흡수, 뚝뚝 끊김 방지). min_shot: 긴 컷 우선 정렬 기준."""
    from shopping_shorts import config
    max_clips = getattr(config, "MAX_CLIPS_PER_BEAT", 3) if max_clips is None else max_clips
    min_shot = getattr(config, "MIN_SHOT_SECONDS", 1.2) if min_shot is None else min_shot
    if need is None:
        if length_status(beat) != "over":
            return dict(beat)
        need = narration_seconds(beat.get("narration", ""))
    elif clip_seconds(beat) >= need:
        return dict(beat)
    used = {(beat.get("primary") or {}).get("seg_id")}
    used |= {a.get("seg_id") for a in (beat.get("alternates") or [])}
    # ★avoid_segs(2026-07-23): 다른 비트들이 이미 쓴 seg. TTS 후 _refill이 fill을 비트마다
    # 돌릴 때 이걸 넘겨 '비트 사이 동일 장면 반복'을 막는다(dedup은 plan에서만 돌아 무력했다).
    # 풀이 모자라 못 채우면 반복 대신 홀드/conform이 흡수 — 사장님 "그만 좀 반복하자".
    if avoid_segs:
        used |= set(avoid_segs)
    nb = dict(beat)
    nb["alternates"] = list(beat.get("alternates") or [])

    def _count():
        return 1 + len(nb["alternates"])   # primary + alternates
    # 1층 — 같은 행위 클립(화면-대본 못 유지). ★긴 컷 우선(파편 억제).
    action = segment_action(beat.get("primary") or {}) or \
        action_dict.tag_action(beat.get("narration", ""))
    if action and _count() < max_clips:
        cands = [c for c in pick_clips_for_action(action, pool_sources)
                 if c.get("seg_id") not in used]
        cands.sort(key=lambda c: -_seg_dur(c))
        for clip in cands:
            nb["alternates"].append(clip)
            used.add(clip.get("seg_id"))
            if clip_seconds(nb) >= need or _count() >= max_clips:
                return nb
    # 2층 — 아직 모자라면 같은 소스 우선 B롤(비주얼·긴 컷 우선). 상한까지만.
    if clip_seconds(nb) < need and _count() < max_clips:
        sc = src_count if src_count is not None else Counter()
        prim_vid = (beat.get("primary") or {}).get("video_id")
        for clip in _broll_segs(pool_sources, sc, used, prefer_video=prim_vid, min_shot=min_shot,
                                want_shots=_wanted_shots(beat.get("role"))):
            nb["alternates"].append(clip)
            used.add(clip.get("seg_id"))
            sc[clip.get("video_id")] = sc.get(clip.get("video_id"), 0) + 1
            if clip_seconds(nb) >= need or _count() >= max_clips:
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


def beat_role_mismatch(beat):
    """비트의 **역할**과 배정 화면의 **결(shot_role)**이 어긋나면 True.

    ★왜 두 번째 축이 필요한가(2026-08-18 사장님 "장면매칭이 왜 이렇게 힘드냐"):
      기존 판정축은 `beat_action_mismatch` 하나뿐인데 그건 **동사사전 30개**에 매달려 있다.
      사전이 요리·살림 전용(자르다·붓다·섞다·굽다…)이라 스토리형 대사
      ("전쟁 치를 뻔한 거 있죠?")엔 동사가 없어 판정이 통째로 보류된다.
      라이브 실측(2026-08-18, 최근 잡 30개·비트 168건): **대사행위 None이 148건(88%)**.
      → 어긋남 미검출 → `_verify_fits`가 fit을 못 깎음 → fit 5로 남음
      → `_repick_weak_beats`(fit<=3 대상)에 안 걸림 → **아무도 안 고친다.**
      실측 결과 훅·CTA 58건 중 **27건이 어긋났는데 fit>=4라 교정 대상에서 빠졌다**
      (fit=5 자기신고 37건 중 26건 = 70%가 실제로는 결이 어긋남).

    그래서 동사가 없어도 도는 축을 하나 더 세운다. 근거는 `shot_role`(라이브 실측 채움률
    **100%**) — 훅·CTA엔 완성/after, 해결·결과엔 사용중/조리가 와야 한다.

    ★판단표를 새로 만들지 않는다(0순위-B) — `edit_plan._ROLE_WANT_SHOTS` 한 곳만 쓴다.
      그 표는 `scene_lab.html`의 useTags와도 짝이라, 여기서 또 적으면 세 벌이 된다.

    보수적으로 판정한다(오탐이 나면 멀쩡한 화면을 갈아치운다):
      · 역할을 모르면(표에 없는 역할) 보류
      · 화면에 shot_role이 없으면 보류
      · **1순위·차선 어디에도 안 들면** 그때만 어긋남
        ★차선까지 봐주는 이유: 소재에 1순위 결이 아예 없어 정당하게 차선을 고른 경우가 있다
          (레시피엔 before·문제가 0건 — `_ROLE_WANT_SHOTS` 주석의 실측). 그걸 어긋남으로
          치면 고칠 수 없는 걸 계속 재픽하게 된다.
    """
    from shopping_shorts import edit_plan
    role = (beat.get("role") or "").strip().lower()
    if not role:
        return False
    sr = ((beat.get("primary") or {}).get("shot_role") or "").strip()
    if not sr:
        return False
    for words, shots, alt, _why in edit_plan._ROLE_WANT_SHOTS:
        if any(w in role for w in words):
            return sr not in (set(shots) | set(alt))
    return False      # 표에 없는 역할 → 보류


def reconcile_beat_by_action(beat, pool_sources, exclude_seg_ids=None):
    """핑퐁 장면-쪽: 나레이션 행위에 맞는 클립을 풀에서 찾아 화면 스왑.
    → (new_beat, need_rewrite). 찾으면 primary 교체+action_fixed, 못 찾으면 need_rewrite=True
    (→ 나레이션 재작성으로 넘김 = 핑퐁 대본-쪽). 나레이션 행위가 없으면 손 안 댐.
    exclude_seg_ids: 이번 ping_pong_reconcile 호출에서 이미 다른 비트가 스왑으로 가져간
    seg_id 집합(2026-08-01) — 안 주면(None) 제외 없이 기존 동작 그대로."""
    n_act = action_dict.tag_action(beat.get("narration", ""))
    if not n_act:
        return dict(beat), False
    clips = pick_clips_for_action(n_act, pool_sources, exclude_seg_ids=exclude_seg_ids)
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
    """백본 '흐름' 뼈대 = 순서대로 [{seg_id, action, scene_desc, seconds, text}].
    text = A 원본 대사/자막 gist(있으면). 새 대본이 이 흐름(순서·행위·**스토리 전개**)을
    창의적으로 변형해 따르되 문장은 우리 것으로 쓴다(카피 아님, 2026-07-27 흐름계승).
    무자막 소스는 text가 빈 문자열 — 그땐 scene_desc/action이 흐름 역할."""
    flow = []
    for seg in backbone_source.get("segments") or []:
        gist = (seg.get("text") or seg.get("narration") or seg.get("caption") or "").strip()
        flow.append({
            "seg_id": seg.get("seg_id"),
            "action": segment_action(seg),
            "scene_desc": seg.get("scene_desc", ""),
            "seconds": round((seg.get("end", 0) - seg.get("start", 0)), 2),
            "text": gist[:60],
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


# 포인트 비트 = 결정적 '투입' 행위(비법 소스 얹기·바르기·뿌리기 등). 이 비트는 그 행위 장면이
# 영상의 핵심이라 정확 매칭+길게 홀드해야 한다(2026-07-22 사장님 원칙). 나머지(앰비언트)는
# 매칭 욕심 대신 맛있어 보이는 비주얼 위주.
_POINT_ACTIONS = {"붓다", "뿌리다", "올리다", "바르다", "짜다", "얹다", "두드리다"}


def is_point_beat(beat):
    """이 비트가 포인트(결정적 투입 행위)인가 — 나레이션 행위가 _POINT_ACTIONS면 True.
    포인트면 그 행위 장면을 주인공으로 길게 홀드하고 파편 B롤로 묻지 않는다."""
    n_act = action_dict.tag_action(beat.get("narration", "") or "")
    return n_act in _POINT_ACTIONS


_ADJ_TOL = 0.35   # 앞 클립 끝과 다음 클립 시작이 이 이내면 '이어붙임'(=컷이 아님)


def is_continuous(prev_clip, cand):
    """두 클립이 화면상 '안 잘린 연속'인가 — 같은 소스 + 앞 끝≈뒤 시작.

    ★2026-07-24 실사고: s2-0→s2-1→s2-2… 처럼 원본 인접 구간을 순서대로 붙이면 seg_id는
    전부 고유(반복 게이트 통과)인데 화면은 원본을 그냥 튼 것이라 컷이 없다. 고유성과 별개로
    이걸 따로 봐야 한다."""
    if not prev_clip or not cand:
        return False
    # ★필드가 없으면 '모른다' = 컷으로 본다. 안 그러면 video_id 둘 다 None(같다)·시각 0≈0으로
    # 모든 클립이 연속으로 오판된다(자체 테스트에서 실측).
    pv, cv = _vid_of(prev_clip), _vid_of(cand)
    if not pv or not cv or pv != cv:
        return False
    if prev_clip.get("end") is None or cand.get("start") is None:
        return False
    return abs(float(prev_clip["end"]) - float(cand["start"])) <= _ADJ_TOL


def dedup_clips_global(beats, pool_sources, max_clips=None):
    """전역 컷 반복 해소(2026-07-22 페이블 — dedup_and_balance는 primary만 봐서 alternates
    B롤 체인이 비트마다 똑같이 반복됐다: job 실측 s0-2·s0-3이 5비트에 반복). primary+alternates를
    **영상 전체에서 seg 1회** 원칙으로 본다. 이미 쓴 alternate는 안 쓴 비주얼 클립으로 교체,
    없으면 드롭(반복보다 낫다 — 길이는 홀드/conform이 흡수). primary는 dedup_and_balance가
    이미 처리하므로 여기선 alternates만 손댄다. ★포인트 비트의 primary는 절대 안 건드린다."""
    from shopping_shorts import config
    max_clips = getattr(config, "MAX_CLIPS_PER_BEAT", 3) if max_clips is None else max_clips
    min_shot = getattr(config, "MIN_SHOT_SECONDS", 1.2)
    used = set()
    src_count = Counter()
    out = []
    prev = None      # ★직전에 화면에 나갈 클립(비트 경계도 넘는다) — 이어붙임 판정용
    for b in beats:
        nb = dict(b)
        p = nb.get("primary") or {}
        used.add(p.get("seg_id"))
        src_count[_vid_of(p)] += 1
        if p.get("seg_id"):
            prev = p
        new_alts = []
        for a in (nb.get("alternates") or []):
            if 1 + len(new_alts) >= max_clips:      # 상한 초과분은 버린다(적고 길게)
                break
            sid = a.get("seg_id")
            # ★is_continuous(2026-07-24 실사고): seg_id가 고유해도 같은 소스의 **인접 구간**을
            # 순서대로 붙이면 컷이 없어 원본을 그냥 트는 화면이 된다(사장님 "연속재생").
            # 고유성만 보던 dedup을 '이어붙임'까지 보게 확장한다.
            if sid not in used and _seg_dur(a) > 0 and not is_continuous(prev, a):
                new_alts.append(a); used.add(sid); src_count[_vid_of(a)] += 1
                prev = a
                continue
            # 이미 쓴/빈/이어붙임 클립 → 안 쓴 비주얼 B롤로 교체(이어붙임 아닌 것으로).
            repl = next((c for c in _broll_segs(pool_sources, src_count, used,
                                                prefer_video=_vid_of(p), min_shot=min_shot)
                         if not is_continuous(prev, c)), None)
            if repl:
                new_alts.append(repl); used.add(repl.get("seg_id")); src_count[_vid_of(repl)] += 1
                prev = repl
        nb["alternates"] = new_alts
        out.append(nb)
    return out


def repick_for_gate(beats, pool_sources, gate):
    """게이트 위반(연속·반복·파편)을 재픽으로 교정한다(2026-07-25). 원본 mutate 안 함,
    Gemini·IO 없음, 나레이션·tts_path 불변. 후보 없으면 그 위반은 그대로 둠(호출부 루프가
    new_beats==beats 로 수렴 판정해 종료).

    ★핵심: primary 비트 간 연속(is_continuous)을 여기서 처음으로 끊는다 —
    dedup_clips_global은 alternates만 봤고, dedup_and_balance는 seg_id 중복만 봐서
    's0-4→s0-5'처럼 고유하지만 인접한 primary 연속이 샜다(job 57ec653ba579 실사고).
    포인트 비트 primary는 결정적 장면이라 불가침 — 런에 끼면 반대쪽(앞 비트)을 바꾼다."""
    out = [dict(b) for b in beats]
    src_count = Counter(_vid_of(b.get("primary")) for b in out if b.get("primary"))
    used = {(b.get("primary") or {}).get("seg_id") for b in out}
    used |= {a.get("seg_id") for b in out for a in (b.get("alternates") or [])}
    used.discard(None)
    for i in range(1, len(out)):
        prev_p = out[i - 1].get("primary") or {}
        cur_p = out[i].get("primary") or {}
        if not is_continuous(prev_p, cur_p):
            continue
        # 포인트 비트 primary는 불가침 → 앞 비트를 바꿔 연속을 깬다(앞이 포인트면 어쩔 수 없이 뒤).
        target = i - 1 if (is_point_beat(out[i]) and not is_point_beat(out[i - 1])) else i
        tb = out[target]
        anchor = out[target - 1].get("primary") if target > 0 else None
        action = segment_action(tb.get("primary") or {}) or \
            action_dict.tag_action(tb.get("narration", ""))
        cands = [c for c in (pick_clips_for_action(action, pool_sources) if action else [])
                 if c.get("seg_id") not in used and not is_continuous(anchor, c)]
        if not cands:
            cands = [c for c in _broll_segs(pool_sources, src_count, used)
                     if not is_continuous(anchor, c)]
        if not cands:
            continue   # 대체 후보 없음 → 그대로(수렴)
        cands.sort(key=lambda c: (src_count.get(_vid_of(c), 0), -_seg_dur(c)))  # 미사용소스·긴컷 우선
        old_sid = (tb.get("primary") or {}).get("seg_id")
        pick = cands[0]
        if old_sid:
            used.discard(old_sid)
        used.add(pick.get("seg_id"))
        src_count[_vid_of(pick)] += 1
        tb["primary"] = pick
    # 반복·파편·alternates 연속은 기존 dedup 재적용(테스트된 로직 재사용).
    out = dedup_and_balance(out, pool_sources)
    out = dedup_clips_global(out, pool_sources)
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


def ping_pong_reconcile(beats, pool_sources, rewrite_call=None, max_rounds=2,
                        trim_call=None, min_total_chars=0):
    """핑퐁(대본↔장면 왕복). 매 라운드:
      1) action 불일치 비트 찾기(fit 안 믿음 — beat_action_mismatch).
      2) 각 비트: 같은 행위 클립이 풀에 있으면 **화면 스왑**(장면 쪽), 없으면 재작성 대기(대본 쪽).
      3) 재작성 대기 비트 나레이션을 화면에 맞게 rewrite_call로 1회 수정.
    불일치 0 또는 max_rounds 소진까지 반복. rewrite_call(beats)->{beat_idx: 새나레이션}.
    rewrite_call 없거나 실패면 그 비트는 스왑만(대본 쪽 스킵). 원본 mutate 안 함."""
    out = [dict(b) for b in beats]
    # ★이번 ping_pong_reconcile 호출 전체(라운드 넘나들며)에서 스왑으로 이미 나간 seg_id.
    # 라운드 안에서만 리셋하면 라운드가 넘어갈 때 재사용될 수 있어(실사고 job 8226822c5b09:
    # bad 두 비트가 같은 행위로 매핑돼 같은 clips[0]을 각자 고름) 호출 전체 스코프로 둔다
    # (2026-08-01).
    claimed_seg_ids = set()
    for _ in range(max_rounds):
        bad = [i for i, b in enumerate(out) if beat_action_mismatch(b)]
        if not bad:
            break
        need_rewrite = []
        for i in bad:
            nb, still = reconcile_beat_by_action(out[i], pool_sources,
                                                  exclude_seg_ids=claimed_seg_ids)
            out[i] = nb
            if not still:
                sid = (nb.get("primary") or {}).get("seg_id")
                if sid:
                    claimed_seg_ids.add(sid)
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
        # ★전체 길이 하한(2026-07-31). 비트마다 "화면보다 말이 길다"고 깎다 보면 소스가 짧을 때
        #   **대본 전체가 쪼그라든다** — 실측(라이브 설정 백테스트 20건): 목표 30초(150~185자)인데
        #   62~106자가 다수였고, 사장님 제보 job은 20초 소스 1개로 11초 대본이 나왔다.
        #   말이 화면을 조금 넘는 것보다 영상이 절반으로 주는 게 훨씬 나쁘다. 게다가 렌더 단계의
        #   _refill_beats_to_tts가 **실 TTS 길이에 맞춰 화면을 늘려주므로** 넘침은 거기서 흡수된다.
        #   → 트림을 다 적용했을 때 총량이 하한 밑으로 내려가면 **아예 적용하지 않는다**.
        if trims and min_total_chars:
            def _clen(s):
                return len("".join((s or "").split()))
            after = sum(_clen(trims.get(b.get("beat_idx")) or b.get("narration", "")) for b in out)
            if after < min_total_chars:
                trims = {}          # 화면 맞추기보다 이야기 길이를 지킨다
        for b in out:
            bi = b.get("beat_idx")
            if bi in trims and trims[bi]:
                b["narration"] = trims[bi]
                b["length_trimmed"] = True
    return out


def _visual_segs_of(pool_sources, vid, min_shot=None):
    """그 소스(vid)의 세그먼트를 **비주얼 좋은 순**(_visual_score)으로 — 앰비언트 비트에 쓸
    '먹음직스러운 그림'. 행위 태그가 없어도 쓸 수 있는 후보를 준다(2트랙 원칙)."""
    from shopping_shorts import config
    min_shot = getattr(config, "MIN_SHOT_SECONDS", 1.2) if min_shot is None else min_shot
    segs = []
    for s in (pool_sources or []):
        if s.get("video_id") != vid:
            continue
        for seg in (s.get("segments") or []):
            c = dict(seg)
            c["video_id"] = vid
            if _seg_dur(c) >= min_shot:
                segs.append(c)
    segs.sort(key=lambda c: (-_visual_score(c), -_seg_dur(c)))
    return segs


def _middle_source_clip(pool_sources, exclude=None):
    """어느 소스든 '중간' 세그먼트(각 소스 첫·끝 제외) 중 비주얼 최상 클립.
    CTA 화면용 — 원본 엔딩(원작자 CTA·워터마크 오염)을 피한다. 없으면 None."""
    exclude = exclude or set()
    best = None
    for s in (pool_sources or []):
        segs = [seg for seg in (s.get("segments") or []) if _seg_dur(seg) >= 1.0]
        if len(segs) < 3:
            continue
        for seg in segs[1:-1]:                       # 첫·끝 제외 = 중간
            c = dict(seg)
            c["video_id"] = s.get("video_id")
            if c.get("seg_id") in exclude:
                continue
            if best is None or _visual_score(c) > _visual_score(best):
                best = c
    return best


def swap_hook_cta_for_differentiation(beats, backbone_video, pool_sources):
    """영상 차별화(사장님 2026-07-27, 아주 중요): 화면만 재배정(narration 불변).
    ① 훅(첫 비트) 화면 = 백본(A)이 아닌 **다른 소스의 가장 강렬한 장면** → 원본과 달라 보이게.
    ② CTA(마지막 비트) 화면 = 원본 엔딩 대신 **중간 소스 클립** → 원작자 CTA·워터마크 회피.
    소스가 부족하면 해당 항목 무변경(억지 교체 안 함). 순수함수(새 리스트 반환)."""
    if not beats or len(beats) < 2:
        return beats
    out = [dict(b) for b in beats]
    used = {(b.get("primary") or {}).get("seg_id") for b in out}
    # ① 훅 = 비-A 소스 비주얼 최고 장면
    non_bb_vids = [s.get("video_id") for s in (pool_sources or [])
                   if s.get("segments") and s.get("video_id") and s.get("video_id") != backbone_video]
    if non_bb_vids:
        cands = []
        for vid in dict.fromkeys(non_bb_vids):       # 소스 순서 유지 dedup
            cands += _visual_segs_of(pool_sources, vid)
        cands.sort(key=lambda c: (-_visual_score(c), -_seg_dur(c)))
        fresh = next((c for c in cands if c.get("seg_id") not in used), None)
        if fresh:
            out[0] = dict(out[0])
            out[0]["primary"] = fresh
            out[0]["hook_visual_swapped"] = True
            used.add(fresh.get("seg_id"))
    # ② CTA = 중간 소스 클립(원본 엔딩 회피)
    mid = _middle_source_clip(pool_sources, exclude=used)
    if mid:
        out[-1] = dict(out[-1])
        out[-1]["primary"] = mid
        out[-1]["cta_visual_swapped"] = True
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
        # ★행위 태그가 하나도 없는 소스라도 건너뛰지 않는다(2026-07-24) — 앰비언트 비트엔
        # 비주얼 클립으로 넣을 수 있다. 예전엔 여기서 continue라 그 소스가 영영 안 쓰였다.
        if not by_action and not _visual_segs_of(pool_sources, vid):
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
            # ★n_act가 None일 때만(=문장이 행위를 아예 안 가리킴) 비주얼로 넣는다.
            # 행위가 있는 문장("썰어요")에 안 맞는 클립을 밀어넣으면 싱크가 깨진다(옛 계약 유지).
            if not clips and not n_act and not is_point_beat(b):
                # ★2026-07-24 실사고("한 영상만 씀"): 대본을 스토리·대화체로 바꾸자 대부분 비트에
                # 행위 태그가 없어(n_act=None) 의무삽입이 조용히 아무것도 안 했고, 후보가 소스
                # 하나만 통째로 쓰게 됐다(실측: 후보0=s0×13, 후보1=s1×16, 후보2=s2×15).
                # 포인트 비트(결정적 행위)는 행위 매칭을 지켜야 하지만, **앰비언트 비트는 그냥
                # 먹음직스러운 그림이면 된다**(2트랙 원칙) → 안 쓴 소스의 비주얼 상위 클립을 쓴다.
                cands = [c for c in _visual_segs_of(pool_sources, vid)]
                clips = cands or None
            if not clips:
                continue
            nb = dict(b)
            nb["primary"] = clips[0]
            nb["forced_source"] = True
            out[i] = nb
            break
    return out


def pick_clips_for_action(action, pool_sources, exclude_video=None, exclude_seg_ids=None):
    """그 행위의 클립들(화면 스왑 best-of-N 후보). exclude_video=백본이면 서브만 반환
    (차별화 1층: 순서·싱크는 백본, 픽셀은 다른 소스).
    exclude_seg_ids: 이 seg_id들은 후보에서 뺀다(2026-08-01) — ping_pong_reconcile이
    같은 호출 안에서 이미 다른 비트에 배정한 클립을 다시 골라 화면이 중복되는 것 방지."""
    clips = action_pool(pool_sources).get(action, [])
    if exclude_video:
        clips = [c for c in clips if c.get("video_id") != exclude_video]
    if exclude_seg_ids:
        clips = [c for c in clips if c.get("seg_id") not in exclude_seg_ids]
    return clips
