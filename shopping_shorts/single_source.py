"""1소스 전용 믹스 로직(2026-08-04, 사장님 확정 스펙).

왜 별도 경로인가 — 실측(최근 45건):
  · 1소스: 소재/목표 배율 중앙값 **0.67배**(20초 원본에 목표 30초) → 100%가 소재부족
  · 다소스: 1.53배 → 부족 2%
1소스는 **원본 길이가 물리적 천장**이다. 편집은 원본에서 빼는 작업이라 결과는 원본보다
짧거나 같을 수밖에 없는데, 목표 30초를 요구하니 없는 10초를 채우라는 요구가 됐다. 그래서
같은 장면 반복·컷 없이 이어붙이기로 늘리다 게이트에 걸리고(길이부족 76%·비트부족 44%),
결국 3~4비트짜리 토막 영상이 나왔다.

확정 스펙(사장님):
  ① 길이: **하한 18초 / 상한 원본** — 원본의 90%를 노리되 18초 밑으론 안 줄인다
     ("최소 18~20초는 돼야 스토리 기본이 들어간다"). 원본이 18초 미만이면 원본 전체.
  ② **is_key(핵심 태깅) 구간은 반드시 살린다** — 잘라내기 후보에서 제외, 군더더기만 걷어낸다.
  ③ 순서는 **반드시 바뀐다**(원본 시간순 그대로 = "원본 그대로 트는 느낌"). 훅→전개→결과→CTA.
  ④ 중복 없음(같은 컷 재사용 금지).
  ⑤ 대본은 원본을 베끼지 말고 **다른 말로 각색**. 훅은 확정 10패턴(hook_patterns)에서.
  ⑥ 나레이션이 컷 경계를 조금 넘어 **다음 장면으로 이어지는 흐름**은 허용
     (사장님: "컷을 약간 벗어나는 대본은 괜찮아. 다음 장면에서 맞추면 되는 흐름으로").
     → 컷마다 한 문장이 아니라 **한 문장이 컷 2~3개를 덮는다**. 컷마다 문장을 요구하면
       총량이 2배로 튄다(실측: 17.8초 화면에 35.2초 나레이션).
"""
import os
import re

MIN_SECONDS = 20.0        # 스토리가 서는 하한(2026-08-04 사장님 상향: "22초 원본이면 최소 20초는 받아야")
RATIO = 0.90              # 원본 대비 목표 비율
# ★실측으로 교정(2026-08-09): 종전 6.5는 근거 없는 가정이었다("기존 파이프라인과 동일").
#   라이브 렌더 영상 8건 실측 = **8.2~8.9자/초**(a0157a0ed29d 8.93 · ddccf1efabd4 8.57 ·
#   df9b54de557d 8.36 · 8b7facca37a8 8.40 · 31b394c4685d 8.23 · bb9db3a5f759 8.25 …).
#   6.5로 잡으면 25초에 162자만 배정하는데 실제로는 같은 시간에 210자가 들어간다 —
#   **대본이 구조적으로 부실해진다**. 실제 히트작은 더 빽빽하다(메종 298~336자·
#   채이 372~383자를 4~6문장에, 문장당 50~93자). 우리는 문장당 31자라 채이 가족액자
#   ("얼마 전에 시어머니가 놀러 오셨는데 ~ 물어보시는 거예요" 93자)가 한 문장에 못 들어가
#   문장이 뚝뚝 끊겼다(사장님 "광고 문구 같다"의 구조적 원인).
#   ⚠️이건 **대본 분량 배정**에만 쓴다. 비트 길이·자막 싱크는 _SYLLABLES_PER_SEC(5.7)이
#     따로 담당한다 — 그쪽을 건드리면 자막이 어긋난다.
#   ⚠️속도감 모드(pace_mode, 무음 제거)와 이중 계산되지 않는다 — 실측으로 확인했다:
#     pace_mode ON 8.13자/초(n=9) vs OFF 8.37자/초(n=16)로 **거의 같다**.
#     무음이 빠지면 영상도 같이 짧아져 비율이 유지되기 때문이다.
#     그래서 둘 중 낮은 쪽(ON, 8.13)에 맞춰 **8.1**로 잡는다 — 넘치면 자막이 밀린다.
#   되돌리려면 서버 env `SCRIPT_CHARS_PER_SEC=6.5`.
_CHARS_PER_SEC = float(os.environ.get("SCRIPT_CHARS_PER_SEC", "8.1") or 8.1)
_SECS_PER_LINE = 3.2      # 문장 하나가 덮는 평균 화면 길이

CTA_PAT = re.compile(r"댓글|남겨주|보내드|링크|프로필|구독|팔로우")

# script_prompt 응답용 스키마(_vault_call에 그대로 전달)
BEATS_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "covers": {"type": "array", "items": {"type": "integer"}},
                    "narration": {"type": "string"},
                },
                "required": ["n", "covers", "narration"],
            },
        },
    },
    "required": ["beats"],
}


def is_single_source(source_scripts):
    """소스가 실질적으로 하나인가(segments가 있는 video_id 기준)."""
    vids = {s.get("video_id") for s in (source_scripts or []) if s.get("segments")}
    vids.discard(None)
    return len(vids) == 1


def _dur(s):
    return max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))


def _is_cta(s):
    return bool(CTA_PAT.search(s.get("text") or "")) or s.get("shot_role") == "기타"


# ★스토리 하한(2026-08-09 사장님 지시): "짧은 쇼츠에도 설득구조가 있어야 하고, 클릭으로
#   이어지려면 스토리가 탄탄한 대본이 가장 우선이다. 스타일을 살리려면 **중복을 허용하고**
#   최대한 살려야 한다."
#   종전엔 원본 길이가 천장이라(min(want, span)) 22초 소재는 20초·130자로 눌렸다 —
#   채이 가족액자(few-shot 377자)·메종 긴 연결이 물리적으로 안 들어가 스타일이 죽었다
#   (라이브 경로 실측: 메종 0/6). 화면은 _fill_beat_screen_time이 클립 재사용으로 채운다.
#   ⚠️시간은 목표가 아니라 **결과**다 — 스토리가 설 분량을 먼저 주고 화면이 따라온다.
STORY_MIN_SECONDS = float(os.environ.get("SCRIPT_STORY_MIN_SEC", "25") or 25)


