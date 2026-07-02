import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import slot_ingest as si


def test_disp_width_ascii():
    assert si._disp_width("abc") == 3


def test_disp_width_korean():
    assert si._disp_width("텔레그램") == 8


def test_pad_korean_label():
    assert si._pad("텔레그램", 10) == "텔레그램  "


def test_pad_ascii_label():
    assert si._pad("youtube", 10) == "youtube   "


def test_pad_already_over_width_no_truncate():
    assert si._pad("아주긴카테고리라벨", 4) == "아주긴카테고리라벨"


def test_extract_pending_korean_label():
    text = "[15/19] ...\n완료: 19개 채널, 124개 원자\n미처리 텔레그램: 6개\n"
    assert si._extract_pending(text) == 6


def test_extract_pending_english_label():
    text = "완료: 0개, 0개 원자\n미처리 youtube: 0개\n"
    assert si._extract_pending(text) == 0


def test_extract_pending_missing_pattern():
    assert si._extract_pending("아무 정보 없는 로그") == 0


def test_extract_error_quota():
    text = "google.api_core.exceptions.ResourceExhausted: 429 RESOURCE_EXHAUSTED"
    err = si._extract_error(text)
    assert err is not None
    assert "RESOURCE_EXHAUSTED" in err


def test_extract_error_traceback():
    text = "Traceback (most recent call last):\n  File x.py\nKeyError: 'x'"
    assert si._extract_error(text) is not None


def test_extract_error_none_on_clean_log():
    text = "[15/19] 2026-07-01_미래시황.md\n  → 13개 원자\n완료: 19개 채널, 124개 원자"
    assert si._extract_error(text) is None
