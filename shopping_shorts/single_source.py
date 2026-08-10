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
    # ★핵심 컷도 **예산 안에서만** 담는다(2026-08-09 사장님 지시: "다른 영상을 해도 똑같은
    #   결과가 나오는 원칙을 찾아야 한다").
    #   종전엔 `keep = list(key)`로 is_key를 통째로 넣어 예산 검사를 건너뛰었다.
    #   그래서 **컷이 전부 is_key인 소재는 원본 길이가 그대로 나갔다** — 실측 DUF9DWKkkki:
    #   컷 10개가 모두 is_key라 예산 30초인데 65.4초가 담겼고 영상이 67초로 나갔다.
    #   같은 목표(30초)를 줬는데 소재에 따라 26초/67초로 갈리면 원칙이 아니다.
    #   ⚠️최소 보장은 남긴다 — 예산이 아무리 작아도 핵심 컷 3개까지는 담아 이야기가 선다
    #     (0개가 되면 훅·전개·CTA 자리가 사라진다).
    key.sort(key=lambda s: float(s.get("start") or 0))
    keep, used = [], 0.0
    for s in key:
        if used + s["_dur"] <= budget or len(keep) < 3:
            keep.append(s)
            used += s["_dur"]
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
    # ★상한은 budget이다(2026-08-09 2차 수정). 처음엔 max(used, budget)로 뒀는데,
    #   그게 **긴 소재에서 천장을 뚫는 통로**가 됐다 — 실측(실제 즐겨찾기 DUF9DWKkkki,
    #   원본 67초): budget 30초인데 used가 65.4초라 요구가 529자로 뛰고 결과가 **1,011자·
    #   영상 124초**로 나왔다(숏폼인데 2분). 사장님이 30초를 골랐으면 30초가 상한이다.
    #   짧은 쪽을 채우는 건 budget에 이미 STORY_MIN_SECONDS 하한이 들어 있어 해결된다.
    script_secs = budget if STORY_MIN_SECONDS > 0 else used
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