def budget_for(segments, target_seconds=None):
    """이 소재로 만들 대본 분량. 하한 STORY_MIN_SECONDS(기본 25초).

    ★원본보다 길어도 된다(2026-08-09) — 부족한 화면은 클립 재사용으로 채운다.
      되돌리려면 서버 env `SCRIPT_STORY_MIN_SEC=0` (그러면 종전처럼 원본이 천장).
    target_seconds(사용자가 고른 값)가 더 짧으면 존중하되 하한은 지킨다.
    """
    if not segments:
        return 0.0, 0.0
    span = (max(float(s.get("end") or 0) for s in segments)
            - min(float(s.get("start") or 0) for s in segments))
    want = max(MIN_SECONDS, span * RATIO)
    if target_seconds:                      # 사용자가 더 짧게 원하면 존중(단 하한은 지킨다)
        want = min(want, max(MIN_SECONDS, float(target_seconds)))
    if STORY_MIN_SECONDS <= 0:              # 롤백 스위치 — 종전과 100% 동일
        return span, min(want, span)
    # 스토리가 설 분량을 보장한다(원본보다 길어도 된다 — 부족분은 클립 재사용으로 채운다).
    floor = min(STORY_MIN_SECONDS, float(target_seconds) if target_seconds else STORY_MIN_SECONDS)
    out = max(min(want, span), floor)
    # ★사용자가 고른 목표는 **최종 상한**이다(2026-08-09 실측 버그): MIN_SECONDS(20초)가
    #   want의 하한이라 목표를 15초로 줘도 want가 20으로 올라가 19.5초가 나왔다.
    #   사장님이 짧게 고른 걸 코드가 늘리면 안 된다.
    if target_seconds:
        out = min(out, float(target_seconds))
    return span, out


_DONE_ROLES = {"after", "완성", "결과"}      # 완성품 샷
_COOK_ROLES = {"사용중", "조리", "과정"}     # 조리(비법) 샷


def select_and_order(segments, target_seconds=None, video_type=None):
    """핵심 보존 + 예산 내 선별 + 스토리 순서 재배치.

    video_type=="recipe"(2026-08-06 사장님): 완성품(훅) → 재료 → 조리 한 덩어리 →
    완성품 → CTA. 조리가 틈틈이 2번 쪼개져 들어가는 게 어색하다 — 비법 구간 한 번이면
    충분. 그룹 안은 시간순이라 공정 순서는 안 깨진다. SCENE_PHASE_ORDER=0으로 off.

    반환: (span, budget, used_secs, ordered_segments)
    """
    segs = [dict(s) for s in (segments or []) if s.get("seg_id")]
    if not segs:
        return 0.0, 0.0, 0.0, []
    for s in segs:
        s["_dur"] = _dur(s)
    span, budget = budget_for(segs, target_seconds)

    key = [s for s in segs if s.get("is_key")]
    rest = [s for s in segs if not s.get("is_key")]
    keep = list(key)
    used = sum(s["_dur"] for s in keep)
    # 여유분은 CTA(마무리) 먼저 확보하고, 그 다음 소재 뒤쪽 컷부터.
    rest.sort(key=lambda s: (0 if _is_cta(s) else 1, -float(s.get("start") or 0)))
    for s in rest:
        if used + s["_dur"] <= budget:
            keep.append(s)
            used += s["_dur"]
    if not keep:
        return span, budget, 0.0, []

    cta = [s for s in keep if _is_cta(s)]
    core = [s for s in keep if not _is_cta(s)]
    if not core:                        # 전부 CTA로 잡히면 순서만 시간순
        core, cta = cta, []
    # 훅 = 가장 임팩트 큰 핵심 컷. 길이가 같으면 **뒤쪽 컷**을 집는다 —
    # 앞 컷을 집으면 나머지가 시간순 그대로라 순서가 안 바뀐다(원본 트는 느낌).
    hook_pool = [s for s in core if s.get("is_key")] or core
    recipe_phase = (video_type == "recipe"
                    and os.environ.get("SCENE_PHASE_ORDER", "1") not in ("0", "off", ""))
    if recipe_phase:
        # 훅은 완성품 우선 — "완성품으로 열고, 조리는 비법 대목에 한 번".
        done_hooks = [s for s in hook_pool if s.get("shot_role") in _DONE_ROLES]
        hook_pool = done_hooks or hook_pool
    hook = max(hook_pool, key=lambda s: (s["_dur"], float(s.get("start") or 0)))
    body = [s for s in core if s is not hook]
    if recipe_phase:
        # 재료/기타(0) → 조리 연속 블록(1) → 완성품(2). 그룹 안은 시간순.
        def _phase(s):
            r = s.get("shot_role")
            return 1 if r in _COOK_ROLES else (2 if r in _DONE_ROLES else 0)
        body.sort(key=lambda s: (_phase(s), float(s.get("start") or 0)))
    else:
        # 전개(사용중=과정) → 결과(완성), 그룹 안에서는 시간순이라 맥락이 안 깨진다.
        body.sort(key=lambda s: (0 if s.get("shot_role") == "사용중" else 1,
                                 float(s.get("start") or 0)))
    cta.sort(key=lambda s: float(s.get("start") or 0))
    # ★대본 분량은 **화면 실측(used)이 아니라 예산(budget)** 기준이다(2026-08-09 사장님 지시).
    #   used는 "고른 컷 길이의 합"이라 원본이 천장이다 — 19.2초 소재는 영원히 124자·4문장이라
    #   채이 가족액자(few-shot 377자)·메종 긴 연결이 물리적으로 못 들어갔다(메종 0/6 실측).
    #   budget에는 STORY_MIN_SECONDS 하한이 들어 있어 스토리가 설 분량이 확보된다.
    #   모자란 화면은 _fill_beat_screen_time이 **클립 재사용**으로 채운다(중복 허용 = 사장님 지시).
    #   ⚠️used를 바꾸지 않는 이유: 화면 배정·conform이 실제 화면 길이로 계산해야 한다.
    script_secs = max(used, budget) if STORY_MIN_SECONDS > 0 else used
    return span, budget, script_secs, [hook] + body + cta


