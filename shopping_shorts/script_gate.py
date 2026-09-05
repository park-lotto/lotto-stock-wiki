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

# ─────────────────────────────────────────────────────────────────────────
# ★길이의 단위는 **norm(공백·문장부호 제외)** 하나뿐이다 (2026-08-24)
#
# 이 시스템에서 길이를 재는 곳은 전부 `norm()` 기준이다:
#   · est_seconds()  — 화면의 "N초" 표시
#   · check()        — 말 밀도 판정
#   · _speech_cps()  — edit_plan._SYLLABLES_PER_SEC(5.7). 주석이 못 박는다:
#                      "한글 1글자 ≈ 1음절" → 공백은 음절이 아니다 = norm
#
# 그런데 **DB `spine.chars_per_30s`만 raw(공백 포함)**로 쌓였다. 히트작 전사를
# 그대로 세어 넣었기 때문이다. 실측(693편)으로 확인:
#     norm/raw = 0.7395 (중앙값, p10~p90 = 0.715~0.776)
#     히트작 밀도 raw 309 / norm 229 per 30s
#
# ## 이 한 줄이 없으면 무슨 일이 나는가 (전부 실측)
#
# raw 스케일 밀도(270~327)를 norm 천장(≈222/30초)과 비교하니 **항상 천장에 잘렸다**:
#     밀도 240 → 창 155~222자
#     밀도 327 → 창 155~222자      ← 서로 다른 창이 **1종류뿐**
# 승인 스타일 11개가 100% 같은 창을 썼다 = **스타일별 밀도가 통째로 죽어 있었다.**
# 천장 222가 히트작 norm 229와 우연히 가까워 결과가 그럴듯해 안 들켰다.
#
# 재측정으로 교차검증했다(hook_axis로 스파인↔전사를 이어 norm으로 다시 셈):
#     가족갈등 반전형 230 (×0.7395 → 227) · 단정 명령형 236 (242)
#     금지경고형     230 (230)            · 다이소 내부인형 228 (220)
# 두 방법이 2% 안에서 일치한다. 표본이 5편 미만인 스타일도 덮으려고 계수를 쓴다.
#
# ## 왜 DB를 안 고치고 여기서 바꾸나
#
# DB 값을 환산해 넣으면 **저장된 수의 뜻이 조용히 바뀐다** — 다음에 누가 전사에서
# 밀도를 다시 재 넣으면(그게 자연스러운 동작이다) raw가 다시 들어오고, 아무도 모른다.
# 값은 잰 그대로 두고 **쓰는 자리에서 한 번** 환산한다. 환산하는 곳은 여기 하나뿐이다.
_NORM_PER_RAW = 0.7395   # 히트작 전사 693편 실측 중앙값


def norm_chars_per_30s(style):
    """스타일의 히트작 밀도를 **norm 기준**으로 돌려준다 — 길이 판단의 유일한 입구.

    DB는 raw로 쌓여 있고 이 시스템의 나머지는 전부 norm이다. 그 경계가 여기다.
    """
    raw = (style or {}).get("chars_per_30s") or 0
    return int(raw * _NORM_PER_RAW) if raw else DEFAULT_CHARS_PER_30S

# ★말 밀도의 **천장**(2026-08-18 사장님: "계속 4초 이상 나온다 / 30초 이내가 릴스 기본").
#   히트작 실측 밀도(chars_per_30s)를 그대로 목표로 주면 264~377자가 나오는데, 우리
#   라이브 보이스의 실측 속도는 **8.19자/초**(edit_plan.py:4226, 라이브 렌더 20건)라
#   300자 = 약 37초다. 즉 "30초짜리"를 시켜놓고 44초 대본을 받고 있었다.
#   밀도는 스타일의 색이지만 길이는 플랫폼 규격이다 — 규격이 이긴다.
# ★상수를 여기 또 박지 않는다(2026-08-18). 말속도는 edit_plan이 이미 정한다 —
#   _SYLLABLES_PER_SEC(5.7, 성우 14명 실합성 측정) × _speech_speed()(라이브 배속 1.44).
#   여기에 8.19를 따로 적어두면 배속을 튜닝한 날 화면·판정·계획이 서로 다른 초를 말한다
#   (같은 판단이 두 곳에 적히면 반드시 어긋난다 = 0순위-B). 값 하나만 빌려 쓴다.
def _speech_cps():
    from shopping_shorts import edit_plan as _ep
    return _ep._SYLLABLES_PER_SEC * _ep._speech_speed()


