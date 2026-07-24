from shopping_shorts import youtube_client as yc


def test_parse_duration_secs():
    assert yc._parse_duration_secs("PT59S") == 59
    assert yc._parse_duration_secs("PT1M") == 60
    assert yc._parse_duration_secs("PT1M1S") == 61
    assert yc._parse_duration_secs("PT2M") == 120
    assert yc._parse_duration_secs("PT1H2M3S") == 3723
    assert yc._parse_duration_secs("") is None
    assert yc._parse_duration_secs(None) is None
