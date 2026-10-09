# -*- coding: utf-8 -*-
"""관제 169: 장면꾸미기 페이지 시각 → 골라 지우기 화면의 '장면 N'(clean_pick_cuts 순서, 1부터)."""
from shopping_shorts.mix_pipeline import clean_cut_no_at

CUTS = [{"fin": 0.0, "dur": 2.13}, {"fin": 2.13, "dur": 2.57}, {"fin": 4.7, "dur": 1.1}]


def test_page_time_maps_to_cut_number():
    assert clean_cut_no_at(CUTS, 0.53) == 1
    assert clean_cut_no_at(CUTS, 3.22) == 2
    assert clean_cut_no_at(CUTS, 4.7) == 3          # 경계는 뒤 컷


def test_gap_and_bad_input():
    assert clean_cut_no_at(CUTS, 9.0) == 3          # 끝 너머(프레임 반올림)는 마지막 컷
    assert clean_cut_no_at([], 1.0) is None
    assert clean_cut_no_at(CUTS, None) is None