def __getattr__(name):          # 모듈 속성 지연 평가 — import 순환을 피한다
    if name == "SPEECH_CHARS_PER_SEC":
        return _speech_cps()
    raise AttributeError(name)


def est_seconds(text):
    """이 문장이 우리 보이스로 몇 초인가(실측 8.19자/초). 화면 표시·판정이 **같은 상수**를
    쓰게 하려고 여기에 둔다(0순위-B) — 화면이 따로 계산하면 언젠가 다른 수를 말한다."""
    n = len(norm(text or ""))
    return round(n / _speech_cps(), 1) if n else 0.0


def density_target(style, seconds=30):
    """이 스타일·이 길이에서 목표 글자수. **한 곳에서만 정한다**(0순위-B) —
    프롬프트(bank_assemble.style_block)와 판정(check)이 서로 다른 수를 쓰면
    "시킨 대로 썼는데 반려"가 난다."""
    sec = max(5, min(int(seconds or 30), 90))
    # ★norm 기준으로 환산해서 쓴다 — 천장(_speech_cps)도 norm이라 단위가 맞아야
    #   비교가 성립한다. 종전엔 raw 예산을 norm 천장과 견줘 **항상 천장에 잘렸고**,
    #   그 탓에 스타일별 밀도가 전부 같은 값이 됐다(위 주석의 실측 참조).
    tgt = int(norm_chars_per_30s(style) * sec / 30)
    return max(1, min(tgt, int(_speech_cps() * sec)))


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
# 유튜브 썰쇼핑에서 나오면 안 되는 존댓말 어미(2026-08-19 실측).
# 1개까지는 봐준다 — 한 문장쯤 섞이는 건 흔하고, 0개를 요구하면 멀쩡한 대본이 반려된다
# (오탐이 미탐보다 나쁘다).
_POLITE_TAILS = ("거든요", "가요", "에요", "예요", "해요", "드릴게요", "세요", "습니다",
                 "합니다", "니다", "더라고요", "죠")

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
        # 재료에 같은 숫자+단위가 있으면 통과. 숫자만 있어도 인정(단위 표기가 흔들린다).
        # ★단, 숫자만 볼 때는 **숫자 경계**를 본다(2026-08-21 실측으로 고침).
        #   종전엔 부분 문자열이라 뜻이 전혀 달라도 통과했다:
        #     대본 "체취의 53%"  + 재료 "가격 5300원"   → 5300 안의 53이 걸려 통과
        #     대본 "20년 경력"   + 재료 "조회수 20만회"  → 통과
        #   실측: 라이브 대본 754편 중 44편(5%)에 지어낸 연차가 있었고
        #   값이 20년·30년으로 흔들렸다(daiso_spine.py가 경고한 그 함정).
        #   ⚠️완화 자체를 없애지는 않는다 — 단위 표기가 실제로 흔들리기 때문이다
        #     ("5분"/"5 분"/"오분"). 경계만 본다.
        if token in hay or re.search(r"(?<!\d)%s(?!\d)" % re.escape(norm(num)), hay):
            continue
        bad.append(num + unit)
    return (not bad), bad


#: 제품명에서 검사에 쓸 토큰을 뽑는다. 브랜드·수식어가 섞여 있어도 하나만 맞으면 된다.
#  ★한 글자는 버린다 — '펜' 같은 조각은 아무 대본에나 걸려 검사가 무력해진다.
#  ★'다이소'처럼 파는 곳 이름도 남긴다: 그 단어라도 나오면 우리 소재 얘기가 맞다.
def _product_tokens(product):
    raw = (product or "").strip()
    if not raw:
        return []
    out = []
    for t in re.split(r"[\s/·,()\[\]&]+", raw):
        t = t.strip()
        if len(t) >= 2:
            out.append(norm(t))
    return [t for t in out if t]


