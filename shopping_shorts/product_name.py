"""제품명 판독 — "같은 제품 영상 모으기"의 재료 (2026-08-04).

■ 왜 만들었나 (사장님 목적)
렌즈로 하던 걸 우리 아카이브 안에서 하려는 것: 오늘 터진 영상의 **제품**을 보고,
과거에 같은 제품을 다룬 우리 채널 영상들을 모아 믹스한다.

■ 왜 기존 비전태그로는 안 되나 (실측 2026-08-04)
vision_tags의 subject/keywords는 **분위기어가 지배**한다. 아카이브 4,222건 기준
가장 흔한 토큰이 '살림꿀팁' 638건(15%), '주방용품' 410건(9%), '살림꿀템' 355건(8%).
그래서 오늘 랭킹 상위 4건 전부 **제품명 완전일치가 0건**이었고, 토큰 겹침 상위는
'다이소 걸레' → 냉장고정리용품(겹침3), '천사점토' → 비즈스트랩(겹침3)처럼
**같은 제품이 아니라 같은 분위기**로 묶였다.

임베딩으로도 안 됐다: 태그 텍스트 임베딩은 '비슷한 소재'(라멘↔마라탕)는 잘 찾지만
같은 제품과는 다른 축이다. 썸네일 이미지 임베딩은 자막 타이포에 끌려 순위가 뒤집혔다
(같은제품 최저 0.613 < 다른제품 최고 0.727 — 임계값으로 분리 불가).

■ 되는 방법 (사장님 아이디어)
**비전 모델에게 "자막은 무시하고 실물 제품만 상품명으로 답하라"고 지시**한다.
임베딩은 지시를 못 받지만 flash-lite는 받는다. 실측: 답을 받은 3쌍 전부
같은 제품으로 묶였다 — 텀블러↔아소부 텀블러, 소파베드↔접이식 소파베드,
전동 채칼↔채칼 세트(핵심어 '채칼' 공유).

■ 언제 도나 (사장님 지시: "미리 돌리지 말고 검색 누를 때")
14,000건을 미리 태우지 않는다. 검색을 누르면 그때 질의 1건 + 후보 30건만 판독하고
결과를 캐시한다. 쓸수록 캐시가 쌓여 점점 빨라진다.
"""
import concurrent.futures as _fut
import json

from pipeline.atoms import key_vault
from shopping_shorts import comment_gen
from shopping_shorts.store import Store

_PROMPT = """이 이미지는 한국어 쇼츠 영상의 썸네일이다.

★가장 중요: 화면에 크게 박힌 **자막·문구·타이포그래피는 완전히 무시하라**.
자막 내용을 답에 반영하지 마라. 오직 **화면에 실물로 찍혀 있는 물건**만 보고 답하라.

그 물건이 무엇인지 **구체적인 상품명**으로 답하라.
- 좋은 예: "스텐 채칼", "3단 욕실 코너선반", "접이식 소파베드", "극세사 밀대걸레"
- 나쁜 예: "주방용품", "살림꿀팁", "인테리어", "청소" (← 범주·분위기는 금지)
- 제품이 안 보이거나 특정할 수 없으면 product를 빈 문자열로 두라.

JSON으로만 답하라:
{"product": "구체적 상품명", "category": "대분류"}"""

_SCHEMA = {"type": "object",
           "properties": {"product": {"type": "string"}, "category": {"type": "string"}},
           "required": ["product", "category"]}

# 제품명에서 핵심어를 뽑을 때 떼는 수식어. '전동 채칼'과 '채칼 세트'가 같은 제품으로
# 묶여야 한다 — 실측에서 이 둘이 글자 불일치로 갈렸다.
_MODIFIERS = {
    "전동", "수동", "무선", "유선", "접이식", "폴딩", "휴대용", "미니", "대형", "소형",
    "스텐", "스테인리스", "실리콘", "플라스틱", "원목", "우드", "알루미늄", "세트",
    "다용도", "자동", "회전", "3단", "2단", "4단", "1+1", "신형", "구형", "投",
    # 재질어(2026-08-04 실사고): '유리 믹싱볼' 레시피 영상이 '유리창 청소기·유리 물병·
    # 유리 밀폐용기'와 전부 "같은 제품"으로 묶였다 — 재질 '유리'가 핵심어로 남아
    # 하나만 겹치면 같다는 규칙에 걸린 것. 재질은 제품이 아니다.
    "유리", "강화유리", "도자기", "세라믹", "고무", "메탈", "티타늄", "투명",
}

