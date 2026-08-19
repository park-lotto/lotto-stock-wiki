# -*- coding: utf-8 -*-
"""썰쇼핑 대본 재료 추출 (2026-08-19).

사장님 지시: "대본 템플릿은 많이 만들어 놓았으니 **영상들에서 뭘 추출해야 대본을
완성할 수 있는지**만 알면 되는 거니까 그걸 뽑아"

## 무엇을 푸는가

유튜브 썰쇼핑 스파인 2종(은폐형·오용형)이 요구하는 빈칸은 8종인데, 기존
`product_facts`가 뽑는 것으로는 **4종만** 채워진다. 나머지 4종은 아무도 안 뽑는다:

    {나라}    ← origin      (product_facts)     {본래용도}  ← 없음  ★
    {제품}    ← title       (product_facts)     {속성}      ← 없음  ★
    {효능}    ← why         (product_facts)     {용도}      ← 없음  ★
    {효능2}   ← why         (product_facts)     {제품군}    ← 없음  ★

빈칸이 안 채워지면 **모델이 지어낸다** — 그게 "AI 티 나는 대본"의 정체다.
이 모듈은 그 4종을 실제 영상(자막·캡션)에서 뽑는다.

## 왜 product_facts로는 안 되나

`product_facts`는 **쿠팡 상세페이지·리뷰**를 읽는다(specs·why·origin / pain·trigger·satisfy).
그건 "이 제품이 왜 좋은가"를 아는 데 맞다. 그런데 오용형 서사가 요구하는 건 다르다:

    "이게 원래는 {본래용도}로 개발된 제품이었음"          ← 쿠팡은 '원래 용도'를 안 판다
    "사람들은 {속성}을 눈치채고 엉뚱한 용도로 쓰기 시작"   ← 리뷰가 아니라 **영상**에 있다
    "근데 미친 사용법은 따로 있었는데 {용도}"             ← 이것도 영상에 있다

즉 재료의 **출처가 다르다**(상품페이지 vs 영상). 그래서 별도 모듈이다.
0순위-B에 어긋나지 않는다 — 같은 판단을 두 번 하는 게 아니라 다른 것을 뽑는다.

## 쓰는 법

    facts = analyze_sul({"captions": [...자막/캡션 문자열...], "title": "..."})
    block = sul_prompt_block(facts)        # 대본 프롬프트에 붙인다(비면 "")

재료가 없으면 조용히 {} / "" 를 돌려준다 — 예외로 대본 생성을 죽이지 않는다.
"""

# ── 템플릿 빈칸 → 무엇으로 채우나 ────────────────────────────────────────
# ★이 표가 seed_style_youtube.py의 {빈칸}과 **짝**이다.
#   템플릿에 새 빈칸이 생기면 여기도 늘어야 한다 — test_sul_facts.py가 강제한다.
#   (안 그러면 그 빈칸은 모델이 지어낸다 = 대본이 거짓말을 한다)
SLOT_SOURCE = {
    # 기존 product_facts가 이미 뽑는 것
    "제품":   "product_facts.title      (상품명)",
    "효능":   "product_facts.why[0]     (왜 좋은가)",
    "효능2":  "product_facts.why[1]     (두 번째 셀링포인트 — 2차 반전용)",
    "나라":   "product_facts.origin     (브랜드·기술·인증에서 나라)",
    # ★이 모듈이 새로 뽑는 것 (영상에서)
    "본래용도": "sul_facts.original_use   (원래 무엇을 하라고 만든 물건인가)",
    "속성":   "sul_facts.hidden_property(사람들이 눈치챈 숨은 성질)",
    "용도":   "sul_facts.misuses        (엉뚱하게 쓰는 실제 사례들)",
    "제품군": "sul_facts.category_word  (제품을 안 밝힐 때 쓸 상위 분류어)",
}

