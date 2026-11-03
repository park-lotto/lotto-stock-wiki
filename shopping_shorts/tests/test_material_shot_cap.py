# -*- coding: utf-8 -*-
"""재료 영상 컷도 '그 샷 끝까지' 한도를 받는다(10-27 TV 스탠드 편 — 서버 샷 표가 없는 재료 컷이 장면 전환을 넘어 계획 반려 17번).
경계는 그 편 재료(v_7524308249198202142.mp4)의 shot_starts 실측값."""
from pathlib import Path

from tools.calcopy.hybrid import render_bench as RB

STARTS = [1.1, 3.467, 5.8, 7.067, 8.033, 9.433, 11.167, 12.233, 13.367, 14.8, 15.9, 17.733, 19.167, 22.033, 23.533,
          25.633, 27.267, 29.067, 30.4, 32.033, 33.9, 36.867, 38.8]


def _fake(monkeypatch, tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda src: STARTS)
    return p


def test_cap_is_next_boundary(monkeypatch, tmp_path):
    p = _fake(monkeypatch, tmp_path)
    c = {"src": "v.mp4", "ss": 11.5}            # 반려 글: '11.5초부터 1.2초 안에 장면 전환' — 경계 12.233
    RB.shot_cap(c, p)
    assert c["max"] == round(12.233 - 11.5, 3)


def test_start_right_before_boundary_moves_to_next_shot(monkeypatch, tmp_path):
    p = _fake(monkeypatch, tmp_path)
    c = {"src": "v.mp4", "ss": 12.2}            # 경계 12.233 까지 0.03초 — 다음 샷 처음으로
    RB.shot_cap(c, p)
    assert c["ss"] == 12.233 and c["ss_planned"] == 12.233
    assert c["max"] == round(13.367 - 12.233, 3)


def test_room_lists_long_enough_shots(monkeypatch, tmp_path):
    p = _fake(monkeypatch, tmp_path)
    monkeypatch.setattr(RB, "src_left", lambda src, ss: 41.9 - ss)
    room = RB.shot_room(p, 2.5)
    assert room and all(b - a >= 2.5 for a, b in room)
    assert (33.9, 36.87) in room
