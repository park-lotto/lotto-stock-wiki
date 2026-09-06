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
import sys

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

★재질을 반드시 확인하라(2026-08-10 추가) — 겉보기가 비슷해 자주 틀린다:
  클레이(찰흙·지점토) / 유리 / 아크릴·레진 / 플라스틱 / 도자기 / 금속 / 나무 / 천·실 / 종이 / 식품
  - 반투명하다고 유리로 단정하지 마라. 클레이·레진·아크릴도 반투명하다.
  - 손으로 빚은 자국·무광 질감이면 클레이일 확률이 높다.
  - 못 정하겠으면 material을 빈 문자열로 두라(억지로 찍지 마라).
  ⚠️ 재질은 **material에만** 적어라. product에 재질어를 넣지 마라
     ('유리 믹싱볼' → product는 "믹싱볼", material은 "유리").

★made_by: 그 물건을 **직접 만드는 과정**을 보여주는 영상이면 "직접만들기",
  완제품을 소개·사용하는 영상이면 "완제품". 모르겠으면 빈 문자열.

JSON으로만 답하라:
{"product": "구체적 상품명", "material": "재질", "made_by": "", "category": "대분류"}"""

# material·made_by는 2026-08-10 추가. 실측(사장님 제보 케이스):
#   클레이 토끼  A(현행) "레진 파츠" ❌ → B(재질질문) "클레이 캐릭터 피규어"/클레이/직접만들기 ✅
#   피규어장식장 A "아크릴 피규어 진열장" → B "피규어 진열장"/아크릴/완제품
# made_by가 갈리면 '만드는 영상'과 '파는 물건'이 안 섞인다 — 이 케이스의 핵심 오답이었다.
# ★product에는 재질을 넣지 않는다: _MODIFIERS가 재질어를 떼는 이유(위 주석)와 같은 사고를
#   막기 위함이다. 재질은 별도 필드로 두어야 비교에 쓸지 말지를 코드가 고를 수 있다.
_SCHEMA = {"type": "object",
           "properties": {"product": {"type": "string"},
                          "material": {"type": "string"},
                          "made_by": {"type": "string"},
                          "category": {"type": "string"}},
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
        return None, None, None, None
    if not image_bytes:
        return None, None, None, None
    for _ in range(3):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return None, None, None, None
        try:
            client = video_analysis._client_for_key(key)
            r = client.models.generate_content(
                model=video_analysis._TRANSLATE_MODEL,
                contents=[_PROMPT, types.Part.from_bytes(data=image_bytes,
                                                         mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA))
            d = json.loads(r.text)
            # material·made_by는 2026-08-10 추가. 옛 호출부가 2개만 받아도 안 깨지도록
            # **뒤에** 붙인다(앞에 끼우면 언패킹하는 모든 곳이 조용히 어긋난다).
            return ((d.get("product") or "").strip(),
                    (d.get("category") or "").strip(),
                    (d.get("material") or "").strip(),
                    (d.get("made_by") or "").strip())
        except Exception as e:      # noqa: BLE001
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx, key_vault.retry_delay_seconds(e), exc=e)
                continue           # 다음 키로 (죽은 키 8·11번이 여기서 걸러진다)
            if key_vault.is_quota_error(e):
                continue           # 429는 다음 키로 — 기다리지 않는다(검색은 대화형이다)
            return None, None, None, None
    return None, None, None, None


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
            # 썸네일 만료 — 캐시에 안 남긴다(살아나면 다시 판독한다)
            return it["shortcode"], None, None, None, None
        p, cat, mat, made = _identify_one(img)
        return it["shortcode"], p, cat, mat, made

    out = dict(cached)
    with _fut.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sc, p, cat, mat, made in ex.map(_work, todo):
            if p is None:
                continue        # 판정 실패 — 다음에 다시 시도한다
            store.save_product(sc, p, cat, mat, made)
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


# ════════════════════════════════════════════════════════════════════════════
# 쿠팡 검색용 판독(2026-09-05) — 위 _PROMPT/identify_many와 **목적이 다르다**
# ════════════════════════════════════════════════════════════════════════════
# 위쪽은 "같은 제품 영상 모으기"용이다. 자막을 일부러 무시시켜 범주어("벽선반")를
# 얻는데, same_product가 핵심어 하나만 겹쳐도 같다고 보므로 그게 오히려 잘 묶인다.
#
# 쿠팡 검색은 정반대다 — **살 물건 하나를 특정**해야 한다. 실측(2026-09-05 사장님 제보):
# 랭킹 카드 버튼에 "벽선반"·"청소용 스펀지"·"프라이팬"이 박혀 쿠팡에서 엉뚱한 게 나왔다.
# 원인은 프리워밍이 **썸네일 이미지만** 보낸 것 + 그 프롬프트가 자막을 껐다는 것 둘 다.
#
# ★그래서 여기서는 캡션 본문을 이미지와 **같이** 준다. 모델 호출은 그대로 1회 —
#   추가 비용·시간이 0이다(대본 추출은 영상 업로드라 완전히 다른 급의 비용: 0.1P 과금).
# ⚠️ 위 _PROMPT를 고쳐 재사용하지 않는다. identify_many는 아카이브 유사도(app.py 2곳)와
#    product_backfill이 같이 쓴다 — 프롬프트를 건드리면 그 묶기가 조용히 바뀐다(0순위-B).
# ⚠️ 캐시도 따로다(vision_tags.shop_product). 같은 칸에 쓰면 위와 같은 사고가 난다.
_SHOP_PROMPT = """이 이미지는 한국어 쇼츠 영상의 썸네일이고, 아래는 그 영상에 올린 사람이 쓴 설명 글이다.