def line_count(used_secs, n_cuts):
    """나레이션 문장 수 — 컷 수보다 적게(한 문장이 컷 2~3개를 덮는다).

    ★상한 9(2026-08-04 실측 job 923d/285d): 43초 원본·컷 25개 → 13문장이 요구되자
    글자예산에 눌려 "찌든 때 밀면 끝"류 전보문이 됐다(사장님 "대본이 이상해").
    문장당 4~5초가 자연스러운 호흡이다 — 컷 커버는 코드가 배정하니 문장이 적어도 안전."""
    secs_per_line = _SECS_PER_LINE
    # ★채널 스타일 ON이면 문장을 길게(2026-08-05): 30초=8문장(문장당 ~13자)에선 메종식
    #   "~는데 ~니까 ~더라고요" 긴 호흡이 구조적으로 불가능했다(실측 job 64e0a110 드라이런).
    try:
        from shopping_shorts import style_profiles
        if style_profiles.active_style():
            secs_per_line = 4.8          # 30초 → 6문장(문장당 ~23자) — 메종 실측 호흡
    except Exception:
        pass
    return max(3, min(n_cuts, 9, round(used_secs / secs_per_line)))


def char_budget(used_secs):
    return int(used_secs * _CHARS_PER_SEC)


def _style_extra(cand_idx=None):
    """채널 스타일 블록(style_profiles, 2026-08-05). 실패해도 생성을 죽이지 않는다.

    ★cand_idx를 주면 **그 후보에 배정된 채널**의 few-shot을 싣는다(2026-08-09).
      안 주면 종전과 100% 동일(trio면 maison 공통) — 하위호환."""
    try:
        from shopping_shorts import style_profiles
        if cand_idx is not None:
            return style_profiles.candidate_style_block(cand_idx)
        return style_profiles.style_block()
    except Exception:
        return ""