SUL_PROMPT = """아래는 한국 쇼핑 쇼츠 영상의 자막·설명이다. 이 영상으로 **썰쇼핑 대본**을
쓰려고 한다. 대본의 빈칸을 채울 재료만 뽑아라.

★영상에 실제로 나온 것만 써라. 안 나온 건 **지어내지 마라** — 빈 배열로 두면 된다.
  (지어내면 "천재가 만든 발명품" 같은 거짓말이 대본에 박힌다)
★★값은 **반드시 한국어**로 써라. 자막이 영어·중국어여도 한국어로 옮겨 적어라.
  이 값이 한국어 대본 문장에 그대로 박힌다 — 원문 언어로 두면 대본이 통째로 못 쓰게 된다.
  (실측 2026-08-19: 영어 자막에서 "mobile device support"·"holder"가 그대로 나와
   "이게 원래는 mobile device support로 개발된 holder였음"이 조립됐다.
   같은 지시가 없던 중국어는 운 좋게 한국어로 나왔지만 운에 맡길 일이 아니다)

뽑을 것:
- original_use  : {본래용도} — 이 물건이 **원래** 무엇을 하라고 만들어진 것인가.
                  (예: 의류 태그 부착용, 커튼 걸이용). 영상이 안 밝히면 빈 배열.
                  ★제품 자체나 그 제품군 이름을 여기 쓰지 마라. "마카의 원래 용도=필기구"
                    같은 동어반복이면 뒤집을 게 없어 대본이 통째로 공허해진다(실측
                    2026-08-19: "이게 원래는 필기구로 개발된 마카였음"). 그런 경우 빈 배열.
- hidden_property: {속성} — 사람들이 눈치챈 **숨은 성질**. 왜 다른 용도로 쓸 수 있었나.
                  (예: 옷감이 손상되지 않는다, 봉 없이 고리만으로 걸린다)
- misuses       : {용도} — 원래 용도가 **아닌** 실제 사용처들. 2~4개.
                  ★★"그 물건을 그 물건답게 쓰는 것"은 여기 넣지 마라. 이 칸은
                    **"어? 그걸 그렇게 쓴다고?" 소리가 나오는 것**만 담는다.
                    나쁜 예(실측 2026-08-19, 마커펜): "돌에 그림 그리기"·"자녀 필통에
                    선물로 넣어주기" — 둘 다 그냥 펜을 펜으로 쓰는 것이라 반전이 없다.
                    좋은 예(살림킹왕짱 실측): 텐트용 선풍기를 **주방 벽에 달아** 요리 /
                    가죽 펀칭기로 **지퍼백에 구멍 뚫어** 디스펜서 만들기.
                  ★순서가 중요하다 — **흔한 것부터, 의외인 것을 뒤로** 정렬해라.
                    대본이 "초보들은 기껏해야 {첫째}인데 고수들은 {둘째}까지" 하고
                    마지막을 반전으로 쓴다. 비슷한 것 둘을 앞뒤로 놓으면 대비가 죽는다
                    (실측 2026-08-19: "땀 식히기"와 "환기하기"가 나란히 와서 같은 말이 됐다).
                  ★이런 게 없는 영상이면 **빈 배열로 두라**. 억지로 채우면 대본이
                    "미친 사용법"이라 해놓고 하나도 안 놀라운 말을 하게 된다.
                  ★"어디에 어떻게 쓰는지"가 드러나게 **짧은 서술구**로 써라(명사 하나 금지).
                    좋은 예: 주방 벽에 달아서 시원하게 요리하기 / 물티슈 걸어두고 뽑아쓰기
                    나쁜 예: 환기 / 주방 벽 설치        ← 이러면 대본이 말이 안 되고 짧아진다
                  (실측 2026-08-19: 명사구로 뽑았더니 조립 대본이 145자로 나왔다.
                   같은 장르 히트작 실측은 234~284자다 — 재료가 짧아서 대본이 짧았다)
- category_word : {제품군} — 제품명을 숨기고 부를 상위 분류어 한 단어.
                  (예: 주방템, 집게, 정리도구). 은폐형 훅에서 쓴다.
- hook_points   : 어그로가 될 만한 지점 — 놀랍거나 반전인 사실 1~3개. 짧게.
- misuse_genre  : **이 영상이 '원래 용도를 뒤집는' 오용형인가**(true/false).
                  true = 원래 A를 하라고 만든 물건인데 사람들이 전혀 다른 B로 쓰더라,
                         라는 반전이 실제로 있는 영상.
                  false = 그냥 좋은 제품 소개·사용법 안내·꿀템 추천(대부분이 여기다).
                  ★애매하면 false로 해라. true로 잘못 표시하면 "미친 사용법"이라 해놓고
                    하나도 안 놀라운 대본이 나간다(실측 2026-08-19 마커펜 사고).

JSON만 출력:
{"original_use": [], "hidden_property": [], "misuses": [], "category_word": "", "hook_points": [], "misuse_genre": false}

자막·설명:
"""
# ★.format()을 쓰지 않는다(2026-08-19 실측으로 잡음).
#   이 프롬프트에는 {본래용도}·{속성} 같은 **설명용 중괄호**가 들어 있어서
#   SUL_PROMPT.format(body=...)를 하면 그것들을 치환 필드로 보고 KeyError로 죽는다.
#   실측: 실제 자막 2건이 통째로 "추출 실패(빈 dict)"였다 — 예외를 삼키는 구조라
#   오류도 안 보였다. 본문은 그냥 이어붙인다.