이 영상이 소개하는 **물건 하나**를 쿠팡에서 검색할 상품명으로 답하라.

★설명 글에 물건 이름이 적혀 있으면 **그것을 최우선으로 믿어라**(이미지보다 정확하다).
  글에 없으면 이미지에 실물로 찍힌 물건을 보고 답하라.
  이미지의 큰 자막 문구는 낚시성이라 그대로 베끼지 마라 — 물건 이름만 가져와라.

★구체적으로: 쓰임새·형태·단수를 붙여 실제로 검색할 이름으로.
  - 좋은 예: "3단 조립식 벽선반", "무선 노래방 마이크", "슬라이더 지우개", "전동 채칼"
  - 나쁜 예: "벽선반", "프라이팬", "주방용품", "살림꿀템"  (← 범주어·분위기어는 금지)

★방법·레시피 영상도 **쓰는 물건**이 있으면 그것을 답하라(2026-09-06).
  "방법을 알려주는 영상"이라는 이유만으로 빈 문자열로 두지 마라 — 그 방법에
  **반드시 쓰이는 물건**이 있으면 그게 답이다.
  - 세탁·청소 방법 → 그때 넣는 **세제·세정제·도구** ("산소계 표백제", "배수구 세정제")
  - 레시피 → ①만든 **완성품**을 파는 것이면 그것 ②아니면 핵심 **재료**나 **조리도구**
    ("냉동 생지", "식빵 슬라이서", "부침가루", "실리콘 찜기")
  - 설명 글의 해시태그에 상품명이 있으면 그것을 쓴다(#살균세제 → "살균 세탁세제")

★물건을 일부러 숨긴 낚시 문구("이것만 넣으세요", "이거 하나면")여도 포기하지 마라.
  글과 이미지의 **맥락으로 좁혀지는 물건**이 있으면 그것을 답하라.
  예) "배추 절일 때 소금만 넣지 말고 이것" → 절임 맥락에서 흔히 쓰는 재료를 이미지에서 찾아라
  ⚠️ 단 이미지에도 근거가 없으면 그때는 빈 문자열이다 — 상상해서 찍지는 마라.

★"정보성 영상이라서" / "상품을 홍보하지 않아서"는 빈 문자열의 이유가 **못 된다**.
  이 판독은 광고인지 아닌지를 묻는 게 아니다 — **그 영상을 보고 사고 싶어질 물건**을 묻는다.
  요리 팁·살림 팁은 거의 언제나 재료나 도구를 쓴다. 그것을 답하라.

★product를 빈 문자열로 둘 경우 — 아래 넷뿐이다:
  1. 맛집·장소·여행처럼 **살 수 있는 물건 자체가 없는** 영상
  2. 몸으로만 하는 것(스트레칭·자세 교정처럼 도구가 안 쓰이는 것)
  3. 물건이 여러 개 나열되기만 하고 주인공이 없는 영상
  4. 글에도 이미지에도 **근거가 전혀 없어** 무엇인지 못 정할 때
  ⚠️ 상상해서 찍지는 마라. 다만 **화면이나 글에 물건이 보이는데** 빈 문자열로 두는 것이
     틀린 상품명보다 더 나쁘다.

