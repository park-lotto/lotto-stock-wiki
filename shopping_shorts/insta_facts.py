# -*- coding: utf-8 -*-
"""인스타 릴스 전사 → **대본 재료**(insta_facts) 추출 (2026-08-19).

## 왜 sul_facts·product_facts와 따로인가 (0순위-B 위반 아님)

재료의 **출처와 종류가 다르다**:

    product_facts : 쿠팡 상세페이지·리뷰   ("이 제품이 왜 좋은가")
    sul_facts     : 유튜브 썰 자막         ("원래 용도 / 엉뚱한 사용처")
    insta_facts   : 인스타 릴 전사         ("어떻게 쓰나 / 어디에 쓰나 / 뭐가 되나")  ← 이 모듈

★**쿠팡을 안 쓴다.** 사장님 지시(2026-08-19):
> "다이소 이거 사세요 영상은 실제 쿠팡에 매칭되는 게 없는 게 많아. 중국 영상 제품을
>  비슷한 걸로 쿠팡 링크를 올려주는 게 많은 거야. 이건 1:1 매칭 제품이 안 되니 그런 걸로
>  하면 안 되고. 내가 4~5개 영상을 넣으면 거기 대본에서 어떤 특징·장점들이 있구나 해서
>  뽑는 게 첫 번째"

실측이 이를 뒷받침한다(2026-08-19): 다이소 영상 **146편 중 product_facts 보유 0편**.
쿠팡 경로가 통째로 비어 있어서, 재료는 영상 전사에서만 나온다.

## 뽑는 재료 7종 — 다이소 전사 16편 실측에서 반복해 나온 것

| 슬롯 | 실제 문장 (전사 원문) |
|---|---|
| `how_to`     | "이거 **한 스푼 넣으면**" / "**칙칙 뿌리고 딱 5분만** 두라는" |
| `targets`    | "**양말** 누런 때부터 **신발** 찌든 때까지" / "줄눈·물때·유리·변기" |
| `effects`    | "자국없이 싹 사라지는데" / "입주 청소한 것처럼 깨끗해진다" |
| `numbers`    | "**체취의 53%**를 제거" / "**5분**" / "**한 스푼**" |
| `edge`       | "**국내에서 생산된 특수 비누**인데" |
| `pain`       | "아무리 문질러도 안 지워지던" / "매번 새걸로 바꿀 수도 없었는데" |
| `price`      | "**천 원**밖에 안 해서" / "단돈 몇 천 원" |

★`targets`가 여럿인 게 이 축의 핵심이다 — 한 제품이 양말→신발→운동화로 번진다.
  그게 "쓰임새"다. 하나만 뽑으면 대본이 얇아진다.

★`pain`·`price`는 사장님 확인 후 5종에서 늘린 것(2026-08-19). 늘려도 안전한 이유:
  `spine_fill.slots_from_facts`가 **빈 값은 아예 안 담아서**, 재료가 없으면 그 슬롯을
  쓰는 템플릿이 자동으로 안 걸린다. 어색한 빈칸 문장이 나갈 자리가 없다.

## 여러 편을 겹쳐야 채워진다

한 편만 보면 칸이 빈다(유튜브 실측: 2편 각각 돌렸더니 `misuses`가 둘 다 0건).
`spine_fill.merge_sul`이 여러 편의 재료를 한 벌로 합친다 — 이 모듈도 같은 규약
(값은 전부 **리스트**)이라 그 함수를 그대로 쓴다. 상한은 `app._FACTS_MAX_SOURCES`(5편).

⚠️ **같은 소재의 영상만 합쳐라.** 서로 다른 제품을 합치면 슬롯은 차는데 말이 안 되는
   대본이 나온다(spine_fill.merge_sul 주석의 실측 사고).
"""

SLOT_SOURCE = {
    # 인스타 다이소축 템플릿의 빈칸 ↔ 이 모듈이 뽑는 값. **이 표가 정본이다.**
    # 템플릿에 새 빈칸이 생기면 여기와 INSTA_SCHEMA에 같이 추가해야 한다(테스트가 강제).
    "사용법":   "insta_facts.how_to    (어떻게 쓰나 — 동작)",
    "적용대상": "insta_facts.targets   (어디에 쓰나 — 여러 개)",
    "효과":     "insta_facts.effects   (쓰고 나면 뭐가 되나)",
    "수치":     "insta_facts.numbers   (숫자·시간·비율 근거)",
    "차별점":   "insta_facts.edge      (왜 이게 특별한가)",
    "불편함":   "insta_facts.pain      (쓰기 전 어떤 고생을 했나)",
    "가격":     "insta_facts.price     (얼마인가 — 다이소축의 무기)",
}

