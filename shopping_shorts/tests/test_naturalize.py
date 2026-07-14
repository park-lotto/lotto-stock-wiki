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
