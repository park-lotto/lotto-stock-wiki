"""11-05 박은숙 #7759: 읽는 글의 'kg' 을 코드가 못 고쳐 '타입캐스트가 건너뛴다' 관문으로 제작자 과제까지 갔다 — 흔한 단위는 읽기 사전에서 고친다."""
from tools.calcopy.hybrid import script_audit as SA


def test_lowercase_units_have_readings():
    assert SA._read_latin("kg") == "킬로그램" and SA._read_latin("ml") == "밀리리터" and SA._read_latin("cm") == "센티미터"


def test_plain_words_still_left_to_claude():
    assert SA._read_latin("Apple") is None and SA._read_latin("g") is None
