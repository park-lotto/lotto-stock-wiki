"""픽업영상 대본 — 씨앗 영상의 구조·훅 문형만 빌리고 내용은 새로 (2026-08-26 사장님).

## 지시
화면 2단계 대본 스타일 첫 칸이 `🤖 AI에게 맡김`인데, 실측하니 이건 "AI가 알아서"가 아니라
**옆 카드 중에서 AI가 대신 골라주는 것**이었다(auto_style=true → 추천 상위 2개 자동 선택).
즉 씨앗(픽업한 영상)의 구조를 전혀 안 쓴다.

사장님: "AI에게 맡김을 빼고 **픽업영상 대본**이라고 하고, 실제 대본 템플릿 구조만 동일하게
끌고 가고, 훅도 터지는 영상이니 변형해서 하고, 스토리는 전혀 다른 내용으로, CTA도 다르게"
→ 확정(2026-08-26): **"여러분 ~ 하지마세요" 구조에 커피 소재 동일하게 / 스토리·등장인물
   모두 다르게 / CTA는 단어도 구조도 달라도 된다.**

## 씨앗은 이미 구조를 갖고 있다 (실측)
produce_works.state_json → s2.seed.structure:
    segments  = 훅 12.5% → 주변인물등장 25% → 해결책제시 25% → 결과/증거 25% → CTA 12.5%
    hook_type = 경고형
    devices   = 권위자인용·손실회피·감정트리거·궁금증유발
그리고 서버 생성 API는 body의 structure를 받는 통로가 이미 있다(app.py:2662).
→ 새로 만드는 게 아니라 **있는 둘을 잇는 것**이다.

## 왜 판정이 필요한가 (실측)
프롬프트로 "원본 훅의 문형을 지켜라"라고 지시만 했을 때 라이브 4안 중 **2안만** 지켰다:
    1안 "여러분 믹스커피 절대 … 마세요"        ✅
    2안 "믹스커피 끊겠다고 선언한 우리 엄마…"   ❌ 문형 버림
    3안 "커피에 이것 한 번 넣으면…"            ❌ 문형 버림
    4안 "여러분 믹스커피 절대 오후 3시쯤 … 마세요" ✅
메모리 `판정축_하나면_교정이_통째로_죽는다`의 교훈 그대로 — **프롬프트만 고치지 말고
판정으로 되돌려야** 한다. 지시는 강제가 아니다.
"""
from shopping_shorts.pickup_script import hook_templates, hook_copied, hook_ok


SEED_HOOK = "여러분 믹스 커피 절대 물에만 타 먹지 마세요"


# ── 씨앗 훅 → 문형 템플릿 ────────────────────────────────────────────────
def test_마세요_문형을_뽑는다():
    tpl = hook_templates(SEED_HOOK)
    assert tpl, "문형을 못 뽑았다"
    assert any("마세요" in t for t in tpl)
    assert any("{" in t for t in tpl), "소재 자리가 슬롯으로 안 비었다"


def test_문형이_없는_훅이면_빈_목록():
    """모든 훅이 틀을 갖진 않는다 — 못 뽑으면 판정도 걸지 않는다(빈손이 오탐보다 낫다)."""
    assert hook_templates("이거 진짜 대박이에요") == []
    assert hook_templates("") == []
    assert hook_templates(None) == []


# ── 문형 판정 ───────────────────────────────────────────────────────────
def test_실측_4안을_정확히_가른다():
    """★라이브에서 실제로 나온 4안. 육안 채점과 판정이 일치해야 한다."""
    tpl = hook_templates(SEED_HOOK)
    ok = ["여러분 믹스커피 절대 그냥 뜨거운 물에만 타 먹지 마세요.",
          "여러분 믹스커피 절대 오후 3시쯤 멍하니 타서 마시지 마세요."]
    bad = ["믹스커피 끊겠다고 선언한 우리 엄마, 대체 무슨 일이 있었던 걸까요?",
           "커피에 이것 한 번 넣으면 인생 맛집보다 백배 더 고소해지거든요."]
    for h in ok:
        assert hook_ok(h, tpl, SEED_HOOK), f"문형을 지킨 훅이 반려됐다: {h}"
    for h in bad:
        assert not hook_ok(h, tpl, SEED_HOOK), f"문형을 버린 훅이 통과했다: {h}"


