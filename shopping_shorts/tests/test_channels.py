from shopping_shorts.channels import username_from_url, parse_rows


def test_username_from_url_basic():
    assert username_from_url("https://www.instagram.com/self_interior/ ") == "self_interior"


def test_username_from_url_no_trailing_slash():
    assert username_from_url("https://www.instagram.com/habom_official") == "habom_official"


def test_username_from_url_invalid_returns_none():
    assert username_from_url("http://zamvie.com") is None
    assert username_from_url("") is None
    assert username_from_url(None) is None


def test_parse_rows_extracts_channels():
    rows = [
        ("채널명", "주소", "팔로워", "인포크링크"),  # header
        ("오후살림", "https://www.instagram.com/self_interior/ ", 690934, "https://link.inpock.co.kr/ohusalim"),
        ("셀프DIY", "https://www.instagram.com/self_diy/ ", 566246, "http://zamvie.com"),
        ("깨진행", None, None, None),  # 무효 URL → 스킵
    ]
    channels = parse_rows(rows)
    assert len(channels) == 2
    assert channels[0] == {
        "name": "오후살림", "username": "self_interior",
        "followers": 690934, "inpock": "https://link.inpock.co.kr/ohusalim",
    }
    assert channels[1]["username"] == "self_diy"