INSTA_PROMPT = """아래는 한국 인스타 릴스(살림·홈템) 영상의 전사·캡션이다.
이 영상들로 **인스타 릴스 대본**을 쓰려고 한다. 대본의 빈칸을 채울 재료만 뽑아라.

★영상에 실제로 나온 것만 써라. 안 나온 건 **지어내지 마라** — 빈 배열로 두면 된다.
  (지어내면 "5년째 근무하는 이모" 같은 거짓말이 대본에 박힌다. 실측 2026-08-19:
   같은 소재인데 생성할 때마다 "3년째"·"5년째", "10년 동안"·"30년 동안"으로 흔들렸다)
★★값은 **반드시 한국어**로 써라. 전사가 영어·중국어여도 한국어로 옮겨 적어라.
  이 값이 한국어 대본 문장에 그대로 박힌다 — 원문 언어로 두면 대본을 통째로 못 쓴다.
★값은 **문장에 그대로 끼울 수 있는 짧은 서술구**로 써라(명사 하나만 쓰지 마라).
  좋은 예: "물에 한 스푼 풀어 담가두기" / "욕실 줄눈 곰팡이"
  나쁜 예: "한 스푼" / "곰팡이"        ← 이러면 조립 대본이 짧고 말이 안 된다

뽑을 것:
- how_to   : {사용법} — 이 제품을 **어떻게** 쓰는가. 손동작이 보이게.
             (예: 물에 한 스푼 풀어 담가두기 / 뿌리고 5분 뒤 물로 헹구기)
- targets  : {적용대상} — **어디에** 쓰는가. ★2~5개, 많을수록 좋다.
             한 제품이 여러 곳에 번지는 게 이 장르의 핵심이다.
             (예: 누렇게 변한 흰 양말 / 신발 밑창 찌든 때 / 셔츠 목때)
- effects  : {효과} — 쓰고 나면 **뭐가 되는가**. 눈에 보이는 변화로.
             (예: 누런 때가 자국 없이 빠짐 / 입주 청소한 것처럼 깨끗해짐)
- numbers  : {수치} — 숫자·시간·비율 근거. 영상이 말한 것만.
             (예: 체취 53퍼센트 제거 / 5분 방치 / 한 스푼)
- edge     : {차별점} — 왜 이게 특별한가. 성분·제조·인증·구조.
             (예: 국내에서 생산된 특수 비누 / 색을 맞춰 쓰는 메꿈제)
- pain     : {불편함} — 이걸 쓰기 전에 어떤 고생을 했는가. 도입부 공감 재료.
             (예: 아무리 문질러도 안 지워지던 곰팡이 / 매번 새로 사야 했던 양말)
- price    : {가격} — 얼마인가. 영상이 밝힌 것만.
             (예: 천 원 / 오천 원 / 단돈 몇 천 원)

JSON만 출력:
{"how_to": [], "targets": [], "effects": [], "numbers": [], "edge": [], "pain": [], "price": []}

전사·캡션:
"""
# ★.format()을 쓰지 마라 — 위 프롬프트에 {사용법}·{적용대상} 같은 **설명용 중괄호**가 있어서
#   .format()을 부르면 치환 필드로 보고 KeyError로 죽는다(sul_facts가 실제로 겪은 사고).
#   본문은 그냥 이어붙인다.

_FIELDS = ("how_to", "targets", "effects", "numbers", "edge", "pain", "price")

INSTA_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "array", "items": {"type": "string"}} for k in _FIELDS},
    # ★required를 비워둔다 — 일부만 채워져도 나머지는 쓴다(product_facts·sul_facts와 같은 원칙).
    "required": [],
}

_MAX_BODY = 4000


