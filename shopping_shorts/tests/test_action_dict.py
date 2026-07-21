from shopping_shorts import action_dict


def test_vocab_derived_from_keywords():
    assert action_dict.ACTION_VOCAB == list(action_dict.ACTION_KEYWORDS)
    assert "당기다" in action_dict.ACTION_VOCAB


def test_tag_action_picks_highest_hit():
    assert action_dict.tag_action("뚜껑을 당겨서 뜯어요") == "당기다"
    assert action_dict.tag_action("반죽에 물을 붓고 섞어요") in ("붓다", "섞다")


def test_tag_action_none_on_no_hit():
    assert action_dict.tag_action("가격은 삼천원입니다") is None
    assert action_dict.tag_action("") is None
