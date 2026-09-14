"""대본 제품 주제 계약 — 제품 동일성·합의·본문 언급 판정의 단일 정본."""
import re


GENERIC_WORDS = {
    "차량용", "차량", "자동차", "휴대용", "간이", "접이식", "유아용", "어린이", "캠핑",
    "다용도", "미니", "스마트", "신형", "필수", "용품", "제품", "아이템", "액세서리",
    "세트", "종", "도구", "기기", "장치", "가정용", "업소용", "추천",
    "무선", "유선", "물때", "청소", "세척", "관리", "방법", "사용법", "활용",
    "리뷰", "후기", "비교", "제거", "꿀팁",
    "투명", "불투명", "블랙", "화이트", "검정", "흰색", "빨강", "파랑", "핑크",
    "대형", "소형", "초대형", "초소형", "강력", "신제품",
}
ALIASES = (
    ("변기", "화장실", "토일렛", "toilet"),
    ("휴대폰", "스마트폰", "핸드폰"),
    ("냉온장고", "냉장고", "쿨러"),
)


def words(text):
    return [x for x in re.findall(r"[가-힣a-z0-9]+", str(text or "").lower()) if len(x) >= 2]


def canonical_word(word):
    w = str(word or "").lower()
    for group in ALIASES:
        if w in group:
            return group[0]
    return w


def core_terms(product):
    return [canonical_word(w) for w in words(product)
            if w not in GENERIC_WORDS and not w.isdigit()]


def product_head(product):
    terms = core_terms(product)
    return terms[-1] if terms else ""


def is_multi_product(product):
    p = str(product or "")
    return bool(re.search(r"(?:[2-9]|\d{2,})\s*종|여러\s*종|모음|종합|액세서리\s*세트", p))


def same_product(anchor, candidate):
    """제품 종류가 같은가. 브랜드·판매처·장소 공통어는 동일제품 근거가 아니다."""
    a, c = str(anchor or "").strip(), str(candidate or "").strip()
    if not a or not c:
        return False
    ah, ch = product_head(a), product_head(c)
    if not ah or not ch:
        return False
    if is_multi_product(a):
        return ch in set(core_terms(a))
    if is_multi_product(c):
        return False
    ac, cc = set(core_terms(a)), set(core_terms(c))
    return ah == ch or ac == cc


def topic_mentions(text, product):
    """본문에 제품 종류 또는 허용 동의어가 실제로 나오는가."""
    terms = list(dict.fromkeys(core_terms(product)))
    if not terms:
        return []
    raw = str(text or "").lower()
    hit = []
    for term in terms:
        aliases = next((g for g in ALIASES if g[0] == term), (term,))
        hit.extend(x for x in aliases if len(x) >= 2 and x in raw and x not in hit)
        # 기존 출구 계약: 합성어는 앞 두 글자로 자연스럽게 줄여 부를 수 있다
        # (네일펜→네일). 공통 수식어는 core_terms에서 이미 제외했다.
        if not any(x in raw for x in aliases) and len(term) >= 3 and term[:2] in raw:
            hit.append(term[:2])
    return hit


def consensus(products):
    """(product, ambiguous). 최다 제품군이 동률이면 임의 순서로 고르지 않는다."""
    clean = [str(p or "").strip() for p in products
             if str(p or "").strip() and not is_multi_product(p) and product_head(p)]
    groups = {}
    for p in clean:
        groups.setdefault(product_head(p), []).append(p)
    if not groups:
        return "", False
    ranked = sorted(groups.values(), key=lambda g: -len(g))
    if len(ranked) > 1 and len(ranked[0]) == len(ranked[1]):
        return "", True
    return ranked[0][0], False
