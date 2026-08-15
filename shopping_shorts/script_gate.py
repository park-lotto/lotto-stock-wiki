"""대본이 고른 스타일을 **실제로 지켰는지** 검사한다 — 순수함수(DB·네트워크·Gemini 없음).

## 왜 필요한가 (2026-08-15 코드 실측)

`script_generate._STORY_RULES_CORE`에는 CTA·종결어미·고조연결어 규칙이 매우 상세히 적혀
있는데, **지켜졌는지 확인하는 코드가 한 줄도 없었다.** 그래서 잘 나온 날과 안 나온 날을
구분할 방법조차 없었고, 그게 "대본이 복불복"의 정체다.

여기는 부탁을 **판정**으로 바꾼다. 통과 못 하면 호출부가 재작성을 건다(`gate_feedback`).

## 실험실에서 실제로 밟은 함정 2개 (이식 시 반드시 유지)

1. 문장틀을 통째로 `re.escape`하면 `{`가 `\\{`가 되고, 그걸 다시 치환할 때 앞의 백슬래시가
   남아 리터럴 점(`\\.`)이 돼 **절대 안 맞는다** — 틀을 지킨 문장을 FAIL로 잡았다.
   → 빈칸으로 **먼저 쪼갠 뒤 조각만** 이스케이프한다.
2. 빈칸 뒤 조사는 받침에 따라 바뀐다("{제품}이라고" → "세제라고").
   → 빈칸 다음 조각의 **맨 앞 조사 한 글자는 있으나 없으나** 통과시킨다.
   조사까지 강제하면 맞는 문장을 튕긴다.
"""
import re

# 빈칸 하나가 삼킬 수 있는 최대 글자수. 너무 크면 아무 문장이나 통과(오탐), 너무 작으면
# "살림 유튜버" 같은 정상 치환을 못 담는다. 실측으로 16자면 둘 다 만족.
_SLOT = ".{0,16}"
_JOSA = ("이", "가", "은", "는", "을", "를", "라", "과", "와")

# 말 밀도 허용 폭 — 스타일 히트작 밀도의 70~140%. 밖이면 "그 스타일이 아니다".
DENSITY_LO, DENSITY_HI = 0.7, 1.4
DEFAULT_CHARS_PER_30S = 135      # 스타일에 실측값이 없을 때만(일반 기준 4.5자/초)


def norm(s):
    """비교용 정규화 — 공백·문장부호 제거. 띄어쓰기 차이로 판정이 갈리면 안 된다."""
    return re.sub(r"[\s\.,!?~]+", "", s or "")


def template_matches(text, templates):
    """문장이 주어진 문장틀 중 하나를 실제로 쓴 것인가."""
    for t in templates or []:
        parts = []
        for i, p in enumerate(re.split(r"\{[^}]*\}", t)):
            n = norm(p)
            if i > 0 and n[:1] in _JOSA:
                n = n[1:]
            parts.append(re.escape(n))
        pat = _SLOT.join(x for x in parts if x)
        if pat and re.search(pat, norm(text)):
            return True
    return False


def check(style, beats):
    """(checks, full_text) 반환. checks = [{name, ok, detail}, ...]

    style: {"beat_roles": [...], "templates": {role: [...]}, "chars_per_30s": int}
    beats: [{"role": "...", "text": "..."}, ...]  ← 모델이 돌려준 것
    """
    beats = beats or []
    want = list(style.get("beat_roles") or [])
    got = [b.get("role", "") for b in beats]
    checks = [{"name": "구간 순서", "ok": got == want,
               "detail": "기대 %s / 실제 %s" % (want, got)}]

    templates = style.get("templates") or {}
    for role in want:
        tmpl = templates.get(role) or []
        if not tmpl:
            continue
        hit = [b for b in beats if b.get("role") == role]
        text = hit[0].get("text", "") if hit else ""
        checks.append({"name": "%s 문장틀 준수" % role,
                       "ok": bool(text) and template_matches(text, tmpl),
                       "detail": text[:60] or "(해당 구간 없음)"})

    full = " ".join(b.get("text", "") for b in beats)
    checks.append({"name": "CTA 단어유도", "ok": "남겨주세요" in full,
                   "detail": full[-40:]})

    tgt = style.get("chars_per_30s") or DEFAULT_CHARS_PER_30S
    lo, hi = int(tgt * DENSITY_LO), int(tgt * DENSITY_HI)
    n = len(norm(full))
    checks.append({"name": "말 밀도(%d~%d자)" % (lo, hi), "ok": lo <= n <= hi,
                   "detail": "%d자 / 이 스타일 히트작 %d자" % (n, tgt)})
    return checks, full


def passed(checks):
    return bool(checks) and all(c["ok"] for c in checks)


def gate_feedback(checks):
    """실패 항목을 **그대로** 재작성 지시문으로 만든다. 전부 통과면 "".

    ★부탁이 아니라 되돌리기(2026-08-15 실측): 밀도를 프롬프트로 부탁만 했을 때
      117자 → 203자로 여전히 미달이었다. 실패를 알려주고 다시 쓰게 해야 채워진다."""
    bad = [c for c in checks or [] if not c["ok"]]
    if not bad:
        return ""
    return ("\n\n[재작성 지시 — 방금 쓴 것이 아래를 어겼다. 그대로 고쳐라]\n"
            + "\n".join("- %s: %s" % (c["name"], c["detail"]) for c in bad)
            + "\n분량이 모자라면 문장을 더 쪼개고 상황 묘사를 늘려 채워라. "
              "구조·문장틀은 그대로 두고 살만 붙여라.")
