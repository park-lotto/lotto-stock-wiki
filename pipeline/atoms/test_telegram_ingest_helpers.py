from pipeline.atoms.telegram_ingest import _parse_filename, _is_image_file


def test_parse_filename():
    date, channel = _parse_filename("2026-06-19_하나반도체.md")
    assert date == "2026-06-19"
    assert channel == "하나반도체"


def test_image_file_skipped():
    assert _is_image_file("스크린샷 2026-06-06 002815.png") is True
    assert _is_image_file("2026-06-19_하나반도체.md") is False
