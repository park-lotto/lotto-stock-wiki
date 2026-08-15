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

# 빈칸 하나가 삼킬 수 있는 최대 글자수.
# ★16 → 28로 넓힘(2026-08-15 라이브 실측). 모델이 빈칸에 살을 붙인다:
#   "시어머니한테" 뒤에 "기름때 다 안 지워졌다고"를 끼워 넣고도 "욕 바가지로 먹을 뻔했어요"로
#   끝냈는데, 16자로는 이 정상 문장을 FAIL로 잡았다. 틀의 뼈대(고정 어구 순서)만 지키면 된다.
_SLOT = ".{0,28}"
# 빈칸 **바로 뒤**에 붙는 조사. 빈칸이 무엇으로 채워지느냐에 따라 붙었다 떨어졌다 하고,
# 모델이 그 자리에 살을 붙이기도 한다("{가족}한테" → "시어머니한테 기름때 다 안 지워졌다고").
# 조사를 고정 어구에 붙여두면 그 어구가 통째로 안 맞아 정상 문장을 튕긴다 → 앞에서 떼어낸다.
# 긴 것부터 검사해야 "한테"가 "한"으로 잘리지 않는다.
_JOSA = ("이라고", "한테서", "에게서", "한테", "에게", "께서", "부터", "까지", "처럼",
         "에서", "라고", "이", "가", "은", "는", "을", "를", "라", "과", "와", "도", "의")

# ★어미 흔들림 흡수(2026-08-15 라이브 실측). "하더라구요"(틀) vs "하더라고요"(생성)는
#   같은 말인데 한 글자 차이로 FAIL이 났다. 표기 흔들림은 스타일 위반이 아니다.
_EMI_FIX = (("구요", "고요"), ("구여", "고요"), ("드라구", "드라고"))

# 말 밀도 허용 폭 — 스타일 히트작 밀도의 70~140%. 밖이면 "그 스타일이 아니다".
DENSITY_LO, DENSITY_HI = 0.7, 1.4
DEFAULT_CHARS_PER_30S = 135      # 스타일에 실측값이 없을 때만(일반 기준 4.5자/초)


def norm(s):
    """비교용 정규화 — 공백·문장부호 제거 + 어미 표기 흔들림 통일.
    띄어쓰기나 '구요/고요' 차이로 판정이 갈리면 안 된다(실측 오탐 원인)."""
    out = re.sub(r"[\s\.,!?~'\"]+", "", s or "")
    for a, b in _EMI_FIX:
        out = out.replace(a, b)
    return out


def _chunks(template):
    """문장틀 → 빈칸을 뺀 고정 어구 조각들(정규화·조사 흡수). 2자 이하는 버린다.

    ★버리는 이유: "가"·"에" 같은 한두 글자는 어느 문장에나 있어 판정이 무의미해진다."""
    out = []
    for i, p in enumerate(re.split(r"\{[^}]*\}", template or "")):
        n = norm(p)
        if i > 0:
            for j in _JOSA:                    # 긴 조사부터 — "한테"가 "한"으로 안 잘리게
                if n.startswith(j):
                    n = n[len(j):]
                    break
        if len(n) >= 3:
            out.append(n)
    return out


def template_matches(text, templates, min_ratio=0.5):
    """문장이 문장틀 중 하나를 **실제로 쓴 것인가**.

    ★통짜 일치를 요구하지 않는다(2026-08-15 라이브 실측). 모델은 틀의 앞머리를 소재에 맞게
      바꾸고("이것 때문에" → "주방 청소하다가") 중간에 살을 붙이면서도 특징 어구
      ("…한테 욕 바가지로 먹을 뻔했어요")는 그대로 쓴다. 그게 이 스타일을 스타일이게 하는
      부분이므로 통과여야 한다. 통짜로 요구했더니 정상 문장을 FAIL로 잡았다.

    판정: 고정 어구들이 **순서대로** 나타난 총 글자수가 절반 이상이고,
          그중 **가장 긴 어구(=서명 어구)**는 반드시 있어야 한다.
    """
    n_text = norm(text)
    for t in templates or []:
        chunks = _chunks(t)
        if not chunks:
            continue
        longest = max(chunks, key=len)
        if longest not in n_text:
            continue                      # 서명 어구가 없으면 그 틀이 아니다
        matched, pos = 0, 0
        for ch in chunks:
            at = n_text.find(ch, pos)
            if at >= 0:
                matched += len(ch)
                pos = at + len(ch)        # 순서 보장
        if matched >= sum(len(c) for c in chunks) * min_ratio:
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
    # ★"남겨주세요"만 보면 안 된다(2026-08-15 라이브 실측). 기존 헌장(_STORY_RULES_CORE,
    #   2026-08-04 사장님 확정)이 요구하는 형태는 "댓글에 'OO' **남겨주시면** [받는 것]
    #   드릴게요"다 — 받는 게 안 보이면 아무도 안 남기기 때문. 그 옳은 규칙을 따른 대본을
    #   내 검사가 FAIL로 잡았다. 어간 '남겨주'로 보고, 받는 것까지 있으면 더 좋다.
    checks.append({"name": "CTA 단어유도", "ok": "남겨주" in norm(full),
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