# ── 훅 3초 게이트(2026-08-19) ─────────────────────────────────────────────
# 왜 필요한가: 유튜브 썰쇼핑은 **완시청 장사**다(실측 댓글률 0.005% vs 인스타 2.35%,
# 구독 1.46만 채널이 1,047만 조회). 그런데 게이트는 구간순서·문장틀·밀도만 봤다 —
# 3초 안에 못 잡으면 나머지가 아무리 좋아도 안 본다.
#
# ★감으로 만들지 않았다. 라이브 스파인 55·56의 **실제 도입 문장**에서 규칙을 뽑았다:
#     은폐형 bait : "최근 딱 봤을 때는 도저히 용도를 알기 힘든 이 제품이"
#     오용형 origin: "이게 원래는 {본래용도} 개발된 제품이었음"
#   둘 다 (1) 인사·예고가 없고 (2) 바로 상황을 던진다. 은폐형은 제품 정체를
#   `reveal` 구간(4번째)까지 **숨긴다** — 실측 대본이 5~7초에 공개했다.
#
# ⚠️ 오탐이 미탐보다 나쁘다(CTA 사고와 같은 유형: 옳게 쓴 대본을 FAIL로 잡으면
#   재작성 루프가 스타일을 망가뜨린다). 그래서 **스타일이 선언할 때만** 돈다.
_INTRO_BAD = ("안녕하세요", "안녕하십니까", "반갑습니다", "오늘은", "오늘 소개",
              "소개해드릴", "소개해드리", "소개할게", "알아보겠습니다", "준비했습니다",
              "시작하겠습니다", "구독과 좋아요", "본격적으로")


def hook_window(style, full, seconds=3):
    """대본의 앞 `seconds`초에 해당하는 글자. 말속도는 **빌려 쓴다**(0순위-B) —
    여기에 상수를 또 박으면 화면·편성과 다른 수를 말하게 된다."""
    n = max(1, int(_speech_cps() * max(1, seconds)))
    return norm(full or "")[:n]


def hook_checks(style, full, product=""):
    """훅 3초 검사 항목들. 스타일이 `hook_3s`를 선언하지 않으면 **빈 목록**
    (검사 항목 자체를 안 만든다 = 재작성 지시문도 안 섞인다 = 회귀 0)."""
    if not (style or {}).get("hook_3s"):
        return []
    win = hook_window(style, full)
    out = []
    if not win.strip():
        return [{"name": "훅 3초", "ok": False,
                 "detail": "앞 3초가 비었다 — 첫 문장부터 바로 들어가라"}]

    bad = [w for w in _INTRO_BAD if w in win]
    out.append({"name": "훅 3초 서론금지", "ok": not bad,
                "detail": ("앞 3초에 서론이 있다(%s) — 인사·예고를 빼고 바로 "
                           "상황을 던져라. 완시청 장사라 3초를 서론에 쓰면 끝이다."
                           % ", ".join(bad)) if bad else "OK(%s…)" % win[:20]})

    # 은폐형 전용 — 정체를 3초 안에 밝히면 훅이 죽는다(reveal은 4번째 구간이다).
    if (style or {}).get("hook_conceal"):
        toks = _product_tokens(product)
        leaked = [t for t in toks if t in win]
        out.append({"name": "훅 3초 정체은폐", "ok": not leaked,
                    "detail": ("앞 3초에 제품 정체(%s)가 나왔다 — 은폐형은 정체를 "
                               "`reveal` 구간까지 숨긴다(실측 5~7초 공개). "
                               "앞에서는 '이 제품이'처럼 가려라." % ", ".join(leaked[:2]))
                              if leaked else "OK"})
    return out