def script_prompt(order, used_secs, hook_block, frame_block="", cand_idx=None,
                  facts_block=""):
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
            # ★역할 부여(v5 방식을 1소스에 이식, 2026-08-09). v5는 제약을 얹는 대신
            #   **무슨 일을 하는 건지** 알려줘서 통째 복사를 없앴다(`_rewrite_block`).
            #   그런데 그 블록은 **2소스 경로에만** 쓰이고 1소스엔 없었다 — 1소스는
            #   "어순·어휘·문형 전부 바꿔라"라는 제약만 있었고, 그게 오히려 왜곡을 만들었다
            #   ("20년 동안 전집 하셨던 시어머니" → "20년 경력 시어머니").
            "\n너는 국내 최정상 숏폼 벤치마킹 전문가다. 아래 화면들로 **새로운 영상**을 만든다.\n"
            "★목표는 '다르게 쓰기'가 아니라 **원본을 본 시청자도 알아차리지 못하게 각색하기**다.\n"
            "  같은 사실을 **우리 시청자 입장**에서 다시 말해라.\n"
            "  ⚠️바꾸는 건 **말투와 표현**이지 사실이 아니다. 원본 그대로 둘 것:\n"
            "    성능·수치·가격 / **누가 무엇을 했는지** / **누가 어디로 갔는지(방향)**.\n"
            # ★2026-08-09 사장님 지적 2건이 같은 계열이다 — 관계·방향을 뒤집으면 뒤 문장이
            #   통째로 모순된다:
            #   ① "20년 동안 **전집** 하셨던 시어머니" → "20년 경력 **시어머니**"
            #      (경력이 붙는 건 가게인데 사람에 붙였다)
            #   ② 원본 "내가 **시댁에 갔다**" → 대본 "시어머니가 **놀러 오셨다**"
            #      → 그래서 뒤의 "집에 오자마자 써봤는데"가 말이 안 되게 됐다.
            #   방향 하나만 뒤집혀도 뒤 문장 전체가 무너지므로 여기서 못박는다.
            "    예) 내가 시댁에 갔다 → \"어머니가 놀러 오셨다\"로 뒤집지 마라"
            "(뒤에 '집에 오자마자'가 나오면 말이 안 된다).\n"
            # ★사실표(v7): 있으면 사실의 출처를 이 표 하나로 못박는다. 빈 문자열=종전 동일.
            + (facts_block or "") + "\n"
            "아래는 숏폼 한 편을 재편집한 컷 순서다. 이 화면들에 얹을 **나레이션**을 써라.\n\n"
            "[절대규칙]\n"
            # ★2026-08-09 사장님 지시: "그냥 자유롭게 표현하라고 자유를 줘."
            #   종전 "어순·어휘·문형 **전부** 바꿔라"가 왜곡을 만들었다 — 모델이 그 지시를
            #   지키려고 "20년 동안 전집 하셨던 시어머니"를 압축해 "20년 경력 시어머니"로
            #   만들었다(수식 대상이 가게→사람으로 바뀐다).
            #   ⚠️그 자리에 "수식 관계는 바꾸지 마라" 같은 예외를 덧대는 것도 결국 제약이다
            #     (제약 과적재 = 규칙끼리 이긴다). 지시를 **빼는 쪽**으로 간다.
            #   각색 자체는 _rewrite_block·스타일 few-shot이 이미 이끈다.
            "1. 원본 대사에 매이지 말고 **자유롭게** 네 말로 써라(그대로 옮겨 적지만 마라).\n"
            f"2. ★문장은 **정확히 {n_lines}개**만 써라. 컷마다 하나씩 쓰는 게 아니다 —\n"
            "   한 문장이 컷 2~3개에 걸쳐 흐르고, 다음 장면에서 자연스럽게 이어받는 구성이다.\n"
            "   각 문장에 그 문장이 덮는 컷 번호를 covers로 적어라(예: covers:[1,2,3]).\n"
            f"3. ★전체 합계 **{total}자를 넘기지 마라**(화면 {used_secs:.1f}초). 이게 제일 중요하다 —\n"
            f"   넘으면 영상이 끝났는데 말이 남는다. 한 문장은 평균 {max(8, total // max(1, n_lines))}자 정도다.\n"
            "4. 컷 순서대로 이야기가 이어져야 한다. 첫 문장은 위 훅 패턴으로 시작하라.\n"
            "5. 화면에 없는 걸 지어내지 마라(원본에 있는 사실·수치만).\n"
            # ★2026-08-04 실측(job 53bd4a4a): 후보 3개 전부 '다이소'가 사라졌다. 구매처는
            #   원본의 '파는 힘'이라 보존한다. 다만 **위치·표현은 자유**(2026-08-09 단순화).
            "   원본에 구매처·브랜드(다이소·쿠팡 등)가 있으면 대본 어딘가에 한 번 살려라.\n"
            "6. ★마지막 문장은 **반드시** \"댓글에 '키워드' 남겨주시면 [받는 것] 드릴게요\" "
            "형태로 끝내라(링크·프로필 금지). 뭘 받는지 반드시 말하라 — 받는 게 안 보이면 "
            "아무도 안 남긴다. 그래서 **핵심 비법의 가장 구체적인 한 조각**(정확한 비율·"
            "핵심 재료 이름·수치)은 본문에서 말하지 말고 CTA로 남겨라.\n"
            # ★2026-08-09 사장님 지시: "정말 필요한 가이드·하네스 테두리만 치고 제미니한테
            #   대본의 창작 자유를 줘. 우리 3개 모델들의 장점을 알려주고 벤치마킹해서."
            #   → 걷어낸 것: 구매처 위치 설명 5줄 · 미끼 예시 6줄 · 고조 연결어 목록 지정 ·
            #     어미 종류 지시. 전부 "어떻게 쓸지"를 지시하던 것들이다.
            #     그 자리는 위의 [스타일 예시](실제 히트 대본 few-shot)가 대신한다 —
            #     규칙으로 설명하는 것보다 **잘된 대본을 보고 배우는 게** 낫다(어미교정 실측).
            #   ⚠️되풀이 금지: 여기에 "~하지 마라"를 다시 쌓지 마라. 안 지켜지고(합쇼체
            #     금지했는데 위반), 규칙끼리 이겨 품질이 떨어진다. 결과를 고쳐야 하면
            #     프롬프트가 아니라 **코드 교정**으로 잡는다(edit_plan의 서명 보장들).
            # ★스타일이 꺼져 있으면(_style_extra가 '') 이 문구도 빼야 한다 —
            #   "위 [스타일 예시]"가 없는데 참조하면 모델이 헷갈리고, 배선 테스트도 깨진다.
            + ("7. 위 [스타일 예시]는 조회수 수백만짜리 실제 히트 대본이다. 규칙을 지키는 "
               "것보다 **그 대본들처럼 들리게 쓰는 것**이 중요하다 — 리듬·호흡·말맛을 "
               "벤치마킹해라. 나머지는 네 판단대로 자유롭게 써라.\n\n"
               if _style_extra(cand_idx) else
               "7. 나머지는 네 판단대로 자유롭게 써라.\n\n") +
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


def restyle_prompt(beats, length_note="", style_name=None, facts_block=""):
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
            + (facts_block or "")   # ★사실표(v7) — 리스타일이 사실을 발명하지 못하게
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