def script_prompt(order, used_secs, hook_block, frame_block="", cand_idx=None):
    """1소스 각색 대본 프롬프트. hook_block은 hook_patterns.prompt_block() 결과.
    frame_block: 후보별 이야기 구도(style_profiles.story_frame_block) — 빈 문자열이면 종전 동일.
    cand_idx: 이 후보의 인덱스(0부터). 주면 후보별 채널 스타일 few-shot이 실린다 —
      ★안 주면 종전과 100% 동일(회귀 0)."""
    import json
    cuts = [{"n": i + 1, "seg": s.get("seg_id"), "초": round(s["_dur"], 1),
             "화면": s.get("scene_desc") or "", "원본대사": s.get("text") or "",
             "핵심": bool(s.get("is_key"))}
            for i, s in enumerate(order)]
    n_lines = line_count(used_secs, len(order))
    total = char_budget(used_secs)
    return (hook_block + _style_extra(cand_idx) + (frame_block or "") +   # ★채널 스타일(2026-08-05, 후보별 2026-08-09)·구도(2026-08-06)
            "\n아래는 숏폼 한 편을 재편집한 컷 순서다. 이 화면들에 얹을 **나레이션**을 써라.\n\n"
            "[절대규칙]\n"
            "1. 원본대사를 베끼지 마라. 같은 뜻을 완전히 다른 표현으로 바꿔라(어순·어휘·문형 전부).\n"
            f"2. ★문장은 **정확히 {n_lines}개**만 써라. 컷마다 하나씩 쓰는 게 아니다 —\n"
            "   한 문장이 컷 2~3개에 걸쳐 흐르고, 다음 장면에서 자연스럽게 이어받는 구성이다.\n"
            "   각 문장에 그 문장이 덮는 컷 번호를 covers로 적어라(예: covers:[1,2,3]).\n"
            f"3. ★전체 합계 **{total}자를 넘기지 마라**(화면 {used_secs:.1f}초). 이게 제일 중요하다 —\n"
            f"   넘으면 영상이 끝났는데 말이 남는다. 한 문장은 평균 {max(8, total // max(1, n_lines))}자 정도다.\n"
            "4. 컷 순서대로 이야기가 이어져야 한다. 첫 문장은 위 훅 패턴으로 시작하라.\n"
            # ★2026-08-04 원본대조 실측(job 53bd4a4a): 후보 3개 전부 '다이소'가 사라지고
            #   CTA가 혜택 설명문으로 바뀜. 원본의 파는 힘(구매처·참여유도)은 각색해도 보존.
            "   원본대사에 구매처·브랜드(다이소·쿠팡 등)가 있으면 대본 어딘가에 **한 번** "
            "자연스럽게 살려라 — 위치는 자유(뒷부분·CTA 근처도 좋다). ★단 스토리와 모순되게 "
            "끼워넣지 마라(예: '독일 친구가 알려줬다'는 이야기에 '쿠팡에서 찾은'을 훅에 박으면 "
            "출처가 둘이 된다 — 그럴 땐 구매처를 뒤로 미뤄 '쿠팡에서 샀어요'로 풀어라).\n"
            "   (2026-08-04 완화: 훅 강제였더니 스토리 모순 발생 — 사장님 지시로 위치 자유화)\n"
            "5. 화면 설명과 어긋나는 말을 지어내지 마라.\n"
            "6. ★마지막 문장은 **반드시** \"댓글에 '키워드' 남겨주시면 [받는 것] 드릴게요\" "
            "형태로 끝내라(링크·프로필 금지). ★남기면 뭘 받는지(제가 산 링크·정확한 방법·"
            "최저가 정보)를 반드시 말하라 — 받는 게 안 보이면 아무도 안 남긴다. "
            "감상('참 좋네요')으로 끝나거나 '댓글'이 마지막 문장에 없으면 통째로 버려진다. "
            "원본대사에 참여유도(예: \"'나도' 남겨주세요\")가 있으면 그 키워드를 이어받아라.\n"
            # ★CTA 미끼(2026-08-06 사장님 확정: 본문에 비법 한 조각 남기기 — 조회수 우선).
            #   기존엔 본문이 비법을 다 풀어 CTA에 줄 게 안 남았다(3후보 공통, 실측 잡 다수).
            "   ★미끼 규칙: 핵심 비법의 **가장 구체적인 한 조각**(정확한 비율·핵심 재료 하나·"
            "온도/시간 같은 수치)은 본문에서 말하지 마라 — '비법이 있다'는 것과 효과만 보여주고, "
            "그 조각이 뭔지는 CTA에서 \"궁금하시면 댓글에…\"로 남겨라. 본문에서 방법을 다 "
            "알려주면 댓글 남길 이유가 사라진다. 단, 뭘 숨겼는지는 시청자가 알게 하라"
            "(예: 본문 '재료 하나만 바꾸면 끝' → CTA '그 재료 궁금하시면 댓글에').\n"
            "7. ★중간 문장 중 **하나는 반드시 고조 연결어로 시작**하라 — '심지어' '더군다나' "
            "'근데 이게 대박인 게' '놀랍게도' '이럴 수가 있나 싶게' 중 소재에 맞는 것 하나"
            "(훅·마지막 문장엔 금지, 두 번 이상도 금지). 이야기가 한 단계 올라가는 문장 앞에 "
            "놓고, 연결어 뒤엔 반드시 **앞에서 안 나온 새로운 추가 장점**을 말하라 — "
            "이미 말한 장점 반복은 고조가 아니라 동어반복이다. 그리고 종결어미를 다양하게 — 전 문장이 '~요/~니다'로 똑같으면 "
            "낭독문처럼 들린다('~거든요' '~더라고요' '~죠' 섞기).\n\n"
            "[컷]\n" + json.dumps(cuts, ensure_ascii=False, indent=1) + "\n\n"
            "JSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


ESCALATE_SCHEMA = {
    "type": "object",
    "properties": {"n": {"type": "integer"}, "narration": {"type": "string"}},
    "required": ["n", "narration"],
}


def escalate_prompt(beats):
    """고조 문장 재작성 프롬프트(2026-08-04 사장님: "연결어랑 뒷내용이 안 이어진다 — 디벨롭해라").

    기계적으로 연결어만 앞붙이면 '심지어' 뒤에 이미 말한 장점이 반복돼 고조가 안 된다.
    중간 문장 중 하나를 골라 **앞 문장들을 한 단계 넘는 새 장점**으로 다시 쓰게 한다."""
    import json
    cur = [{"n": i + 1, "narration": (b.get("narration") or "")}
           for i, b in enumerate(beats)]
    return ("아래는 숏폼 나레이션이다. 구조는 훅→문제→해결장점→**고조(한 단계 위 장점)**→CTA다.\n"
            "중간 문장(첫 문장·마지막 문장 제외) 중 고조 자리에 가장 어울리는 것 **하나**를 골라,\n"
            "'심지어 / 놀랍게도 / 근데 이게 대박인 게 / 더군다나' 중 하나로 시작하면서\n"
            "**앞 문장들에서 아직 안 나온 새로운 장점**으로 이어지게 다시 써라.\n"
            "규칙: ①앞 문장 내용의 반복·재표현 금지 — 반드시 새 정보로 한 단계 올라가야 한다\n"
            "②원래 문장이 말하던 화면(장면)과 어긋나는 내용을 지어내지 마라 — 그 문장의 소재를\n"
            "  유지하되 '더 놀라운 점'으로 각도를 올려라 ③길이는 원래 문장의 ±20% ④말투 유지.\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"n\": 고른 문장 번호, \"narration\": \"다시 쓴 문장\"}")


RESTYLE_SCHEMA = {
    "type": "object",
    "properties": {"beats": {"type": "array", "items": {
        "type": "object",
        "properties": {"n": {"type": "integer"}, "narration": {"type": "string"}},
        "required": ["n", "narration"]}}},
    "required": ["beats"],
}

_CLICHE = ("꿀템", "갓성비", "완벽 해결", "삶의 질", "필수템", "역대급")


def restyle_prompt(beats, length_note="", style_name=None):
    """★스타일 통째 리라이트(2026-08-05 사장님 "메종이랑 결이 아예 안 맞네").

    프롬프트 지시로 3바퀴를 밀어도 컷 매핑 생성은 광고 카피 결을 못 벗었다 —
    오프라인 40개 교정(전규칙 40/40)에서 증명된 방식 그대로, 완성된 나레이션을
    스타일 예시를 보고 **문체만 통째로 고쳐 쓰게** 한다. 내용·순서·문장수 고정이라
    covers(컷 매핑)가 그대로 유효하다."""
    import json
    from shopping_shorts import style_profiles
    cur = [{"n": i + 1, "narration": (b.get("narration") or "")}
           for i, b in enumerate(beats)]
    total = sum(len(c["narration"]) for c in cur)
    return (style_profiles.style_block(style_name)
            + "\n위 [스타일 예시]의 결로 아래 나레이션을 **문체만** 고쳐 써라.\n"
            "[절대규칙]\n"
            "1. 문장 수와 순서는 그대로 — n번 문장은 n번 자리에서 같은 내용을 말한다"
            "(그 문장이 덮는 화면이 고정돼 있다. 내용을 옮기면 화면과 어긋난다).\n"
            "2. 사실·스펙·정보 추가 금지. 없던 인물·구매처·수치(분·%·회수)를 지어내지 마라. "
            "★제품이 무엇이고 어떻게 쓰는 물건인지(착용/바르는/먹는)를 절대 바꾸지 마라 — "
            "원래 문장에 없는 동사로 제품을 쓰게 하면 화면과 어긋난다. 등장 인물도 원래 "
            "문장의 인물 그대로(아내를 친구로 바꾸지 마라).\n"
            f"3. ★전체 길이는 지금({total}자)의 ±15% 안 — 이 나레이션은 화면 길이에 묶여 "
            "있어 길어지면 영상이 끝났는데 말이 남는다. 각 문장도 원래 문장과 비슷한 길이로. "
            "결을 살리되 **바꿔 쓰는 것이지 늘려 쓰는 게 아니다**.\n"
            + (f"   {length_note}\n" if length_note else "")
            + "4. ★마지막 문장(CTA)은 반드시 \"댓글에 '키워드' 남겨주시면 [받는 것] "
            "드릴게요\" 형태 — 키워드와 받는 것(링크·방법·최저가)을 빼먹지 마라. "
            "\"남겨주세요\"로만 끝나면 실패다. ★원본이 숨겨둔 비법 조각(비율·재료·수치)을 "
            "리라이트에서 본문에 풀지 마라 — 그건 CTA의 미끼다.\n"
            "5. 상투어 금지: 꿀템·갓성비·완벽 해결·삶의 질·필수템·역대급 — 있으면 지워라.\n"
            # ★어미 지시는 **스타일이 정한다**(2026-08-07). 여기에 "합쇼체 금지"를
            #   하드코딩해 뒀더니, 끝맺음 합쇼체가 서명인 홈테리어픽에서 스타일 블록과
            #   [절대규칙]이 같은 프롬프트 안에서 싸우고 '절대'가 이겼다(실측 job
            #   cc794cf30b4b: C안 합쇼체 0건). 스타일 미지정이면 종전 문구 그대로.
            "6. 예시처럼: 훅은 감탄/사건 선언, 문장은 '~는데 ~니까 ~더라고요'로 길게 잇고, "
            "다음 문장이 앞을 이어받게(그래서/근데/심지어). "
            + style_profiles.hapsyo_rule(style_name) + "\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"narration\":\"...\"}]}")


def apply_restyle(beats, call, max_tries=3, style_name=None, report=None):
    """스타일 리라이트 — 길이 초과·상투어는 버리지 말고 피드백 재시도(최대 3회).

    ★첫 구현은 길이 밖이면 조용히 원본 복귀였는데, 메종 문체가 원문보다 길어
    **매번 1.5배로 불어 게이트에 걸리고 아무 일도 안 일어났다**(2026-08-05 서버 실측
    — '조용한 폴백' 계보). 이제 초과분은 '줄여서 다시'를 알려주고 재요청한다.
    문장수 불일치·빈 응답 같은 구조 실패만 즉시 원본 유지.

    report(dict, 선택): 호출자가 성공/실패를 알 수 있게 채워준다 —
    {"ok": bool, "style": str, "why": str}. 실패가 조용히 원본으로 남으면 trio가
    전부 같은 결로 수렴하는데 로그 0줄이라 진단 불가였다(2026-08-06 서버 실측)."""
    import sys
    from shopping_shorts import style_profiles

    def _done(out, ok, why):
        if report is not None:
            report.update(ok=ok, style=style_name or style_profiles.active_style(),
                          why=why)
        print(f"[restyle] 스타일={style_name} {'성공' if ok else '실패'}({why})",
              file=sys.stderr)
        return out

    if not style_profiles.active_style() or not beats:
        return beats
    old_total = sum(len(b.get("narration") or "") for b in beats)
    note = ""
    best = None
    closest = None          # 구조는 멀쩡하나 길이 밖인 스타일본 중 1.0배에 가장 근접한 것
    closest_ratio = None
    for _ in range(max_tries):
        resp = call(restyle_prompt(beats, length_note=note, style_name=style_name),
                    RESTYLE_SCHEMA)
        got = (resp or {}).get("beats") if isinstance(resp, dict) else None
        if not got or len(got) != len(beats):
            return _done(best or beats, best is not None, "빈 응답·비트수 불일치")
        by_n = {int(g.get("n", 0)): (g.get("narration") or "").strip() for g in got}
        if sorted(by_n) != list(range(1, len(beats) + 1)) or not all(by_n.values()):
            return _done(best or beats, best is not None, "번호 불일치·빈 나레이션")
        out = []
        for i, b in enumerate(beats):
            nb = dict(b)
            nb["narration"] = by_n[i + 1]
            out.append(nb)
        ratio = sum(len(v) for v in by_n.values()) / max(1, old_total)
        if closest is None or abs(ratio - 1) < abs(closest_ratio - 1):
            closest, closest_ratio = out, ratio
        if ratio > 1.25:
            note = (f"직전 결과가 원본의 {ratio:.2f}배로 너무 길었다 — 결은 유지하되 "
                    f"군더더기를 덜어 {old_total}자 근처로 줄여라.")
            best = best or (out if ratio <= 1.45 else None)   # 아주 심하지 않으면 예비 보관
            continue
        if ratio < 0.75:
            note = f"직전 결과가 원본의 {ratio:.2f}배로 너무 짧았다 — {old_total}자 근처로."
            continue
        if any(c in v for v in by_n.values() for c in _CLICHE):
            note = "직전 결과에 금지 상투어(꿀템·삶의 질 등)가 남았다 — 전부 제거하라."
            best = out
            continue
        last = by_n[len(beats)]
        if "댓글" in last and not re.search(r"드릴게요|보내드|알려드", last):
            note = ("직전 결과의 마지막 CTA가 보상 없이 끝났다 — 반드시 "
                    "\"남겨주시면 [받는 것] 드릴게요\" 형태로.")
            best = out
            continue
        return _done(out, True, "정상")
    if best is not None:
        return _done(best, True, "재시도 소진(길이·상투어·CTA)")
    # ★마지막 압축 패스(2026-08-07): 재시도가 전부 길이 밖이면 종전엔 스타일을 통째로
    # 버리고 원본 복귀 → trio가 같은 결로 수렴("메종/채이/홈테리어 매칭이 안 됨" 실사고,
    # job 11:38 maison·chae 실패 로그). 스타일이 입혀진 최근접본을 붙잡고 "문체는 두고
    # 길이만 줄여라"를 한 번 더 태운다 — 스타일과 화면 길이를 둘 다 지키는 마지막 기회.
    if closest is not None:
        import json as _json
        cur = [{"n": i + 1, "narration": (b.get("narration") or "")}
               for i, b in enumerate(closest)]
        resp = call(
            ("아래 나레이션의 **문체·어미·결은 그대로** 두고, 각 문장의 군더더기만 "
             f"덜어 전체를 {old_total}자(±15%) 안으로 맞춰라. 문장 수·순서·내용 유지, "
             "사실 추가 금지, 마지막 문장의 댓글 CTA 형태 유지.\n"
             "JSON만: {\"beats\":[{\"n\":1,\"narration\":\"...\"}]}\n\n")
            + _json.dumps(cur, ensure_ascii=False, indent=1), RESTYLE_SCHEMA)
        got = (resp or {}).get("beats") if isinstance(resp, dict) else None
        if got and len(got) == len(beats):
            by_n = {int(g.get("n", 0)): (g.get("narration") or "").strip() for g in got}
            if (sorted(by_n) == list(range(1, len(beats) + 1)) and all(by_n.values())):
                ratio = sum(len(v) for v in by_n.values()) / max(1, old_total)
                if 0.75 <= ratio <= 1.25:
                    out = []
                    for i, b in enumerate(beats):
                        nb = dict(b)
                        nb["narration"] = by_n[i + 1]
                        out.append(nb)
                    return _done(out, True, f"압축패스({closest_ratio:.2f}→{ratio:.2f}배)")
    return _done(beats, False,
                 f"재시도 소진(최근접 {closest_ratio:.2f}배)" if closest_ratio
                 else "재시도 소진(길이·상투어·CTA)")


def parse_beats(resp):
    """모델 응답에서 beats 배열을 꺼낸다 — {"beats":[...]}로도, 배열로도 온다(실측)."""
    if isinstance(resp, list):
        return [b for b in resp if isinstance(b, dict)]
    if isinstance(resp, dict):
        for k in ("beats", "lines", "narrations", "result"):
            v = resp.get(k)
            if isinstance(v, list):
                return [b for b in v if isinstance(b, dict)]
    return []


def over_budget(beats, used_secs, tol=0.15):
    """나레이션 총량이 화면을 넘었나 → (초과여부, 나레이션초, 초과초)."""
    chars = sum(len((b.get("narration") or "")) for b in (beats or []))
    secs = chars / _CHARS_PER_SEC
    return (secs > used_secs * (1 + tol)), secs, secs - used_secs


def cta_missing(beats):
    """마지막 문장에 댓글 유도가 없는가 — 실측 2026-08-04: 프롬프트만으론 2/3만 지켜져
    코드 교정이 필요했다(감상문 '참 좋네요'류로 끝나는 후보가 계속 나옴)."""
    if not beats:
        return False
    return "댓글" not in (beats[-1].get("narration") or "")


def fix_cta_prompt(beats, source_text=""):
    """마지막 문장만 댓글 CTA로 고쳐 받는 교정 프롬프트(shrink와 같은 방식).

    전체 재생성이 아니라 마지막 문장만 — 다른 문장 품질을 흔들지 않는다."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    kw = "나도" if "나도" in (source_text or "") else "정보"
    return ("아래 나레이션의 **마지막 문장만** 고쳐라. 나머지는 글자 하나 바꾸지 마라.\n"
            f"마지막 문장은 반드시 \"댓글에 '{kw}' 남겨주세요\" 형태의 댓글 유도로 끝내라"
            "(길이는 지금 마지막 문장과 비슷하게, 링크·프로필 금지).\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


import re as _re

# 합쇼체 = 종성 ㅂ인 음절 + '니다'(합니다·훌륭합니다·됩니다·줍니다·집니다·습니다).
# ★고정 목록(습니다|입니다|됩니다)으로 검사하지 마라 — "추천합니다"·"훌륭합니다"를 놓친다
#   (2026-08-09 실측에서 실제로 놓쳐 판정이 틀렸다. CLAUDE.md '고정 명사 목록 체커 함정').
_HAPSYO_END = _re.compile(r"[가-힣]니다\s*[.!?~]*\s*$")


def hapsyo_tail_missing(beats, style_name=None):
    """홈테리어픽 서명 — **CTA 직전 문장**이 합쇼체로 닫히는가(2026-08-09).

    이 채널은 본문을 요체로 가다가 CTA 앞 한 문장만 합쇼체로 끊는 낙차가 서명이다
    (실측: 히트 35편 중 34편). 프롬프트로 2차까지 지시했으나 10회 실측 7/10에 그쳤다 —
    CTA·빈비트와 같은 방식으로 코드가 보장한다.
    ★해당 스타일이 아니면 항상 False(다른 스타일은 합쇼체가 오히려 감점 대상이다)."""
    if (style_name or "") != "hometerior":
        return False
    if not beats or len(beats) < 2:
        return False
    prev = (beats[-2].get("narration") or "").strip()
    if not prev:
        return False
    return not _HAPSYO_END.search(prev)


def fix_hapsyo_prompt(beats):
    """CTA 직전 문장만 합쇼체로 닫아 다시 받는다(fix_cta_prompt와 같은 방식).

    전체 재생성이 아니라 그 한 문장만 — 다른 문장 품질을 흔들지 않는다."""
    import json
    n = len(beats) - 1                      # 1-based로 CTA 직전
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션에서 **%d번째 문장(마지막 CTA 바로 앞) 하나만** 고쳐라. "
            "나머지 문장은 글자 하나 바꾸지 마라.\n"
            "그 문장의 **끝을 합쇼체로 짧게 닫아라** — 예: \"멘탈 지켜줍니다\" / "
            "\"감성 미쳤습니다\" / \"롤러 한 번 굴리는 걸로 끝입니다\".\n"
            "★뜻과 길이는 지금과 비슷하게 두고 **어미만** 합쇼체로 바꾼다. "
            "문장 전체를 합쇼체 문어체로 새로 쓰지 마라(본문은 요체 그대로다).\n"
            "★마지막 CTA 문장은 절대 건드리지 마라 — 합쇼체로 바꾸면 안 된다.\n\n"
            % n
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


# 채이 스타일의 생명 = 가족·지인 액자("시어머니가 오셨는데 ~라고 하시는 거예요").
# 관계 프레임은 원본에 없어도 빌리라고 가이드가 명시한다(사실·수치만 원본 범위).
_CHAE_PEOPLE = ("엄마", "어머니", "시어머니", "친정", "남편", "와이프", "아내",
                "딸", "아들", "친구", "동생", "언니", "누나", "형", "이웃", "지인")


def chae_person_missing(beats, style_name=None):
    """채이 서명 — 본문에 **인물**이 등장하는가(2026-08-09).

    이 채널은 가족과의 티키타카(갈등→반전)가 뼈대다. 인물이 없으면 어미만 채이고
    이야기는 다른 채널과 같아진다(실측 10회 중 1건이 인물 0명으로 밋밋해졌다).
    ★해당 스타일이 아니면 항상 False(다른 채널은 인물이 서명이 아니다).
    CTA 문장은 제외하고 본문만 본다."""
    if (style_name or "") != "chae":
        return False
    if not beats:
        return False
    body = " ".join((b.get("narration") or "") for b in beats[:-1]) if len(beats) > 1 \
        else (beats[0].get("narration") or "")
    if not body.strip():
        return False
    return not any(p in body for p in _CHAE_PEOPLE)


def fix_chae_person_prompt(beats):
    """본문 한 문장에 가족 액자를 넣어 다시 받는다(fix_cta_prompt와 같은 방식).

    ★새 사실·수치를 지어내지 말고 **관계 프레임만** 빌린다 — 가이드와 같은 선."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션은 '가족 에피소드' 스타일인데 **등장인물이 없어** 밋밋하다.\n"
            "본문 문장 중 **한 문장만** 골라 가족·지인이 등장하는 장면으로 고쳐라 "
            "(예: \"시어머니가 놀러 오셨는데 이게 뭐냐고 물어보시는 거예요\", "
            "\"엄마가 보더니 왜 이런 걸 말 안 했냐고 하시더라고요\").\n"
            "★지켜야 할 것:\n"
            "- 나머지 문장은 글자 하나 바꾸지 마라. 문장 수도 그대로.\n"
            "- **마지막 CTA 문장은 절대 건드리지 마라.**\n"
            "- 제품의 성능·수치·가격 같은 **사실은 새로 지어내지 마라** — 빌리는 건 "
            "인물과 관계 프레임뿐이다.\n"
            "- 길이는 지금 문장과 비슷하게.\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


# 메종 서명 = ①인물을 통과한다("그 사람이 이렇게 쓰더라") ②장점을 한 문장에 몰아
# 긴 호흡으로 잇는다("~는데 ~니까 ~더라고요") ③"심지어/더 대박인 건" 보너스.
# 가이드(_MAISON_GUIDE)가 요구하는 그대로다.
_MAISON_PEOPLE = _CHAE_PEOPLE + ("사장님", "손님", "직원", "형", "누나")
_MAISON_PROOF = ("난리", "없어서 못", "대박", "심지어", "더 대박인", "다들")
_MAISON_LONG = _re.compile(r"(는데|니까|어서).{0,40}(더라고요|거든요|잖아요|는 거예요)")


def maison_signature_missing(beats, style_name=None):
    """메종 서명 — 인물·긴연결·사회적증거 중 **하나도 없으면** True(2026-08-09).

    ★셋 다 요구하지 않는다 — 소재에 인물이 없을 수도 있어 과교정이 된다. 하나라도
      있으면 통과시키고, 전무할 때만 고친다(밋밋한 광고 카피체가 되는 경우).
    실측 배경: 축약(shrink)이 총량 초과를 줄일 때 메종의 긴 연결·보너스 문장이 제일
      먼저 깎인다. 채이·홈테리어픽은 보장이 있어 살아남는데 메종만 없어 0/6이었다.
    ★해당 스타일이 아니면 항상 False(회귀 0)."""
    if (style_name or "") != "maison":
        return False
    if not beats:
        return False
    body = " ".join((b.get("narration") or "") for b in beats[:-1]) if len(beats) > 1 \
        else (beats[0].get("narration") or "")
    if not body.strip():
        return False
    if any(p in body for p in _MAISON_PEOPLE):
        return False
    if any(p in body for p in _MAISON_PROOF):
        return False
    return not _MAISON_LONG.search(body)


def fix_maison_prompt(beats):
    """본문 한 문장을 메종 결로 고쳐 받는다(다른 서명 보장과 같은 방식)."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션이 '발견담' 스타일인데 **밋밋한 광고 문구**처럼 됐다.\n"
            "본문 문장 중 **한 문장만** 골라 아래 셋 중 하나가 되게 고쳐라.\n"
            "1) 인물을 통과시킨다 — \"친구가 이렇게 쓰더라고요\" / \"엄마가 보시더니\"\n"
            "2) 장점 2~3개를 **한 문장에 몰아** 길게 잇는다 — "
            "\"~는데 ~니까 ~더라고요\" (문장을 뚝뚝 끊지 않는다)\n"
            "3) 사회적 증거를 붙인다 — \"심지어 없어서 못 산다고 하더라고요\"\n"
            "★지켜야 할 것:\n"
            "- 나머지 문장은 글자 하나 바꾸지 마라. 문장 수도 그대로.\n"
            "- **마지막 CTA 문장은 절대 건드리지 마라.**\n"
            "- 성능·수치·가격 같은 **사실은 새로 지어내지 마라**(빌리는 건 관계 프레임뿐).\n"
            "- 어미는 요체(~더라고요·~거든요·~잖아요). 합쇼체(~습니다) 금지.\n"
            "- 길이는 지금 문장과 비슷하게.\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


HOOK_SANITY_SCHEMA = {
    "type": "object",
    "properties": {
        "contradicts": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["contradicts", "reason"],
}


def hook_sanity_prompt(hook_line, material_text):
    """훅 첫 문장이 **소재와 모순되는가**를 묻는다(2026-08-09).

    ★왜 정규식이 아니라 사후검사인가 — 소재 신호를 정규식으로 미리 거르는 방식은
      **새 소재가 나올 때마다 뚫린다**. 실제로 같은 계열 사고가 세 번 났다:
        1) 2026-08-04 y_never  → "피규어 대충 만들지 마세요"(선물 소재)
        2) 2026-08-04 diy      → "피규어를 사 먹지 마세요"(먹거리 아님)
        3) 2026-08-09 diy      → "이제 집에서 파전 안 부쳐요"(원래 집에서 만드는 음식,
                                  job d8a17db5d99f — 만드는 법 영상인데 안 만든다고 했다)
      매번 조건을 덧댔지만 근본은 **훅 틀이 안 맞아도 모델이 억지로 끼운다**는 것이다.
      결과물을 보고 판정하면 소재 종류와 무관하게 걸러진다.
    반환 스키마: {contradicts: bool, reason: str}"""
    return ("아래는 숏폼 영상의 **원본 소재 설명**과 그 영상에 붙인 **첫 문장(훅)**이다.\n"
            "훅이 소재와 **논리적으로 모순되는지만** 판정해라.\n\n"
            "[모순의 예]\n"
            "- 만드는 법을 알려주는 영상인데 훅이 \"이제 안 만들어요/안 사 먹어요\"라고 한다\n"
            "- 원래 집에서 해 먹는 음식인데 \"이제 사 먹지 마세요\"라고 한다\n"
            "- 소재에 없는 장소·인물·사건을 사실인 것처럼 말한다\n"
            "- 제품 용도와 정반대로 말한다\n\n"
            "[모순이 아닌 것 — contradicts=false]\n"
            "- 과장·감탄·호기심 유발(\"진짜 충격받았어요\", \"역대급\")\n"
            "- 시청자를 부르는 말(\"~하시는 분들 이거 보세요\")\n"
            "- 소재에 있는 사실을 다른 표현으로 각색한 것\n\n"
            f"[원본 소재]\n{(material_text or '')[:1200]}\n\n"
            f"[훅 첫 문장]\n{hook_line}\n\n"
            "JSON만: {\"contradicts\": true/false, \"reason\": \"한 줄\"}")


def hook_contradicts(beats, material_text, call):
    """훅이 소재와 모순이면 True. 판정 실패·빈 값이면 **False**(종전 동작 유지 = 회귀 0).

    ★모순일 때만 True — 애매하면 통과시킨다. 멀쩡한 훅을 버리는 쪽이 더 나쁘다."""
    if not beats or not call:
        return False
    hook = (beats[0].get("narration") or "").strip()
    if not hook or not (material_text or "").strip():
        return False
    try:
        r = call(hook_sanity_prompt(hook, material_text), HOOK_SANITY_SCHEMA)
    except Exception:
        return False
    if not isinstance(r, dict):
        return False
    return bool(r.get("contradicts"))


def fix_hook_prompt(beats, material_text):
    """첫 문장만 소재에 맞게 다시 받는다(fix_cta_prompt와 같은 방식)."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션의 **첫 문장만** 고쳐라. 나머지 문장은 글자 하나 바꾸지 마라.\n"
            "지금 첫 문장이 원본 소재와 **모순된다**(소재에 없는 말을 하거나 뜻이 반대다).\n"
            "★소재에 실제로 있는 내용으로, 3초 안에 스크롤을 멈출 만한 한 문장(30자 내외)으로 "
            "다시 써라. 없는 사실·인물·장소를 지어내지 마라.\n"
            "★문장 수와 covers는 그대로 둔다.\n\n"
            f"[원본 소재]\n{(material_text or '')[:900]}\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


def shrink_prompt(beats, used_secs):
    """초과분 교정 재요청 프롬프트(게이트 교정루프와 같은 방식)."""
    import json
    _, secs, over = over_budget(beats, used_secs)
    total = char_budget(used_secs)
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션이 화면보다 %.1f초 길다(나레이션 %.1f초 / 화면 %.1f초).\n"
            "**뜻과 순서는 그대로 두고 표현만 줄여라.** 문장 수는 그대로, 전체 %d자 이하로.\n"
            "문장을 통째로 지우지 말고 군더더기 수식어부터 덜어내라.\n\n%s\n\n"
            "JSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}"
            % (over, secs, used_secs, total, json.dumps(cur, ensure_ascii=False, indent=1)))
