"""숫자 한글 읽기 결함 2건 회귀 테스트(2026-07-17, 사장님 라이브 샘플 실측).

결함1: normalize_reading이 천단위 쉼표(","")를 숫자 경계로 인식 못해 "2,847"을
       "2"와 "847"로 쪼개 읽고 쉼표를 그대로 남김.
결함2: _int_to_sino가 0~9999만 지원, 그 이상은 자리별 근사("이,팔백..." 류)로
       읽어 만 단위가 대부분인 쇼핑 가격에서 실사용 불가.

⚠️ 일반 문장부호 쉼표("안녕, 1개")나 천단위가 아닌 쉼표("1,2")는 절대 숫자로
삼키면 안 된다 — 아래 test_normalize_reading_does_not_swallow_plain_comma 참고."""
from shopping_shorts.narration_naturalize import (
    naturalize, merge_profile, normalize_reading, _int_to_sino,
)


def _only(stage):
    p = merge_profile({})
    for k, v in p.items():
        if isinstance(v, dict) and "on" in v:
            v["on"] = (k == stage)
    return p


# ---------- _int_to_sino: 만/억/조 확장 ----------

def test_int_to_sino_small_values_unchanged():
    """기존 4자리 이하 로직은 그대로(회귀 방지)."""
    assert _int_to_sino(0) == "영"
    assert _int_to_sino(7) == "칠"
    assert _int_to_sino(10) == "십"
    assert _int_to_sino(2847) == "이천팔백사십칠"
    assert _int_to_sino(1000) == "천"          # "일천" 아님(기존 로직 유지 확인)


def test_int_to_sino_man_unit():
    assert _int_to_sino(10000) == "만"          # "일만" 아님(한국어 관용)
    assert _int_to_sino(19900) == "만 구천구백"
    assert _int_to_sino(100000) == "십만"


def test_int_to_sino_man_group_with_lower_group():
    assert _int_to_sino(1234567) == "백이십삼만 사천오백육십칠"
    assert _int_to_sino(12345678) == "천이백삼십사만 오천육백칠십팔"


def test_int_to_sino_eok_unit_uses_il_prefix():
    """억은 만과 달리 "일억"이 자연스럽다(비대칭, 의도적 — 코드 주석 참고)."""
    assert _int_to_sino(100000000) == "일억"
    assert _int_to_sino(120000000) == "일억 이천만"


def test_int_to_sino_zero_group_is_skipped():
    """0인 그룹은 통째로 생략한다 — "일억 영만" 같은 표기가 나오면 안 된다."""
    assert "영만" not in _int_to_sino(100000000)
    assert "영" not in _int_to_sino(120000000)


# ---------- normalize_reading: 천단위 쉼표 인식 ----------

def test_normalize_reading_thousand_comma_count():
    text, n = normalize_reading("2,847개")
    assert text == "이천팔백사십칠개"
    assert n == 1


def test_normalize_reading_won_prices():
    assert normalize_reading("19,900원") == ("만 구천구백원", 1)
    assert normalize_reading("1,000원") == ("천원", 1)


def test_normalize_reading_large_grouped_number():
    assert normalize_reading("12,345,678원") == ("천이백삼십사만 오천육백칠십팔원", 1)


def test_normalize_reading_no_comma_large_number_still_grouped():
    """쉼표가 없어도 만 단위는 자리별이 아니라 그룹 단위로 읽어야 한다."""
    text, n = normalize_reading("19900원")
    assert text == "만 구천구백원"
    assert n == 1


def test_normalize_reading_4digit_no_comma_unaffected():
    """4자리 이하 + 쉼표 없음 케이스는 원래도 정상이었다(회귀 방지)."""
    text, n = normalize_reading("2847개")
    assert text == "이천팔백사십칠개"
    assert n == 1


def test_normalize_reading_does_not_swallow_plain_comma():
    """일반 문장부호 쉼표는 숫자의 일부가 아니다 — 삼키면 안 된다."""
    text, n = normalize_reading("안녕, 1개")
    assert text == "안녕, 일개"
    assert n == 1


def test_normalize_reading_non_thousand_comma_not_grouped():
    """"1,2"는 뒤가 3자리가 아니므로 천단위 쉼표가 아니다 — 따로 읽는다."""
    text, n = normalize_reading("1,2")
    assert text == "일,이"
    assert n == 2


def test_naturalize_end_to_end_price_examples():
    """사장님이 라이브 샘플에서 실측 지적한 6줄 그대로 검증."""
    p = _only("normalize")
    assert naturalize("2,847개", p) == "이천팔백사십칠개"
    assert naturalize("19,900원", p) == "만 구천구백원"
    assert naturalize("1,000원", p) == "천원"
    assert naturalize("12,345,678원", p) == "천이백삼십사만 오천육백칠십팔원"
    assert naturalize("19900원", p) == "만 구천구백원"
    assert naturalize("2847개", p) == "이천팔백사십칠개"   # 기존 정상 케이스 유지