def prior_verdict(checks):
    """앞서 나온 '화자 일관성' 판정을 **그대로 재사용**하는 판정기를 만든다.

    ★왜 필요한가: 길이가 넘친 대본은 재단(_trim_to_budget) 뒤 게이트를 다시 돈다.
      그때 판정기를 안 넘기면 앞서 찾은 화자 실패가 checks에서 **조용히 사라진다**
      (판정은 했는데 화면·재작성 지시문에 안 실리는 미탐).
      그렇다고 판정기를 다시 넘기면 **유료 LLM 호출이 두 배**가 된다.
      재단은 군더더기 부사만 덜어내므로 화자를 바꿀 수 없다 → 앞 판정을 물려준다.

    앞에 판정이 없으면(키 소진 등) None을 돌려주는 판정기 → 검사 항목이 안 생긴다.
    """
    hit = [c for c in (checks or []) if c.get("name") == "화자 일관성"]
    if not hit:
        return lambda _text: {}
    return lambda _text: {"ok": hit[0]["ok"], "why": hit[0].get("detail") or ""}


def check(style, beats, facts_text="", product="", seconds=30, assembled=False,
          speaker_judge=None, scene_ids=None, grounded=False, is_recipe=False):
    """(checks, full_text) 반환. checks = [{name, ok, detail}, ...]

    style: {"beat_roles": [...], "templates": {role: [...]}, "chars_per_30s": int}
    beats: [{"role": "...", "text": "..."}, ...]  ← 모델이 돌려준 것
    facts_text: 이 대본에 준 **재료 원문**(product_facts 등). 주면 수치 그라운딩을
        검사한다. 안 주면 그 검사는 건너뛴다 — 기존 호출부는 그대로 = 회귀 0.
    assembled: 이 대본이 **조립**(spine_fill)으로 만들어졌나. 조립만 '문장틀 준수'를
        묻는다 — 아래 그 검사 주석 참조. 기본 False = 생성기.
    speaker_judge: 대본 전문을 받아 {"ok": bool, "why": str}를 돌려주는 판정기.
        주면 '화자 일관성'을 검사한다. 안 주면 그 검사는 **항목 자체를 안 만든다**
        (기존 호출부 그대로 = 회귀 0). 아래 그 검사 주석 참조.
    """
    beats = beats or []
    want = list(style.get("beat_roles") or [])
    got = [b.get("role", "") for b in beats]
    # ★나열형(is_list)은 item이 **편수만큼 반복**된다(item1·item2·…) — 서사형처럼
    #   순서를 1:1로 맞추면 항상 실패한다(2026-08-21 실측).
    #   item 반복을 하나로 접어서 비교한다. 나머지 칸의 순서는 그대로 본다.
    if style.get("is_list"):
        folded, prev = [], ""
        for r in got:
            base = "item" if r.startswith("item") else r
            if base != prev:
                folded.append(base)
            prev = base
        got_cmp = folded
    else:
        got_cmp = got
    checks = [{"name": "구간 순서", "ok": got_cmp == want,
               "detail": "기대 %s / 실제 %s" % (want, got_cmp)}]

    # ★'문장틀 준수'는 **조립 대본에만** 묻는다(2026-08-22 실측).
    #   이 검사는 대본을 템플릿 원문과 **글자 단위로** 대조한다(template_matches).
    #   조립(spine_fill)은 틀을 글자 그대로 쓰므로 옳다. 그러나 생성기는 틀을
    #   **참고만** 하고 문장을 새로 쓴다 — assemble_off=1(사장님 지시)로 지금은
    #   전부 생성기다. 그대로 두면 **잘 쓸수록 떨어진다**.
    #   라이브 실측(스콘 소재 실제 대본 6편): 비문 0건인데 6편 전부 게이트 실패
    #   (cta 83% · escalation 67% · hook 67%가 '문장틀 준수'로 떨어졌다).
    #   피해가 두 겹이다 — ①무의미한 ⚠️가 화면을 덮어 진짜 문제를 가린다
    #   ②재작성 루프가 "틀에 맞춰라"로 돌아 생성기의 장점을 도로 깎는다.
    #   ⚠️없애지 않는다. 조립은 종전대로 검사한다(회귀 0).
    templates = (style.get("templates") or {}) if assembled else {}
    for role in want:
        tmpl = templates.get(role) or []
        if not tmpl:
            continue
        # ★나열형은 item이 item1·item2…로 나뉜다 — 접두어로 찾아야 '해당 구간 없음'이
        #   안 뜬다(2026-08-21). 서사형은 종전대로 정확히 일치하는 것만 본다.
        if style.get("is_list") and role == "item":
            hit = [b for b in beats if (b.get("role") or "").startswith("item")]
        else:
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
    # ★CTA가 서명인 스타일(인스타 채이홈)에만 해당한다. 유튜브 썰쇼핑은 정반대다 —
    #   이븐쇼핑·살림킹왕짱 실측 4편 전부 CTA가 없고(댓글률 0.005% vs 인스타 2.35%)
    #   구독 1.46만 채널이 1,047만 조회를 낸다. 완시청이 전부라 댓글을 안 부른다.
    #   그대로 두면 유튜브 스파인은 아무리 잘 써도 이 한 줄 때문에 영구 FAIL이고,
    #   재작성 루프가 없는 CTA를 억지로 붙이라 시켜 스타일을 망가뜨린다.
    #   → 스타일이 no_cta를 선언하면 **검사 항목 자체를 만들지 않는다**(ok=True로
    #     통과시키면 재작성 지시문에 CTA 얘기가 섞인다). 기본값은 기존 동작 = 회귀 0.
    if not style.get("no_cta"):
        # ★어간을 하나만 보면 **스타일 자신의 템플릿을 자기 게이트가 떨어뜨린다**
        #   (2026-09-05 실측: spine 57 '다이소 내부인형'의 cta 템플릿 6개 중 2개가
        #    "댓글 **달아주시면**"·"**물어봐 주시면**"이라, 모델이 그걸 고르면 무조건 FAIL.
        #    취지인 "받는 게 보이는가"는 완벽히 만족하는 문장인데도 재작성 3회를 돌았다).
        #   요구하는 형태는 여전히 위 헌장 그대로다 — 시청자에게 **행동을 청하는 말**.
        _CTA_ASKS = ("남겨주", "달아주", "물어봐", "물어보", "말씀해주", "적어주")
        checks.append({"name": "CTA 단어유도",
                       "ok": any(w in norm(full) for w in _CTA_ASKS),
                       "detail": full[-40:]})
    else:
        # ★반대 방향 검사가 통째로 없었다(2026-08-19 라이브 실측). no_cta는 'CTA 검사를
        #   건너뛴다'로만 구현돼 있어서, **CTA가 붙어도 아무도 안 잡았다** —
        #   사장님 화면에 "댓글에 무소음 남겨주세요"가 그대로 나왔다(spine 55 은폐형).
        #   유튜브 썰쇼핑은 완시청 장사라 CTA가 없는 게 정답이다(실측 히트작 4편 전부 무CTA).
        _cta_hit = [w for w in ("남겨주", "댓글", "구독", "링크", "좋아요") if w in norm(full)]
        checks.append({"name": "CTA 금지(유튜브 썰)", "ok": not _cta_hit,
                       "detail": ("CTA가 들어갔다(%s) — 이 스타일은 CTA를 쓰지 않는다. "
                                  "완시청으로 먹는 장르라 댓글을 부르면 흐름이 끊긴다."
                                  % ", ".join(_cta_hit)) if _cta_hit else "OK"})

    # ★말끝 검사(2026-08-19 사장님 제보 "존댓말이 갑자기"). 유튜브 썰은 '~었음 / ~다는 거'
    #   반말체인데 생성기가 '~가요 / ~거든요 / ~드릴게요' 존댓말로 썼다(실측 spine 55).
    #   인스타 스타일은 존댓말이 정답이므로 **유튜브 썰(hook_3s)에만** 건다.
    if style.get("hook_3s"):
        _po = [w for w in _POLITE_TAILS if w in norm(full)]
        checks.append({"name": "말끝(반말체)", "ok": len(_po) <= 1,
                       "detail": ("존댓말이 섞였다(%s) — 이 장르는 '~었음 / ~다는 거 / "
                                  "~하더라고요' 반말체다(실측 히트작 전부)."
                                  % ", ".join(_po[:4])) if len(_po) > 1 else "OK"})

    tgt = density_target(style, seconds)
    # ★위 천장(hi)은 말속도 환산 길이를 절대 못 넘는다 — 안 그러면 245자로 시켜놓고
    #   343자(=42초)까지 통과시켜 "30초짜리"가 다시 40초가 된다(2026-08-18).
    _cap = int(_speech_cps() * max(5, min(int(seconds or 30), 90)))
    lo, hi = int(tgt * DENSITY_LO), min(int(tgt * DENSITY_HI), _cap)
    n = len(norm(full))
    # ★방향을 말해준다(2026-08-18 사장님 "40초 대본이 나오는데 고친 거 아니었나").
    #   예전 detail은 "300자 / 히트작 245자"라 넘쳤는지 모자란지가 안 드러났고, 재작성
    #   지시문도 "모자라면 채워라"만 있어 모델이 계속 길게 썼다 — 판정은 맞는데 고칠
    #   방향을 안 알려주니 재작성이 소용없었다.
    if n > hi:
        _d = "%d자 — %d자를 **넘겼다**. %d자 이하로 줄여라(영상 길이 규격)." % (n, hi, hi)
    elif n < lo:
        _d = "%d자 — %d자에 모자란다. %d자 이상으로 채워라." % (n, lo, lo)
    else:
        _d = "%d자 / 이 스타일 히트작 %d자" % (n, tgt)
    checks.append({"name": "말 밀도(%d~%d자)" % (lo, hi), "ok": lo <= n <= hi,
                   "detail": _d, "over": n > hi})

    # ★고조 심화(2026-08-16) — 헌장은 "한 단계 더 올라가는 문장을 반드시 하나, 한 번만".
    #   0회면 밋밋하고, 2회 이상이면 남발이라 오히려 죽는다(헌장 문구 그대로).
    esc = _escalation(full)
    # ★나열형은 고조를 **안 쓴다** — 실측 9편 전부 고조어 0회(2026-08-21).
    #   서사가 없어 "한 단계 더 올라가는 문장"을 놓을 자리가 없다.
    #   여기서 면제하지 않으면 나열형은 영영 통과 못 한다.
    if style.get("is_list"):
        esc = 1 if esc == 0 else esc      # 0회는 정상 / 남발(2회+)은 그대로 잡는다
    checks.append({"name": "고조 심화(1회)", "ok": esc == 1,
                   "detail": ("고조 연결어가 없다 — 해결 뒤에 '심지어/더 대박인 건'으로 "
                              "새로운 장점 하나를 더 얹어라" if esc == 0
                              else ("%d번 나왔다 — 한 번만 써라(남발하면 죽는다)" % esc
                                    if esc > 1 else "OK"))})

    # ★소재 일치(2026-08-18) — **출구 검사**. 이번 사고("재료는 네일펜인데 대본은 주방
    #   기름 가림막")를 막으려고 지금까지 한 것은 전부 프롬프트에 경고를 더 넣는 일이었다.
    #   그건 통로를 하나씩 막는 두더지잡기라, 새 통로가 생기면 또 샌다.
    #   여기서 잡으면 **어디서 새든 결과에서 걸린다** — 출구는 하나뿐이다.
    #   판정은 느슨하게: 제품명 토큰이 **하나라도** 나오면 통과. 대본이 제품을 '이거'로만
    #   부르는 건 정상이므로 전체 일치를 요구하면 멀쩡한 대본을 반려한다(오탐이 더 나쁘다).
    #   product를 안 주면 검사 자체를 건너뛴다 = 회귀 0.
    if _product_tokens(product):
        toks = _product_tokens(product)
        nf = norm(full)
        # 토큰 그대로 못 찾으면 **앞 2글자**로도 본다 — '네일펜'을 대본이 '네일'로만
        # 부르는 건 정상이다. 오탐(멀쩡한 대본 반려)이 미탐보다 나쁘므로 느슨하게 잡는다.
        hit = [t for t in toks if t in nf or (len(t) >= 3 and t[:2] in nf)]
        checks.append({"name": "소재 일치", "ok": bool(hit),
                       "detail": ("OK(%s)" % ", ".join(hit[:3])) if hit else
                                 ("대본에 「%s」 얘기가 한 번도 안 나온다 — 다른 소재로 "
                                  "샜을 가능성이 높다(재료 밖 소재 금지)" % product)})

    # ★훅 3초(2026-08-19) — 스타일이 선언할 때만. 위 함수 하나가 판단을 전담한다.
    checks += hook_checks(style, full, product)

    # ★화자 일관성(2026-08-23 사장님 "말이되는건지") — 판정기를 준 경우에만.
    #   헌장(_STORY_RULES_CORE)에 "훅에서 등장시킨 그 인물이 결말에서 회수돼야 하고
    #   중간에 슬그머니 다른 인물로 갈아타지 마라"가 **이미 적혀 있었다**. 그런데
    #   규칙은 프롬프트에만 있고 **지켰는지 보는 판정이 없었다** — 어겨도 미검출이라
    #   재작성 루프가 안 걸리고 아무도 안 고쳤다.
    #   실측 제보: "저 친구네 집 갔다가" → "남편 턱이 달라진 거예요"(누구 남편?) →
    #   "저도 해보니까"(화자가 자기가 씀). 라이브 게이트는 이걸 **전부 통과**시켰다.
    #   ★규칙(정규식)으로 안 잡는 이유: 라이브 27개에 돌려보니 멀쩡한 대본 2건을
    #     잡았다(오탐). 이 파일의 기존 원칙대로 오탐이 미탐보다 나쁘다 → LLM 판정.
    #   ★fail-open: 판정을 못 하면(_call_json이 키 소진 시 {} 반환·예외) **통과**시킨다.
    #     여기서 막으면 키가 마른 날 대본이 통째로 안 나온다.
    if speaker_judge is not None:
        try:
            _v = speaker_judge(full) or {}
        except Exception:      # noqa: BLE001 — 판정 실패가 대본 생성을 죽이면 안 된다
            _v = {}
        if isinstance(_v, dict) and isinstance(_v.get("ok"), bool):
            checks.append({"name": "화자 일관성", "ok": _v["ok"],
                           "detail": (_v.get("why") or "").strip()[:200] or
                                     ("말하는 사람이 도중에 바뀐다 — 훅에서 등장시킨 그 인물로 "
                                      "끝까지 꿰어라(3인칭은 '친구 남편'처럼 누구 것인지 밝혀라)")
                                     if not _v["ok"] else "OK"})

    # ★수치 그라운딩(2026-08-16) — 재료를 준 경우에만. 지어낸 수치를 잡는다.
    ok_g, bad = grounding_check(full, facts_text)
    if (facts_text or "").strip():
        checks.append({"name": "수치 근거", "ok": ok_g,
                       "detail": ("재료에 없는 수치: " + ", ".join(bad[:5])
                                  + " — 지어내지 말고 확인된 것만 써라") if bad else "OK"})

    # ★장면 근거(2026-09-04, 2단계 '본 것만 쓰기'): grounded 모드에서만 항목을 만든다(종전 호출 = 회귀 0).
    #   규칙은 프롬프트(_GROUNDED_RULE)에 적혀 있고 **여기가 그 판정**이다 — 지시와 판정은 짝
    #   (메모리 '규칙은 있는데 판정이 없다': 지시만 있으면 어겨도 미검출 → 재작성이 안 걸린다).
    if grounded and scene_ids is not None:
        ok_s, det = scene_grounding_check(beats, scene_ids, is_recipe=is_recipe)
        checks.append({"name": "장면 근거", "ok": ok_s, "detail": det})
    return checks, full