JSON으로만 답하라: {"product": "구체적 상품명 또는 빈 문자열", "why": "근거 한 줄"}"""

_SHOP_SCHEMA = {"type": "object",
                "properties": {"product": {"type": "string"}, "why": {"type": "string"}},
                "required": ["product"]}


def _identify_shop_one(image_bytes, caption_text):
    """썸네일 + 캡션본문 → 쿠팡 검색용 상품명. 실패·키소진은 None(재시도 대상).

    ""(빈 문자열)은 '살 물건 없음' 확정이라 캐시에 남긴다 — None과 구분한다.
    이미지가 없어도 캡션만으로 답할 수 있으면 답한다(캡션이 이미지보다 정확한 경우가 있다)."""
    try:
        from google.genai import types

        from shopping_shorts import video_analysis
    except Exception:      # noqa: BLE001 — 비전 모듈 없으면 조용히 포기
        return None
    cap = (caption_text or "").strip()
    if not image_bytes and not cap:
        return None                                  # 근거가 아예 없다
    body = _SHOP_PROMPT + "\n\n설명 글:\n" + (cap if cap else "(없음)")
    for _ in range(3):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return None
        try:
            client = video_analysis._client_for_key(key)
            parts = [body]
            if image_bytes:
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            r = client.models.generate_content(
                model=video_analysis._TRANSLATE_MODEL, contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SHOP_SCHEMA))
            return (json.loads(r.text).get("product") or "").strip()
        except Exception as e:      # noqa: BLE001
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx, key_vault.retry_delay_seconds(e), exc=e)
                continue
            if key_vault.is_quota_error(e):
                continue           # 429는 다음 키로 — 화면이 기다리고 있다
            print(f"[shop_product] 판독 실패(무해): {type(e).__name__}: {e}", file=sys.stderr)
            return None
    return None


def identify_shop_many(items, db_path, max_workers=_MAX_WORKERS, out_no_evidence=None):
    """[{shortcode, thumbnail, caption}] → {shortcode: 상품명}. 캐시된 건 안 묻는다.

    캐시는 vision_tags.shop_product(묶기용 product와 별도). 판정 실패는 저장하지 않아
    다음 기회에 다시 시도한다 — 빈 문자열('살 물건 없음')만 확정으로 저장한다.

    out_no_evidence: 리스트를 주면 **근거가 0이라 모델을 부르지도 못한** shortcode를 담아준다
    (썸네일 만료 + 캡션 없음). '살 물건 없음'과 화면에서 갈라 보여주기 위한 것이다."""
    from shopping_shorts import coupang_query, video_analysis
    store = Store(db_path)
    codes = [i.get("shortcode") for i in items if i.get("shortcode")]
    cached = store.shop_products_map(codes)
    todo = [i for i in items if i.get("shortcode") and i["shortcode"] not in cached
            and (i.get("thumbnail") or coupang_query.caption_body(i.get("caption") or ""))]
    if not todo:
        return cached

    def _work(it):
        img = video_analysis.fetch_thumb_bytes(it.get("thumbnail")) if it.get("thumbnail") else None
        cap = coupang_query.caption_body(it.get("caption") or "")
        if not img and not cap:
            # ★근거가 0이다(썸네일 만료 + 캡션 없음) — 모델을 부를 수조차 없다.
            #   "살 물건 없음"과 구분해야 한다(2026-09-06): 화면이 둘을 같게 보여주면
            #   사장님이 "왜 이렇게 없다고 나오나"로 읽는다. 실측 3,191건 중 2,771건(87%).
            return it["shortcode"], None, True
        return it["shortcode"], _identify_shop_one(img, cap), False

    out = dict(cached)
    no_evidence = []
    with _fut.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sc, p, blind in ex.map(_work, todo):
            if blind:
                no_evidence.append(sc)
            if p is None:
                continue            # 판정 실패 — 캐시에 안 남긴다(재시도)
            store.save_shop_product(sc, p)
            out[sc] = p
    if out_no_evidence is not None:
        out_no_evidence.extend(no_evidence)    # 호출부가 리스트를 주면 거기 담아준다
    return out