def apply_restyle(beats, call, max_tries=3, style_name=None, report=None,
                  facts_block=""):
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
        resp = call(restyle_prompt(beats, length_note=note, style_name=style_name,
                                   facts_block=facts_block),
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


def under_budget(beats, used_secs, floor=0.85):
    """대본이 예산보다 **짧은가** → (미달여부, 나레이션초, 모자란초).

    ★사장님 지시(2026-08-09): "대본이 짧은 건 있을 수가 없다. 그렇게 되면 스토리 자체가
      안 나오고 **설득 구조가 실패한 대본**이다."
      종전엔 over_budget(넘침)만 있고 미달은 방치였다 — 실측: 요구 202자인데 115자(56%)가
      그대로 나갔다(4문장). 넘치면 줄이면서 모자라면 안 채우는 건 비대칭이다.
    floor: 예산의 이 비율 미만이면 미달로 본다(기본 85%)."""
    chars = sum(len((b.get("narration") or "")) for b in (beats or []))
    secs = chars / _CHARS_PER_SEC
    need = used_secs * floor
    return (secs < need), secs, need - secs


def expand_prompt(beats, used_secs, material_text=""):
    """모자란 분량을 채워 다시 받는다 — **문장을 늘리지 말고 살을 붙인다**.

    ★새 사실을 지어내면 안 된다(원본에 없는 성능·수치·가격 금지). 늘리는 건
      '어떻게 그랬는지·그래서 어땠는지'의 서사·묘사다 — few-shot 채널들이 그렇게 쓴다."""
    import json
    n_lines = max(len(beats or []), 5)
    total = char_budget(used_secs)
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in (beats or [])]
    now = sum(len((b.get("narration") or "")) for b in (beats or []))
    return ("아래 나레이션이 **너무 짧아서 이야기가 서지 않는다**"
            f"(지금 {now}자 / 목표 {total}자).\n"
            f"★문장 수를 **{n_lines}개로** 맞추고, 전체를 **{total}자에 가깝게** 늘려라.\n"
            "[늘리는 방법 — 이것만 해라]\n"
            "- 상황을 구체적으로: 언제·어디서·누가 그랬는지 한 겹 더 (원본 재료 범위 안에서)\n"
            "- 동작을 순서대로: 뭘 어떻게 했는지 손에 잡히게\n"
            "- 반응·결과를 붙여서: 그래서 어땠는지, 누가 뭐라고 했는지\n"
            "- 문장을 길게 이어라: \"~는데 ~니까 ~더라고요\"처럼 한 문장에 두세 마디를 몬다\n"
            "[절대 하지 마라]\n"
            "- 원본에 없는 **성능·수치·가격·구매처를 지어내는 것**\n"
            "- 같은 말을 다르게 반복해 글자만 늘리는 것\n"
            "- 마지막 CTA 문장의 형식을 바꾸는 것(댓글 유도는 그대로 둔다)\n\n"
            f"[원본 소재]\n{(material_text or '')[:900]}\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


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
    # ★2026-08-09 2차 수정(사장님 지적: "이것도 어색한 문장들 아닌가?").
    #   종전엔 인물·증거·긴연결 **셋 중 하나**만 있으면 통과였다. 그래서 "지인 집에
    #   갔는데…" 한 마디로 인물이 잡히면, 나머지가 "…흘러내려요 / …편해요"처럼 뚝뚝
    #   끊긴 설명 나열이어도 그냥 지나갔다(실측).
    #   메종 가이드의 핵심은 **"문장을 뚝뚝 닫지 마라 — ~는데 ~니까 ~더라고요로 길게
    #   잇고 다음 문장은 앞을 이어받아라"**다. 그게 이 채널을 이야기로 만든다.
    #   → **긴 연결(또는 이어받는 접속)** 을 필수로 보고, 인물·증거는 보조로 둔다.
    _has_flow = bool(_MAISON_LONG.search(body))
    if not _has_flow:
        # 문장 머리에서 앞을 이어받는 접속어도 '이어짐'으로 인정한다.
        _conn = ("근데", "그래서", "심지어", "게다가", "더군다나", "그러다", "그랬더니")
        _sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", body) if s.strip()]
        _has_flow = sum(1 for s in _sentences[1:]
                        if s.startswith(_conn)) >= 1
    if not _has_flow:
        return True                          # 이어지지 않으면 메종이 아니다
    # 이어지긴 하는데 인물·증거가 전무하면 그때만 보강한다.
    if any(p in body for p in _MAISON_PEOPLE):
        return False
    if any(p in body for p in _MAISON_PROOF):
        return False
    return True


def fix_maison_prompt(beats):
    """본문 한 문장을 메종 결로 고쳐 받는다(다른 서명 보장과 같은 방식)."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in beats]
    return ("아래 나레이션이 **문장을 뚝뚝 끊어 나열**해서 광고 문구처럼 들린다.\n"
            "★본문 문장들이 **이야기로 이어지게** 고쳐라 — 이게 이 채널의 핵심이다.\n"
            "1) 장점 2~3개를 **한 문장에 몰아** 길게 잇는다 — \"~는데 ~니까 ~더라고요\"\n"
            "2) 다음 문장은 **앞 문장을 이어받아** 시작한다 — 근데/그래서/심지어/그랬더니\n"
            "3) 여유가 되면 인물을 통과시키거나(\"친구가 이렇게 쓰더라고요\") "
            "사회적 증거를 붙인다(\"없어서 못 산다고 하더라고요\")\n"
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


FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "distorts": {"type": "boolean"},
        "worst": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["distorts", "worst", "reason"],
}

# ── 증거검증형 날조 검사(2026-08-10) ─────────────────────────────────────────
# fact_distorted(불리언 판정)는 소재마다 결과가 흔들려 배선 보류됐다(정상 대본까지
# 3/3 True — edit_plan.py의 보류 주석). 판정을 "날조 구절을 대본에서 **그대로 인용**"
# 하게 바꾸고, 인용이 ①대본에 실재하고 ②원본 소재에 없을 때만 유효로 친다.
# 애매한 True가 구절 인용을 못 대면 코드가 기계적으로 버린다 → 오탐이 회귀를 못 만든다.
# 실사고(job 890c2f41e35a): "우유로 구운 우유"·"칼로리가 절반"·"에어프라이어" —
# 훅 검사는 첫 문장만 봐서 본문 날조가 전부 통과했다.

# ── 사실표(v7, 2026-08-10) ───────────────────────────────────────────────────
# 두더지잡기의 뿌리 처방: "긴 원문 + 몰라보게 각색" 조합이 사실까지 바꿨다
# (실사고 job 890c2f41: '우유로 구운 우유'·'칼로리 절반'·'에어프라이어').
# 사실을 **닫힌 목록**으로 먼저 뽑아 고정하고, 생성·리스타일엔 "사실은 이 표에서만,
# 표현은 자유"를 준다 — 무엇(고정)/어떻게(자유)를 입력에서 갈라 사후 검사 의존을 줄인다.

FACTSHEET_SCHEMA = {
    "type": "object",
    "properties": {"facts": {"type": "array", "items": {"type": "string"}}},
    "required": ["facts"],
}


def factsheet_prompt(material_text):
    return ("아래 [원본 소재]에서 **사실만** 짧은 문장 목록으로 뽑아라(8~16개).\n"
            "반드시 넣을 것: 제품/음식의 **이름(원문 표기 그대로)** · 재료·도구 · "
            "수치·가격 · 장소·사건(누가 무엇을 했는지) · 반응/평가 · 댓글 CTA 키워드.\n"
            "★이름이 문장 속 서술로만 나오면(예: \"그냥 우유 구운거야\") 그 표현을 "
            "그대로 이름으로 적어라(\"이름: 우유 구운 것\"). 다른 말로 합성하거나 "
            "\"이름 없음\"으로 버리지 마라 — 대본이 이 이름을 그대로 쓴다.\n"
            "원문에 없는 것을 추측해 넣지 마라. 조리법·스펙이 원문에 없으면 "
            "\"만드는 법 상세는 원문에 없음\"처럼 **없음도 사실로** 적어라.\n\n"
            f"[원본 소재]\n{(material_text or '')[:1500]}\n\n"
            "JSON만: {\"facts\":[\"...\"]}")


def build_factsheet(material_text, call):
    """사실표(문장 리스트). 실패·빈 결과면 [] — 호출부는 빈 표면 무주입(종전 동일)."""
    if not call or not (material_text or "").strip():
        return []
    try:
        r = call(factsheet_prompt(material_text), FACTSHEET_SCHEMA)
    except Exception:
        return []
    facts = r.get("facts") if isinstance(r, dict) else None
    if not isinstance(facts, list):
        return []
    return [f.strip() for f in facts if isinstance(f, str) and f.strip()][:16]


def factsheet_block(facts):
    """생성·리스타일 프롬프트에 끼우는 사실표 블록. 빈 표면 빈 문자열(회귀 0)."""
    if not facts:
        return ""
    return ("\n[사실표 — 이 영상의 사실 전부]\n"
            + "\n".join("- %s" % f for f in facts)
            + "\n★사실은 이 표에 있는 것만 써라. 표에 없는 도구·재료·수치·가격·효능·"
            "사건을 만들지 마라. 제품·음식 **이름은 표의 표기 그대로**(줄이거나 "
            "합성하지 마라). 말투·화자·구도·표현은 완전히 자유다.\n")


FAB_SCHEMA = {
    "type": "object",
    "properties": {
        "fabrications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["quote", "reason"],
            },
        },
    },
    "required": ["fabrications"],
}


def fabrication_prompt(narrs, material_text):
    body = "\n".join("%d. %s" % (i + 1, n) for i, n in enumerate(narrs or []))
    return ("아래 [대본]에서 [원본 소재]에 **없는 사실을 지어낸 구절**만 찾아라.\n"
            "구절은 반드시 [대본]에서 **글자 그대로 복사**해라(6자 이상). "
            "바꿔 쓰면 무효 처리된다.\n\n"
            "[날조인 것]\n"
            "- 원본에 없는 조리도구·재료·수치·가격·효능 (예: 원본에 없는 \"에어프라이어\", "
            "\"칼로리가 절반\")\n"
            "- 제품·음식 이름을 바꾸거나 문법이 어긋나게 비튼 것 (예: \"구운 우유\"를 "
            "\"우유로 구운 우유\"로)\n\n"
            "[날조가 아닌 것 — 넣지 마라]\n"
            "- 같은 사실을 다른 표현으로 각색한 것(이건 목표다)\n"
            "- 화자·관계 설정(\"친구가\", \"엄마가\") / 과장·감탄(\"역대급\")\n\n"
            f"[원본 소재]\n{(material_text or '')[:1200]}\n\n"
            f"[대본]\n{body}\n\n"
            "없으면 빈 배열. JSON만: {\"fabrications\":[{\"quote\":\"대본 그대로\","
            "\"reason\":\"한 줄\"}]}")


def _norm_ws(s):
    return _re.sub(r"\s+", "", s or "")


def fact_fabrications(beats, material_text, call, samples=2):
    """검증된 날조 구절 목록. 판정 실패·인용 불일치·애매하면 [] (회귀 0).

    유효 조건(코드 검증 — LLM 오탐을 기계적으로 거른다):
      ①quote(공백 무시)가 나레이션에 실재  ②원본 소재에는 없음  ③6자 이상.

    ★samples=2 합집합(2026-08-10 실측): 단발 판정은 같은 입력에서 잡았다 놓쳤다
    한다(C안 1/2, A안 2/3). 감도는 합집합으로 올리고, 오탐은 위 코드 필터가
    계속 막는다(정상 대본 실측 오탐 0)."""
    if not beats or not call or not (material_text or "").strip():
        return []
    narrs = [(b.get("narration") or "").strip() for b in beats]
    narrs = [n for n in narrs if n]
    if not narrs:
        return []
    script_n = _norm_ws(" ".join(narrs))
    mat_n = _norm_ws(material_text)
    out = []
    for _ in range(max(1, samples)):
        try:
            r = call(fabrication_prompt(narrs, material_text), FAB_SCHEMA)
        except Exception:
            continue
        items = r.get("fabrications") if isinstance(r, dict) else None
        if not isinstance(items, list):
            continue
        for it in items:
            q = (it.get("quote") or "").strip() if isinstance(it, dict) else ""
            qn = _norm_ws(q)
            if len(qn) >= 6 and qn in script_n and qn not in mat_n and q not in out:
                out.append(q)
    return out


def fix_fabrication_prompt(beats, material_text, quotes):
    """검증된 날조 구절이 든 문장만 원본 사실로 고쳐 받는다."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in (beats or [])]
    ql = "\n".join("- %s" % q for q in quotes)
    return ("아래 대본에 **원본 소재에 없는 날조 구절**이 있다:\n"
            f"{ql}\n\n"
            "이 구절이 든 문장만 원본 사실에 맞게 고쳐라. 나머지는 글자 하나 바꾸지 마라.\n"
            "★원본에 없는 도구·재료·수치·가격·효능을 새로 넣지 마라.\n"
            "★문장 수·covers·어미는 그대로. 마지막 CTA 문장은 건드리지 마라.\n\n"
            f"[원본 소재]\n{(material_text or '')[:1000]}\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


def fact_check_prompt(narrs, material_text):
    """★대본 **전체**가 원본 사실을 왜곡했는가(2026-08-09).

    훅 검사(hook_contradicts)는 첫 문장만 본다 — 본문 왜곡은 통과했다.
    실측: 원본 "20년 동안 **전집** 하셨던 시어머니" → 대본 "20년 차 시어머니"/"20년 차
    사장님"(경력이 붙는 건 가게인데 사람에 붙였다), "아이들도 여섯 장을 순삭"(원본에
    없는 사실). 사장님 지적: "2회차에 20년차 시어머니가 말이 되나?"
    """
    body = "\n".join("%d. %s" % (i + 1, n) for i, n in enumerate(narrs or []))
    return ("아래 [대본]이 [원본 소재]에 **없는 사실을 지어냈거나 뜻을 왜곡했는지** 판정해라.\n\n"
            "[왜곡의 예 — distorts=true]\n"
            "- 원본 \"20년 동안 전집 하셨던 시어머니\" → 대본 \"20년 차 시어머니\"\n"
            "  (경력이 붙는 건 **가게**지 사람이 아니다. 수식 대상을 바꾸면 왜곡이다)\n"
            "- 원본에 없는 수치·인원·가격·후기를 만든 것(\"아이들이 여섯 장을 순삭\")\n"
            "- 원본에 없는 제품 성능·효과를 단정한 것\n\n"
            "[왜곡이 아닌 것 — distorts=false]\n"
            "- 같은 사실을 다른 표현으로 각색한 것(이건 오히려 목표다)\n"
            "- 관계 프레임을 빌린 것(\"친구가\"·\"엄마가\") — 사실이 아니라 화자 설정이다\n"
            "- 과장·감탄(\"역대급\", \"진짜 놀랐어요\")\n\n"
            f"[원본 소재]\n{(material_text or '')[:1200]}\n\n"
            f"[대본]\n{body}\n\n"
            "JSON만: {\"distorts\":true/false,\"worst\":\"가장 문제인 문장 그대로\","
            "\"reason\":\"한 줄\"}")


def fact_distorted(beats, material_text, call):
    """대본이 원본을 왜곡했으면 True. 판정 실패·애매하면 False(회귀 0)."""
    if not beats or not call or not (material_text or "").strip():
        return False
    narrs = [(b.get("narration") or "").strip() for b in beats]
    narrs = [n for n in narrs if n]
    if not narrs:
        return False
    try:
        r = call(fact_check_prompt(narrs, material_text), FACT_SCHEMA)
    except Exception:
        return False
    return bool(r.get("distorts")) if isinstance(r, dict) else False


def fix_fact_prompt(beats, material_text):
    """왜곡된 문장만 원본 사실에 맞게 고쳐 받는다."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in (beats or [])]
    return ("아래 대본에 **원본에 없는 사실이거나 뜻이 왜곡된 문장**이 있다.\n"
            "그 문장만 원본 사실에 맞게 고쳐라. 나머지는 글자 하나 바꾸지 마라.\n"
            "★수식 대상을 바꾸지 마라 — \"20년 동안 전집 하셨던 시어머니\"를 "
            "\"20년 차 시어머니\"로 줄이면 뜻이 달라진다.\n"
            "★원본에 없는 수치·인원·가격·후기를 만들지 마라.\n"
            "★문장 수·길이·어미는 그대로. 마지막 CTA 문장은 건드리지 마라.\n\n"
            f"[원본 소재]\n{(material_text or '')[:1000]}\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


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


# CTA 키워드로 쓰기엔 뜻이 없는 말 — 소재에서 뽑을 때 걸러낸다.
_KW_STOP = {
    "이거", "그거", "저거", "이것", "그것", "정말", "진짜", "너무", "완전", "그냥",
    "제가", "저는", "우리", "여기", "거기", "지금", "다음", "하나", "두는", "때문",
    "하면", "해서", "있는", "없는", "같은", "이런", "저런", "그런", "바로", "다들",
    "매번", "요즘", "제품", "사용", "가능", "생각", "경우", "방법", "정보",
    # 수량·순서를 세는 말은 키워드가 못 된다(실측: "번째"가 뽑혔다).
    "번째", "하나씩", "가지", "개씩", "정도", "얼마", "조금", "많이", "그리고",
}
# ★어미·서술어는 키워드가 될 수 없다(2026-08-09 실측 버그: CTA가 "댓글에 '거예요'"로
#   나갔다). 명사만 뽑아야 하는데 형태소 분석기가 없어 어미를 정규식으로 걸러낸다.
_KW_TAIL_RX = _re.compile(
    r"(거예요|예요|에요|해요|아요|어요|더라고요|거든요|잖아요|네요|세요|시요|"
    r"습니다|입니다|합니다|십니다|는데|니까|어서|라고|다고|면서|으로|처럼|같이)$")


def cta_keyword_for(beats, material_text=""):
    """CTA 폴백에 쓸 키워드 — **소재에서** 뽑는다(2026-08-09).

    종전엔 '나도'/'정보' 둘뿐이라 파전·곰팡이 영상에도 "댓글에 '정보'"가 나갔다
    (10회 실측 6번). 소재와 겉돌 뿐 아니라 **인포크 자동응답 키워드가 대본과 어긋난다**.
    순서: ①대본이 이미 쓴 따옴표 키워드 ②소재에서 자주 나오는 명사 ③'정보'(최후)."""
    # ① 대본에 이미 있는 CTA 키워드를 그대로 따른다(후보 간 일관성).
    for b in reversed(beats or []):
        m = _re.search(r"['\"]([가-힣]{2,6})['\"]", b.get("narration") or "")
        if m and m.group(1) not in _KW_STOP:
            return m.group(1)
    # ② 소재에서 2~4글자 한글 명사 중 최빈어.
    #   ★조사를 떼고 센다 — 안 떼면 "파전이"·"곰팡이가"가 키워드로 나간다(실측).
    words = _re.findall(r"[가-힣]{2,6}", material_text or "")
    freq = {}
    for w in words:
        if _KW_TAIL_RX.search(w):        # 어미·서술어는 제외(명사만 키워드가 된다)
            continue
        w = _re.sub(r"(이|가|은|는|을|를|에|의|도|만|과|와|로|으로|께|한테|에서|부터|까지)$",
                    "", w)
        if len(w) < 2 or w in _KW_STOP:
            continue
        freq[w] = freq.get(w, 0) + 1
    if freq:
        best = max(freq.items(), key=lambda kv: (kv[1], len(kv[0])))
        if best[1] >= 2:                     # 한 번만 나온 말은 소재의 핵심이 아니다
            return best[0]
    return "나도" if "나도" in (material_text or "") else "정보"


def hapsyo_violation(beats, style_name=None):
    """★합쇼체를 **쓰면 안 되는 스타일**인데 썼는가(2026-08-09).

    메종·채이 few-shot 원문에는 합쇼체가 **0회**이고 가이드도 "합쇼체(~습니다)로 닫지
    마라"라고 명시한다. 그런데 실측에서 메종 대본이 "비법 공개합니다 / 식감이 완전히
    달라집니다"로 나왔다 — style_penalty가 0.27점 감점은 하지만 **고치지는 않는다**.
    감점은 순위표일 뿐이라 3후보가 다 위반하면 위반한 게 그대로 추천된다.
    CTA·서명과 같은 원칙으로 **코드가 교정**한다.
    허용 편수(_HAPSYO_ALLOWANCE)를 넘긴 경우만 위반으로 본다 — 홈테리어픽은 2편까지
    서명이므로 대상이 아니다."""
    try:
        from shopping_shorts import style_profiles as _sp
    except Exception:
        return False
    if not beats:
        return False
    allowed = _sp._HAPSYO_ALLOWANCE.get(style_name or "", 0)
    narrs = [(b.get("narration") or "").strip() for b in beats]
    hits = [n for n in narrs if _re.search(r"[가-힣]니다[.!?~]*$", n)]
    return len(hits) > allowed


def fix_hapsyo_violation_prompt(beats, style_name=None):
    """합쇼체로 닫은 문장만 요체로 되돌려 받는다(다른 교정과 같은 방식)."""
    import json
    cur = [{"n": b.get("n"), "covers": b.get("covers"), "narration": b.get("narration")}
           for b in (beats or [])]
    return ("아래 나레이션에서 **'~습니다/~합니다/~됩니다'처럼 합쇼체로 끝나는 문장만** "
            "요체로 고쳐라. 나머지 문장은 글자 하나 바꾸지 마라.\n"
            "★이 채널은 합쇼체를 쓰지 않는다 — 예시 대본에 한 번도 안 나온다.\n"
            "고칠 어미: ~더라고요 / ~거든요 / ~는 거예요 / ~잖아요 / ~네요\n"
            "  예) \"식감이 완전히 달라집니다\" → \"식감이 완전히 달라지더라고요\"\n"
            "      \"비법을 공개합니다\" → \"비법을 알려드릴게요\"\n"
            "★뜻과 길이는 그대로, **어미만** 바꾼다. 문장 수도 그대로.\n"
            "★마지막 CTA 문장은 건드리지 마라.\n\n"
            + json.dumps(cur, ensure_ascii=False, indent=1)
            + "\n\nJSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


# 훅 첫머리에 오는 감탄사·부름말 — 이 채널들이 실제로 쓰는 시작이다.
# (메종 52만 "와, 저 이거 보고 소리 질렀어요" / 홈테리어픽 178만 "와... 커튼도 블라인드도")
# ★2026-08-09 사장님 지시: "와 / 여러분을 넣으라니까 **아니는 빼**."
#   '아니'는 실제 few-shot에도 없고 시비조로 들린다 — 목록에서 제외했다.
_HOOK_OPENERS = ("와", "여러분")


def hook_opener_missing(beats, style_name=None):
    """훅 첫머리에 감탄사·부름말이 없는가(2026-08-09 사장님 지시).

    "처음 훅은 와~ / 여러분 이런 것 좀 들어가게. 적당히 좀 넣어야 살지.
     메종이랑 홈테리어 영상들 대부분 쓰던데."
    ★프롬프트로는 안 됐다 — 훅 틀에 "와,"를 넣고 "감탄사는 살려라"까지 적었는데도
      실측 3/3, 재시도 3/3 전부 사라졌다(훅 블록의 "베끼지 마라"에 밀린다).
      그래서 CTA·서명과 같이 코드로 보장한다.
    ★채이는 대상이 아니다 — few-shot 2편 모두 "이거 몰라서/저 이거 때문에"로 열고
      감탄사를 안 쓴다(그 채널 결이 아니다)."""
    if (style_name or "") == "chae":
        return False
    if not beats:
        return False
    first = (beats[0].get("narration") or "").strip()
    if not first:
        return False
    head = first[:12]
    return not any(head.startswith(o) or (o + ",") in head or (o + " ") in head
                   for o in _HOOK_OPENERS)


# ★매장 추천 훅 — 사장님이 준 형태 그대로(2026-08-09): "이게 지금 제일 핫한 건데".
#   모델에 맡기면 "다이소 정리함 보고 깜짝 놀랐어요"로 축약해버려 코드가 직접 세운다.
_STORE_HOOKS = (
    "와 여러분 {place} 가면 이거 꼭 사오셔야 합니다.",
    "와 {place} 가면 이건 꼭 쟁여놓으세요.",
    "여러분 {place} 가면 이건 꼭 챙기셔야 합니다.",
)
_STORE_NAMES = ("다이소", "올리브영", "이마트", "코스트코", "편의점", "마트")


def store_hook_for(material_text, idx=0):
    """소재에 매장이 있으면 그 매장으로 매장추천 훅 문장을 만든다. 없으면 None.

    ★3후보 중 **한 후보에만** 쓴다(사장님: "3개 중 한 개는 강제시켜봐") — 셋 다 같은
      훅으로 열면 후보를 나눈 의미가 없다."""
    m = material_text or ""
    place = next((s for s in _STORE_NAMES if s in m), None)
    if not place:
        return None
    return _STORE_HOOKS[idx % len(_STORE_HOOKS)].format(place=place)


def force_store_hook(beats, material_text, idx=0):
    """첫 문장을 매장추천 훅으로 **교체**한다(코드가 직접 — 모델은 축약해버린다).

    ★원래 첫 문장은 버리지 않고 **둘째 문장 앞에 붙여** 내용 손실을 막는다."""
    hook = store_hook_for(material_text, idx)
    if not hook or not beats:
        return beats
    first = (beats[0].get("narration") or "").strip()
    if not first or first.startswith(("와 ", "여러분 ")):
        return beats                      # 이미 그 형태면 그대로 둔다
    beats[0]["narration"] = hook
    beats[0]["caption_lines"] = None
    if len(beats) > 1:                    # 밀려난 원문은 다음 비트 앞에 얹는다
        # ★밀려난 문장이 감탄사로 시작하면 그 감탄사를 뗀다(2026-08-09 실측 버그):
        #   강제 훅이 "와 여러분 …"인데 뒤에 "와, 저 이거 보고…"가 붙어 **"와"가 두 번**
        #   나왔다. 훅은 한 번만 터져야 한다.
        _moved = _re.sub(r"^(와|여러분)[,\.\s]+", "", first).strip()
        nxt = (beats[1].get("narration") or "").strip()
        beats[1]["narration"] = (_moved + " " + nxt).strip() if _moved else nxt
        beats[1]["caption_lines"] = None
    return beats


# ★내 감정·반응에 '~더라고요'가 붙으면 틀린 말이다(2026-08-09 사장님 지적).
#   '~더라고요'는 **남의 일을 보거나 겪어서 알게 된 것**에 쓴다 —
#   "충격받았더라고요"(X) → "충격받았어요"(O).
_SELF_FEEL_RX = _re.compile(
    r"(충격받았|놀랐|당황했|감동했|짜증났|화났|기뻤|속상했|서운했|소리 질렀|"
    r"기절할 뻔했|현타 왔)더라고요")


def fix_self_feeling_endings(beats):
    """내 감정 + '더라고요'를 '~어요'로 바로잡는다(코드가 직접 — 한 글자 치환이다)."""
    if not beats:
        return beats
    for b in beats:
        t = b.get("narration") or ""
        if not t:
            continue
        new = _SELF_FEEL_RX.sub(lambda m: m.group(1) + "어요", t)
        if new != t:
            b["narration"] = new
            b["caption_lines"] = None
    return beats


def add_hook_opener(beats):
    """첫 문장 앞에 감탄사를 **코드가 직접** 붙인다(2026-08-09).

    ★LLM에 맡기지 않는다 — fix 프롬프트로 "첫 문장 맨 앞에만"이라고 지시했더니
      모델이 **6문장 전부에 "아니,"를 붙였다**(실측, 사장님 확인). 한 단어 얹는 일에
      모델을 부를 이유가 없다. 결정적으로 코드가 한다(CTA 폴백과 같은 원칙).
    ★맨 앞 한 마디만 얹고 나머지 문장은 손대지 않는다."""
    if not beats:
        return beats
    first = (beats[0].get("narration") or "").strip()
    if not first:
        return beats
    # ★'와'만 붙인다(2026-08-09 사장님 지시: "여러분이 나올 때는 ~하지 마라 / ~해라
    #   이런 건데 지금 억지로 넣은 거야. 저렇게밖에 안 되면 빼고 와~ 이걸 넣어").
    #   '여러분'은 **명령·권유형과 짝**이다("여러분 다이소 가면 사오세요"). 그건 훅 패턴
    #   y_store/y_when/y_never 틀에 이미 들어 있으니 거기서 나온다.
    #   여기서 붙이는 건 서술형 문장 앞이라 '여러분'을 얹으면 어색해진다
    #   (실측: "여러분 시댁 놀러 갔다가 ~ 소리 질렀잖아요" — 명령형이 아닌데 부름말).
    #   '아니'도 뺐다(few-shot에 없고 시비조로 들린다).
    opener = "와, "
    beats[0]["narration"] = opener + first
    beats[0]["caption_lines"] = None
    return beats


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
