from shopping_shorts.categorize import categorize, ctype_of, classify


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

def test_tie_breaks_by_declaration_order():
    # 점수가 같으면 KEYWORDS 선언 순서(앞선 것) 우선
    assert categorize("인테리어 뷰티 다하는 계정", "") == "인테리어"


def test_caption_beats_name_stuffing():
    # 실제 버그: 채널명에 태그 도배(집꾸미기·인테리어·생활꿀템)한 채널이
    # 요리 영상을 올려도, 캡션 우선 가중 덕에 레시피로 잡혀야 한다.
    name = "홈스텐다드 | 집꾸미기 | 인테리어 | 생활꿀템"
    caption = "감자 요리 이렇게 하면 대박 꿀팁"
    assert categorize(name, caption) == "레시피"


def test_ctype_mapping():
    assert ctype_of("인테리어") == "비법형"
    assert ctype_of("레시피") == "비법형"
    assert ctype_of("생활용품") == "제품형"
    assert ctype_of("가전") == "제품형"
    assert ctype_of("뷰티") == "혼합형"
    assert ctype_of("기타") == "기타"


def test_classify_returns_both_axes():
    out = classify("가전 리뷰", "최신 로봇청소기 언박싱")
    assert out == {"topic": "가전", "ctype": "제품형"}
