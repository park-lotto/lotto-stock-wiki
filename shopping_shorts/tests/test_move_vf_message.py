# -*- coding: utf-8 -*-
"""11-05 회원 편 f65c321f656a: 영상 컷에 move "in" → 반려 문구가 in 까지 '가능'으로 알려 회원 Claude 가 같은 값을 두 번 넣고 결함 신고.
영상 컷(move_vf)은 sway·bounce·punch·shake 만, in·out·left·right 는 사진 파일 컷(still_move) 전용 — 문구가 그대로 말해야 한다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as NV  # noqa: E402


def test_video_cut_in_message_does_not_offer_in():
    with pytest.raises(ValueError) as e:
        NV.move_vf("in", 30, 1080, 870)
    m = str(e.value)
    head = m.split("—")[0]
    assert "영상 컷 가능" in head and "sway" in head
    assert "in·out" not in head                      # 영상 컷 '가능' 목록에 사진 전용 값을 섞지 않는다
    assert "사진 파일 컷 전용" in m


def test_live_moves_still_work_on_video_cut():
    for k in NV.LIVE_MOVES:
        assert NV.move_vf(k, 30, 1080, 870)
