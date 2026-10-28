"""관제 217: 모델이 신호어 뒤에 쉼표를 찍으면("진짜 말도 안 되는 게, …") 떼지 못해 신호어가 두 겹으로 붙었다."""
from shopping_shorts import story_writer as sw


def test_comma_after_signal_is_stripped():
    out = sw.attach_signal("진짜 말도 안 되는 게, 뒷면 전체가 착 붙는다는 거", "진짜 말도 안 되는게")
    assert out.count("말도 안") == 1
    assert out.endswith("뒷면 전체가 착 붙는다는 거")


def test_space_form_still_stripped():
    assert sw.attach_signal("심지어 자국도 없음", "심지어") == "심지어 자국도 없음"