def test_템플릿이_없으면_무조건_통과():
    """문형을 못 뽑은 씨앗에서는 이 판정이 아무도 막지 않아야 한다."""
    assert hook_ok("아무 훅이나", [], "이거 진짜 대박이에요")


# ── 베끼기 판정 ─────────────────────────────────────────────────────────
# ★메모리 `참고훅주입_베끼기숫자창작`: 원문을 프롬프트에 실으면 통째로 베낀다.
#   문형 판정만 두면 **원본을 그대로 복사한 훅이 만점으로 통과**한다(가장 나쁜 통과).
def test_원본을_그대로_베끼면_막는다():
    tpl = hook_templates(SEED_HOOK)
    assert hook_copied(SEED_HOOK, SEED_HOOK)
    assert not hook_ok(SEED_HOOK, tpl, SEED_HOOK), "원본 복사가 통과했다"


def test_띄어쓰기_구두점만_바꾼_것도_베낀_것이다():
    assert hook_copied("여러분 믹스커피 절대 물에만 타 먹지 마세요!", SEED_HOOK)
    assert hook_copied("여러분믹스커피절대물에만타먹지마세요", SEED_HOOK)


def test_문형만_같고_내용이_다르면_베낀_게_아니다():
    """★이게 우리가 원하는 결과물이다 — 막으면 안 된다."""
    assert not hook_copied("여러분 믹스커피 절대 오후 3시쯤 멍하니 타서 마시지 마세요.", SEED_HOOK)
    assert not hook_copied("여러분 믹스커피 절대 그냥 뜨거운 물에만 타 먹지 마세요.", SEED_HOOK)


# ── CTA 판정 ────────────────────────────────────────────────────────────
def test_CTA_키워드가_원본과_같으면_반려():
    """사장님 지시: CTA는 단어도 구조도 달라야 한다.
    실측 1안이 원본과 같은 '믹스'를 그대로 썼다."""
    from shopping_shorts.pickup_script import cta_keyword, cta_ok
    seed_cta = "댓글에 '믹스' 남겨주시면 건강하게 마시는 법 보내드릴게요"
    assert cta_keyword(seed_cta) == "믹스"
    assert not cta_ok("댓글에 '믹스' 남겨주시면 레시피 드릴게요", seed_cta)
    assert cta_ok("댓글에 '건강믹스' 남겨주시면 핵심 레시피 공유해드릴게요", seed_cta)
    assert cta_ok("댓글에 '고소커피' 남겨주시면 배합 비율 알려드릴게요", seed_cta)


def test_CTA_키워드를_못_찾으면_통과():
    """따옴표 키워드가 없는 CTA도 있다 — 못 찾으면 막지 않는다."""
    from shopping_shorts.pickup_script import cta_keyword, cta_ok
    assert cta_keyword("링크는 프로필에 있어요") is None
    assert cta_ok("아무 CTA나", "링크는 프로필에 있어요")


# ── 초안 걸러내기 (생성 결과에 판정을 실제로 거는 자리) ─────────────────────
def _draft(hook, script="본문입니다"):
    return {"hook": hook, "script": script}


def test_문형을_어긴_초안만_걸러낸다():
    """★실측 4안 그대로. 통과 2안만 남고 어긴 2안은 사유와 함께 걸러진다."""
    from shopping_shorts.pickup_script import filter_drafts
    drafts = [
        _draft("여러분 믹스커피 절대 그냥 뜨거운 물에만 타 먹지 마세요."),
        _draft("믹스커피 끊겠다고 선언한 우리 엄마, 대체 무슨 일이 있었던 걸까요?"),
        _draft("커피에 이것 한 번 넣으면 인생 맛집보다 백배 더 고소해지거든요."),
        _draft("여러분 믹스커피 절대 오후 3시쯤 멍하니 타서 마시지 마세요."),
    ]
    ok, bad = filter_drafts(drafts, SEED_HOOK, "")
    assert len(ok) == 2, f"통과 2안이어야 하는데 {len(ok)}안"
    assert len(bad) == 2
    assert all(b.get("reason") for b in bad), "왜 걸러졌는지 사유가 없다"


