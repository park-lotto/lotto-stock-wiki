from shopping_shorts.categorize import categorize, ctype_of, classify


def test_hometem_from_interior_side():
    # 2026-07-16: 옛 '인테리어'는 홈템에 흡수됨(경계가 실무에 없어 병합)
    assert categorize("셀프DIY 인테리어 계정", "") == "홈템"

def test_recipe_from_caption():
    assert categorize("팡팡", "오늘의 간단 레시피 자취요리") == "레시피"

def test_beauty():
    assert categorize("뷰티템 추천", "") == "뷰티"

def test_appliance():
    # 2026-07-31 가전→홈템 병합: 가전 소재도 홈템으로 들어온다
    assert categorize("가전 리뷰", "최신 로봇청소기 언박싱") == "홈템"

def test_hometem_from_household_side():
    # 옛 '생활용품'도 같은 홈템 — 양쪽 키워드를 다 흡수해야 한다
    assert categorize("살림템", "주방 생활용품 꿀템") == "홈템"

def test_unmatched_is_etc():
    assert categorize("그냥계정", "안녕하세요") == "기타"

def test_tie_breaks_by_declaration_order():
    # 점수가 같으면 KEYWORDS 선언 순서(앞선 것) 우선
    assert categorize("인테리어 뷰티 다하는 계정", "") == "홈템"


def test_caption_beats_name_stuffing():
    # 실제 버그: 채널명에 태그 도배(집꾸미기·인테리어·생활꿀템)한 채널이
    # 요리 영상을 올려도, 캡션 우선 가중 덕에 레시피로 잡혀야 한다.
    name = "홈스텐다드 | 집꾸미기 | 인테리어 | 생활꿀템"
    caption = "감자 요리 이렇게 하면 대박 꿀팁"
    assert categorize(name, caption) == "레시피"


def test_name_only_weak_keyword_not_recipe():
    # 실측 오분류: 캐릭터 굿즈 채널이 소개글에 '간식'을 넣어둠. 영상 캡션엔
    # 요리 신호가 없으니(우산·저금통) 레시피로 잡히면 안 된다 → 기타.
    name = "냠사친 | 꿀템•간식•캐릭터콜라보(포켓몬,가나디)"
    assert categorize(name, "꼬부기 우산 나왔다") == "기타"
    assert categorize("계란말이", "") == "기타"


def test_strong_name_keyword_still_classifies():
    # 캡션이 비어도 채널명의 '강한' 장르어는 그대로 분류한다.
    assert categorize("셀프DIY 인테리어 계정", "") == "홈템"
    assert categorize("뷰티템 추천", "") == "뷰티"


def test_restaurant_caption_stays_recipe():
    # 맛집(식당추천)은 캡션 키워드로 레시피 유지(B안: 분리 안 함).
    assert categorize("팡팡 맛집 | 살림템", "전대 웨이팅 1등 맛집 마라 국물") == "레시피"


def test_ctype_mapping():
    # 홈템=혼합형: 병합 전 인테리어(비법형)·생활용품(제품형)이 정반대였다
    assert ctype_of("홈템") == "혼합형"
    assert ctype_of("레시피") == "비법형"
    assert ctype_of("뷰티") == "혼합형"
    assert ctype_of("기타") == "기타"


def test_classify_returns_both_axes():
    out = classify("가전 리뷰", "최신 로봇청소기 언박싱")
    assert out == {"topic": "홈템", "ctype": "혼합형"}
