"""F1 상품군 확장(P2) — 비요리 상품(뷰티·수납·청소·의류·생활)의 화면 행위 태깅.
요리 전용이면 비요리 영상은 행위 못이 없어 ping_pong·서브의무삽입·백본이 통째로 무력하다."""
from shopping_shorts import action_dict as A


def test_beauty_actions():
    assert A.tag_action("에센스를 톡톡 두드려 흡수시켜요") == "두드리다"
    assert A.tag_action("튜브를 쭉 짜서 덜어요") == "짜다"


def test_storage_organize_actions():
    assert A.tag_action("옷을 반듯하게 접어 개켜요") == "접다"
    assert A.tag_action("선반에 차곡차곡 쌓아 정리해요") in ("쌓다", "정리하다")
    assert A.tag_action("행거에 옷을 걸어요") == "걸다"


def test_cleaning_actions():
    assert A.tag_action("롤러로 먼지를 굴려서 떼요") == "밀다"
    assert A.tag_action("이불을 탁탁 털어요") == "털다"


def test_wear_and_stick_actions():
    assert A.tag_action("운동화를 신어봤어요") == "신다"
    assert A.tag_action("벽에 스티커를 붙여요") == "붙이다"


def test_new_actions_in_vocab():
    for a in ("두드리다", "짜다", "접다", "걸다", "쌓다", "밀다", "신다", "붙이다", "털다"):
        assert a in A.ACTION_VOCAB


def test_cooking_still_works():
    # 회귀: 기존 요리 행위 태깅이 새 어휘와 충돌해 깨지지 않는지
    assert A.tag_action("팬케이크를 뒤집어요") == "뒤집다"
    assert A.tag_action("반죽을 섞어요") == "섞다"
    assert A.tag_action("바나나를 썰어요") == "자르다"
    assert A.tag_action("소스를 뿌려요") == "뿌리다"
