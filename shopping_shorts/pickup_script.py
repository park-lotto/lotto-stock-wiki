"""픽업영상 대본 — 씨앗 영상의 **훅 문형·CTA**를 판정한다 (2026-08-26 사장님).

## 무엇을 하나
2단계 첫 칸('픽업영상 대본')은 담은 씨앗 영상의 **대본 템플릿 구조**를 그대로 쓰고,
훅은 **문형만** 물려받아 문장은 새로 쓰고, 스토리·등장인물·CTA는 전부 새로 만든다.

## 왜 프롬프트만으로는 안 되나 (실측)
"원본 훅의 문형을 지켜라"라고 프롬프트에 적기만 했을 때 라이브 4안 중 **2안만** 지켰다.
지시는 강제가 아니다 — 메모리 `판정축_하나면_교정이_통째로_죽는다`의 교훈대로
**판정으로 되돌려야** 한다. 이 모듈이 그 판정이다.

## 판정은 두 축이다 (한쪽만 있으면 반대쪽으로 샌다)
  ① 문형 유지  — 안 지키면 "다른 대본"이 된다(2·3안이 여기서 샜다)
  ② 베끼기 차단 — 문형만 보면 **원본 그대로 복사가 만점 통과**한다(가장 나쁜 통과).
     메모리 `참고훅주입_베끼기숫자창작`: 원문을 프롬프트에 실으면 실제로 통째로 베낀다.

★판정은 여기 한 곳에서만 한다(0순위-B). 프롬프트 문구와 검사 규칙이 두 벌이 되면 어긋난다.
"""
import difflib
import re

from shopping_shorts import script_gate

# 훅 문형을 알아보는 어미들. 씨앗마다 훅이 다르므로 규칙으로 뽑는다.
# ⚠️여기 없는 문형은 템플릿이 안 나오고, 그러면 판정도 안 건다(빈손이 오탐보다 낫다).
_HOOK_ENDINGS = ("마세요", "마요", "말고", "하지마")

# 문형에서 소재·행동이 들어가는 자리. script_gate._chunks가 "{...}"를 슬롯으로 읽는다.
_SLOT_SUBJ = "{대상}"
_SLOT_ACT = "{행동}"

# 베끼기 판정 기준 — 원본과 이만큼 겹치면 "새로 쓴 것"이 아니다.
_COPY_MIN_RUN = 8       # 연속 일치 최소 글자
_COPY_RATIO = 0.6       # 원본 길이 대비 연속 일치 비율


def hook_templates(seed_hook):
    """씨앗 훅 → 문형 템플릿 목록. 못 뽑으면 [].

    소재어와 세부 행동은 슬롯으로 비우고 **뼈대 어절만** 남긴다.
    예) "여러분 믹스 커피 절대 물에만 타 먹지 마세요"
        → ["여러분 {대상} 절대 {행동} 마세요"]
    """
    h = (seed_hook or "").strip()
    if not h:
        return []
    end = next((e for e in _HOOK_ENDINGS if e in h), None)
    if not end:
        return []                      # 아는 문형이 아니다 — 판정을 걸지 않는다
    head = h.split()[0] if h.split() else ""
    # '여러분' 같은 호칭으로 시작하면 그것도 뼈대다(이 계열 훅의 서명).
    lead = head if head and end not in head else ""
    strong = "절대" if "절대" in h else ""
    parts = [p for p in (lead, _SLOT_SUBJ, strong, _SLOT_ACT, end) if p]
    return [" ".join(parts)]


def hook_copied(hook, seed_hook):
    """원본 훅을 그대로(또는 거의 그대로) 베꼈나.

    띄어쓰기·구두점만 바꾼 것도 베낀 것이다 — script_gate.norm이 그걸 정규화한다.
    """
    a, b = script_gate.norm(hook), script_gate.norm(seed_hook)
    if not a or not b:
        return False
    if b in a or a in b:
        return True
    m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return m.size >= max(_COPY_MIN_RUN, len(b) * _COPY_RATIO)


def hook_ok(hook, templates, seed_hook):
    """이 훅을 받아들일까 — 문형을 지켰고(①) 베끼지 않았나(②).

    templates가 비면(문형을 못 뽑은 씨앗) **무조건 통과**한다.
    없는 기준으로 반려하면 멀쩡한 대본이 죽는다.
    """
    if hook_copied(hook, seed_hook):
        return False
    if not templates:
        return True
    return script_gate.template_matches(hook, templates, min_ratio=0.5)


# ── CTA ────────────────────────────────────────────────────────────────
# 사장님 지시: CTA는 단어도 구조도 달라야 한다. 실측 1안이 원본과 같은 '믹스'를 그대로 썼다.
_CTA_KW = re.compile(r"['\"‘’“”]([^'\"‘’“”]{1,12})['\"‘’“”]")


def cta_keyword(cta_text):
    """CTA에서 댓글 키워드를 뽑는다(따옴표 안). 없으면 None."""
    m = _CTA_KW.search(cta_text or "")
    return m.group(1).strip() if m else None


def cta_ok(cta_text, seed_cta):
    """CTA 키워드가 씨앗과 다른가. 씨앗 키워드를 못 찾으면 막지 않는다."""
    seed_kw = cta_keyword(seed_cta)
    if not seed_kw:
        return True
    kw = cta_keyword(cta_text)
    if not kw:
        return True                    # 형식이 아예 달라졌다 — 그것도 '다른 CTA'다
    return script_gate.norm(kw) != script_gate.norm(seed_kw)


def filter_drafts(drafts, seed_hook, seed_cta=""):
    """생성된 초안들을 판정해 (통과, 반려) 로 가른다.

    ★판정을 여기 한 곳에 모은다(0순위-B). 호출부는 '몇 안이 남았나'만 보면 된다.
    ★반려에는 **사유를 반드시 남긴다** — 조용히 사라지면 왜 안이 줄었는지 아무도 모른다
      (메모리 `대본퀄_하네스함정`: 조용한 폴백이 쳇바퀴의 뿌리였다).
    """
    tpl = hook_templates(seed_hook)
    ok, bad = [], []
    for d in drafts or []:
        hook = (d.get("hook") or "").strip()
        script = d.get("script") or ""
        if hook_copied(hook, seed_hook):
            bad.append({"draft": d, "reason": "훅이 원본과 거의 같음(베끼기)"})
            continue
        if tpl and not hook_ok(hook, tpl, seed_hook):
            bad.append({"draft": d, "reason": "훅이 씨앗 문형을 안 지킴"})
            continue
        # CTA는 본문 끝에 있다 — 따옴표 키워드로만 판정한다(형식이 달라진 건 통과).
        if seed_cta and not cta_ok(script, seed_cta):
            bad.append({"draft": d, "reason": "CTA 키워드가 원본과 같음"})
            continue
        ok.append(d)
    return ok, bad
