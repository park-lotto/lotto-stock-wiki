"""채널명+캡션 키워드 기반 카테고리 자동 태깅."""

# CATEGORIES 순서대로 검사 → 먼저 매칭되는 것 채택. 미매칭 "기타".
KEYWORDS = {
    "인테리어": ["인테리어", "diy", "셀프", "홈스타일", "집꾸", "공간"],
    "레시피": ["레시피", "요리", "맛집", "자취요리", "쿠킹", "베이킹"],
    "생활용품": ["살림", "생활용품", "꿀템", "주방", "정리", "청소템"],
    "가전": ["가전", "로봇청소기", "청소기", "에어컨", "냉장고", "언박싱"],
    "뷰티": ["뷰티", "화장", "메이크업", "스킨케어", "코스메틱"],
}


def categorize(name, caption=""):
    """채널명+캡션 → 카테고리. CATEGORIES 순서로 첫 매칭. 없으면 '기타'."""
    text = f"{name or ''} {caption or ''}".lower()
    for category, kws in KEYWORDS.items():
        if any(kw.lower() in text for kw in kws):
            return category
    return "기타"