SUL_SCHEMA = {
    "type": "object",
    "properties": {
        "original_use": {"type": "array", "items": {"type": "string"}},
        "hidden_property": {"type": "array", "items": {"type": "string"}},
        "misuses": {"type": "array", "items": {"type": "string"}},
        "category_word": {"type": "string"},
        "hook_points": {"type": "array", "items": {"type": "string"}},
        # 이 영상이 오용형 장르인가 — 조립 자격을 여기서 가른다(2026-08-19).
        "misuse_genre": {"type": "boolean"},
    },
    # ★required를 비워둔다 — 모델이 일부를 못 채워도 나머지는 쓴다.
    #   (product_facts와 같은 원칙: 재료가 부분만 있어도 대본은 나와야 한다)
    "required": [],
}

_MAX_BODY = 4000


def _body_of(raw):
    """입력에서 대본 재료가 될 텍스트를 모은다. 없으면 ''."""
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


def analyze_sul(raw, *, log=print):
    """영상 자막·캡션 → 썰쇼핑 재료 dict. 재료가 없으면 {} (예외 없음)."""
    body = _body_of(raw)
    if not body:
        return {}
    try:
        from shopping_shorts import video_analysis
        from google.genai import types
    except Exception:                       # noqa: BLE001 — 비전 모듈 없어도 죽지 않는다
        return {}
    keys = getattr(video_analysis, "SHORTS_GEMINI_KEYS", None)
    if not keys:
        return {}
    try:
        from shopping_shorts import comment_gen
        key, _idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return {}
        client = video_analysis._client_for_key(key)
        resp = client.models.generate_content(
            model=video_analysis._TRANSLATE_MODEL,
            contents=[SUL_PROMPT + body],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SUL_SCHEMA,
            ),
        )
        import json as _json
        data = _json.loads(resp.text) or {}
    except Exception as e:                  # noqa: BLE001 — 실패해도 대본은 나와야 한다
        try:
            log("[sul_facts] 추출 실패: %s" % str(e)[:120])
        except Exception:
            pass
        return {}

    out = {}
    for k in ("original_use", "hidden_property", "misuses", "hook_points"):
        v = data.get(k) or []
        if isinstance(v, str):
            v = [v]
        v = [str(x).strip() for x in v if str(x).strip()]
        if v:
            out[k] = v
    cw = (data.get("category_word") or "").strip()
    if cw:
        out["category_word"] = cw
    # ★모델이 이 칸을 안 주면 **false로 본다**(없는 걸 true로 보면 옛 사고가 재발한다).
    out["misuse_genre"] = bool(data.get("misuse_genre"))
    return out


def sul_prompt_block(facts, max_items=4):
    """썰 재료 → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀 0).

    ★product_facts.prompt_block과 같은 규약이다 — 빈 문자열이면 기존 경로 그대로.
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
        _line("original_use", "원래 용도(이게 원래 무엇을 하라고 만든 물건인가)"),
        _line("hidden_property", "숨은 성질(사람들이 눈치챈 것)"),
        _line("misuses", "엉뚱한 사용처(실제 사례)"),
        _line("category_word", "상위 분류어(제품명을 숨길 때 쓸 말)"),
        _line("hook_points", "어그로 포인트(놀라운 사실)"),
    ])
    if not body:
        return ""
    return ("\n[이 영상에서 확인된 사실 — 대본의 빈칸은 여기 있는 것만 써라. "
            "없는 건 지어내지 말고 그 칸을 비워라]" + body)