def parse_src_segs(raw):
    """src_seg 문자열 → 번호 목록(순수 함수). 모델은 한 줄에 여러 장면을 적는다(실측 "s3-10,s3-11,s3-12").
    쉼표·공백·가운뎃점·슬래시로 가른다. 첫 번째가 대표(3단계 primary)."""
    import re
    s = str(raw or "").strip()
    if not s:
        return []
    out = []
    for tok in re.split(r"[,\s·/;]+", s):
        tok = tok.strip().strip("[]")
        if tok and tok not in out:
            out.append(tok)
    return out


def scene_grounding_check(beats, scene_ids, is_recipe=False, min_ratio=0.34):
    """(ok, detail) — 줄마다 src_seg가 실제 장면 목록에 있는지, 장면이 필요한 줄이 비지 않았는지.

    · 지어낸 번호(목록에 없음) → 실패(레시피도)
    · needs_scene=true인데 src_seg 없음 → 실패(레시피도)
    · 제품형: 장면 붙은 줄이 전체의 min_ratio 미만이면 실패(모델이 전부 needs_scene=false로 도망치는 것 방지)
      ★min_ratio=0.34(2026-09-04 실측): 5칸 구조(첫말·문제·시연·결과·약속)는 첫말·문제·약속이 정당하게 장면 없음 →
        절반(0.5)이면 시연·결과가 다 맞아도 2/5로 반려된다. 3분의 1이면 "시연·결과는 반드시"가 남는다.
    detail은 재작성 지시문에 그대로 들어간다 — 어느 줄이 왜 걸렸는지."""
    ids = {str(x) for x in (scene_ids or set())}
    beats = beats or []
    invented, missing, with_scene = [], [], 0
    for i, b in enumerate(beats, 1):
        sids = parse_src_segs(b.get("src_seg"))
        need = bool(b.get("needs_scene"))
        text = (b.get("text") or "").strip()[:30]
        bad_ids = [x for x in sids if x not in ids]
        if bad_ids:
            invented.append(f"{i}번 '{text}' src_seg={','.join(bad_ids)}(목록에 없음)")
        elif sids:
            with_scene += 1
        elif need:
            missing.append(f"{i}번 '{text}'")
    problems = []
    if invented:
        problems.append("지어낸 장면 번호: " + "; ".join(invented[:4]) + " — 장면 목록의 번호만 써라")
    if missing:
        problems.append("장면이 필요한 줄인데 src_seg가 비었다: " + "; ".join(missing[:4])
                        + " — 그 내용이 보이는 장면 번호를 적거나, 장면에 없는 장점이면 그 줄을 빼라")
    need = max(1, int(len(beats) * min_ratio + 0.999)) if beats else 0
    if not is_recipe and beats and with_scene < need:
        # 문구의 기준은 상수에서 만든다(리뷰 L1: '절반'이라 적혀 있는데 실제는 1/3이었다)
        problems.append("장면이 붙은 줄이 %d/%d — 최소 %d줄(전체의 %d%%)은 장면 목록에서 온 줄이어야 한다(제품형)"
                        % (with_scene, len(beats), need, int(min_ratio * 100)))
    return (not problems), ("; ".join(problems) if problems else "OK(%d/%d줄에 장면)" % (with_scene, len(beats)))


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
            + ("\n분량이 넘쳤다 — **문장을 덜어내거나 짧게 줄여라**. 칸 개수·순서는 "
               "그대로 두고 설명을 압축해라. 길이는 영상 규격이라 못 넘긴다."
               if any(c.get("over") for c in bad) else
               "\n분량이 모자라면 문장을 더 쪼개고 상황 묘사를 늘려 채워라. "
               "구조·문장틀은 그대로 두고 살만 붙여라."))