_MAX_WORKERS = 6      # 살아있는 키가 9개(실측) — 그보다 낮게 잡아 429를 피한다


def _identify_one(image_bytes):
    """썸네일 1장 → (product, category). 실패·키소진은 (None, None) = '판정 못함'.

    (None, None)과 ("", cat)은 다르다: 전자는 재시도 대상, 후자는 '제품 없음' 확정이라
    캐시에 남겨 다시 안 묻는다."""
    try:
        from google.genai import types

        from shopping_shorts import video_analysis
    except Exception:      # noqa: BLE001 — 비전 모듈 없으면 조용히 포기
        return None, None
    if not image_bytes:
        return None, None
    for _ in range(3):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return None, None
        try:
            client = video_analysis._client_for_key(key)
            r = client.models.generate_content(
                model=video_analysis._TRANSLATE_MODEL,
                contents=[_PROMPT, types.Part.from_bytes(data=image_bytes,
                                                         mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA))
            d = json.loads(r.text)
            return (d.get("product") or "").strip(), (d.get("category") or "").strip()
        except Exception as e:      # noqa: BLE001
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue           # 다음 키로 (죽은 키 8·11번이 여기서 걸러진다)
            if key_vault.is_quota_error(e):
                continue           # 429는 다음 키로 — 기다리지 않는다(검색은 대화형이다)
            return None, None
    return None, None


def identify_many(items, db_path, max_workers=_MAX_WORKERS, expired_out=None):
    """[{shortcode, thumbnail}] → {shortcode: product}. 캐시된 건 건드리지 않는다.

    items 중 product_at이 없는 것만 실제로 판독하고 저장한다. 반환은 캐시+신규 합본."""
    store = Store(db_path)
    codes = [i.get("shortcode") for i in items if i.get("shortcode")]
    cached = store.products_map(codes)
    todo = [i for i in items
            if i.get("shortcode") and i["shortcode"] not in cached and i.get("thumbnail")]
    if not todo:
        return cached

    from shopping_shorts import video_analysis

    def _work(it):
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail"))
        if not img:
            if expired_out is not None:
                expired_out.append(it["shortcode"])
            return it["shortcode"], None, None      # 썸네일 만료 — 캐시에 안 남긴다
        p, cat = _identify_one(img)
        return it["shortcode"], p, cat

    out = dict(cached)
    with _fut.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sc, p, cat in ex.map(_work, todo):
            if p is None:
                continue        # 판정 실패 — 다음에 다시 시도한다
            store.save_product(sc, p, cat)
            out[sc] = p
    return out


def core_tokens(product):
    """제품명 → 핵심어 집합. 수식어를 떼어 '전동 채칼'과 '채칼 세트'가 만나게 한다."""
    if not product:
        return set()
    words = [w.strip().lower() for w in str(product).replace(",", " ").split()]
    core = {w for w in words if len(w) >= 2 and w not in _MODIFIERS}
    return core or {w for w in words if len(w) >= 2}


def same_product(a, b):
    """두 제품명이 같은 제품인가. 핵심어가 하나라도 겹치면 같다고 본다.

    '채칼'처럼 핵심 명사가 곧 제품인 한국어 상품명 특성을 쓴다. 느슨해 보이지만
    비교 대상이 이미 '기존 태그로 추린 후보 30개'라 여기서 과하게 조이면
    (예: 완전일치) 실측처럼 0건이 된다."""
    ca, cb = core_tokens(a), core_tokens(b)
    if not ca or not cb:
        return False
    if ca & cb:
        return True
    # 부분문자열(붙여쓴 상품명 대비): '채칼세트' ⊃ '채칼'
    ja, jb = "".join(sorted(ca)), "".join(sorted(cb))
    return ja in jb or jb in ja
