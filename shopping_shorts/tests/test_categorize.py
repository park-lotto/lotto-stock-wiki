from shopping_shorts.categorize import categorize


def test_interior():
    assert categorize("셀프DIY 인테리어 계정", "") == "인테리어"

def test_recipe_from_caption():
    assert categorize("팡팡", "오늘의 간단 레시피 자취요리") == "레시피"

def test_beauty():
    assert categorize("뷰티템 추천", "") == "뷰티"

def test_appliance():
    assert categorize("가전 리뷰", "최신 로봇청소기 언박싱") == "가전"

def test_household():
    assert categorize("살림템", "주방 생활용품 꿀템") == "생활용품"

def test_unmatched_is_etc():
    assert categorize("그냥계정", "안녕하세요") == "기타"

def test_priority_first_match_wins():
    # 여러 카테고리 키워드가 겹치면 CATEGORIES 순서(앞선 것) 우선
    assert categorize("인테리어 뷰티 다하는 계정", "") == "인테리어"
