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

# ★문장틀 **끝의 종결어미**는 갈아끼워도 같은 틀이다(2026-08-17 실측).
#   틀이 "…먹을 뻔했어요"인데 생성이 "…먹을 뻔했거든요"로 끝나면 서명 어구가 통째로
#   깨져 FAIL이 났다. 그런데 `~거든요`는 **이 스타일의 말버릇 사전에 든 어미**다 —
#   즉 스타일을 잘 지킨 문장이 스타일 검사에서 벌을 받는 구조였다(같은 유형의 사고:
#   메모리 `스타일감점_스타일무지함정`). 틀이 정하는 것은 **뼈대**이지 어미가 아니다.
#   서명 어구의 꼬리에서만 떼어낸다 — 문장 중간의 어미는 건드리지 않는다.
_TAIL_EMI = ("거든요", "더라고요", "더라구요", "었어요", "았어요", "네요", "어요", "아요",
             "예요", "에요", "구요", "고요", "죠", "요", "다")

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


def _strip_tail_emi(chunk):
    """고정 어구의 **꼬리 종결어미**를 떼어낸다. 뗄 게 없으면 그대로.

    ★왜(2026-08-17 실측): 틀 "…먹을 뻔했어요" vs 생성 "…먹을 뻔했거든요"는 같은 틀인데
      서명 어구가 안 맞아 FAIL이었다. 게다가 `~거든요`는 그 스타일의 **말버릇 사전에 든
      어미**라, 스타일을 지킨 문장이 스타일 검사에서 떨어지는 모순이 생긴다.
    ★3자 미만으로 줄어들면 떼지 않는다 — "요"만 남기면 아무 문장에나 걸려 판정이 무의미해진다
      (`_chunks`가 2자 이하를 버리는 것과 같은 이유).
    """
    for e in _TAIL_EMI:
        if chunk.endswith(e) and len(chunk) - len(e) >= 3:
            return chunk[:-len(e)]
    return chunk


def _signature_split_ok(sig, n_text, max_gap=12):
    """서명 어구가 **한 군데 끊겨** 들어간 경우를 살린다(2026-08-17 실측).

    ★왜: 틀 "{가족} 때문에 진짜 충격 받았어요"는 빈칸 뒤가 한 덩어리라 슬롯이 문장 맨
      앞에만 올 수 있다. 그런데 모델은 "…식습관 때문에 **엄마한테** 진짜 충격 받았어요"처럼
      덩어리 **중간에** 말을 끼워 넣는다 — 사람이 읽으면 명백히 그 틀인데 판정만 못 따라가
      정상 문장이 FAIL로 떨어졌다(실측 4개 중 1개). `_SLOT` 주석이 이미 같은 취지로
      "모델이 빈칸에 살을 붙인다 / 틀의 뼈대만 지키면 된다"고 적어둔 것의 연장이다.

    ★느슨해지지 않게 못을 박는다:
      · 끊는 곳은 **한 군데만**. 두 군데 이상 갈라지면 그건 다른 문장이다.
      · 끼워 넣은 말은 max_gap자까지(`_SLOT`의 28자보다 좁게 — 여긴 빈칸이 아니라
        어구 **안쪽**이라 더 엄격해야 한다).
      · 갈라진 두 조각 모두 3자 이상이어야 한다. 짧은 조각은 아무 문장에나 걸린다.
    """
    for i in range(3, len(sig) - 2):
        head, tail = sig[:i], sig[i:]
        if len(tail) < 3:
            break
        at = n_text.find(head)
        if at < 0:
            continue
        nxt = n_text.find(tail, at + len(head))
        if nxt >= 0 and (nxt - (at + len(head))) <= max_gap:
            return True
    return False


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
        # ★어구의 꼬리 종결어미를 떼고 대조한다(2026-08-17) — 틀이 정하는 건 뼈대이지
        #   어미가 아니다. 어미까지 강제하면 스타일의 말버릇(`~거든요`)을 쓴 문장이
        #   그 스타일 검사에서 떨어지는 모순이 난다.
        chunks = [_strip_tail_emi(c) for c in chunks]
        longest = max(chunks, key=len)
        if longest not in n_text and not _signature_split_ok(longest, n_text):
            continue                      # 서명 어구가 없으면 그 틀이 아니다
        matched, pos = 0, 0
        for ch in chunks:
            at = n_text.find(ch, pos)
            if at >= 0:
                matched += len(ch)
                pos = at + len(ch)        # 순서 보장
            elif ch is longest and _signature_split_ok(ch, n_text[pos:]):
                # 서명 어구가 한 군데 끊겨 들어간 경우 — 위에서 이미 인정했으므로
                # 여기서도 세어 준다(안 그러면 ratio가 0이 돼 결국 FAIL로 떨어진다).
                matched += len(ch)
        if matched >= sum(len(c) for c in chunks) * min_ratio:
            return True
    return False


