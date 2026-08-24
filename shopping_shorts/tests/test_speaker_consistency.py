# -*- coding: utf-8 -*-
"""화자(인물) 일관성 — 규칙은 있는데 판정이 없던 것 (2026-08-23).

사장님 제보(스크린샷, 가족갈등 반전형 A안):
    "저 친구네 집 갔다가 충격 받았잖아요."
    "남편 턱이 예전보다 훨씬 깔끔하게 달라진 거예요."   ← 누구 남편? 내 남편으로 읽힌다
    "저도 해보니까 자극 없이 밀리는 거죠."              ← 화자가 면도기를 자기가 쓴다
사장님 말: "말이 되는건지"

## 왜 필요한가 (실측 2026-08-23)

`script_generate.py`의 헌장에는 규칙이 **이미 정확히** 적혀 있다:
    "★★★탄탄한 회수 — 훅에서 등장시킨 그 인물·갈등이 결말에서 반드시 회수돼야 한다.
      중간에 슬그머니 다른 인물로 갈아타 시작한 갈등을 버리지 마라"

그런데 **규칙은 프롬프트에만 있고 지켰는지 보는 판정이 없었다.**
게이트가 내는 검사 12종을 전수로 뽑아보니:
    구간순서·문장틀준수·CTA단어유도·CTA금지·말끝·말밀도·고조심화·소재일치·훅3초·수치근거
`화자|speaker|주어|인칭` grep → **0건**.

라이브 실증(work_id 57043b8fc843 = 스크린샷과 같은 면도기 건):
    금지경고형 = 6개 검사 **전부 통과**. 말이 되는지는 아무도 안 본다.
→ 어겨도 미검출 → 재작성 루프 안 걸림 → 아무도 안 고침
  (메모리 `판정축_하나면_교정이_통째로죽는다`와 같은 모양)

## 왜 규칙(정규식) 판정이 아니라 LLM 판정인가

규칙 기반을 라이브 27개 대본에 실제로 돌려봤더니 **오탐 2건**이 났다
(멀쩡한 다이소 대본을 "3인칭 소유격 누락"으로 잡았다). 이 코드베이스의 기존
원칙은 "오탐이 미탐보다 나쁘다"(script_gate.py 소재일치 주석)이므로 규칙은 뺐다.

## fail-open 이 핵심이다

`_call_json`은 키가 없거나 소진되면 **{}를 돌려준다**(fail-open). 판정을 못 했는데
FAIL로 잡으면 키가 마른 날 **모든 대본이 통째로 막힌다**. 판정 불가 = 통과다.
"""
from shopping_shorts import script_gate


def _beats(pairs):
    return [{"role": r, "text": t} for r, t in pairs]


STYLE = {"beat_roles": ["hook", "situation", "result"], "templates": {},
         "chars_per_30s": 300}

# 사장님 스크린샷 그대로 — 친구네 → 남편(소유격 없음) → 저도
BROKEN = _beats([
    ("hook", "저 친구네 집 갔다가 충격 받았잖아요."),
    ("situation", "남편 턱이 예전보다 훨씬 깔끔하게 달라진 거예요."),
    ("result", "저도 해보니까 자극 없이 밀리는 거 있죠."),
])
OK = _beats([
    ("hook", "저 친구네 집 갔다가 충격 받았잖아요."),
    ("situation", "친구 남편 턱이 예전보다 훨씬 깔끔하게 달라진 거예요."),
    ("result", "그래서 우리 남편한테도 사줬더니 자극 없이 밀린다는 거 있죠."),
])


def _named(checks, name):
    return [c for c in checks if c["name"] == name]


# ─────────────────────────────────────────────────────────────
# 1. 판정을 안 주면 종전과 완전히 같다 (회귀 0)
# ─────────────────────────────────────────────────────────────
def test_판정을_안_주면_화자검사가_아예_없다():
    """기존 호출부는 speaker_judge를 안 넘긴다 → 검사 항목 자체가 안 생긴다."""
    checks, _ = script_gate.check(STYLE, BROKEN)
    assert not _named(checks, "화자 일관성"), \
        "판정을 안 줬는데 검사가 생겼다 — 기존 호출부에 회귀가 난다"


# ─────────────────────────────────────────────────────────────
# 2. 깨진 대본을 잡는다
# ─────────────────────────────────────────────────────────────
def test_화자가_바뀌면_잡는다():
    """사장님이 제보한 그 대본이 FAIL로 걸려야 한다."""
    judge = lambda text: {"ok": False, "why": "친구 남편인데 '남편'이라고만 써서 화자의 남편으로 읽힌다"}
    checks, _ = script_gate.check(STYLE, BROKEN, speaker_judge=judge)
    hit = _named(checks, "화자 일관성")
    assert hit, "화자 검사가 안 생겼다"
    assert hit[0]["ok"] is False
    assert "친구 남편" in hit[0]["detail"], "왜 틀렸는지가 재작성 지시문에 실려야 한다"


