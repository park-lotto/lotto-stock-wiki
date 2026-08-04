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
import re

MIN_SECONDS = 18.0        # 스토리가 서는 하한(사장님 지시)
RATIO = 0.90              # 원본 대비 목표 비율
_CHARS_PER_SEC = 6.5      # 한국어 나레이션 속도(기존 파이프라인과 동일 가정)
_SECS_PER_LINE = 3.2      # 문장 하나가 덮는 평균 화면 길이

CTA_PAT = re.compile(r"댓글|남겨주|보내드|링크|프로필|구독|팔로우")


def is_single_source(source_scripts):
    """소스가 실질적으로 하나인가(segments가 있는 video_id 기준)."""
    vids = {s.get("video_id") for s in (source_scripts or []) if s.get("segments")}
    vids.discard(None)
    return len(vids) == 1


def _dur(s):
    return max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))


def _is_cta(s):
    return bool(CTA_PAT.search(s.get("text") or "")) or s.get("shot_role") == "기타"


def budget_for(segments, target_seconds=None):
    """이 소재로 만들 수 있는 목표 길이. 하한 18초, 상한 원본길이.

    target_seconds(사용자가 고른 값)가 원본보다 크면 **무시한다** — 물리적으로 불가능하다.
    """
    if not segments:
        return 0.0, 0.0
    span = (max(float(s.get("end") or 0) for s in segments)
            - min(float(s.get("start") or 0) for s in segments))
    want = max(MIN_SECONDS, span * RATIO)
    if target_seconds:                      # 사용자가 더 짧게 원하면 존중(단 하한은 지킨다)
        want = min(want, max(MIN_SECONDS, float(target_seconds)))
    return span, min(want, span)            # 원본을 넘을 수 없다


def select_and_order(segments, target_seconds=None):
    """핵심 보존 + 예산 내 선별 + 스토리 순서 재배치.

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
    hook = max(hook_pool, key=lambda s: (s["_dur"], float(s.get("start") or 0)))
    body = [s for s in core if s is not hook]
    # 전개(사용중=과정) → 결과(완성), 그룹 안에서는 시간순이라 맥락이 안 깨진다.
    body.sort(key=lambda s: (0 if s.get("shot_role") == "사용중" else 1,
                             float(s.get("start") or 0)))
    cta.sort(key=lambda s: float(s.get("start") or 0))
    return span, budget, used, [hook] + body + cta


def line_count(used_secs, n_cuts):
    """나레이션 문장 수 — 컷 수보다 적게(한 문장이 컷 2~3개를 덮는다)."""
    return max(3, min(n_cuts, round(used_secs / _SECS_PER_LINE)))


def char_budget(used_secs):
    return int(used_secs * _CHARS_PER_SEC)


def script_prompt(order, used_secs, hook_block):
    """1소스 각색 대본 프롬프트. hook_block은 hook_patterns.prompt_block() 결과."""
    import json
    cuts = [{"n": i + 1, "seg": s.get("seg_id"), "초": round(s["_dur"], 1),
             "화면": s.get("scene_desc") or "", "원본대사": s.get("text") or "",
             "핵심": bool(s.get("is_key"))}
            for i, s in enumerate(order)]
    n_lines = line_count(used_secs, len(order))
    total = char_budget(used_secs)
    return (hook_block +
            "\n아래는 숏폼 한 편을 재편집한 컷 순서다. 이 화면들에 얹을 **나레이션**을 써라.\n\n"
            "[절대규칙]\n"
            "1. 원본대사를 베끼지 마라. 같은 뜻을 완전히 다른 표현으로 바꿔라(어순·어휘·문형 전부).\n"
            f"2. ★문장은 **정확히 {n_lines}개**만 써라. 컷마다 하나씩 쓰는 게 아니다 —\n"
            "   한 문장이 컷 2~3개에 걸쳐 흐르고, 다음 장면에서 자연스럽게 이어받는 구성이다.\n"
            "   각 문장에 그 문장이 덮는 컷 번호를 covers로 적어라(예: covers:[1,2,3]).\n"
            f"3. ★전체 합계 **{total}자를 넘기지 마라**(화면 {used_secs:.1f}초). 이게 제일 중요하다 —\n"
            f"   넘으면 영상이 끝났는데 말이 남는다. 한 문장은 평균 {max(8, total // max(1, n_lines))}자 정도다.\n"
            "4. 컷 순서대로 이야기가 이어져야 한다. 첫 문장은 위 훅 패턴으로 시작하라.\n"
            "5. 화면 설명과 어긋나는 말을 지어내지 마라.\n"
            "6. 마지막 문장은 '댓글에 OO 남겨주세요'로 끝내라(링크·프로필 금지).\n\n"
            "[컷]\n" + json.dumps(cuts, ensure_ascii=False, indent=1) + "\n\n"
            "JSON만: {\"beats\":[{\"n\":1,\"covers\":[1,2],\"narration\":\"...\"}]}")


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
