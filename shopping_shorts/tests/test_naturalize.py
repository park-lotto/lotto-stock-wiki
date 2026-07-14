from shopping_shorts.narration_naturalize import naturalize, merge_profile, DEFAULT_PROFILE


def _only(stage):
    """해당 스테이지만 켜고 나머지 전부 끈 프로파일."""
    p = merge_profile({})
    for k, v in p.items():
        if isinstance(v, dict) and "on" in v:
            v["on"] = (k == stage)
    return p


def test_merge_profile_fills_defaults():
    p = merge_profile({"spoken_style": {"intensity": 0.9}})
    assert p["spoken_style"]["intensity"] == 0.9
    assert p["spoken_style"]["on"] is True          # 기본 채워짐
    assert p["normalize"]["on"] is True

def test_normalize_percent_and_units():
    p = _only("normalize")
    assert naturalize("50% 할인, 3kg 무게", p) == "오십 퍼센트 할인, 삼 킬로그램 무게"

def test_normalize_decimal():
    p = _only("normalize")
    assert naturalize("3.5kg", p) == "삼 점 오 킬로그램"

def test_off_is_noop():
    p = _only("normalize")
    p["normalize"]["on"] = False
    assert naturalize("50%", p) == "50%"

def test_spoken_style_converts_formal_endings():
    p = _only("spoken_style")
    p["spoken_style"]["intensity"] = 1.0   # 전부 변환
    # 문어체 종결 → 서울 구어체
    assert naturalize("이건 정말 좋습니다.", p) == "이건 정말 좋아요."
    assert naturalize("가격이 저렴합니다.", p) == "가격이 저렴해요."

def test_spoken_style_intensity_partial_deterministic():
    p = _only("spoken_style")
    p["spoken_style"]["intensity"] = 0.5   # 절반만(앞에서부터 결정적)
    src = "좋습니다. 쌉니다. 편합니다. 예쁩니다."  # 4개 종결
    out = naturalize(src, p)
    # 결정적: 같은 입력 두 번 → 동일
    assert out == naturalize(src, p)

def test_spoken_style_off_noop():
    p = _only("spoken_style"); p["spoken_style"]["on"] = False
    assert naturalize("좋습니다.", p) == "좋습니다."

def test_pronunciation_dict_replace():
    p = _only("pronunciation")
    p["pronunciation"]["dict"] = {"SNS": "에스엔에스", "AI": "에이아이"}
    assert naturalize("SNS와 AI", p) == "에스엔에스와 에이아이"

def test_pronunciation_longest_first():
    p = _only("pronunciation")
    p["pronunciation"]["dict"] = {"A": "에이", "AI": "에이아이"}
    # 긴 키 우선(AI가 A로 먼저 안 깨지게)
    assert naturalize("AI", p) == "에이아이"

def test_phrasing_inserts_comma_after_connectives():
    p = _only("phrasing")
    p["phrasing"]["intensity"] = 1.0
    # 연결어미(고/는데) 뒤에 쉼표 삽입 → 호흡
    assert naturalize("이게 싸고 좋은데 품질도 최고예요", p) == "이게 싸고, 좋은데, 품질도 최고예요"

def test_phrasing_skip_if_already_punctuated():
    p = _only("phrasing"); p["phrasing"]["intensity"] = 1.0
    assert naturalize("싸고, 좋아요", p) == "싸고, 좋아요"   # 이미 쉼표면 중복삽입 안 함

def test_phrasing_off_noop():
    p = _only("phrasing"); p["phrasing"]["on"] = False
    assert naturalize("싸고 좋은데 최고", p) == "싸고 좋은데 최고"

def test_endings_softens_period_to_ellipsis():
    p = _only("endings"); p["endings"]["intensity"] = 1.0
    # 마침표 종결을 부드러운 여운(…)으로(모두)
    assert naturalize("좋아요. 예뻐요.", p) == "좋아요… 예뻐요…"

def test_endings_partial_deterministic():
    p = _only("endings"); p["endings"]["intensity"] = 0.5
    src = "하나. 둘. 셋. 넷."
    assert naturalize(src, p) == naturalize(src, p)  # 결정적

def test_endings_off_noop():
    p = _only("endings"); p["endings"]["on"] = False
    assert naturalize("좋아요.", p) == "좋아요."