def _body_of(raw):
    """입력에서 대본 재료가 될 텍스트를 모은다. 없으면 ''.

    sul_facts._body_of와 **같은 규약**이다(title·caption·description·captions).
    호출부가 두 모듈에 같은 모양의 dict를 넘길 수 있어야 한다.
    """
    if not raw:
        return ""
    parts = []
    for key in ("title", "caption", "description"):
        v = (raw.get(key) or "").strip()
        if v:
            parts.append(v)
    caps = raw.get("captions") or []
    if isinstance(caps, str):
        caps = [caps]
    parts += [str(c).strip() for c in caps if str(c).strip()]
    return "\n".join(parts)[:_MAX_BODY]


def analyze_insta(raw, *, log=print):
    """인스타 전사·캡션 → 재료 dict. 재료가 없으면 {} (예외 없음).

    실패해도 {}를 돌려준다 — 재료 추출 실패가 대본 생성을 막으면 안 된다.
    """
    body = _body_of(raw)
    if not body:
        return {}
    # ★"왜 비었는지"를 반드시 남긴다(2026-08-19 실사고). 처음엔 아래 세 갈래가 전부
    #   말없이 `return {}`이었다 — 실측에서 5편 전부 0/7이 나왔는데 **로그가 한 줄도 없어**
    #   "재료가 원래 없구나"로 오독할 뻔했다. 진짜 원인은 `pipeline` 모듈이 경로에 없어
    #   import가 죽은 것이었고, except가 그걸 삼켰다.
    #   재료 없음(정상)과 고장(비정상)은 **화면에서 구분돼야 한다**.
    #   관련 메모리: reference_silent_fallback_pipeline_undo
    def _fail(why):
        try:
            log("[insta_facts] 추출 못 함: %s" % why)
        except Exception:      # noqa: BLE001
            pass
        return {}

    try:
        from shopping_shorts import video_analysis
        from google.genai import types
    except Exception as e:                  # noqa: BLE001 — 비전 모듈 없어도 죽지 않는다
        return _fail("모듈 import 실패 — %s: %s" % (type(e).__name__, str(e)[:100]))
    if not getattr(video_analysis, "SHORTS_GEMINI_KEYS", None):
        return _fail("SHORTS_GEMINI_KEYS 비어있음(환경변수 로드했나?)")
    try:
        from shopping_shorts import comment_gen
        key, _idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return _fail("살아있는 키 없음(키 풀 소진)")
        resp = video_analysis._client_for_key(key).models.generate_content(
            model=video_analysis._TRANSLATE_MODEL,
            contents=[INSTA_PROMPT + body],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=INSTA_SCHEMA,
            ),
        )
        import json as _json
        data = _json.loads(resp.text) or {}
    except Exception as e:                  # noqa: BLE001 — 실패해도 대본은 나와야 한다
        try:
            log("[insta_facts] 추출 실패: %s" % str(e)[:120])
        except Exception:
            pass
        return {}

    out = {}
    for k in _FIELDS:
        v = data.get(k) or []
        if isinstance(v, str):
            v = [v]
        v = [str(x).strip() for x in v if str(x).strip()]
        if v:                               # ★빈 값은 담지 않는다 — 담으면 "채워졌다"고 보고
            out[k] = v                      #   빈칸이 그대로 대본에 나간다(spine_fill 규약)
    return out


def insta_prompt_block(facts, max_items=5):
    """재료 → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀 0).

    ★product_facts.prompt_block·sul_facts.sul_prompt_block과 같은 규약이다.
    """
    if not facts:
        return ""

    def _line(key, label):
        v = facts.get(key)
        if not v:
            return ""
        if isinstance(v, str):
            v = [v]
        v = [str(x).strip() for x in v if str(x).strip()][:max_items]
        return ("\n- %s: " % label) + " / ".join(v) if v else ""

    body = "".join([
        _line("pain", "쓰기 전 겪던 불편(도입부 공감에 쓴다)"),
        _line("how_to", "사용법(어떻게 쓰나)"),
        _line("targets", "적용 대상(어디에 쓰나 — 여러 곳에 번지는 게 강점이다)"),
        _line("effects", "효과(쓰고 나면 뭐가 되나)"),
        _line("numbers", "수치 근거(영상이 말한 숫자)"),
        _line("edge", "차별점(왜 특별한가)"),
        _line("price", "가격"),
    ])
    if not body:
        return ""
    return ("\n\n[이 영상들에서 뽑은 재료 — 대본은 **이 안에서만** 말해라. "
            "여기 없는 효능·수치를 지어내지 마라]" + body + "\n")