# ★고조 연결어(2026-08-16 추가). 헌장(_STORY_RULES_CORE, 2026-08-04 사장님 확정)이
#   "해결을 보여준 뒤 한 단계 더 올라가는 문장을 반드시 하나 두라"고 요구하는데
#   **검사하는 코드가 없어 밋밋해도 통과**했다(실측: 고조어 0개 대본이 6항목 전부 OK).
#   메종홈디노 히트작 12편 중 6편이 이 구조로 터진다("심지어 100% 방수에…7일이나 유지").
_ESCALATORS = ("심지어", "더대박", "더놀라운", "더좋은건", "미친포인트", "놀랍게도",
               "더군다나", "이럴수가있나싶게", "이걸왜몰랐는지", "진짜미쳐")

# 숫자가 붙는 단위 — 대본에 수치가 나왔는데 재료에 없으면 지어낸 것이다(그라운딩 검사).
_NUM_UNIT = re.compile(
    r"(\d[\d,.]*)\s*(mm|cm|m|kg|g|ml|l|초|분|시간|일|주|개월|년|개|장|자루|명|인|배|퍼센트|%|원)")


def _escalation(full):
    """고조 연결어가 **몇 번** 쓰였나. 헌장은 '한 번만'이다(남발하면 죽는다)."""
    n = norm(full)
    return sum(n.count(w) for w in _ESCALATORS)


def grounding_check(full, facts_text):
    """대본의 수치가 **재료에 실제로 있는 것인가** — 지어낸 수치를 잡는다.

    ★왜 필요한가(2026-08-16 A/B 실측): 재료를 안 준 대본이 "조리 시간이 5분도 안 걸려서"를
      만들어냈는데 원본 4편 어디에도 5분이 없었다. 필통에서도 "펜이 수십 자루"처럼
      근거 없는 수를 붙였다. **수치는 신뢰의 핵심이라 지어내면 안 된다**(헌장도
      "없는 가격·할인·한정수량 지어내기 금지").

    facts_text가 비면(재료를 안 준 경우) **검사하지 않는다** — 재료가 없는데 수치를
    금지하면 정상 대본까지 튕긴다. 재료를 준 경우에만 대조한다.
    반환: (ok, 지어낸것으로 보이는 수치 리스트)
    """
    if not (facts_text or "").strip():
        return True, []
    hay = norm(facts_text)
    bad = []
    for num, unit in _NUM_UNIT.findall(full or ""):
        token = norm(num + unit)
        # 재료에 같은 숫자+단위가 있으면 통과. 숫자만 있어도 인정(단위 표기가 흔들린다)
        if token in hay or norm(num) in hay:
            continue
        bad.append(num + unit)
    return (not bad), bad


def check(style, beats, facts_text=""):
    """(checks, full_text) 반환. checks = [{name, ok, detail}, ...]

    style: {"beat_roles": [...], "templates": {role: [...]}, "chars_per_30s": int}
    beats: [{"role": "...", "text": "..."}, ...]  ← 모델이 돌려준 것
    facts_text: 이 대본에 준 **재료 원문**(product_facts 등). 주면 수치 그라운딩을
        검사한다. 안 주면 그 검사는 건너뛴다 — 기존 호출부는 그대로 = 회귀 0.
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

    # ★고조 심화(2026-08-16) — 헌장은 "한 단계 더 올라가는 문장을 반드시 하나, 한 번만".
    #   0회면 밋밋하고, 2회 이상이면 남발이라 오히려 죽는다(헌장 문구 그대로).
    esc = _escalation(full)
    checks.append({"name": "고조 심화(1회)", "ok": esc == 1,
                   "detail": ("고조 연결어가 없다 — 해결 뒤에 '심지어/더 대박인 건'으로 "
                              "새로운 장점 하나를 더 얹어라" if esc == 0
                              else ("%d번 나왔다 — 한 번만 써라(남발하면 죽는다)" % esc
                                    if esc > 1 else "OK"))})

    # ★수치 그라운딩(2026-08-16) — 재료를 준 경우에만. 지어낸 수치를 잡는다.
    ok_g, bad = grounding_check(full, facts_text)
    if (facts_text or "").strip():
        checks.append({"name": "수치 근거", "ok": ok_g,
                       "detail": ("재료에 없는 수치: " + ", ".join(bad[:5])
                                  + " — 지어내지 말고 확인된 것만 써라") if bad else "OK"})
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
