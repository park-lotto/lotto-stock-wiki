"""유튜브 카테고리별 프리셋 키워드 — 딸깍 수집용(사용자가 안 쳐도 되게 코드 내장).

키는 index.html CTYPES 버튼 key와 1:1(홈템/비법형/제품형/혼합형/기타). v1 한국어(lang=ko).
키워드는 초안 — 수집 결과 보고 조정한다. 편집 UI·언어별은 범위 밖(YAGNI).
"""

CATEGORY_KEYWORDS = {
    "홈템":   ["살림템", "주방템", "정리수납", "생활꿀템", "청소템"],
    "비법형": ["살림꿀팁", "청소꿀팁", "요리꿀팁", "자취꿀팁", "생활꿀팁"],
    "제품형": ["다이소추천", "쿠팡추천", "주방용품", "살림추천템"],
    "혼합형": ["뷰티꿀팁", "메이크업", "화장법", "다이소뷰티"],
    "기타":   ["자취요리", "냉장고정리", "집꾸미기"],
}


def preset_keywords(categories=None):
    """스코프에 맞는 프리셋 키워드 리스트(중복 제거, 순서 보존).

    categories=None → 전 카테고리 union / ["혼합형"] → 그 카테고리만 /
    알 수 없는 key는 조용히 무시(빈 기여)."""
    keys = list(CATEGORY_KEYWORDS) if categories is None else categories
    out, seen = [], set()
    for key in keys:
        for kw in CATEGORY_KEYWORDS.get(key, []):
            if kw not in seen:
                seen.add(kw)
                out.append(kw)
    return out
