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