def test_CTA가_같으면_그것도_걸러낸다():
    """실측 1안이 원본과 같은 '믹스'를 그대로 썼다 — 문형은 맞아도 반려한다."""
    from shopping_shorts.pickup_script import filter_drafts
    # ⚠️훅은 **확실히 다른 문장**을 써야 CTA 축을 검사할 수 있다. 원본과 비슷한 훅을 넣으면
    #   베끼기 판정에 먼저 걸려 CTA까지 안 간다(처음에 그렇게 짰다가 이 테스트가 잡아냈다).
    seed_cta = "댓글에 '믹스' 남겨주시면 건강하게 마시는 법 보내드릴게요"
    same = _draft("여러분 믹스커피 절대 오후 3시쯤 멍하니 타서 마시지 마세요.",
                  "본문… 댓글에 '믹스' 남겨주시면 레시피 드릴게요")
    diff = _draft("여러분 믹스커피 절대 사무실에서 대충 타 드시지 마세요.",
                  "본문… 댓글에 '건강믹스' 남겨주시면 레시피 드릴게요")
    ok, bad = filter_drafts([same, diff], SEED_HOOK, seed_cta)
    assert len(ok) == 1 and ok[0] is diff
    assert "CTA" in bad[0]["reason"]


def test_화면이_구어체_씨앗에서_훅_한_문장만_뽑는다():
    """★라이브 실측 버그(2026-08-26). 마침표만 보고 자르면 훅이 아니라 대본 대부분이 실린다.

    씨앗 원문 320자에 물음표가 1개뿐이라 `split(/(?<=[.!?])\\s+/)`로는 **240자**가
    훅으로 잡혔다(브라우저에서 seed_hook 길이를 실측해 발견). 한국어 구어체 대본은
    마침표가 거의 없다 — 종결어미까지 경계로 봐야 한다(서버 script_sentences와 같은 규약).
    ⚠️'요' 앞이 명사인 경우(필요·중요·주요)는 자르면 안 된다(같은 날 고친 실사고와 같은 함정).

    화면 코드에 그 규칙이 실제로 박혀 있는지 확인한다(정규식이 옛것으로 되돌아가면 잡힌다).

    ★2026-08-26 갱신: 자르는 규칙을 **공용 함수 s2SeedSentences 한 곳으로** 뽑았다.
      전체 생성과 [바꾸기]가 같은 훅을 봐야 하는데 규칙이 두 벌이면 어긋난다(0순위-B).
    """
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
    src = p.read_text(encoding="utf-8")
    # 규칙은 공용 함수에 있다.
    i = src.index("function s2SeedSentences")
    fn = src[i:i + 900]
    assert "(?<=죠)" in fn, "종결어미 경계가 없다 — 훅이 통짜로 실린다"
    assert "가게고구군까나네데돼든래려서세아어에예와지해" in fn, \
        "'요' 종결어미 화이트리스트가 없다 — 명사 안의 '요'에서 잘린다"
    # 쓰는 쪽 둘 다 그 함수를 부르는가(두 벌로 갈라지면 결과가 어긋난다).
    gen = src[src.index("async function s2Generate"):]
    gen = gen[:gen.index("\n}\n")]
    assert "seed_hook" in gen, "생성 요청에 씨앗 훅을 안 싣는다"
    assert "s2SeedSentences" in gen, "전체 생성이 공용 분리기를 안 쓴다"


def test_씨앗_문형을_못_뽑으면_아무도_안_걸러낸다():
    """판정 기준이 없으면 통과시킨다 — 없는 기준으로 반려하면 멀쩡한 대본이 죽는다."""
    from shopping_shorts.pickup_script import filter_drafts
    drafts = [_draft("아무 훅"), _draft("또 다른 훅")]
    ok, bad = filter_drafts(drafts, "이거 진짜 대박이에요", "")
    assert len(ok) == 2 and not bad