def test_멀쩡한_대본은_통과한다():
    judge = lambda text: {"ok": True, "why": ""}
    checks, _ = script_gate.check(STYLE, OK, speaker_judge=judge)
    hit = _named(checks, "화자 일관성")
    assert hit and hit[0]["ok"] is True


# ─────────────────────────────────────────────────────────────
# 3. ★fail-open — 판정을 못 하면 통과시킨다
# ─────────────────────────────────────────────────────────────
def test_판정불가면_통과시킨다_키가_말라도_대본이_막히면_안_된다():
    """_call_json은 키 소진 시 {}를 준다. 그때 FAIL로 잡으면 전 대본이 막힌다."""
    for empty in ({}, None, {"why": "x"}):        # ok 키가 없는 응답들
        checks, _ = script_gate.check(STYLE, BROKEN, speaker_judge=lambda t: empty)
        hit = _named(checks, "화자 일관성")
        assert not hit or hit[0]["ok"] is True, \
            "판정 불가(%r)인데 FAIL로 잡았다 — 키 마른 날 대본이 통째로 막힌다" % (empty,)


def test_판정기가_터져도_대본은_통과한다():
    """판정기 예외가 대본 생성을 죽이면 안 된다(fail-open)."""
    def boom(text):
        raise RuntimeError("gemini down")
    checks, _ = script_gate.check(STYLE, BROKEN, speaker_judge=boom)
    hit = _named(checks, "화자 일관성")
    assert not hit or hit[0]["ok"] is True


# ─────────────────────────────────────────────────────────────
# 4. 재작성 지시문에 실린다 (판정 → 교정으로 이어지는 배선)
# ─────────────────────────────────────────────────────────────
def test_실패하면_재작성_지시문에_실린다():
    judge = lambda text: {"ok": False, "why": "친구 남편인데 '남편'이라고만 썼다"}
    checks, _ = script_gate.check(STYLE, BROKEN, speaker_judge=judge)
    fb = script_gate.gate_feedback(checks)
    assert "화자 일관성" in fb and "친구 남편" in fb, \
        "판정만 하고 교정으로 안 이어지면 아무도 안 고친다"


def test_판정기는_대본_전문을_받는다():
    """칸 하나만 보면 화자가 바뀌었는지 알 수 없다 — 전문을 봐야 한다."""
    seen = {}
    def judge(text):
        seen["text"] = text
        return {"ok": True}
    script_gate.check(STYLE, BROKEN, speaker_judge=judge)
    assert "친구네" in seen["text"] and "저도" in seen["text"], \
        "판정기가 대본 전문을 못 받았다"


# ─────────────────────────────────────────────────────────────
# 5. 재단(trim) 경로에서 판정이 조용히 사라지지 않는다
# ─────────────────────────────────────────────────────────────
def test_재단후_재검사에도_화자판정이_남는다():
    """★길이 초과 대본은 재단 뒤 게이트를 **다시** 돈다(script_generate.py:471).
    그때 speaker_judge를 안 넘기면 앞서 찾은 화자 실패가 checks에서 조용히 사라진다
    — 판정은 했는데 화면·재작성에 안 실리는 미탐이 된다.
    재단은 군더더기 부사만 덜어내므로 화자를 바꿀 수 없다 → 앞의 판정을 **재사용**
    한다(두 번째 유료 호출 금지)."""
    calls = []
    def judge(text):
        calls.append(text)
        return {"ok": False, "why": "친구 남편인데 '남편'이라고만 썼다"}

    checks1, _ = script_gate.check(STYLE, BROKEN, speaker_judge=judge)
    prior = _named(checks1, "화자 일관성")[0]

    # 재단 후 재검사 — 앞 판정을 그대로 물려준다
    checks2, _ = script_gate.check(STYLE, BROKEN,
                                   speaker_judge=script_gate.prior_verdict(checks1))
    hit = _named(checks2, "화자 일관성")
    assert hit and hit[0]["ok"] is False, "재단 뒤 화자 판정이 사라졌다"
    assert hit[0]["detail"] == prior["detail"]
    assert len(calls) == 1, "재단 후 판정기를 또 불렀다 — 유료 호출이 두 배가 된다"


def test_앞_판정이_없으면_물려줄_것도_없다():
    """판정을 아예 안 한 경우(키 소진 등) prior_verdict는 검사를 만들지 않는다."""
    checks1, _ = script_gate.check(STYLE, BROKEN)          # 판정기 없음
    checks2, _ = script_gate.check(STYLE, BROKEN,
                                   speaker_judge=script_gate.prior_verdict(checks1))
    assert not _named(checks2, "화자 일관성")
